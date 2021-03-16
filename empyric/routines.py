import time
import numbers
import numpy as np
import pandas as pd
from importlib import import_module
from scipy.interpolate import interp1d

from empyric.control import PIDController

def convert_time(time_value):
    """
    Converts a time of the form "number units" (e.g. "3.5 hours") to the time in seconds.

    :param time_value: (str/float) time value, possibly including units such as 'hours'
    :return: (int) time in seconds
    """

    if hasattr(time_value, '__len__') and not isinstance(time_value, str):
        return [convert_time(t) for t in time_value]

    if isinstance(time_value, numbers.Number):
        return time_value
    elif isinstance(time_value, str):
        # times can be specified in the runcard with units, such as minutes, hours or days, e.g.  "6 hours"
        time_parts = time_value.split(' ')

        if len(time_parts) == 1:
            return float(time_parts[0])
        elif len(time_parts) == 2:
            value, unit = time_parts
            value = float(value)
            return value * {
                'seconds': 1, 'second':1,
                'minutes': 60, 'minute': 60,
                'hours': 3600, 'hour': 3600,
                'days': 86400, 'day':86400
            }[unit]
        else:
            raise ValueError(f'Unrecognized time format for {time_value}!')

## Routines ##

class Routine:
    """
    Base class for all routines
    """

    def __init__(self, variables=None, values=None, start=0, end=np.inf):
        """

        :param variables: (1D array) array or list of variables to be controlled
        :param values: (1D/2D array) array or list of values for each variable
        :param start: (float) time to start the routine
        :param stop: (float) time to end the routine
        """

        if variables:
            self.variables = variables
        else:
            raise AttributeError(f'{self.__name__} routine requires variables!')

        if values:
            self.values = values

            # values can be specified in a CSV file
            for i, values_i in enumerate(self.values):
                if values_i == 'csv':
                    df = pd.read_csv(values_i)
                    self.values[i] = df[df.columns[-1]].values

            self.values = np.array([self.values]).flatten().reshape((len(self.variables),-1)) # make rows match self.variables
        else:
            raise AttributeError(f'{self.__name__} routine requires values!')


        self.start = start
        self.end = end


class Hold(Routine):
    """
    Holds a fixed value
    """

    def update(self, state):

        update = {name: value for name, value in state.items() if name in self.variables}
        if state['time'] < self.start or state['time'] > self.end:
            return update  # no change

        for name, variable, value in zip(self.variables, self.variables.values(), self.values):
            variable.value = value
            update[name] = value

        return update


class Timecourse(Routine):
    """
    Ramps linearly through a series of values at given times
    """

    def __init__(self, times=None, **kwargs):
        """

        :param times: (1D/2D array) array or list of times, relative to the start time, to set each variable to each value
        :param kwargs: keyword arguments for Routine
        """

        Routine.__init__(self, **kwargs)

        if times:
            self.times = times

            # times can be specified in a CSV file
            for i, times_i in enumerate(times):
                if times_i == 'csv':
                    df = pd.read_csv(times_i)
                    self.times[i] = df[df.columns[-1]].values

            self.times = np.array([self.times]).flatten().reshape((len(self.variables), -1))  # make rows match self.variables
        else:
            raise AttributeError('Timecourse routine requires times!')

        self.interpolators = {variable: interp1d(times, values, bounds_error=False) for variable, times, values
                              in zip(self.variables, self.times, self.values)}

    def update(self, state):

        update = {name: value for name, value in state.items() if name in self.variables}
        if state['time'] < self.start or state['time'] > self.end:
            return update  # no change

        for name, variable in zip(self.variables, self.variables.values()):
            value = self.interpolators[name](state['time']-self.start)
            variable.value = value
            update[name] = value

        return update


class Sequence(Routine):
    """
    Passes through a series of values regardless of time
    """

    def __init__(self, **kwargs):
        Routine.__init__(**kwargs)

        self.iteration = 0

    def update(self, state):

        update = {name: value for name, value in state.items() if name in self.variables}
        if state['time'] < self.start or state['time'] > self.end:
            return update  # no change

        for name, variable, values in zip(self.variables, self.variables.values(), self.values):
            value = values[self.iteration]
            variable.value = value
            update[name] = value

        self.iteration = (self.iteration + 1) % len(self.values)

        return update


class Set(Routine):
    """
    Sets a knob based on the value of another variable
    """

    def __init__(self, input=None, **kwargs):

        Routine.__init__(**kwargs)

        if inputs:
            self.inputs = inputs
        else:
            raise AttributeError('Set routine requires inputs!')

    def update(self, state):

        update = {name: value for name, value in state.items() if name in self.variables}
        if state['time'] < self.start or state['time'] > self.end:
            return update  # no change

        for name, variable, input in zip(self.variables, self.variables.values(), self.inputs):
            value = state[input]
            variable.value = value
            update[name] = value

        return update


class Minimize(Routine):
    """
    Minimize a variable influenced by a knob
    """
    pass


class Maximize(Routine):
    """
    Mazimize a variable influenced by a knob
    """
    pass
