import time
import numpy as np
from importlib import import_module
from scipy.interpolate import interp1d

from mercury.control import PIDController

## Routines ##

class Routine:

    def __init__(self, **kwargs):
        """
        A preset program for the values that a variable takes during an experiment

        :param kwargs: any attributes that the routine should have
        """

        for key, value in kwargs.items():
            self.__setattr__(key, value)

        # Make an interpolator if there are multiple times and values
        if 'values' in kwargs and 'times' in kwargs:

            if len(kwargs['times']) != len(kwargs['values']):
                raise ValueError('Routine times keyword argument must match length of values keyword argument!')

            self.interpolator = interp1d(kwargs['times'], kwargs['values'])

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
