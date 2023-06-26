import importlib
import numbers
import socket
import queue
import threading
import asyncio
import time
from typing import Union

import select
import functools

import numpy as np
import pandas as pd

from bayes_opt import BayesianOptimization, UtilityFunction

from empyric.tools import (
    convert_time,
    autobind_socket,
    read_from_socket,
    write_to_socket,
    get_ip_address,
)
from empyric.types import (
    recast,
    Boolean,
    Integer,
    Float,
    Toggle,
    OFF,
    ON,
    Array,
    String,
)
from empyric.types import supported as supported_types
from empyric.variables import Variable


class Routine:
    """
    A Routine periodically updates a set of `knobs` based on a given state of an
    experiment. The knobs argument should be a dictionary of the form
    {..., name: variable, ...}.

    The optional `enable` argument should be a string corresponding to a key in whatever
    object is being passed as the `state` argument to the `update` method. The
    corresponding value should be boolean. When the enabling value is False, the
    `update` method takes no action. Otherwise, the `update` method proceeds normally.

    The optional `start`, `end` and `duration` arguments indicate when the routine
    should start and end. The `start` argument can be a number in seconds or a string
    with a number and units, e.g. "2 minutes", indicating when the routine starts, or it
    can be set to 'on enable' such that the start time is set to the time at which it is
    enabled (possibly repeatedly) and the end time is set to the start time plus
    `_duration` on each call to the `update` method. One can specify either `end` or
    `duration`, but not both; `end` is the absolute time at which the routine will end,
    while `duration` is the length of time the routine will run for (end minus start).

    All other arguments are fixed values or dictionary keys, corresponding to variable
    values of the controlling experiment.
    """

    assert_control = True

    _start_on_enable = False

    _duration = 0.0

    def __init__(
            self, knobs: dict, enable: String = None,
            start: Union[Float, String] = None, end: Union[Float, String] = None,
            duration: Union[Float, String] = None, **kwargs
    ):
        self.knobs = knobs

        for knob in self.knobs.values():
            knob._controller = None  # to control access to knob

        self.enable = enable

        if start is not None:
            if start == 'on enable':
                self.start = np.nan  # will be set when routine is enabled
                self._start_on_enable = True
            else:
                self.start = convert_time(start)
        else:
            self.start = 0.0

        if end is not None:
            self.end = convert_time(end)
            self._duration = self.end - self.start
        elif duration is not None:
            self.end = self.start + convert_time(duration)
            self._duration = duration
        else:
            self.end = np.inf
            self._duration = np.inf

        self.prepped = False
        self.finished = False

        for key, value in kwargs.items():
            self.__setattr__(key.replace(" ", "_"), value)

    @staticmethod
    def enabler(update):
        """
        Checks the enabling variable, start and stop times for the
        routine. If the enable variable evaluates to `True` and the time is
        between the start and stop times, the update method is called.

        If the enabling variable does not evaluate to `True`, then the routine's
        control of the knobs is revoked and no other action is taken.

        Otherwise, if the time is before the start time, the routine's prep
        method is called. If the time is after the end time, the routine's
        cleanup method is called.
        """

        @functools.wraps(update)
        def wrapped_update(self, state):
            if self.enable is not None and not state[self.enable]:
                for name, knob in self.knobs.items():
                    if knob._controller == self:
                        knob._controller = None

                if self._start_on_enable:
                    self.start = np.nan
                    self.end = np.nan

                return

            elif state["Time"] < self.start:
                if not self.prepped:
                    self.prep(state)
                    self.prepped = True

                return

            elif state["Time"] >= self.end:
                if not self.finished:
                    self.finish(state)
                    self.finished = True

                    # Release knobs from control
                    for name, knob in self.knobs.items():
                        if knob._controller == self:
                            knob._controller = None

                return

            else:
                if not self.prepped:
                    self.prep(state)

                if self._start_on_enable and np.isnan(self.start):
                    self.start = state['Time']
                    self.end = self.start + self._duration

                for name, knob in self.knobs.items():
                    if knob._controller and knob._controller != self:
                        # take no action if another routine has control
                        return
                    elif self.assert_control:
                        # assert control if needed
                        knob._controller = self

                update(self, state)

        return wrapped_update

    def update(self, state):
        """
        Updates the knobs controlled by the routine based on the given state.

        :param state: (dict/Series) state of the calling experiment or process
        in the form, {..., variable: value, ...}
        :return: None
        """

        pass

    def terminate(self):
        """
        Signals the routine to stop
        """

        pass

    def prep(self, state):
        """
        Does any needed preparation before the routine starts
        """

        pass

    def finish(self, state):
        """
        Makes any final actions after the routine ends
        """


class Set(Routine):
    """
    Sets `knobs` to the given values.

    The `values` argument should be either a single key/value for all knobs or
    a 1D array of keys/values of the same length as the `knobs` argument.
    """

    def __init__(self, knobs: dict, values, **kwargs):
        Routine.__init__(self, knobs, **kwargs)

        if len(self.knobs) > 1 and np.ndim(values) == 0:
            # One value for all knobs
            self.values = [values] * len(self.knobs)
        else:
            self.values = values

    @Routine.enabler
    def update(self, state):
        for knob, value in zip(self.knobs.values(), self.values):
            if isinstance(value, str):
                value = state[value]

            if value:
                knob.value = value


class Ramp(Routine):
    """
    Ramps the set of `knobs` to given `target` values at `given rates`.

    The `target` or `rate` arguments can be single keys/values for all knobs, or
    1D arrays of keys/values.
    """

    def __init__(self, knobs: dict, targets, rates, **kwargs):
        """
        :param rates: (1D array) list of ramp rates
        """

        Routine.__init__(self, knobs, **kwargs)

        if np.ndim(rates) == 0:  # single rate for all knobs
            rates = [rates] * len(self.knobs)

        if np.ndim(targets) == 0:  # single target for all knobs
            targets = [targets] * len(self.knobs)

        self.rates = rates
        self.targets = targets

        self.now = None
        self.then = None

    @Routine.enabler
    def update(self, state):
        self.now = state["Time"]

        if self.then is None:
            self.then = state["Time"]

        for knob, rate, target in zip(self.knobs, self.rates, self.targets):
            if isinstance(target, String):
                target = state[target]

            if isinstance(rate, String):
                rate = state[rate]

            val_now = self.knobs[knob]._value

            if (
                not isinstance(target, numbers.Number)
                or not isinstance(rate, numbers.Number)
                or not isinstance(val_now, numbers.Number)
                or target == val_now
            ):
                # Do nothing if knob, rate or target are undefined
                continue

            sign = (target - val_now) / abs(target - val_now)

            val_nxt = val_now + sign * rate * (self.now - self.then)

            if sign * val_now <= sign * target < sign * val_nxt:
                self.knobs[knob].value = target
            else:
                self.knobs[knob].value = val_nxt

        self.then = state["Time"]


class Timecourse(Routine):
    """
    Ramps the `knobs` linearly through a series of `values` at given `times`.

    The `times` and `values` should be 1D or 2D arrays of values (or keys for
    `values`); if 2D then the first dimension needs to have the same length as
    the `knobs` argument.
    """

    def __init__(self, knobs: dict, times, values, **kwargs):
        """

        :param times: (1D/2D array) array or list of times relative to
                      the start time
        :param values: (1D/2D array) array or list of values
        :param kwargs: keyword arguments for Routine
        """

        Routine.__init__(self, knobs, **kwargs)

        if np.ndim(times) == 0:  # single value or file path
            self.times = [[times]] * len(self.knobs)
        elif np.ndim(times) == 1:  # single list of times for all knobs
            self.times = [times] * len(self.knobs)
        else:
            self.times = times

        if np.ndim(values) == 0:  # single value or file path
            self.values = [[values]] * len(self.knobs)
        elif np.ndim(values) == 1:  # single list of values for all knobs
            self.values = [values] * len(self.knobs)
        else:
            self.values = values

        # Times and/or values can be stored in CSV files
        for i, (t_elem, v_elem) in enumerate(zip(self.times, self.values)):
            if type(t_elem[0]) == str and ".csv" in t_elem[0]:
                df = pd.read_csv(t_elem[0])
                self.times[i] = df["times"].values

            if type(v_elem[0]) == str and ".csv" in v_elem[0]:
                df = pd.read_csv(v_elem[0])
                self.values[i] = [recast(val) for val in df["values"].values]

        self.times = np.array(convert_time(self.times)).astype(float)
        self.values = np.array(self.values, dtype=object)

        # Infer start and end times from times argument, if not given
        if "start" not in kwargs:
            self.start = np.min(self.times)

        if "end" not in kwargs:
            self.end = np.max(self.times)

    @Routine.enabler
    def update(self, state):
        knobs_times_values = zip(self.knobs, self.times, self.values)
        for knob, times, values in knobs_times_values:
            if np.min(times) > state["Time"] or np.max(times) < state["Time"]:
                continue

            j_last = np.argwhere(times <= state["Time"]).flatten()[-1]
            j_next = np.argwhere(times > state["Time"]).flatten()[0]

            last_time = times[j_last]
            next_time = times[j_next]

            last_value = values[j_last]
            next_value = values[j_next]

            if last_value in list(state.keys()):
                # if last_value is a variable name,
                # use that variable's value from state
                last_value = state[last_value]

            if next_value in list(state.keys()):
                next_value = state[next_value]

            # Ramp linearly between numerical values
            value = last_value + (next_value - last_value) * (
                state["Time"] - last_time
            ) / (next_time - last_time)

            self.knobs[knob].value = value

    def prep(self, state):
        # Validate values
        for knob, value_list in zip(self.knobs.keys(), self.values):
            for value in value_list:
                is_number = isinstance(value, numbers.Number)
                is_variable = value in list(state.keys())

                if not is_number and not is_variable:
                    raise ValueError(
                        f"value {value} given for knob {knob} in Timecourse "
                        f"routine is invalid; value must be a numeric type or "
                        f"the name of a variable in the updating state"
                    )

    def finish(self, state):
        # Upon routine completion, set each knob to its final value
        for knob, value in zip(self.knobs.values(), self.values[:, -1]):
            if knob._controller is None or knob._controller == self:
                if isinstance(value, String) and value in state:
                    knob.value = state[value]
                else:
                    knob.value = value


class Sequence(Routine):
    """
    Passes the `knobs` through a series of `values` regardless of time.

    The `values` should be a 1D or 2D array of keys/values; if 2D then the first
    dimension needs to have the same length as the `knobs` argument.
    """

    def __init__(self, knobs: dict, values, **kwargs):
        Routine.__init__(self, knobs, **kwargs)

        if np.ndim(values) == 0:  # single value or file path
            self.values = [[values]] * len(self.knobs)
        elif np.ndim(values) == 1:  # single list of values for all knobs
            self.values = [values] * len(self.knobs)
        else:
            self.values = values

        # Times and/or values can be stored in CSV files
        for i, v_elem in enumerate(self.values):
            if type(v_elem[0]) == str and ".csv" in v_elem[0]:
                df = pd.read_csv(v_elem[0])
                self.values[i] = [recast(val) for val in df["values"].values]

        self.values = np.array(self.values, dtype=object)

        self.iteration = 0

    @Routine.enabler
    def update(self, state):
        for knob, values in zip(self.knobs.values(), self.values):
            value = values[self.iteration]

            if isinstance(value, String):
                value = state[value]

            knob.value = value

        self.iteration = (self.iteration + 1) % len(self.values[0])

    def finish(self, state):
        # Upon routine completion, set each knob to its final value
        for knob, value in zip(self.knobs.values(), self.values[:, -1]):
            if knob._controller is None or knob._controller == self:
                if isinstance(value, String) and value in state:
                    knob.value = state[value]
                else:
                    knob.value = value


class Maximization(Routine):
    """
    Maximize a meter or expression influenced by the set of knobs.

    This routine uses a `bayesian optimizer
    <https://github.com/bayesian-optimization/BayesianOptimization>`_, which models
    the relation between the knobs and the meter as a gaussian process.

    The `bounds` parameter
    provides the parameter space over which the knob values can be explored.

    The `max_deltas` parameter is a value or 1-D array of values which are the
    maximum change in a single step the knob(s) can take.

    The `kappa` parameter determines how much time the algorithm spends
    exploring the parameter space away from the maximum versus the parameter
    space in the vicinity of the maximum. Higher `kappa` leads to more
    exploration, lower `kappa` leads to more "exploitation" of the maximum.
    """

    _sign = 1.0

    def __init__(
        self, knobs: dict, meter, bounds, max_deltas=None, kappa=2.5, **kwargs
    ):
        Routine.__init__(self, knobs, **kwargs)

        self.bounds = {
            knob: subbounds
            for knob, subbounds in zip(knobs, np.reshape(bounds, (len(knobs), -1)))
        }

        if max_deltas:
            if np.ndim(max_deltas) == 0:
                self.max_deltas = np.array([max_deltas] * len(knobs))
            elif np.ndim(max_deltas) == 1 and len(max_deltas) == len(knobs):
                self.max_deltas = np.array(max_deltas)
            else:
                ValueError(
                    f"Improperly specified max_deltas parameter {max_deltas} for "
                    "optimization routine; must be either a single value or 1-D array "
                    "with the same length as the knobs argument"
                )
        else:
            self.max_deltas = np.array([np.inf] * len(self.knobs))

        self.meter = meter

        self.best_meter = None
        self.best_knobs = [None for _ in self.knobs]

        self.optimizer = BayesianOptimization(
            f=None,
            verbose=0,
            pbounds=self.bounds,
            random_state=6174,
            allow_duplicate_points=True,
        )

        self._kappa0 = kappa
        self.util_func = UtilityFunction(
            kappa=kappa,  # exploration vs. exploitation parameter
        )

    @Routine.enabler
    def update(self, state):
        if np.any([not isinstance(state[knob], numbers.Number) for knob in self.knobs]):
            # undefined state; take no action
            return

        if not isinstance(state[self.meter], numbers.Number):
            # undefined target value; take no action
            return

        self.optimizer.register(
            params={knob: state[knob] for knob in self.knobs},
            target=self._sign * state[self.meter],
        )

        suggestion = self.optimizer.suggest(self.util_func)

        for i, (knob, value) in enumerate(suggestion.items()):
            if value is None or not np.isfinite(value):
                pass
            elif np.abs(value - state[knob]) <= self.max_deltas[i]:
                self.knobs[knob].value = value
            else:
                sign = (value - state[knob]) / np.abs(value - state[knob])
                self.knobs[knob].value = state[knob] + sign * self.max_deltas[i]

        self.best_meter = self.optimizer.max["target"]
        self.best_knobs = self.optimizer.max["params"]

        if np.isfinite(self.end):
            kappa = self._kappa0 * (self.end - state["Time"]) / self._duration
            self.util_func.kappa = kappa

    def finish(self, state):
        for i, (knob, value) in enumerate(self.best_knobs.items()):
            if value is None or not np.isfinite(value):
                print(f"Warning: No optimal value was found for {knob}")
            if np.abs(value - state[knob]) <= self.max_deltas[i]:
                self.knobs[knob].value = value
            else:
                print(
                    f"Warning: optimal value for {knob} suggested by optimizer "
                    f"is {value}, but applying this value would exceed the "
                    f"max_delta parameter. Instead, {knob} will be set as "
                    f"close as possible without exceeding this limit."
                )
                sign = (value - state[knob]) / np.abs(value - state[knob])
                self.knobs[knob].value = state[knob] + sign * self.max_deltas[i]


class Minimization(Maximization):
    """Same as Maximization except that the sign of the meter is inverted"""

    _sign = -1.0


class SocketServer(Routine):
    """
    Server routine for transmitting data to other experiments, local or remote,
    using the socket interface.

    Any knobs given in the `knobs` argument can be read and set by clients.
    Clients can also read the values of any variables of the controlling
    experiment, via the `state` argument of the `update` method.
    """

    assert_control = False

    def __init__(self, knobs: dict = None, **kwargs):
        if knobs is None:
            knobs = {}

        Routine.__init__(self, knobs, **kwargs)

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self.ip_address, self.port = autobind_socket(self.socket)

        self.socket.listen(5)
        self.socket.settimeout(1)

        self.clients_queue = queue.Queue(1)
        self.clients_queue.put({})

        self.running = True

        self.state = {}

        self.acc_conn_thread = threading.Thread(target=self.accept_connections)

        self.acc_conn_thread.start()

        self.proc_requ_thread = threading.Thread(target=self.process_requests)

        self.proc_requ_thread.start()

    def terminate(self):
        # Kill client handling threads
        self.running = False
        self.acc_conn_thread.join()
        self.proc_requ_thread.join()

    def accept_connections(self):
        while self.running:
            try:
                (client, address) = self.socket.accept()

                clients = self.clients_queue.get()

                clients[address] = client

                self.clients_queue.put(clients)

                print(f"Client at {address} has connected")

            except socket.timeout:
                pass

            time.sleep(0.1)

        # Close sockets
        try:
            self.socket.shutdown(socket.SHUT_RDWR)
        except OSError:  # socket was not connected
            pass
        self.socket.close()

        clients = self.clients_queue.get()

        for address, client in clients.items():
            try:
                client.shutdown(socket.SHUT_RDWR)
                client.close()
            except ConnectionError:
                pass

        # Return empty clients dict to queue so process_requests can exit
        self.clients_queue.put({})

    def process_requests(self):
        while self.running:
            clients = self.clients_queue.get()

            # Purge disconnected clients
            clients = {
                address: client
                for address, client in clients.items()
                if client is not None
            }

            for address, client in clients.items():
                outgoing_message = None

                try:
                    request = read_from_socket(client, chunk_size=1)
                except ConnectionError:
                    clients[address] = None
                    continue

                if client and request:
                    alias = " ".join(request.split(" ")[:-1])
                    value = request.split(" ")[-1]

                    if alias not in self.knobs and alias not in self.state:
                        outgoing_message = f"Error: invalid alias"

                    elif value == "settable?":
                        settable = (alias in self.knobs) and self.knobs[alias].settable

                        if settable:
                            outgoing_message = f"{alias} settable"
                        elif alias in self.state:
                            outgoing_message = f"{alias} read-only"
                        else:
                            outgoing_message = f"{alias} undefined"

                    elif value == "type?":
                        if alias in self.knobs:
                            _type = self.knobs[alias].type
                        elif alias in self.state:
                            _type = None
                            for supported_type in supported_types.values():
                                value = self.state[alias]
                                if isinstance(value, supported_type):
                                    _type = supported_type

                        else:
                            _type = None

                        outgoing_message = f"{alias} {_type}"

                    elif value == "?":  # Query of value
                        if alias in self.knobs:
                            _value = self.knobs[alias].value
                        elif alias in self.state:
                            _value = self.state[alias]
                        else:
                            _value = None

                        outgoing_message = f"{alias} {_value}"

                    else:  # Setting a value
                        knob_exists = alias in self.knobs

                        is_free = not getattr(self.knobs[alias], "_controller", None)

                        if knob_exists and is_free:
                            knob = self.knobs[alias]

                            knob.value = recast(value, to=knob.type)

                            outgoing_message = f"{alias} {knob.value}"

                        else:
                            outgoing_message = f"Error: cannot set {alias}"

                # Send outgoing message
                if outgoing_message is not None:
                    write_to_socket(client, outgoing_message)

                # Remove clients with problematic connections
                exceptional = client in select.select([], [], [client], 0)[2]

                if exceptional:
                    print(f"Client at {address} has a connection issue")
                    clients[address] = None

            self.clients_queue.put(clients)

            time.sleep(0.01)

    @Routine.enabler
    def update(self, state):
        self.state = state

    def __del__(self):
        if self.running:
            self.terminate()


class ModbusServer(Routine):
    """
    Server routine for transmitting data to other experiments, local or remote,
    using the Modbus over TCP/IP protocol.

    Any variables given in the `knobs` argument will be readable and writeable
    by connected clients. All variable values provided as the `state` argument
    of the `update` method can be read by clients.

    Because data is stored in statically assigned registers, only variables
    of boolean, toggle, integer or float types can be used. Variable values are
    stored in consecutive 4 registers (64 bits per value).

    Values of writeable variables (the `knobs` argument) will be stored in
    holding registers in the same order as given in the argument, starting from
    address 0. Values provided in the `state` argument of the `update` method
    will be stored in input registers in the same order as defined therein,
    starting from address 0. Each value in both sets of registers is stored as 5
    consecutive registers, 4 registers for the 64-bit value and 1 register for
    any metadata (i.e. data type). Note that the that `state` of an instance of
    `Experiment` has `Time` as its first entry.
    """

    assert_control = False

    def __init__(self, knobs: dict = None, meters=None, **kwargs):
        if knobs is None:
            knobs = {}

        Routine.__init__(self, knobs, **kwargs)

        self.meters = meters

        self.state = None  # set by update method

        # Check for PyModbus installation
        try:
            importlib.import_module("pymodbus")
        except ModuleNotFoundError:
            raise ModuleNotFoundError(
                "pymodbus must be installed to run a Modbus server"
            )

        # Import tools from pymodbus
        datastore = importlib.import_module(".datastore", package="pymodbus")
        device = importlib.import_module(".device", package="pymodbus")
        payload = importlib.import_module(".payload", package="pymodbus")

        self._builder_cls = payload.BinaryPayloadBuilder
        self._decoder_cls = payload.BinaryPayloadDecoder

        DataBlock = datastore.ModbusSequentialDataBlock

        # Set up a PyModbus TCP Server
        datastore.ModbusSlaveContext.setValues = self.setValues_decorator(
            datastore.ModbusSlaveContext.setValues
        )

        self.slave = datastore.ModbusSlaveContext(
            ir=DataBlock.create(), hr=DataBlock.create()
        )

        self.context = datastore.ModbusServerContext(slaves=self.slave, single=True)

        self.identity = device.ModbusDeviceIdentification(
            info_name={
                "VendorName": "Empyric",
                "VendorUrl": "https://github.com/dmerthe/empyric",
                "ProductName": "Modbus Server",
                "ModelName": "Modbus Server",
            }
        )

        # Run server
        self.server = None  # assigned in _run_async_server
        self.ip_address = kwargs.get("address", get_ip_address())
        self.port = kwargs.get("port", 502)

        self.server_thread = threading.Thread(
            target=asyncio.run, args=(self._run_async_server(),)
        )

        self.server_thread.start()

    def setValues_decorator(self, setValues_method):
        """
        This decorator adds a `from_vars` kwarg to indicate that the intention
        is to update the registers from variable values. Otherwise, the wrapped
        method sets the corresponding variables instead.
        """

        @functools.wraps(setValues_method)
        def wrapped_method(self2, *args, from_vars=False):
            if from_vars:
                # update context from variables
                return setValues_method(self2, *args)
            else:
                # update variables according to the request

                fc_as_hex, address, values = args

                if fc_as_hex != 16:
                    print(
                        f"Warning: an attempt was made to write to a readonly "
                        f"register at address {address}"
                    )
                else:
                    if self.knobs:
                        variable = list(self.knobs.values())[address // 5]

                        controller = getattr(variable, "_controller", None)

                        if controller:
                            name = list(self.knobs.keys())[address // 5]

                            print(
                                f"Warning: an attempt was made to set {name}, "
                                "but it is currently controlled by "
                                f"{controller}."
                            )
                            return

                        decoder = self._decoder_cls.fromRegisters(values, byteorder=">")

                        if issubclass(variable._type, Boolean):
                            variable.value = decoder.decode_64bit_uint()
                        elif issubclass(variable._type, Toggle):
                            int_value = decoder.decode_64bit_uint()
                            variable.value = ON if int_value == 1 else OFF
                        elif issubclass(variable._type, Integer):
                            variable.value = decoder.decode_64bit_int()
                        elif issubclass(variable._type, Float):
                            variable.value = decoder.decode_64bit_float()

        return wrapped_method

    async def _update_registers(self):
        if self.state is None:  # do nothing if state is undefined
            await asyncio.sleep(0.1)
            asyncio.create_task(self._update_registers())
            return

        # Store readwrite variable values in holding registers (fc = 3)
        builder = self._builder_cls(byteorder=">")

        for i, (name, variable) in enumerate(self.knobs.items()):
            value = variable._value

            # encode the value into the 4 registers
            if value is None or variable.type is None:
                builder.add_64bit_float(float("nan"))
            elif issubclass(variable.type, Boolean):
                builder.add_64bit_uint(value)
            elif issubclass(variable.type, Toggle):
                builder.add_64bit_uint(int(value in Toggle.on_values))
            elif issubclass(variable.type, Integer):
                builder.add_64bit_int(value)
            elif issubclass(variable.type, Float):
                builder.add_64bit_float(value)
            else:
                raise ValueError(
                    f"unable to update modbus server registers from value "
                    f"{value} of variable {name} with data type "
                    f"{variable.type}"
                )

            # encode the meta data
            meta_reg_val = {
                Boolean: 0,
                Toggle: 1,
                Integer: 2,
                Float: 3,
                Array: 4,
                String: 5,
            }.get(variable.type, -1)

            builder.add_16bit_int(meta_reg_val)

        # from_vars kwarg added with setValues_decorator above
        self.slave.setValues(3, 0, builder.to_registers(), from_vars=True)

        # Store readonly variable values in input registers (fc = 4)
        builder.reset()

        if self.meters:
            selection = self.state[self.meters]
        else:
            selection = self.state

        for i, (name, value) in enumerate(selection.items()):
            _type = None
            for supported_type in supported_types.values():
                if isinstance(value, supported_type):
                    _type = supported_type

            # encode the value into the 4 registers
            if value is None or _type is None:
                builder.add_64bit_float(float("nan"))
            elif _type == Boolean:
                builder.add_64bit_uint(value)
            elif _type == Toggle:
                builder.add_64bit_uint(int(value in Toggle.on_values))
            elif _type == Integer:
                builder.add_64bit_int(value)
            elif _type == Float:
                builder.add_64bit_float(value)
            else:
                raise ValueError(
                    f"unable to update modbus server registers from value "
                    f"{value} of variable {name} with data type "
                    f"{_type}"
                )

            # encode the meta data
            type_int = {Boolean: 0, Toggle: 1, Integer: 2, Float: 3}.get(_type, -1)

            builder.add_16bit_int(type_int)

        # from_vars kwarg added with setValues_decorator above
        self.slave.setValues(4, 0, builder.to_registers(), from_vars=True)

        await asyncio.sleep(0.1)

        asyncio.create_task(self._update_registers())

    async def _run_async_server(self):
        asyncio.create_task(self._update_registers())

        server = importlib.import_module(".server", package="pymodbus")

        self.server = server.ModbusTcpServer(
            self.context, identity=self.identity, address=(self.ip_address, self.port)
        )

        try:
            await self.server.serve_forever()
        except asyncio.exceptions.CancelledError:
            # Server shutdown cancels the _update_registers task
            pass

    @Routine.enabler
    def update(self, state):
        self.state = state

    def terminate(self):
        asyncio.run(self.server.shutdown())


supported = {
    key: value
    for key, value in vars().items()
    if type(value) is type and issubclass(value, Routine)
}
