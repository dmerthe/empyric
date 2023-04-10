import importlib
import numbers
import socket
import queue
import threading
import asyncio
import time
import select
import functools

import numpy as np
import pandas as pd

from empyric.tools import convert_time, autobind_socket, read_from_socket, \
    write_to_socket, get_ip_address
from empyric.types import recast, Boolean, Integer, Float, Toggle, OFF, ON, \
    Array, String
from empyric.types import supported as supported_types
from empyric.variables import Parameter, Variable


class Routine:
    """
    A Routine updates a set of `knobs` based on a given state of a process or
    experiment. The knobs should be a dictionary of the form
    {..., name: variable, ...}.

    The optional `start` and `end` arguments indicate when the routine should
    start and end. The default values are 0 and infinity, respectively. When
    updating, the routine compares these values to the `Time` value of the
    given state.

    All other arguments are fixed values or string dictionary keys,
    corresponding the variables values of the controlling experiment.
    """

    assert_control = True

    def __init__(self,
                 knobs: dict,
                 enable: String = None,
                 start=0.0, end=np.inf, **kwargs):

        self.knobs = knobs

        for knob in self.knobs.values():
            knob._controller = None  # to control access to knob

        self.enable = enable
        self.start = convert_time(start)
        self.end = convert_time(end)
        self.prepped = False
        self.finished = False

        for key, value in kwargs.items():
            self.__setattr__(key.replace(' ', '_'), value)

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
                return

            elif state['Time'] < self.start:

                if not self.prepped:
                    self.prep(state)
                    self.prepped = True

                return

            elif state['Time'] >= self.end:

                if not self.finished:
                    self.finish(state)
                    self.finished = True

                    # Release knobs from control
                    for name, knob in self.knobs.items():
                        if knob._controller == self:
                            knob._controller = None

                return

            else:

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

    The `values` argument should be either a single value for all knobs or a 1D
    array of values of the same length as the `knobs` argument. The values can
    be fixed values such as numbers, variables whose values will be checked on
    each update, or string corresponding to a key in the state, whose
    corresponding value will be obtained on each update.
    """

    def __init__(self,
                 knobs: dict,
                 values,
                 **kwargs):

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
    Ramps a set of knobs to given target values at given rates
    """

    def __init__(self,
                 knobs: dict,
                 targets,
                 rates,
                 **kwargs):
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

        self.now = state['Time']

        if self.then is None:
            self.then = state['Time']

        for knob, rate, target in zip(self.knobs, self.rates, self.targets):

            if isinstance(target, String):
                target = state[target]

            if isinstance(rate, String):
                rate = state[rate]

            val_now = self.knobs[knob]._value

            if not isinstance(target, numbers.Number) \
                    or not isinstance(rate, numbers.Number) \
                    or not isinstance(val_now, numbers.Number) \
                    or target == val_now:
                # Do nothing if knob, rate or target are undefined
                continue

            sign = (target - val_now) / abs(target - val_now)

            val_nxt = val_now + sign*rate*(self.now - self.then)

            if sign*val_now <= sign*target < sign*val_nxt:
                self.knobs[knob].value = target
            else:
                self.knobs[knob].value = val_nxt

        self.then = state['Time']


class Timecourse(Routine):
    """
    Ramps linearly through a series of values at given times
    """

    def __init__(self,
                 knobs: dict,
                 times,
                 values,
                 **kwargs):
        """

        :param times: (number/1D/2D array) array or list of times relative to
                      the start time
        :param values: (number/1D/2D array) array or list of values
        :param kwargs: keyword arguments for Routine
        """

        # Infer start and end times from times argument, if not given
        if 'start' not in kwargs:
            kwargs['start'] = np.min(times)

        if 'end' not in kwargs:
            kwargs['end'] = np.max(times)

        Routine.__init__(self, knobs, **kwargs)

        if np.ndim(times) == 1:  # single list of times for all knobs
            times = [times] * len(self.knobs)
        elif np.shape(times)[0] == 1:
            # 1xN array with one N-element list of times for all knobs
            times = [times[0]] * len(self.knobs)

        if np.ndim(values) == 1:  # single list of times for all knobs
            values = [values] * len(self.knobs)
        elif np.shape(values)[0] == 1:
            # 1xN array with one N-element list of times for all knobs
            values = [values[0]] * len(self.knobs)

        self.times = np.array(
            times, dtype=object
        ).reshape((len(self.knobs), -1))

        self.times = np.array(convert_time(self.times)).astype(float)

        self.values = np.array(
            values, dtype=object
        ).reshape((len(self.knobs), -1))

        # Times and/or values can be stored in CSV files
        for i, (t_elem, v_elem) in enumerate(zip(self.times, self.values)):

            if type(t_elem[0]) == str and '.csv' in t_elem[0]:
                df = pd.read_csv(t_elem[0])

                df = df['times']

                self.times[i] = df.values.reshape(len(df))

            if type(v_elem[0]) == str and '.csv' in v_elem[0]:
                df = pd.read_csv(v_elem[0])

                df = df['values']

                self.values[i] = df.values.reshape(len(df))

    @Routine.enabler
    def update(self, state):

        knobs_times_values = zip(self.knobs, self.times, self.values)
        for knob, times, values in knobs_times_values:

            if np.min(times) > state['Time'] \
                    or np.max(times) < state['Time']:
                continue

            j_last = np.argwhere(times <= state['Time']).flatten()[-1]
            j_next = np.argwhere(times > state['Time']).flatten()[0]

            last_time = times[j_last]
            next_time = times[j_next]

            last_value = values[j_last]
            next_value = values[j_next]

            if isinstance(last_value, Variable):
                # replace variable with value for past times
                last_value = last_value._value

            last_is_number = isinstance(last_value, numbers.Number)
            next_is_number = isinstance(next_value, numbers.Number)

            if next_is_number and last_is_number:
                # ramp linearly between numerical values
                value = last_value + (next_value - last_value) \
                        * (state['Time'] - last_time) / (next_time - last_time)
            else:
                # stay at last value until next time,
                # when value variable will be evaluated
                value = last_value

            self.knobs[knob].value = value

    def finish(self, state):

        # Upon routine completion, set each knob to its final value
        for knob, value in zip(self.knobs.values(), self.values[:, -1]):
            if knob._controller is None or knob._controller == self:
                knob.value = value


class Sequence(Routine):
    """
    Passes knobs through a series of values regardless of time; each series for
    each knob must have the same length
    """

    def __init__(self,
                 knobs: dict,
                 values,
                 **kwargs):

        Routine.__init__(self, knobs, **kwargs)

        if np.ndim(values) == 1:  # single list of times for all knobs
            values = [values] * len(self.knobs)
        elif np.shape(values)[0] == 1:
            # 1xN array with one N-element list of times for all knobs
            values = [values[0]] * len(self.knobs)

        self.values = np.array(
            values, dtype=object
        ).reshape((len(self.knobs), -1))

        # Times and/or values can be stored in CSV files
        for i, v_elem in enumerate(self.values):

            if type(v_elem[0]) == str and '.csv' in v_elem[0]:
                df = pd.read_csv(v_elem[0])

                df = df['values']

                self.values[i] = df.values.reshape(len(df))

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
                knob.value = value


class Minimization(Routine):
    """
    Minimize a meter/expression influenced by a set of knobs, using simulated
    annealing.

    Arguments:
    - `knobs`: (required) dictionary containing the knobs to be varied
    - `meters`: (required) dictionary whose first entry is the meter/expression
    to minimize.
    - `max_deltas`: (optional) list/array of same length as `knobs` indicating
    the maximum change per step for each knob; if not are specified, defaults
    to a list of ones.
    -`T0` and `T1`: (optional) the initial and final temperatures; if not
    specified, defaults to T0 = 1.0 and T1 = 0.0.
    - `recency bias`: (optional) weight to assign most recent meter measurement
    of minimum when comparing configurations.
    """

    def __init__(self,
                 knobs: dict,
                 meter,
                 max_deltas=None,
                 T0=0.0, T1=0.0,
                 recency_bias=1.0,
                 **kwargs):

        Routine.__init__(self, knobs, **kwargs)

        self.meter = meter

        if max_deltas:
            self.max_deltas = np.array([max_deltas]).flatten()
        else:
            self.max_deltas = np.ones(len(self.knobs))

        self.T = T0
        self.T0 = T0
        self.T1 = T1
        self.recency_bias = recency_bias

        self.best_meter = None
        self.best_knobs = [knob.value for knob in self.knobs.values()]

        self.revert = False  # going back?

    @Routine.enabler
    def update(self, state):

        if not self.prepped:
            self.prep(state)

        # Update temperature
        self.T = self.T0 + (self.T1 - self.T0) \
                 * (state['Time'] - self.start) / (self.end - self.start)

        # Get meter values
        meter_value = state[self.meter]

        # Take no action if knobs values are undefined
        if None in [state[knob] for knob in self.knobs] \
                or np.nan in [state[knob] for knob in self.knobs]:
            return

        # Check if found (or returned to) minimum
        if self.better(meter_value) or self.revert:

            if self.revert and isinstance(self.best_meter, numbers.Number):
                # taking moving average of best meter values
                r = self.recency_bias
                self.best_meter = r*meter_value + (1-r)*self.best_meter
            else:
                # Record this new optimal state
                self.best_meter = meter_value
                self.best_knobs = [state[knob] for knob in self.knobs]

            # Generate and apply new knob settings
            new_knobs = self.best_knobs \
                        + self.max_deltas \
                        * (2 * np.random.rand(len(self.knobs)) - 1)

            for knob, new_value in zip(self.knobs.values(), new_knobs):
                knob.value = new_value
            self.revert = False

        else:

            for knob, best_val in zip(self.knobs.values(), self.best_knobs):
                knob.value = best_val
            self.revert = True

    def better(self, meter_value):

        if meter_value is None or meter_value == np.nan:
            return False

        if self.best_meter is None or self.best_meter == np.nan:
            return False

        change = meter_value - self.best_meter

        if self.T > 0:
            _rand = np.random.rand()
            return (change < 0) or (np.exp(-change / self.T) > _rand)
        else:
            return change < 0


class Maximization(Minimization):
    """
    Maximize a set of meters/expressions influenced by a set of knobs;
    works the same way as Minimize.
    """

    best_meter = -np.inf

    def better(self, meter_value):

        if meter_value is None or meter_value == np.nan:
            return False

        if self.best_meter is None or self.best_meter == np.nan:
            return False

        change = meter_value - self.best_meter

        if self.T > 0:
            _rand = np.random.rand()
            return (change > 0) or (np.exp(change / self.T) > _rand)
        else:
            return change > 0


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

        self.acc_conn_thread = threading.Thread(
            target=self.accept_connections
        )

        self.acc_conn_thread.start()

        self.proc_requ_thread = threading.Thread(
            target=self.process_requests
        )

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

                print(f'Client at {address} has connected')

            except socket.timeout:
                pass

        # Close sockets
        try:
            self.socket.shutdown(socket.SHUT_RDWR)
        except OSError:  # socket was not connected
            pass
        self.socket.close()

        clients = self.clients_queue.get()

        for address, client in clients.items():
            client.shutdown(socket.SHUT_RDWR)
            client.close()

        # Return empty clients dict to queue so process_requests can exit
        self.clients_queue.put({})

    def process_requests(self):
        while self.running:

            clients = self.clients_queue.get()

            for address, client in clients.items():

                outgoing_message = None

                request = read_from_socket(client)

                if request:

                    alias = ' '.join(request.split(' ')[:-1])
                    value = request.split(' ')[-1]

                    if alias not in self.knobs \
                            and alias not in self.state:

                        outgoing_message = f'Error: invalid alias'

                    elif value == 'settable?':

                        settable = (alias in self.knobs) \
                                   and self.knobs[alias]._settable

                        if settable:
                            outgoing_message = f'{alias} settable'
                        elif alias in self.state:
                            outgoing_message = f'{alias} read-only'
                        else:
                            outgoing_message = f'{alias} undefined'

                    elif value == 'dtype?':

                        if alias in self.knobs:
                            dtype = self.knobs[alias].dtype
                        elif alias in self.state:

                            dtype = None
                            for _type in supported_types.values():
                                if isinstance(self.state[alias], _type):
                                    dtype = _type

                        else:
                            dtype = None

                        outgoing_message = f'{alias} {dtype}'

                    elif value == '?':  # Query of value

                        if alias in self.knobs:
                            _value = self.knobs[alias].value
                        elif alias in self.state:
                            _value = self.state[alias]
                        else:
                            _value = None

                        outgoing_message = f'{alias} {_value}'

                    else:  # Setting a value

                        knob_exists = alias in self.knobs

                        is_free = not getattr(
                            self.knobs[alias], '_controller', None
                        )

                        if knob_exists and is_free:

                            knob = self.knobs[alias]

                            knob.value = recast(value, to=knob.dtype)

                            outgoing_message = f'{alias} {knob.value}'

                        else:
                            outgoing_message = f'Error: cannot set {alias}'

                # Send outgoing message
                if outgoing_message is not None:
                    write_to_socket(client, outgoing_message)

                # Remove clients with problematic connections
                exceptional = client in select.select([], [], [client], 0)[2]

                if exceptional:
                    print(f'Client at {address} has a connection issue')
                    clients.pop(address)

            self.clients_queue.put(clients)

            time.sleep(0.1)

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
    any metadata (i.e. data type).
    """

    assert_control = False

    def __init__(self, knobs: dict = None, **kwargs):

        if knobs is None:
            knobs = {}

        Routine.__init__(self, knobs, **kwargs)

        self.state = {}

        # Check for PyModbus installation
        try:
            importlib.import_module('pymodbus')
        except ModuleNotFoundError:
            raise ModuleNotFoundError(
                'pymodbus must be installed to run a Modbus server'
            )

        # Import tools from pymodbus
        datastore = importlib.import_module('.datastore', package='pymodbus')
        device = importlib.import_module('.device', package='pymodbus')
        payload = importlib.import_module('.payload', package='pymodbus')

        self._builder_cls = payload.BinaryPayloadBuilder
        self._decoder_cls = payload.BinaryPayloadDecoder

        DataBlock = datastore.ModbusSequentialDataBlock

        # Set up a PyModbus TCP Server
        datastore.ModbusSlaveContext.setValues = self.setValues_decorator(
            datastore.ModbusSlaveContext.setValues
        )

        self.slave = datastore.ModbusSlaveContext(
                ir=DataBlock.create(),
                hr=DataBlock.create()
            )

        self.context = datastore.ModbusServerContext(
            slaves=self.slave,
            single=True
        )

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
        self.ip_address = kwargs.get('address', get_ip_address())
        self.port = kwargs.get('port', 502)

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
                        f'Warning: an attempt was made to write to a readonly '
                        f'register at address {address}'
                    )
                else:

                    if self.knobs:

                        variable = list(self.knobs.values())[address//4]

                        controller = getattr(variable, '_controller', None)

                        if controller:

                            name = list(self.knobs.keys())[address // 4]

                            print(
                                f'Warning: an attempt was made to set {name}, '
                                'but it is currently controlled by '
                                f'{controller}.'
                            )
                            return

                        decoder = self._decoder_cls.fromRegisters(
                            values, byteorder='>'
                        )

                        if issubclass(variable.dtype, Boolean):
                            variable.value = decoder.decode_64bit_uint()
                        elif issubclass(variable.dtype, Toggle):
                            int_value = decoder.decode_64bit_uint()
                            variable.value = OFF if int_value == 0 else ON
                        elif issubclass(variable.dtype, Integer):
                            variable.value = decoder.decode_64bit_int()
                        elif issubclass(variable.dtype, Float):
                            variable.value = decoder.decode_64bit_float()

        return wrapped_method

    async def _update_registers(self):

        # Store readwrite variable values in holding registers (fc = 3)
        builder = self._builder_cls(byteorder='>')

        for i, (name, variable) in enumerate(self.knobs.items()):

            # encode the value into the 4 registers
            if variable._value is None or variable.dtype is None:
                builder.add_64bit_float(float('nan'))
            elif issubclass(variable.dtype, Boolean):
                builder.add_64bit_uint(variable._value)
            elif issubclass(variable.dtype, Toggle):
                builder.add_64bit_uint(variable._value)
            elif issubclass(variable.dtype, Integer):
                builder.add_64bit_int(variable._value)
            elif issubclass(variable.dtype, Float):
                builder.add_64bit_float(variable._value)
            else:
                raise ValueError(
                    f'unable to update modbus server registers from value '
                    f'{variable._value} of variable {name} with data type '
                    f'{variable.dtype}'
                )

            # encode the meta data
            meta_reg_val = {
                Boolean: 0,
                Toggle: 1,
                Integer: 2,
                Float: 3,
                Array: 4,
                String: 5,
            }.get(variable.dtype, -1)

            builder.add_16bit_int(meta_reg_val)

        # from_vars kwarg added with setValues_decorator above
        self.slave.setValues(3, 0, builder.to_registers(), from_vars=True)

        # Store readonly variable values in input registers (fc = 4)
        builder.reset()

        for i, (name, value) in enumerate(self.state.items()):

            dtype = None
            for _type in supported_types.values():
                if isinstance(value, _type):
                    dtype = _type

            # encode the value into the 4 registers
            if value is None or dtype is None:
                builder.add_64bit_float(float('nan'))
            elif dtype == Boolean:
                builder.add_64bit_uint(value)
            elif dtype == Toggle:
                builder.add_64bit_uint(value)
            elif dtype == Integer:
                builder.add_64bit_int(value)
            elif dtype == Float:
                builder.add_64bit_float(value)
            else:
                raise ValueError(
                    f'unable to update modbus server registers from value '
                    f'{value} of variable {name} with data type '
                    f'{dtype}'
                )

            # encode the meta data
            dtype_int = {
                Boolean: 0,
                Toggle: 1,
                Integer: 2,
                Float: 3
            }.get(dtype, -1)

            builder.add_16bit_int(dtype_int)

        # from_vars kwarg added with setValues_decorator above
        self.slave.setValues(4, 0, builder.to_registers(), from_vars=True)

        await asyncio.sleep(0.1)

        asyncio.create_task(self._update_registers())

    async def _run_async_server(self):

        asyncio.create_task(self._update_registers())

        server = importlib.import_module('.server', package='pymodbus')

        self.server = server.ModbusTcpServer(
            self.context,
            identity=self.identity,
            address=(self.ip_address, self.port)
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


supported = {key: value for key, value in vars().items()
             if type(value) is type and issubclass(value, Routine)}
