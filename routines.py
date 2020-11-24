import time
import numpy as np
from importlib import import_module

## Routines ##

class Hold:
    """
    Holds a single value indefinitely
    """

    def __init__(self, *args, **kwargs):

        self.times = args[0]

        if isinstance(self.times, float):
            # if only a single time is provided, assume it to be the start time
            self.times = [self.times, float('inf')]

        self.value = args[1]
        self.feedback = kwargs.get('feedback', None)  # name of variable to be used as feedback input

        if self.feedback:
            if not 'controller' not in kwargs:
                raise TypeError('Feedback requires a controller!')

            self.controller = kwargs['controller']

    def __call__(self, state):

        if state['time'] < self.times[0] or state['time'] > self.times[1]:
            return None

        if self.feedback:
            feedback_value = state[self.feedback]
            new_setting = self.controller(feedback_value)
            return new_setting
        else:
            return self.value


class Timecourse:
    """
    Ramps linearly through a series of values at given times
    """

    def __init__(self, *args, **kwargs):

        self.times = args[0]
        self.values = args[1]
        self.feedback = kwargs.get('feedback', None)

        self.interpolator = interp1d(times, values)

        if self.feedback:
            if not 'controller' not in kwargs:
                raise TypeError('Feedback requires a controller!')

            self.controller = kwargs['controller']

    def __call__(self, state):

        try:
            new_value = float(self.interpolator(state['time']))
        except ValueError:
            return None

        if self.feedback:
            self.controller.setpoint = new_value
            feedback_value = state[self.indicator]
            new_setting = self.controller(feedback_value)
            return new_setting
        else:
            return new_value


class Sequence:
    """
    Passes through a series of values regardless of time
    """

    def __init__(self, *args, **kwargs):

        self.values = values
        self.values_iter = iter(values)

    def __call__(self):

        try:
            next_value = next(self.values_iter)
        except StopIteration:
            return None

        return next_value
        

## Controller classes for feedback

class Controller:

    @property
    def setpoint(self):
        return self.controller.setpoint

    @setpoint.setter
    def setpoint(self, value):
        self.controller.setpoint = value

    def __call__(self, input):

        output = self.controller(input)

        if hasattr(self, history):
            _time = time.time() - self.start_time
            self.history = np.concatenate([self.history, np.array([_time, input, output])])

        return output


class PIDController(Controller):
    """
    Basic PID controller
    """

    def __init__(self, setpoint=0, sample_time=0.01, Kp=1, Ki=0, Kd=0):

        simple_pid = import_module('simple_pid')
        self.controller = simple_pid.PID(Kp, Ki, Kd, setpoint=setpoint, sample_time=sample_time)

    def start(self):
        self.controller.set_auto_mode(True)

    def stop(self):
        self.controller.set_auto_mode(False)

    @property
    def sample_time(self):
        return self.controller.sample_time

    @sample_time.setter
    def sample_time(self, value):
        self.controller.sample_time = value

    @property
    def Kp(self):
        return self.controller.Kp

    @Kp.setter
    def Kp(self, value):
        self.controller.Kp = value

    @property
    def Ki(self):
        return self.controller.Ki

    @Kp.setter
    def Ki(self, value):
        self.controller.Ki = value

    @property
    def Kd(self):
        return self.controller.Kd

    @Kd.setter
    def Kd(self, value):
        self.controller.Kd = value


class LinearPredictiveController(Controller):
    """
    Uses a linear predictive method to determine optimal settings based on past responses
    """

    def __init__(self, setpoint, lookback=60):
        pass
