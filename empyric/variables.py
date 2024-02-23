# Experiment variables

import numbers
import socket
import time
import typing
import warnings
from functools import wraps
import numpy as np  # functions used in Expression's eval call
from scipy.optimize import curve_fit

from empyric.collection.instrument import Instrument

from empyric import instruments, types
from empyric.tools import write_to_socket, read_from_socket
from empyric.types import *


class Variable:
    """
    Base class representing a specific quantity of interest monitored in an
    experiment.
    """

    _type = None  #: the data type of the variable

    #: time since the epoch of last evaluation in seconds, being equal to the
    #: result of `time.time()` being called upon the most recent evaluation of
    #: the `value` property
    last_evaluation = None

    _settable = False  #: whether the variable can be set by the user
    _value = None  #: last known value of the variable

    _hidden = False  #: used by GUIs

    @property
    def settable(self):
        return self._settable

    @property
    def value(self):
        """The value of the variable"""
        # overwritten by child classes
        return

    @value.setter
    def value(self, value):
        # overwritten by child classes
        pass

    @staticmethod
    def setter_type_validator(setter):
        """Checks that set value is compatible with variable's type"""

        @wraps(setter)
        def wrapped_setter(self, value):
            if not isinstance(value, Array) and (
                value is None or value == float("nan")
            ):
                self._value = None

            elif self._type is not None:
                setter(self, recast(value, to=self._type))
            else:
                # if type is not explicitly defined upon construction,
                # infer from first set value

                recasted_value = recast(value)

                for _type in types.supported.values():
                    if isinstance(recasted_value, _type):
                        self._type = _type
                        setter(self, recasted_value)

        return wrapped_setter

    @staticmethod
    def getter_type_validator(getter):
        """Checks that get value is compatible with variable's type"""

        @wraps(getter)
        def wrapped_getter(self):
            value = getter(self)

            if not isinstance(value, Array) and (
                value is None or value == float("nan")
            ):
                self._value = None

            elif self._type is not None:
                self._value = recast(value, to=self._type)
            else:
                # if type is not explicitly defined upon construction,
                # infer from first set value

                recasted_value = recast(value)

                for _type in types.supported.values():
                    if isinstance(recasted_value, _type):
                        self._type = _type
                        self._value = recasted_value

            return self._value

        return wrapped_getter

    def __mul__(self, other):
        if isinstance(other, Variable):
            return self._value * other._value
        else:
            return self._value * other

    def __add__(self, other):
        if isinstance(other, Variable):
            return self._value + other._value
        else:
            return self._value + other

    def __bool__(self):
        return np.bool(self._value)

    def __eq__(self, other):
        if isinstance(other, Variable):
            return self._value == other._value
        else:
            return self._value == other


class Knob(Variable):
    """
    Variable that can be directly controlled by an instrument, such as the
    voltage of a power supply.

    The `instrument` argument specifies which instrument the knob is
    associated with.

    The `knob` argument is the label of the knob on the instrument.
    """

    _settable = True  #:

    def __init__(
        self,
        instrument: Instrument,
        knob: str,
        lower_limit: numbers.Number = None,
        upper_limit: numbers.Number = None,
    ):
        self.instrument = instrument
        self.knob = knob  # name of the knob on instrument
        self.lower_limit = lower_limit
        self.upper_limit = upper_limit

        # infer type from type hint of first argument of set method
        set_method = getattr(instrument, "set_" + knob.replace(" ", "_"))
        type_hints = typing.get_type_hints(set_method)
        type_hints.pop("return", None)  # exclude return type hint

        if type_hints:
            arg_hints = list(type_hints)
            self._type = type_hints[arg_hints[0]]

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

        self._value = self.instrument.__getattribute__(self.knob.replace(" ", "_"))

    def __str__(self):
        return f"Knob({self._value})"


class Meter(Variable):
    """
    Variable that is measured by an instrument, such as temperature.

    Some meters can be controlled directly or indirectly through
    an associated (but distinct) knob.

    The `instrument` argument specifies which instrument the meter is
    associated with.

    The `meter` argument is the label of the meter on the instrument.

    The `gate` optional argument is another variable which gates measurements.
    This is useful for situations where indefinitely continuous measurement of
    the meter, as in the usual experiment loop, is not desirable. Generally,
    it should be a variable of integer, boolean or toggle type. When the gate
    variable evaluates to 1/True/On, the meter can be measured. Otherwise,
    attempts to measure the meter will have no effect (`None` is returned).
    """

    _settable = False  #:

    def __init__(self, instrument: Instrument, meter: str, gate=None):
        self.instrument = instrument
        self.meter = meter

        if gate and isinstance(gate, Variable):
            self.gate = gate
        else:
            self.gate = Parameter(ON)

        self._type = typing.get_type_hints(
            getattr(instrument, "measure_" + meter.replace(" ", "_"))
        ).get("return", None)

        self._value = None

    @property
    @Variable.getter_type_validator
    def value(self):
        """
        Measured value of the meter of an instrument
        """

        if not self.gate.value:
            return None

        self._value = self.instrument.measure(self.meter)
        self.last_evaluation = time.time()

        return self._value

    def __str__(self):
        return f"Meter({self._value})"


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

    # shorthand terms for common functions
    # TODO consolidate these functions in a separate module
    _functions = {
        "sqrt(": "np.sqrt(",
        "exp(": "np.exp(",
        "sin(": "np.sin(",
        "cos(": "np.cos(",
        "tan(": "np.tan(",
        "sum(": "np.nansum(",
        "mean(": "np.nanmean(",
        "rms(": "np.nanstd(",
        "std(": "np.nanstd(",
        "var(": "np.nanvar(",
        "diff(": "np.diff(",
        "max(": "np.nanmax(",
        "min(": "np.nanmin(",
        "fft(": "self.fft(",
        "ifft(": "self.ifft(",
        "carrier(": "self.carrier(",
        "ampl(": "self.ampl(",
        "demod(": "self.demod(",
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
        expression = expression.replace("^", "**")

        variables = {
            symbol: variable._value for symbol, variable in self.definitions.items()
        }

        for shorthand, longhand in self._functions.items():
            if shorthand in expression:
                expression = expression.replace(shorthand, longhand)

        try:
            all_values = np.concatenate(
                [np.atleast_1d(val).flatten() for val in variables.values()]
            )

            no_nones = None not in all_values
            no_nans = np.nan not in all_values
            no_infs = (np.inf not in all_values) and (-np.inf not in all_values)

            valid_values = no_nones and no_nans and no_infs
            ""
            if valid_values:
                self._value = eval(expression, {**globals(), **variables}, locals())
            else:
                self._value = None

        except Exception as err:
            warnings.warn(
                f"Unable to evaluate expression {self.expression} due to error: {err}"
            )
            self._value = None

        self.last_evaluation = time.time()

        return self._value

    def __str__(self):
        if len(str(self.value)) < 100:
            return f"Expression({self.expression} = {self.value})"
        elif isinstance(self.value, Array):
            return f"Expression({self.expression} = Array{np.shape(self.value)}"
        else:
            return f"Expression({self.expression} = " \
                   f"{str(self.value)[:50]} ... {str(self.value)[-50:]}"

    # Utility functions for Fourier analysis
    @staticmethod
    def fft(s):
        """Calculate the fast Fourier transform of a signal"""
        return np.fft.fft(s, norm="forward")

    @staticmethod
    def ifft(s):
        """Calculate the inverse fast Fourier transform of a signal"""
        return np.fft.ifft(s, norm="forward")

    @staticmethod
    def _find_carrier(s, dt, f0=0.0, bw=np.inf):
        """Characterize the carrier wave of a signal"""
        fft_s = np.fft.fft(s, norm="forward")
        f = np.fft.fftfreq(len(s), d=dt)

        in_band = (f > f0 - 0.5 * bw) & (f < f0 + 0.5 * bw)

        filt_fft_s = np.abs(in_band * fft_s)

        fc = np.abs(f[filt_fft_s == np.max(filt_fft_s)][0])
        Ac = np.abs(filt_fft_s[filt_fft_s == np.max(filt_fft_s)][0])

        return fc, Ac

    @staticmethod
    def carrier(s, dt, f0=0.0, bw=np.inf):
        """Find the carrier frequency of a signal"""
        return Expression._find_carrier(s, dt, f0=f0, bw=bw)[0]

    @staticmethod
    def ampl(s, dt, f0=0.0, bw=np.inf):
        """Calculate the amplitude of the carrier wave in a signal"""
        return 2 * Expression._find_carrier(s, dt, f0=f0, bw=bw)[1]

    @staticmethod
    def demod(s, dt, f0, bw=np.inf, cycles=np.inf, filt=None):
        """Demodulate an oscillatory signal"""

        if np.isfinite(cycles):
            # Partition signal into segments containing integer number of carrier cycles
            fc = Expression.carrier(s, dt, f0, bw=bw)

            k_cycle = int(1 / (dt * fc))  # number of samples per carrier period

            partitions = np.reshape(s, (-1, cycles * k_cycle))
        else:
            # Demodulate the whole signal
            partitions = np.array([s])

        partitions_demod = np.empty_like(partitions, dtype=np.complex128)

        frequencies = []

        for i, partition in enumerate(partitions):
            # Calculate FFT
            freq = np.fft.fftfreq(len(partition), d=dt)  # frequency values for the FFT
            fft = np.fft.fft(partition)

            # Find principal frequency within the given band about the given frequency
            fft_in_positive_band = np.abs(
                fft * ((freq > f0 - 0.5 * bw) & (freq < f0 + 0.5 * bw))
            )

            where_f0_closest = np.argwhere(
                fft_in_positive_band == np.max(fft_in_positive_band)
            ).flatten()[0]

            frequencies.append(freq[where_f0_closest])

            if np.abs(fft[where_f0_closest]) > 0.0:
                phase = np.log(fft[where_f0_closest]).imag  # Get phase of sinusoid
            else:
                phase = 0.0

            # Construct the demodulated FFT
            fft_demod = np.zeros_like(fft)

            # roll the positive component towards zero and remove phase
            fft_demod += np.roll(fft, -where_f0_closest) * np.exp(-1j * phase)

            # roll the negative component towards zero and remove phase
            fft_demod += np.roll(fft, where_f0_closest) * np.exp(1j * phase)

            # Apply low pass filter
            if filt == "gaussian":
                fft_demod *= np.exp(-(freq**2) / (2 * bw**2))
            if filt == "sinc":
                fft_demod *= np.sinc(freq / bw)
            else:
                fft_demod *= np.abs(freq) < 0.5 * bw

            partitions_demod[i] = np.fft.ifft(fft_demod)

        signal_demod = partitions_demod.flatten()

        return np.abs(signal_demod)


class Remote(Variable):
    """
    Variable controlled by an experiment (running a server routine) on a
    different process or computer.

    The `server` argument is the IP address and port of the server,
    in the form '(ip address)::(port)'.

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

    type_map = {
        Toggle: "64bit_uint",
        Boolean: "64bit_uint",
        Integer: "64bit_int",
        Float: "64bit_float",
    }

    def __init__(
        self,
        server: str,
        alias: Union[int, str],
        protocol: str = None,
        settable: bool = False,  # needed for modbus protocol
    ):
        self.server = server
        self.alias = alias
        self.protocol = protocol

        if protocol == "modbus":
            self._client = instruments.ModbusClient(server)
            self._settable = settable

        else:
            server_ip, server_port = server.split("::")

            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

            self._socket.connect((server_ip, int(server_port)))

            self.get_settable()
            self.get_type()

    @property
    @Variable.getter_type_validator
    def value(self):
        """
        Value of the remote variable on a server
        """

        if self._type is None:
            self.get_type()

        if self.protocol == "modbus":
            fcode = 3 if self.settable else 4

            type_int = self._client.read(fcode, self.alias + 4, _type="16bit_int")

            _type = {
                0: Boolean,
                1: Toggle,
                2: Integer,
                3: Float,
            }.get(type_int, None)

            if _type is not None:
                self._value = self._client.read(
                    fcode, self.alias, count=4, _type=self.type_map[_type]
                )

        else:
            write_to_socket(self._socket, f"{self.alias} ?")

            response = read_from_socket(self._socket, timeout=60, decode=False)

            try:
                if response is None:
                    self._value = None
                elif b"Error" in response:
                    raise RuntimeError(response.decode().split("Error: ")[-1])
                else:
                    bytes_value = response.split(self.alias.encode() + b" ")[-1].strip()

                    if bytes_value[:5] == b"dlpkl":
                        # pickled quantity, usually an array, list or tuple
                        self._value = dill.loads(bytes_value[5:])
                    else:
                        self._value = recast(
                            bytes_value,
                            to=self._type if self._type is not None else Type,
                        )

            except BaseException as error:
                print(
                    f"Warning: unable to retrieve value of {self.alias} "
                    f'from server at {self.server}; got error "{error}"'
                )

        return self._value

    @value.setter
    @Variable.setter_type_validator
    def value(self, value):
        """
        Set the value of a remote variable
        """

        if self.protocol == "modbus":
            self._client.write(16, self.alias, value, _type=self.type_map[self._type])

        else:
            write_to_socket(self._socket, f"{self.alias} {value}")

            check = read_from_socket(self._socket, timeout=60)

            if check == "" or check is None:
                print(
                    f"Warning: received no response from server at "
                    f"{self.server} while trying to set {self.alias}"
                )
            elif "Error" in check:
                print(
                    f'Warning: got response "{check}" while trying to set '
                    f"{self.alias} on server at {self.server}"
                )
            else:
                try:
                    check_value = recast(check.split(f"{self.alias} ")[1])

                    if value != check_value:
                        print(
                            f"Warning: attempted to set {self.alias} on "
                            f"server at {self.server} to {value} but "
                            f"checked value is {check_value}"
                        )

                except ValueError as val_err:
                    print(
                        f"Warning: unable to check value while setting "
                        f"{self.alias} on server at {self.server}; "
                        f'got error "{val_err}"'
                    )
                except IndexError as ind_err:
                    print(
                        f"Warning: unable to check value while setting "
                        f"{self.alias} on server at {self.server}; "
                        f'got error "{ind_err}"'
                    )

    def __del__(self):
        if self.protocol == "modbus":
            self._client.disconnect()
        else:
            self._socket.shutdown(socket.SHUT_RDWR)
            self._socket.close()

    def get_type(self):
        """Get the data type of the remote variable"""
        write_to_socket(self._socket, f"{self.alias} type?")

        response = read_from_socket(self._socket, timeout=60)

        if response is not None:
            for _type in types.supported:
                if str(_type) in response.split(self.alias)[-1]:
                    self._type = types.supported.get(_type, None)
        else:
            self._type = None

    def get_settable(self):
        """Get settability of remote variable"""
        write_to_socket(self._socket, f"{self.alias} settable?")

        response = read_from_socket(self._socket, timeout=60)
        self._settable = response == f"{self.alias} settable"

    def __str__(self):
        return f"Remote({self.alias}@{self.server} = {self._value})"


class Parameter(Variable):
    """
    Variable whose value is assigned directly by the user or indirectly with a
    routine. An example is a unit conversion factor such as 2.54 cm per inch, a
    numerical constant like pi or a setpoint for a control routine.

    The `parameter` argument is the given value of the parameter.
    """

    _settable = True  #:

    def __init__(self, parameter: Type):
        self.parameter = parameter
        self._value = parameter

        for name, _type in types.supported.items():
            if isinstance(parameter, _type):
                self._type = _type

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

    def __str__(self):
        return f"Parameter({self._value})"


supported = {
    key: value
    for key, value in vars().items()
    if type(value) is type and issubclass(value, Variable)
}
