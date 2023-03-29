# Experiment variables

import numbers
import socket
import time
import typing

import numpy as np

from empyric import instruments
from empyric.tools import recast, write_to_socket, read_from_socket, is_on


class Variable:
    """
    Base class representing a specific quantity of interested monitored in an
    experiment.
    """

    settable = False  # whether the value of the variable can be set
    dtype = None  # the data type of the variable
    last_evaluation = None  # time of last evaluation in seconds
    _value = None  # last known value of the variable

    @property
    def value(self):
        # overwritten by child classes
        pass

    @value.setter
    def value(self, value):
        # overwritten by child classes
        pass

    def validate_dtype(self, value):

        if value is not None:
            if self.dtype is not None:
                if not isinstance(value, self.dtype):
                    raise TypeError(
                        f"attempted to set value of {self} to {value} but "
                        f" type {type(value)} does not match variable's data "
                        f" type {self.dtype}"
                    )
            else:
                # if type not explicitly defined upon construction,
                # infer from first set value
                self.dtype = type(recast(value))


class Knob(Variable):
    """
    A knob is a variable that can be directly controlled by an instrument, e.g.
    the voltage of a power supply.
    """

    settable = True

    def __init__(self, instrument=None, knob=None,
                 lower_limit=None, upper_limit=None):

        for required_kwarg in ['instrument', 'knob']:
            if not required_kwarg:
                raise AttributeError(
                    f'missing "{required_kwarg}" keyword for Knob constructor'
                )

        self.instrument = instrument
        self.knob = knob  # name of the knob on instrument
        self.lower_limit = lower_limit
        self.upper_limit = upper_limit

        self.dtype = typing.get_type_hints(
            getattr(instrument, 'set_'+knob)
        ).get('return', None)

        self._value = None

    @property
    def value(self):

        self._value = self.instrument.get(self.knob)
        self.last_evaluation = time.time()

        self.validate_dtype(self._value)

        return self._value

    @value.setter
    def value(self, value):

        if self.upper_limit and value > self.upper_limit:
            self.instrument.set(self.knob, self.upper_limit)
        elif self.lower_limit and value < self.lower_limit:
            self.instrument.set(self.knob, self.lower_limit)
        else:
            self.instrument.set(self.knob, value)

        self._value = self.instrument.__getattribute__(
            self.knob.replace(' ', '_')
        )


class Meter(Variable):
    """
    A meter is a variable that is measured by an instrument, such as
    temperature. Some meters can be controlled directly or indirectly through
    an associated (but distinct) knob.
    """

    def __init__(self, instrument=None, meter=None):

        self.instrument = instrument
        self.meter = meter

        self.dtype = typing.get_type_hints(
            getattr(instrument, 'measure_' + meter)
        ).get('return', None)

        self._value = None

    @property
    def value(self):

        self._value = self.instrument.measure(self.meter)
        self.last_evaluation = time.time()

        self.validate_dtype(self._value)

        return self._value


class Expression(Variable):
    """
    Variable that is calculated based on other variables of the experiment. For
    example, the output power of a power supply could be recorded as an
    expression, where voltage is a knob and current is a meter:
    power = voltage * current.
    """

    _functions = {
        'sqrt(': 'np.sqrt(',
        'exp(': 'np.exp(',
        'sin(': 'np.sin(',
        'cos(': 'np.cos(',
        'tan(': 'np.tan(',
        'sum(': 'np.nansum(',
        'mean(': 'np.nanmean(',
        'rms(': 'np.nanstd(',
        'std(': 'np.nanstd(',
        'var(': 'np.nanvar(',
        'diff(': 'np.diff(',
        'max(': 'np.nanmax(',
        'min(': 'np.nanmin('
    }

    def __init__(self, expression=None, definitions=None):

        self.expression = expression
        self.definitions = definitions if definitions is not None else {}

    @property
    def value(self):

        expression = self.expression

        # carets represent exponents
        expression = expression.replace('^', '**')

        expr_vals = {}
        for symbol, variable in self.definitions.items():
            # take last known value

            expr_vals[symbol] = variable._value

            expression = expression.replace(
                symbol, f"expr_vals['{symbol}']"
            )

        for shorthand, longhand in self._functions.items():
            if shorthand in expression:
                expression = expression.replace(shorthand, longhand)

        try:
            if 'None' not in expression and 'nan' not in expression:
                self._value = eval(expression)
            else:
                self._value = None
        except BaseException as err:
            print(f'Unable to evaluate expression {self.expression}:', err)
            self._value = None

        self.last_evaluation = time.time()

        self.validate_dtype(self._value)

        return self._value


class Remote(Variable):
    """
    Variable controlled by an experiment (running a server routine) on a
    different process or computer.
    """

    def __init__(self, remote=None, alias=None, protocol=None, dtype=None,
                 settable=False):

        self.remote = remote
        self.alias = alias
        self.protocol = protocol
        self.dtype = np.float64 if dtype is None else dtype

        if protocol == 'modbus':
            self._client = instruments.ModbusClient(remote)
            self.settable = settable
        else:
            remote_ip, remote_port = remote.split('::')

            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

            self._socket.connect((remote_ip, int(remote_port)))

            write_to_socket(self._socket, f'{self.alias} settable?')

            response = read_from_socket(self._socket, timeout=None)

            self.settable = response == f'{self.alias} settable'

    @property
    def value(self):

        if self.protocol == 'modbus':

            fcode = 3 if self.settable else 4

            self._value = self._client.read(
                fcode, self.alias, count=4, dtype=self.dtype
            )

        else:
            write_to_socket(self._socket, f'{self.alias} ?')

            response = read_from_socket(self._socket)

            try:
                self._value = recast(response.split(' ')[-1])
            except BaseException as error:
                print(
                    f'Warning: unable to retrieve value of {self.alias} '
                    f'from server at {self.remote}; got error "{error}"'
                )

        self.validate_dtype(self._value)

        return self._value

    @value.setter
    def value(self, value):

        if self.protocol == 'modbus':

            self._client.write(16, self.alias, value, dtype=self.dtype)

        else:
            write_to_socket(self._socket, f'{self.alias} {value}')

            check = read_from_socket(self._socket)

            if check == '' or check is None:
                print(
                    f'Warning: received no response from server at '
                    f'{self.remote} while trying to set {self.alias}'
                )
            elif 'Error' in check:
                print(
                    f'Warning: got response "{check}" while trying to set '
                    f'{self.alias} on server at {self.remote}'
                )
            else:
                try:

                    check_value = recast(check.split(f'{self.alias} ')[1])

                    if value != check_value:
                        print(
                            f'Warning: attempted to set {self.alias} on '
                            f'server at {self.remote} to {value} but '
                            f'checked value is {check_value}'
                        )

                except ValueError as val_err:
                    print(
                        f'Warning: unable to check value while setting '
                        f'{self.alias} on server at {self.remote}; '
                        f'got error "{val_err}"'
                    )
                except IndexError as ind_err:
                    print(
                        f'Warning: unable to check value while setting '
                        f'{self.alias} on server at {self.remote}; '
                        f'got error "{ind_err}"'
                    )

    def __del__(self):

        if self.protocol == 'modbus':
            self._client.disconnect()
        else:
            self._socket.shutdown(socket.SHUT_RDWR)
            self._socket.close()


class Parameter(Variable):
    """
    Variable whose value is assigned directly by the user or indirectly with a
    routine. An example is a unit conversion factor such as 2.54 cm per inch, a
    numerical constant like pi or a setpoint for a control routine.
    """

    settable = True

    def __init__(self, parameter=None):

        self.parameter = parameter
        self._value = parameter

    @property
    def value(self):
        self._value = self.parameter

        self.validate_dtype(self._value)

        return self._value

    @value.setter
    def value(self, value):
        self.parameter = recast(value)


supported = {key: value for key, value in vars().items()
             if type(value) is type and issubclass(value, Variable)}


# Old implementation of the Variable class for reference; to be removed
class OldVariable:
    """
    Basic representation of an experimental variable that comes in 4 kinds:
    knob, meter, expression and parameter.

    A knob is a variable that can be directly controlled by an instrument, e.g.
    the voltage of a power supply.

    A meter is a variable that is measured by an instrument, such as
    temperature. Some meters can be controlled directly or indirectly through
    an associated (but distinct) knob.

    An expression is a variable that is not directly measured, but is
    calculated based on other variables of the experiment. An example of an
    expression is the output power of a power supply, where voltage is a knob
    and current is a meter: power = voltage * current.

    A remote variable is a variable controlled by an experiment (running a
    server) on a different process or computer.

    A parameter is a variable whose value is assigned directly by the user. An
    example is a unit conversion factor such as 2.54 cm per inch, a numerical
    constant like pi or a setpoint for a control routine.

    The value types of variables are either numbers (floats and/or integers),
    booleans, strings or arrays (containing some combination of the previous
    three types).
    """

    # Abbreviated functions that can be used to evaluate expression variables
    # parentheses are included to facilitate search for functions in expressions
    expression_functions = {
        'sqrt(': 'np.sqrt(',
        'exp(': 'np.exp(',
        'sin(': 'np.sin(',
        'cos(': 'np.cos(',
        'tan(': 'np.tan(',
        'sum(': 'np.nansum(',
        'mean(': 'np.nanmean(',
        'rms(': 'np.nanstd(',
        'std(': 'np.nanstd(',
        'var(': 'np.nanvar(',
        'diff(': 'np.diff(',
        'max(': 'np.nanmax(',
        'min(': 'np.nanmin('
    }

    def __init__(self,
                 # Knobs and meters
                 instrument=None, knob=None, meter=None,
                 lower_limit=None, upper_limit=None,

                 # Expressions
                 expression=None, definitions=None,

                 # Remote variables
                 remote=None, alias=None, protocol=None, dtype=None,
                 settable=False,

                 # Parameters
                 parameter=None
                 ):
        """
        For knobs or meters, either an instrument or a server argument must be
        given.

        If an expression is given with symbols/terms representing other
        variables, that mapping must be specified in the definitions argument.

        :param instrument: (Instrument) instrument with the corresponding knob
        or meter
        :param knob: (str) instrument knob label, if variable is a knob
        :param meter: (str) instrument meter label, if variable is a meter

        :param expression: (str) expression for the variable in terms of other
        variables, if variable is an expression
        :param definitions: (dict) dictionary of the form {..., symbol:
        variable, ...} mapping the symbols in the expression to other variable
        objects; only used if type is 'expression'

        :param remote: (str) address of the server of the variable controlling
        the variable, in the form '[host name/ip address]::[port]'.

        :param alias: (str) for a SocketServer, the name of the variable on the
        server; for a ModbusServer, the register address of the variable.
        :param protocol: (str) server communication protocol; set to 'modbus'
        if the server is a `ModbusServer`, otherwise no protocol (default)
        implies that the server is a `SocketServer`.
        :param dtype: (str) the data type of the remote variable. It is only
        relevant for ModbusServer variables which can be either boolean,
        integer or float.

        :param parameter (str) value of a user controlled parameter.
        """

        self._value = None  # last known value of this variable

        if meter:
            self.meter = meter
            self.type = 'meter'
            self.settable = False

        elif knob:
            self.knob = knob
            self.type = 'knob'
            self.settable = True
            self.lower_limit = lower_limit
            self.upper_limit = upper_limit

        elif expression:
            self.expression = expression
            self.type = 'expression'
            self.settable = False

            if definitions:
                self.definitions = definitions
            else:
                self.definitions = {}

        elif remote:
            self.remote = remote
            self.alias = alias
            self.protocol = protocol
            self.dtype = '32bit_float' if dtype is None else dtype
            self.type = 'remote'

            if protocol == 'modbus':
                self._client = instruments.ModbusClient(remote)
                self.settable = settable
            else:
                remote_ip, remote_port = remote.split('::')

                self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

                self._socket.connect((remote_ip, int(remote_port)))

                write_to_socket(self._socket, f'{self.alias} settable?')

                response = read_from_socket(self._socket, timeout=None)

                self.settable = response == f'{self.alias} settable'

        elif parameter:
            self.parameter = parameter
            self._value = parameter
            self.type = 'parameter'
            self.settable = True

        else:
            raise ValueError(
                'variable object must have a specified knob, meter or '
                'expression, or assigned a value if a parameter!'
            )

        # time of last evaluation; used for expressions
        self.last_evaluation = np.nan

        # Check that knob or meter has been assigned an instrument
        if hasattr(self, 'knob') or hasattr(self, 'meter'):
            if not instrument:
                raise AttributeError(
                    f'{self.type} variable definition requires an instrument!'
                )
            self.instrument = instrument

    @property
    def value(self):

        if hasattr(self, 'knob'):
            self._value = self.instrument.get(self.knob)
            self.last_evaluation = time.time()

        elif hasattr(self, 'meter'):
            self._value = self.instrument.measure(self.meter)
            self.last_evaluation = time.time()

        elif hasattr(self, 'expression'):

            expression = self.expression

            # carets represent exponents
            expression = expression.replace('^', '**')

            expr_vals = {}
            for symbol, variable in self.definitions.items():
                # take last known value

                expr_vals[symbol] = variable._value

                expression = expression.replace(
                    symbol, f"expr_vals['{symbol}']"
                )

            for shorthand, longhand in self.expression_functions.items():
                if shorthand in expression:
                    expression = expression.replace(shorthand, longhand)

            try:
                if 'None' not in expression and 'nan' not in expression:
                    self._value = eval(expression)
                else:
                    self._value = None
            except BaseException as err:
                print(f'Unable to evaluate expression {self.expression}:', err)
                self._value = None

            self.last_evaluation = time.time()

        elif hasattr(self, 'remote'):

            if self.protocol == 'modbus':

                fcode = 3 if self.settable else 4

                self._value = self._client.read(
                    fcode, self.alias, count=2, dtype=self.dtype
                )

            else:
                write_to_socket(self._socket, f'{self.alias} ?')

                response = read_from_socket(self._socket)

                try:
                    self._value = recast(response.split(' ')[-1])
                except BaseException as error:
                    print(
                        f'Warning: unable to retrieve value of {self.alias} '
                        f'from server at {self.remote}; got error "{error}"'
                    )

        elif hasattr(self, 'parameter'):

            self._value = recast(self.parameter)

        return self._value

    @value.setter
    def value(self, value):

        if value is None:
            # Do nothing if value is null
            pass

        elif isinstance(value, numbers.Number) and np.isnan(value):
            pass

        elif hasattr(self, 'knob'):

            try:
                if self.upper_limit and value > self.upper_limit:
                    self.instrument.set(self.knob, self.upper_limit)
                elif self.lower_limit and value < self.lower_limit:
                    self.instrument.set(self.knob, self.lower_limit)
                else:
                    self.instrument.set(self.knob, value)

                self._value = self.instrument.__getattribute__(
                    self.knob.replace(' ', '_')
                )
            except TypeError:
                print(self.upper_limit, self.lower_limit)
                raise TypeError(
                    'An upper or lower limit was specified for a non-numeric '
                    'variable.'
                )

        elif hasattr(self, 'remote') and self.settable:

            if self.protocol == 'modbus':

                self._client.write(16, self.alias, value, dtype=self.dtype)

            else:
                write_to_socket(self._socket, f'{self.alias} {value}')

                check = read_from_socket(self._socket)

                if check == '' or check is None:
                    print(
                        f'Warning: received no response from server at '
                        f'{self.remote} while trying to set {self.alias}'
                    )
                elif 'Error' in check:
                    print(
                        f'Warning: got response "{check}" while trying to set '
                        f'{self.alias} on server at {self.remote}'
                    )
                else:
                    try:

                        check_value = recast(check.split(f'{self.alias} ')[1])

                        if value != check_value:
                            print(
                                f'Warning: attempted to set {self.alias} on '
                                f'server at {self.remote} to {value} but '
                                f'checked value is {check_value}'
                            )

                    except ValueError as val_err:
                        print(
                            f'Warning: unable to check value while setting '
                            f'{self.alias} on server at {self.remote}; '
                            f'got error "{val_err}"'
                        )
                    except IndexError as ind_err:
                        print(
                            f'Warning: unable to check value while setting '
                            f'{self.alias} on server at {self.remote}; '
                            f'got error "{ind_err}"'
                        )

        elif hasattr(self, 'parameter'):
            self.parameter = value

        else:
            raise ValueError(
                f'Attempt to set {self.type}! '
                'Only knobs and parameters can be set.'
            )

    def __repr__(self):
        return self.type[0].upper() + self.type[1:] + 'Variable'

    def __del__(self):

        if hasattr(self, 'remote'):
            if self.protocol == 'modbus':
                self._client.disconnect()
            else:
                self._socket.shutdown(socket.SHUT_RDWR)
                self._socket.close()
