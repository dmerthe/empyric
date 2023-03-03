import importlib
import numbers
import socket
import queue
import threading
import asyncio
import time
import select
import numpy as np
import pandas as pd

from empyric.tools import convert_time, recast, \
    autobind_socket, read_from_socket, write_to_socket, get_ip_address


class Routine:
    """
    Base class for all routines
    """

    def __init__(self, knobs=None, values=None, start=0, end=np.inf):
        """

        :param knobs: (Variable/1D array) knob variable(s) to be controlled
        :param values: (1D/2D array) array or list of values for each variable;
        can be 1D iff there is one knob
        :param start: (float) time to start the routine
        :param end: (float) time to end the routine
        """

        if knobs is not None:

            self.knobs = knobs
            # dictionary of the form, {..., name: variable, ...}

            for knob in self.knobs.values():
                knob.controller = None
                # for keeping track of which routines are controlling knobs

        if values is not None:

            if len(self.knobs) > 1:
                if np.ndim(values) == 1:  # single list of values for all knobs
                    values = [values] * len(self.knobs)
                elif np.shape(values)[0] == 1:
                    # 1xN array with one N-element list of times for all knobs
                    values = [values[0]] * len(self.knobs)

            self.values = np.array(
                values, dtype=object
            ).reshape((len(self.knobs), -1))

        self.start = convert_time(start)
        self.end = convert_time(end)

    def update(self, state):
        """
        Updates the knobs controlled by the routine

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


class Set(Routine):
    """
    Sets and keeps knobs at fixed values
    """

    def update(self, state):

        if state['Time'] < self.start or state['Time'] > self.end:
            return  # no change

        for knob, value in zip(self.knobs.values(), self.values):

            if 'Variable' in repr(value):
                knob.value = value._value
            else:
                knob.value = value[0]


class Timecourse(Routine):
    """
    Ramps linearly through a series of values at given times
    """

    def __init__(self, times=None, **kwargs):
        """

        :param times: (1D/2D array) array or list of times relative to the start
         time
        :param kwargs: keyword arguments for Routine
        """

        Routine.__init__(self, **kwargs)

        if times:

            if len(self.knobs) > 1:
                if np.ndim(times) == 1:  # single list of times for all knobs
                    times = [times] * len(self.knobs)
                elif np.shape(times)[0] == 1:
                    # 1xN array with one N-element list of times for all knobs
                    times = [times[0]] * len(self.knobs)

            self.times = np.array(
                times, dtype=object
            ).reshape((len(self.knobs), -1))

            # Values can be stored in a CSV file
            for i, element in enumerate(self.times):
                if type(element[0]) == str:
                    if '.csv' in element[0]:
                        df = pd.read_csv(element[0])

                        df = df[df.coloumns[0]]

                        self.times[i] = df.values.reshape(len(df))

            self.times = np.array(convert_time(self.times)).astype(float)

        else:
            raise AttributeError('Timecourse routine requires times!')

        self.start = np.min(self.times)
        self.end = np.max(self.times)
        self.finished = False

    def update(self, state):

        if state['Time'] < self.start:
            return
        elif state['Time'] > self.end:
            if not self.finished:
                for knob, values in zip(self.knobs.values(), self.values):
                    if knob.controller == self:
                        knob.value = values[-1]
                        # make sure to set the end value

                    knob.controller = None

                self.finished = True

            return
        else:
            for name, knob in self.knobs.items():

                has_controller = isinstance(knob.controller, Routine)

                if has_controller and knob.controller != self:
                    controller = knob.controller
                    if controller.start < state['Time'] < controller.end:
                        raise RuntimeError(
                            f"Knob {name} has more than one controlling "
                            f"routine at time = {state['Time']} seconds!"
                        )
                else:
                    knob.controller = self

        knobs_times_values = zip(self.knobs.values(), self.times, self.values)
        for variable, times, values in knobs_times_values:

            j_last = np.argwhere(times <= state['Time']).flatten()[-1]
            j_next = np.argwhere(times > state['Time']).flatten()[0]

            last_time = times[j_last]
            next_time = times[j_next]

            last_value = values[j_last]
            next_value = values[j_next]

            if 'Variable' in repr(last_value):
                last_value = last_value._value
                # replace variable with value for past times

            last_is_number = isinstance(last_value, numbers.Number)
            next_is_number = isinstance(next_value, numbers.Number)

            if next_is_number and last_is_number:
                # ramp linearly between numerical values
                value = last_value + (
                        next_value - last_value) * (state['Time'] - last_time
                                                    ) / (next_time - last_time)
            else:
                # stay at last value until next time,
                # when value variable will be evaluated
                value = last_value

            variable.value = value


class Sequence(Routine):
    """
    Passes knobs through a series of values regardless of time; each series for
    each knob must have the same length
    """

    def __init__(self, **kwargs):
        Routine.__init__(self, **kwargs)

        self.iteration = 0

    def update(self, state):

        if state['Time'] < self.start or state['Time'] > self.end:
            return  # no change

        for knob, values in zip(self.knobs.values(), self.values):
            value = values[self.iteration]
            knob.value = value

        self.iteration = (self.iteration + 1) % len(self.values[0])


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
                 meters=None, max_deltas=None, T0=1.0, T1=0.0,
                 recency_bias=0.5,
                 **kwargs):

        Routine.__init__(self, **kwargs)

        if meters:
            self.meter = tuple(meters.keys())[0]
        else:
            raise AttributeError(
                f'{self.__name__} routine requires meters for feedback'
            )

        if max_deltas:
            self.max_deltas = np.array([max_deltas]).flatten()
        else:
            self.max_deltas = np.ones(len(self.knobs))

        self.T = T0
        self.T0 = T0
        self.T1 = T1

        self.recency_bias = recency_bias

        self.best_knobs = [knob.value for knob in self.knobs.values()]
        self.best_meter = np.nan

        self.revert = False  # going back?
        self.finished = False

    def update(self, state):

        if state['Time'] < self.start:
            return
        elif state['Time'] > self.end:
            if not self.finished:

                for knob, best_val in zip(self.knobs.values(), self.best_knobs):
                    if knob.controller == self:

                        knob.value = best_val
                        knob.controller = None

                self.finished = True
        else:

            # Take control of knobs
            for knob in self.knobs.values():
                knob.controller = self

            # Update temperature
            self.T = self.T0 + (self.T1 - self.T0) \
                     * (state['Time'] - self.start) / (self.end - self.start)

            # Get meter values
            meter_value = state[self.meter]

            if meter_value is None or meter_value == np.nan:
                # no action taken if meter value is undefined
                return
            elif None in [state[knob] for knob in self.knobs]:
                # no action taken if knobs values are undefined
                return
            elif np.nan in [state[knob] for knob in self.knobs]:
                # no action taken if knobs values are undefined
                return

            # Check if found (or returned to) minimum
            if self.better(meter_value) or self.revert:
                self.revert = False

                # Record this new optimal state
                self.best_knobs = [state[knob] for knob in self.knobs]

                if self.revert and isinstance(self.best_meter, numbers.Number):
                    # moving average of repeated meter value measurements
                    r = self.recency_bias
                    self.best_meter = r*meter_value + (1-r)*self.best_meter
                else:
                    self.best_meter = meter_value

                # Generate and apply new knob settings
                new_knobs = self.best_knobs \
                            + self.max_deltas \
                            * (2 * np.random.rand(len(self.knobs)) - 1)

                for knob, new_value in zip(self.knobs.values(), new_knobs):
                    knob.value = new_value

            else:

                for knob, best_val in zip(self.knobs.values(), self.best_knobs):
                    knob.value = best_val

                self.revert = True

    def better(self, meter_value):

        if meter_value is None or meter_value == np.nan:
            return False

        if self.best_meter == np.nan:
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

    def better(self, meter_value):

        if meter_value is None or meter_value == np.nan:
            return False

        if self.best_meter == np.nan:
            return False

        change = meter_value - self.best_meter

        if self.T > 0:
            _rand = np.random.rand()
            return (change > 0) or (np.exp(change / self.T) > _rand)
        else:
            return change > 0


class ModelPredictiveControl(Routine):
    """
    (NOT IMPLEMENTED)
    Simple model predictive control; learns the relationship between knob x
    and meter y, assuming a linear model,

    y(t) = y0 + int_{-inf}^{t} dt' m(t-t') x(t')

    then sets x to minimize the error in y relative to setpoint, over some
    time interval defined by cutoff.

    """

    def __init__(self, meters=None, **kwargs):
        Routine.__init__(self, **kwargs)
        self.meters = meters

    def update(self, state):
        pass


class SocketServer(Routine):
    """
    Server routine for transmitting data to other experiments, local or remote,
    using the socket interface.

    Variables accessible to the server are specified by providing
    dictionaries of variables in the form, {..., name: variable, ...} as the
    readwrite and/or readonly arguments. Any variables given in the
    `readwrite` argumment will be readable and writeable from by connected
    clients. Variables given in the `readonly` argument will be read-only by
    clients.
    """

    def __init__(self, readwrite=None, readonly=None, **kwargs):

        Routine.__init__(self, **kwargs)

        self.readwrite = {}
        self.readonly = {}

        if readwrite:
            self.readwrite = readwrite

        if readonly:
            self.readonly = readonly

        self.variables = {**self.readonly, **self.readwrite}

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self.ip_address, self.port = autobind_socket(self.socket)

        self.socket.listen(5)
        self.socket.settimeout(1)

        self.clients_queue = queue.Queue(1)
        self.clients_queue.put({})

        self.running = True

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

                    if alias not in self.variables:
                        outgoing_message = f'Error: invalid alias'

                    elif value == 'settable?':

                        settable = self.variables[alias].settable

                        if alias in self.readwrite and settable:
                            outgoing_message = f'{alias} settable'
                        else:
                            outgoing_message = f'{alias} readonly'

                    elif value == '?':  # Query of value
                        var = self.variables[alias]
                        outgoing_message = f'{alias} {var.value}'

                    else:  # Setting a value
                        if alias in self.readwrite:
                            var = self.readwrite[alias]
                            var.value = recast(value)
                            outgoing_message = f'{alias} {var.value}'
                        else:
                            outgoing_message = f'Error: readonly variable'

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

    def __del__(self):
        if self.running:
            self.terminate()


class ModbusServer(Routine):
    """
    Server routine for transmitting data to other experiments, local or remote,
    using the Modbus over TCP/IP protocol.

    Variables accessible to the server are specified by providing
    dictionaries of variables in the form, {..., name: variable, ...} as the
    readwrite and/or readonly arguments. Any variables given in the
    `readwrite` argumment will be readable and writeable from by connected
    clients. Variables given in the `readonly` argument will be read-only by
    clients.

    Only variables with `bool`, `int` or `float` types can be used.

    Readwrite variables will be stored in holding registers in the same order
    as given in the argument, starting from address 0. Readonly variables will
    be stored similarly in input registers.
    """

    def __init__(self, readwrite=None, readonly=None, **kwargs):

        self.readwrite = {}
        self.readonly = {}

        if readwrite:
            self.readwrite = readwrite

        if readonly:
            self.readonly = readonly

        Routine.__init__(self, **kwargs)

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

        # Map each variable to 2 sequential registers
        if self.readonly:
            readonly_block = datastore.ModbusSequentialDataBlock(
                0, [0] * 2 * len(readonly)
            )
        else:
            readonly_block = datastore.ModbusSequentialDataBlock.create()

        if self.readwrite:
            readwrite_block = datastore.ModbusSequentialDataBlock(
                0, [0] * 2 * len(readwrite)
            )
        else:
            readwrite_block = datastore.ModbusSequentialDataBlock.create()

        # Set up a PyModbus TCP Server
        self.slave = datastore.ModbusSlaveContext(
                ir=readonly_block,
                hr=readwrite_block
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

        self.server_thread = threading.Thread(
            target=self._run_server
        )

        self.server_thread.start()

    async def _update_registers(self, update_variables=True):

        # Apply readwrite register values to writable variables
        if update_variables:
            decoder = self._decoder_cls.fromRegisters(
                self.slave.getValues(3, 0, 2*len(self.readwrite))
            )

            for i, (_, variable) in enumerate(self.readwrite.items()):

                if type(variable._value) is bool:
                    value = bool(decoder.decode_32bit_uint())
                elif type(variable._value) is int:
                    value = decoder.decode_32bit_int()
                elif type(variable._value) is float:
                    value = decoder.decode_32bit_float()
                else:
                    decoder.decode_32bit_int()  # decode 2 registers and ignore
                    value = None

                if value is not None:
                    variable.value = value

        # Store readwrite variable values in holding registers (fc = 3)
        builder = self._builder_cls()

        for i, (_, variable) in enumerate(self.readwrite.items()):

            value = variable._value

            if type(value) is bool:
                builder.add_32bit_uint(value)
            elif type(value) is int:
                builder.add_32bit_int(value)
            elif type(value) is float:
                builder.add_32bit_float(value)
            else:
                builder.add_32bit_int(-1)

        self.slave.setValues(3, 0, builder.to_registers())

        # Store readonly variable values in input registers (fc = 4)
        builder.reset()

        for i, (_, variable) in enumerate(self.readonly.items()):

            value = variable._value

            if type(value) is bool:
                builder.add_32bit_uint(value)
            elif type(value) is int:
                builder.add_32bit_int(value)
            elif type(value) is float:
                builder.add_32bit_float(value)
            else:
                builder.add_32bit_int(-1)

        self.slave.setValues(4, 0, builder.to_registers())

        await asyncio.sleep(0.1)

        asyncio.create_task(self._update_registers())

    async def _run_async_server(self):

        asyncio.create_task(self._update_registers())

        server = importlib.import_module('.server', package='pymodbus')

        self.server = server.ModbusTcpServer(
            self.context,
            identity=self.identity,
            address=(get_ip_address(), 502)
        )

        try:
            await self.server.serve_forever()
        except asyncio.exceptions.CancelledError:
            # Server shutdown cancels the _update_registers task
            pass

    def _run_server(self):
        """Run the server"""

        # Input variable values into registers
        asyncio.run(self._update_registers(update_variables=False))

        # Start the Modbus TCP server
        asyncio.run(self._run_async_server())

    def terminate(self):
        asyncio.run(self.server.shutdown())
        self.server_thread.join(timeout=1.0)


supported = {key: value for key, value in vars().items()
             if type(value) is type and issubclass(value, Routine)}
