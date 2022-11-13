import numbers
import socket
import queue
import threading
import time
import select
import numpy as np
import pandas as pd

from empyric.tools import convert_time, recast, \
    autobind_socket, read_from_socket, write_to_socket


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
                    values = [values]*len(self.knobs)
                elif np.shape(values)[0] == 1:
                    # 1xN array with one N-element list of times for all knobs
                    values = [values[0]]*len(self.knobs)

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
                    times = [times]*len(self.knobs)
                elif np.shape(times)[0] == 1:
                    # 1xN array with one N-element list of times for all knobs
                    times = [times[0]]*len(self.knobs)

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
    Minimize the sum of a set of meters/expressions influenced by a set of
    knobs, using simulated annealing.
    """

    def __init__(self, meters=None, max_deltas=None, T0=0.1, T1=0, **kwargs):

        Routine.__init__(self, **kwargs)

        if meters:
            self.meters = np.array([meters]).flatten()
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
        self.last_knobs = [np.nan]*len(self.knobs)
        self.last_meters = [np.nan]*len(self.meters)

    def update(self, state):

        # Get meter values
        meter_values = np.array([state[meter] for meter in self.meters])

        # Update temperature
        self.T = self.T0 + self.T1*(
                state['Time'] - self.start
        )/(self.end - self.start)

        if self.better(meter_values):

            # Record this new optimal state
            self.last_knobs = [state[knob] for knob in self.knobs]
            self.last_meters = [state[meter] for meter in self.meters]

            # Generate and apply new knob settings
            new_knobs = self.last_knobs + self.max_deltas*np.random.rand(
                len(self.knobs)
            )
            for knob, new_value in zip(self.knobs.values(), new_knobs):
                knob.value = new_value

        else:  # go back
            for knob, last_value in zip(self.knobs.values(), self.last_knobs):
                knob.value = last_value

    def better(self, meter_values):

        if np.prod(self.last_meters) != np.nan:
            change = np.sum(meter_values) - np.sum(self.last_meters)
            return (change < 0) or (np.exp(-change/self.T) > np.random.rand())
        else:
            return False


class Maximization(Minimization):
    """
    Maximize a set of meters/expressions influenced by a set of knobs;
    works the same way as Minimize.
    """

    def better(self, meter_values):

        if np.prod(self.last_meters) != np.nan:
            change = np.sum(meter_values) - np.sum(self.last_meters)
            return (change > 0) or (np.exp(change / self.T) > np.random.rand())
        else:
            return False


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


class Server(Routine):

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

        print(f'Running server at {self.ip_address}::{self.port}')

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

        # Close sockets
        self.socket.shutdown(socket.SHUT_RDWR)
        self.socket.close()

        clients = self.clients_queue.get()

        for client in clients.values():
            client.shutdown(socket.SHUT_RDWR)
            client.close()

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
        self.terminate()


supported = {key: value for key, value in vars().items()
             if type(value) is type and issubclass(value, Routine)}
