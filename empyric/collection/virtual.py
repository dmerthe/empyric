import time
import numpy as np
from empyric.instruments import Instrument
from empyric.instruments import setter, measurer
from empyric.adapters import Adapter


class Clock(Instrument):
    """
    Virtual clock for time keeping; works like a standard stopwatch
    """

    name = "Clock"

    supported_adapters = (
        (Adapter, {}),
    )

    knobs = ('state', )
    meters = ('time', )

    @property
    def time(self):
        if self.stop_time:
            elapsed_time = self.stop_time - self.start_time - self.stoppage
        else:
            elapsed_time = time.time() - self.start_time - self.stoppage

        return elapsed_time

    def __init__(self, *args, **kwargs):

        Instrument.__init__(self, *args, **kwargs)

        self.start_time = self.stop_time = time.time()  # clock is initially stopped
        self.stoppage = 0  # total time during which the clock has been stopped

    @setter
    def set_state(self, state):

        if state == 'START':

            if self.stop_time:
                self.stoppage += time.time() - self.stop_time
                self.stop_time = False

        elif state == 'STOP':

            if not self.stop_time:
                self.stop_time = time.time()

        elif state == 'RESET':

            self.__init__()

    @measurer
    def measure_time(self):
        return self.time


class HenonMapper(Instrument):
    """
    Virtual instrument based on the behavior of a 2D Henon Map:

    x_{n+1} = 1 - a x_n^2 + y_n

    y_{n+1} = b x_n

    It has two virtual knobs (a,b) and two virtual meters (x,y)
    """

    name = 'HenonMapper'

    supported_adapters = (
        (Adapter, {}),
    )

    knobs = ('a', 'b')
    presets = {'a': 1.4, 'b': 0.3}

    meters = ('x', 'y')

    a = 1.4
    b = 0.3

    x, y = 0.63, 0.19  # near the unstable fixed point

    @setter
    def set_a(self, value):
        """
        Set the parameter a

        :param value: (float) new value for a
        :return: None
        """
        pass

    @setter
    def set_b(self, value):
        """
        Set the parameter b

        :param value: (float) new value for b
        :return: None
        """
        pass

    @measurer
    def measure_x(self):
        """
        Measure the coordinate x.
        Each call triggers a new iteration, with new values set for x and y based on the Henon Map

        :return: (float) current value of x
        """

        x_new = 1 - self.a * self.x ** 2 + self.y
        y_new = self.b * self.x

        self.x = x_new
        self.y = y_new

        return self.x

    @measurer
    def measure_y(self):
        """
        Measure the coordinate y

        :return: (float) current value of y
        """

        time.sleep(0.25)  # make sure x is evaluated first

        return self.y


class PIDController(Instrument):
    """
    Virtual PID controller

    """

    name = 'PIDController'

    supported_adapters = (
        (Adapter, {}),
    )

    knobs = (
        'setpoint',
        'proportional gain'
        'derivative time'
        'integral time',
        'input'
    )

    presets = {
        'proportional gain': 1,
        'derivative time': 12,
        'integral time': 180
    }

    meters = ('output',)

    def __init__(self, *args, **kwargs):

        self.setpoint = None

        Instrument.__init_(self, *args, **kwargs)
        self.clock = Clock()

        self.times = np.array([])
        self.setpoints = np.array([])
        self.inputs = np.array([])
        self.outputs = np.array([])

    @setter
    def set_setpoint(self, setpoint):
        """Set the process setpoint"""
        pass

    @setter
    def set_proportional_gain(self, gain):
        """Set the proportional gain"""
        pass

    @setter
    def set_derivative_time(self, _time):
        """Set the derivative time"""
        pass

    @setter
    def set_integral_time(self, _time):
        """Set the integral time"""
        pass

    @setter
    def set_input(self, input):
        """Input the process value"""

        if len(self.times) == 0:
            self.clock.start()

        if len(self.outputs) == len(self.inputs):
            self.times = np.concatenate([self.times, [self.clock.time]])
            self.setpoints = np.concatenate([self.setpoints, [self.setpoint]])
            self.inputs = np.concatenate([self.inputs, [input]])

    @measurer
    def measure_output(self):
        """Get the controller output"""
        if self.setpoint is None:  # Don't output anything unless the setpoint is defined
            return None

        if len(self.outputs) < len(self.inputs):  # if input has been updated

            # Proportional term
            error = self.setpoint - self.input

            # Integral and derivative terms
            if len(self.times) > 1:

                interval = np.argwhere(self.times >= self.times[-1] - self.integral_time).flatten()

                dt = np.diff(self.times[interval])
                errors = (self.setpoints - self.inputs)[interval[1:]]

                integral = np.sum(dt*errors)

                derivative = -(self.inputs[-1] - self.inputs[-2]) / (self.times[-1] - self.times[-2])
            else:
                integral = 0
                derivative = 0

            tD = self.derivative_time
            tI = self.integral_time

            output = self.proportional_gain*(error + tD*derivative + integral/tI)

            self.outputs.append(output)

            return output
        else:
            return self.outputs[-1]


class RandomWalk(Instrument):
    """
    Virtual random walk process for testing controllers

    Dynamics of the process value is determined by the mean, step and affinity knobs. The mean is the mean
    value of the process in steady state, the step is the size of the step that the process can take in either direction upon each
    measurement of the process value, and the affinity is the tendancy of the process value to return to its mean value
    at each step.
    """

    name = 'RandomWalk'

    supported_adapters = (
        (Adapter, {}),
    )

    knobs = ('mean',
             'step',
             'affinity')

    meters = ('value',)

    def __init__(self, *args, **kwargs):

        Instrument.__init__(self,*args, **kwargs)

        self.mean = 0
        self.step = 1
        self.affinity = 0.01
        self.value = self.mean

    @setter
    def set_mean(self, mean):
        pass

    @setter
    def set_step(self, step):
        pass

    @setter
    def set_drift(self, drift):
        pass

    @measurer
    def measure_value(self):
        self.value += np.random.choice([-self.step, self.step]) + self.affinity*(self.mean - self.value)
        return self.value


class SimpleProcess(Instrument):
    """
    Virtual process that mimics the behavior of a heating process
    """

    name = 'SimpleProcess'

    supported_adapters = (
        (Adapter, {}),
    )

    knobs = ('setpoint',
             'noise level',
             'response time')

    meters = ('value',)


    def __init__(self, *args, **kwargs):

        Instrument.__init__(self, *args, **kwargs)

        self.time = 0
        self.value = 0
        self.setpoint = 0
        self.noise_level = 0.1
        self.response_time = 10

        self.clock = Clock()
        self.clock.set_state('START')
        self.time = self.clock.measure_time()

    @setter
    def set_setpoint(self, setpoint):
        self.measure_value()  # update process time and value

    @setter
    def set_noise_level(self, noise_level):
        pass

    @setter
    def set_response_time(self, response_time):
        pass

    @measurer
    def measure_value(self):

        t0 = self.time
        last_value = self.value

        t = self.clock.measure_time()
        new_value = self.setpoint + (last_value - self.setpoint)*np.exp(-(t-t0) / self.response_time)

        self.time = t
        self.value = new_value

        return new_value
