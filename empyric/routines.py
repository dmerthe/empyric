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

    def __init__(self, **kwargs):
        """
        A preset program for the values that a variable takes during an experiment

        :param kwargs: any attributes that the routine should have
        """

        for time_kwarg in ['times', 'start', 'end']:
            if time_kwarg in kwargs:
                kwargs[time_kwarg] = convert_time(kwargs[time_kwarg])

        for key, value in kwargs.items():
            self.__setattr__(key, value)

        if 'csv' in kwargs.get('values', ''):  # values can be specified in a CSV file
            df = pd.read_csv(kwargs['values'])
            self.values = df[df.columns[-1]].values

            if len(df.columns) > 1 and 'times' not in kwargs:
                try:
                    times_column = [col for col in df.columns if col.lower() == 'times'][0]
                    self.times = df[times_column].values
                except IndexError:
                    pass

        # Make an interpolator if there are multiple times and values
        if hasattr(self, 'values') and hasattr(self, 'times'):
            if len(kwargs['times']) != len(kwargs['values']):
                raise ValueError('Routine times keyword argument must match length of values keyword argument!')

            if isinstance(kwargs['values'][0], numbers.Number):
                self.interpolator = interp1d(kwargs['times'], kwargs['values'])
            else:
                def interpolator(_time):
                    return kwargs['values'][np.argwhere(np.array(kwargs['times'])<_time).flatten()[-1]]

                self.interpolator = interpolator

        # Register the start and end of the routine
        if not 'start' in kwargs:
            if 'times' in kwargs:
                self.start = kwargs['times'][0]
            else:
                self.start = -np.inf

        if not 'end' in kwargs:
            if 'times' in kwargs:
                self.end = kwargs['times'][-1]
            else:
                self.end = np.inf

        if 'feedback' in kwargs:
            self.controller = kwargs.get('controller', PIDController())


    def __call__(self, state):
        """
        When called, a routine returns a knob setting which depends on the state of the experiment using the routine.
        This method should be overwritten by child classes

        :param state: (pandas.Series) state of the experiment
        :return: (float/str) value of new setting to be applied
        """

        pass


class Hold(Routine):
    """
    Holds a fixed value; most useful for maintaining fixed variables with feedback
    """

    def __call__(self, state):

        if state['time'] < self.start or state['time'] > self.end:
            return None

        if hasattr(self, 'feedback'):
            self.controller.setpoint = self.value
            feedback_value = state[self.feedback]
            new_setting = self.controller(feedback_value)
            return new_setting
        else:
            return self.value


class Timecourse(Routine):
    """
    Ramps linearly through a series of values at given times
    """

    def __call__(self, state):

        try:
            new_value = float(self.interpolator(state['time']))
        except ValueError:  # happens when outside the routine times
            return None

        if hasattr(self, 'feedback'):
            self.controller.setpoint = new_value
            feedback_value = state[self.indicator]
            new_setting = self.controller(feedback_value)
            return new_setting
        else:
            return new_value


class Sequence(Routine):
    """
    Passes through a series of values regardless of time
    """

    iteration = 0

    def __call__(self, state):

        if state['time'] < self.start or state['time'] > self.end:
            return None

        next_value = self.values[self.iteration]

        self.iteration = (self.iteration + 1) % len(self.values)

        return next_value


class Set(Routine):
    """
    Sets a knob based on the value of another variable
    """

    def __call__(self, state):

        if not hasattr(self,'input'):
            raise AttributeError('Set routine must be given an input variable!')

        return state[self.input]
