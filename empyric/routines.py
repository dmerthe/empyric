import numbers
import numpy as np
import pandas as pd

from empyric.tools import convert_time


class Routine:
    """
    Base class for all routines
    """

    def __init__(self, knobs=None, values=None, start=0, end=np.inf):
        """

        :param knobs: (Variable/1D array) knob variable(s) to be controlled
        :param values: (1D/2D array) array or list of values for each variable; can be 1D iff there is one knob
        :param start: (float) time to start the routine
        :param end: (float) time to end the routine
        """

        if knobs is not None:
            self.knobs = knobs  # dictionary of the form, {..., name: variable, ...}
            for knob in self.knobs.values():
                knob.controller = None  # for keeping track of which routines are controlling knobs

        if values is not None:

            if len(self.knobs) > 1:
                if np.ndim(values) == 1:  # single list of values for all knobs
                    values = [values]*len(self.knobs)
                elif np.shape(values)[0] == 1: # 1xN array with one N-element list of times for all knobs
                    values = [values[0]]*len(self.knobs)

            self.values = np.array(values, dtype=object).reshape((len(self.knobs), -1))

        self.start = convert_time(start)
        self.end = convert_time(end)

    def update(self, state):
        """
        Updates the knobs controlled by the routine

        :param state: (dict/Series) state of the calling experiment or process in the form, {..., variable: value, ...}
        :return: None
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

        :param times: (1D/2D array) array or list of times relative to the start time
        :param kwargs: keyword arguments for Routine
        """

        Routine.__init__(self, **kwargs)

        if times:

            if len(self.knobs) > 1:
                if np.ndim(times) == 1:  # single list of times for all knobs
                    times = [times]*len(self.knobs)
                elif np.shape(times)[0] == 1: # 1xN array with one N-element list of times for all knobs
                    times = [times[0]]*len(self.knobs)

            self.times = np.array(times, dtype=object).reshape((len(self.knobs), -1))

            # Values can be stored in a CSV file
            for i, element in enumerate(self.times):
                if type(element[0]) == str:
                    if '.csv' in element[0]:
                        df = pd.read_csv(element[0])
                        self.times[i] = df[df.columns[0]].values.reshape(len(df))

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
                        knob.value = values[-1]  # make sure to set the end value

                    knob.controller = None

                self.finished = True

            return
        else:
            for name, knob in self.knobs.items():

                if isinstance(knob.controller, Routine) and knob.controller != self:
                    controller = knob.controller
                    if controller.start < state['Time'] < controller.end:
                        raise RuntimeError(f"Knob {name} has more than one controlling routine at time = {state['Time']} seconds!")
                else:
                    knob.controller = self

        for variable, times, values in zip(self.knobs.values(), self.times, self.values):

            j_last = np.argwhere(times <= state['Time']).flatten()[-1]
            j_next = np.argwhere(times > state['Time']).flatten()[0]

            last_time = times[j_last]
            next_time = times[j_next]

            last_value = values[j_last]
            next_value = values[j_next]

            if 'Variable' in repr(last_value):
                last_value = last_value._value  # replace variable with value for past times

            if isinstance(next_value, numbers.Number) and isinstance(last_value, numbers.Number):
                # ramp linearly between numerical values
                value = last_value + (next_value - last_value) * (state['Time'] - last_time) / (next_time - last_time)
            else:
                value = last_value  # stay at last value until next time, when value variable will be evaluated

            variable.value = value


class Sequence(Routine):
    """
    Passes knobs through a series of values regardless of time; each series for each knob must have the same length
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
    Minimize the sum of a set of meters/expressions influenced by a set of knobs, using simulated annealing.
    """

    def __init__(self, meters=None, max_deltas=None, T0=0.1, T1=0, **kwargs):

        Routine.__init__(self, **kwargs)

        if meters:
            self.meters = np.array([meters]).flatten()
        else:
            raise AttributeError(f'{self.__name__} routine requires meters for feedback')

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
        self.T = self.T0 + self.T1*(state['Time'] - self.start)/(self.end - self.start)

        if self.better(meter_values):

            # Record this new optimal state
            self.last_knobs = [state[knob] for knob in self.knobs]
            self.last_meters = [state[meter] for meter in self.meters]

            # Generate and apply new knob settings
            new_knobs = self.last_knobs + self.max_deltas*np.random.rand(len(self.knobs))
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
    Maximize a set of meters/expressions influenced by a set of knobs; works the same way as Minimize.
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
    Simple model predictive control; learns the relationship between knob x and meter y, assuming a linear model,

    y(t) = y0 + int_{-inf}^{t} dt' m(t-t') x(t')

    then sets x to minimize the error in y relative to setpoint, over some time interval defined by cutoff.

    """

    def __init__(self, meters=None, **kwargs):

        Routine.__init__(self, **kwargs)
        self.meters = meters

    def update(self, state):
        pass


supported = {key: value for key, value in vars().items()
             if type(value) is type and issubclass(value, Routine)}
