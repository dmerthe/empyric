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
            self.variables = np.array([variables]).flatten()  # assert 1D array; user can specify just a single variable
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

    #
    # def __init__(self, **kwargs):
    #     """
    #     A preset program for the values that a variable takes during an experiment
    #
    #     :param kwargs: any attributes that the routine should have
    #     """
    #
    #     for time_kwarg in ['times', 'start', 'end']:
    #         if time_kwarg in kwargs:
    #             kwargs[time_kwarg] = convert_time(kwargs[time_kwarg])
    #
    #     # Register the start and end of the routine
    #     if not 'start' in kwargs:
    #         if 'times' in kwargs:
    #             self.start = kwargs['times'][0]
    #         else:
    #             self.start = -np.inf
    #
    #     if not 'end' in kwargs:
    #         if 'times' in kwargs:
    #             self.end = kwargs['times'][-1]
    #         else:
    #             self.end = np.inf
    #
    #     for key, value in kwargs.items():
    #         self.__setattr__(key, value)
    #
    #     if 'csv' in kwargs.get('values', ''):  # values can be specified in a CSV file
    #         df = pd.read_csv(kwargs['values'])
    #         self.values = df[df.columns[-1]].values
    #
    #         if len(df.columns) > 1 and 'times' not in kwargs:
    #             try:
    #                 times_column = [col for col in df.columns if col.lower() == 'times'][0]
    #                 self.times = df[times_column].values
    #             except IndexError:
    #                 pass
    #
    #     # Make an interpolator if there are multiple times and values
    #     if hasattr(self, 'values') and hasattr(self, 'times'):
    #         if len(kwargs['times']) != len(kwargs['values']):
    #             raise ValueError('Routine times keyword argument must match length of values keyword argument!')
    #
    #         if isinstance(kwargs['values'][0], numbers.Number):
    #             self.interpolator = interp1d(kwargs['times'], kwargs['values'])
    #         else:
    #             def interpolator(_time):
    #                 return kwargs['values'][np.argwhere(np.array(kwargs['times'])<_time).flatten()[-1]]
    #
    #             self.interpolator = interpolator
    #
    #     if 'feedback' in kwargs:
    #         self.controller = kwargs.get('controller', PIDController())
    #
    #
    # def __call__(self, state):
    #     """
    #     When called, a routine returns a knob setting which depends on the state of the experiment using the routine.
    #     This method should be overwritten by child classes
    #
    #     :param state: (pandas.Series) state of the experiment
    #     :return: (float/str) value of new setting to be applied
    #     """
    #
    #     pass


class Hold(Routine):
    """
    Holds a fixed value
    """

    def __call__(self, state):

        update = {name: value for name, value in state.items() if name in self.variables}
        if state['time'] < self.start or state['time'] > self.end:
            return update  # no change

        update.update({variable: value[0] for variable, value in zip(self.variables, self.values)})

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

    def __call__(self, state):

        update = {name: value for name, value in state.items() if name in self.variables}
        if state['time'] < self.start or state['time'] > self.end:
            return update  # no change

        update.update({variable: self.interpolators[variable](state['time']-self.start) for variable in self.variables})

        return update


class Sequence(Routine):
    """
    Passes through a series of values regardless of time
    """

    def __init__(self, **kwargs):
        Routine.__init__(**kwargs)

        self.iteration = 0

    def __call__(self, state):

        update = {name: value for name, value in state.items() if name in self.variables}
        if state['time'] < self.start or state['time'] > self.end:
            return update  # no change

        update.update({variable: values[self.iteration] for variable, values in zip(self.variables, self.values)})

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

    def __call__(self, state):

        update = {name: value for name, value in state.items() if name in self.variables}
        if state['time'] < self.start or state['time'] > self.end:
            return update  # no change

        update.update({variable: state[input] for variable, input in zip(self.variables, self.inputs)})

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
