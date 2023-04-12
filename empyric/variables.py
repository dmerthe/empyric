# Experiment variables

import numbers
import socket
import time
import typing
from functools import wraps
import numpy as np
from empyric.collection.instrument import Instrument

from empyric import instruments, types
from empyric.tools import write_to_socket, read_from_socket
from empyric.types import recast, Integer, Float, Boolean, Toggle, Type, Array, \
    String


class Variable:
    """
    Base class representing a specific quantity of interest monitored in an
    experiment.
    """

    dtype = None  #: the data type of the variable

    #: time since the epoch of last evaluation in seconds, being equal to the
    #: result of `time.time()` being called upon the most recent evaluation of
    #: the `value` property
    last_evaluation = None

    _settable = None  #: whether the variable can be set by the user
    _value = None  #: last known value of the variable

    @property
    def value(self):
        """The value of the variable"""
        # overwritten by child classes
        pass

    @value.setter
    def value(self, value):
        # overwritten by child classes
        pass

    @staticmethod
    def setter_type_validator(setter):
        """Checks that set value is compatible with variable's dtype"""
        @wraps(setter)
        def wrapped_setter(self, value):

            if value is None or value == float('nan'):
                self._value = None
                return

            elif self.dtype is not None:
                setter(self, recast(value, to=self.dtype))
            else:
                # if type is not explicitly defined upon construction,
                # infer from first set value

                recasted_value = recast(value)

                for _type in types.supported.values():
                    if isinstance(recasted_value, _type):
                        self.dtype = _type
                        setter(self, recasted_value)

        return wrapped_setter

    @staticmethod
    def getter_type_validator(getter):
        """Checks that get value is compatible with variable's dtype"""
        @wraps(getter)
        def wrapped_getter(self):

            value = getter(self)

            if not isinstance(value, Array) and value is None or value == float('nan'):
                self._value = None

            elif self.dtype is not None:
                self._value = recast(value, to=self.dtype)
            else:
                # if type is not explicitly defined upon construction,
                # infer from first set value

                recasted_value = recast(value)

                for _type in types.supported.values():
                    if isinstance(recasted_value, _type):
                        self.dtype = _type
                        self._value = recasted_value

            return self._value

        return wrapped_getter


class Knob(Variable):
    """
    Variable that can be directly controlled by an instrument, such as the
    voltage of a power supply.

    The `instrument` argument specifies which instrument the knob is
    associated with.

    The `knob` argument is the label of the knob on the instrument.
    """

    _settable = True  #:

    def __init__(self,
                 instrument: Instrument,
                 knob: str,
                 lower_limit: numbers.Number = None,
                 upper_limit: numbers.Number = None):

        self.instrument = instrument
        self.knob = knob  # name of the knob on instrument
        self.lower_limit = lower_limit
        self.upper_limit = upper_limit

        # infer dtype from type hint of first argument of set method
        set_method = getattr(instrument, 'set_'+knob.replace(' ', '_'))
        type_hints = typing.get_type_hints(set_method)
        type_hints.pop('return', None)  # exclude return type hint

        if type_hints:
            arg_hints = list(type_hints)
            self.dtype = type_hints[arg_hints[0]]

        self._value = None

    @property
    @Variable.getter_type_validator
    def value(self):
        """
        Value of the knob of an instrument
        """

        self._value = self.instrument.get(self.knob)
        self.last_evaluation = time.time()

        return self._value

    @value.setter
    @Variable.setter_type_validator
    def value(self, value):
        """
        Set an instrument knob to value
        """

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
    Variable that is measured by an instrument, such as temperature.

    Some meters can be controlled directly or indirectly through
    an associated (but distinct) knob.

    The `instrument` argument specifies which instrument the meter is
    associated with.

    The `meter` argument is the label of the meter on the instrument.
    """

    _settable = False  #:

    def __init__(self, instrument: Instrument, meter: str):

        self.instrument = instrument
        self.meter = meter

        self.dtype = typing.get_type_hints(
            getattr(instrument, 'measure_' + meter.replace(" ","_"))
        ).get('return', None)

        self._value = None

    @property
    @Variable.getter_type_validator
    def value(self):
        """
        Measured value of the meter of an instrument
        """

        self._value = self.instrument.measure(self.meter)
        self.last_evaluation = time.time()

        return self._value


class Expression(Variable):
    """
    Variable that is calculated based on other variables of the experiment

    For example, the output power of a power supply could be recorded as an
    expression, where voltage is a knob and current is a meter:
    power = voltage * current.

    The `expression` argument is a string that can be evaluated by the Python
    interpreter, replacing symbols with the values of variables according to
    the `definitions` argument.

    The `definitions` argument is a dictionary mapping symbols in the
    `expression` argument to variables.
    """

    _settable = False  #:

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

    def __init__(self, expression: str, definitions: dict = None):

        self.expression = expression
        self.definitions = definitions if definitions is not None else {}

    @property
    @Variable.getter_type_validator
    def value(self):
        """
        Value of the expression
        """

        expression = self.expression

        # carets represent exponents
        expression = expression.replace('^', '**')

        for symbol, variable in self.definitions.items():

            expression = expression.replace(
                symbol, f"({variable._value})"
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
            print(
                f'Unable to evaluate expression {self.expression} due to '
                f'error: ', err
            )
            self._value = None

        self.last_evaluation = time.time()

        return self._value


class Remote(Variable):
    """
    Variable controlled by an experiment (running a server routine) on a
    different process or computer.

    The `remote` argument is generally the IP address and port of the server, in
    the form '(ip address)::(port)'.

    The `alias` argument identifies the particular variable on the server to
    link to. For socket servers, this is simply the name of the variable on
    the server. For Modbus servers, this is the starting address of the
    holding or input register for a read/write or readonly variable,
    respectively. For either set of registers, the starting address is 5*(n-1)
    for the nth variable in the `readwrite` or `readonly` list/dictionary of
    variables in the server routine definition.

    The (optional) `protocol` argument indicates which kind of server to connect
    to. Setting `protocol='modbus'` indicates a Modbus server (controlled by a
    ModbusServer routine on the remote process/computer), and any other value
    or no value indicates a socket server (controlled by a SocketServer
    routine).

    The `settable` argument is required for remote variables on a Modbus server,
    and is not used for a socket server. If `settable` is set to True, then
    the variable value is read from the holding registers (`readwrite`
    variables), otherwise the variable value is read from the input registers
    (`readonly` variables).

    """

    dtype_map = {
        Toggle: '64bit_uint',
        Boolean: '64bit_uint',
        Integer: '64bit_int',
        Float: '64bit_float'
    }

    _settable = None  #: determined by the server

    def __init__(self,
                 remote: str,
                 alias: [int, str],
                 protocol: str = None,
                 settable: bool = False  # needed for modbus protocol
                 ):

        self.remote = remote
        self.alias = alias
        self.protocol = protocol

        if protocol == 'modbus':
            self._client = instruments.ModbusClient(remote)
            self._settable = settable

        else:
            remote_ip, remote_port = remote.split('::')

            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

            self._socket.connect((remote_ip, int(remote_port)))

            write_to_socket(self._socket, f'{self.alias} settable?')

            response = read_from_socket(self._socket, timeout=None)

            self._settable = response == f'{self.alias} settable'

            # Get dtype
            write_to_socket(self._socket, f'{self.alias} dtype?')

            response = read_from_socket(self._socket, timeout=None)

            try:
                self.dtype = types.supported[response.split(' ')[-1]]
            except KeyError:
                self.dtype = None  # to be inferred based in values

    @property
    @Variable.getter_type_validator
    def value(self):
        """
        Value of the remote variable on a server
        """

        if self.protocol == 'modbus':

            fcode = 3 if self._settable else 4

            dtype_int = self._client.read(
                fcode, self.alias + 4, dtype='16bit_int'
            )

            dtype = {
                0: Boolean,
                1: Toggle,
                2: Integer,
                3: Float,
            }.get(dtype_int, None)

            if dtype is not None:
                self._value = self._client.read(
                    fcode, self.alias, count=4,
                    dtype=self.dtype_map[dtype]
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

        return self._value

    @value.setter
    @Variable.setter_type_validator
    def value(self, value):
        """
        Set the value of a remote variable
        """

        if self.protocol == 'modbus':

            self._client.write(
                16, self.alias, value, dtype=self.dtype_map[self.dtype]
            )

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

    The `parameter` argument is the given value of the parameter.
    """

    _settable = True  #:

    def __init__(self, parameter: [bool, str, numbers.Number]):

        self.parameter = recast(parameter)
        self._value = parameter

    @property
    @Variable.getter_type_validator
    def value(self):
        """Value of the parameter"""
        return self._value

    @value.setter
    @Variable.setter_type_validator
    def value(self, value):
        """Set the parameter value"""
        self.parameter = value
        self._value = value


supported = {key: value for key, value in vars().items()
             if type(value) is type and issubclass(value, Variable)}
