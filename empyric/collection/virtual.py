import time
import numpy as np

from empyric.types import Float, String
from empyric.instruments import Instrument, setter, measurer
from empyric.adapters import Adapter, Modbus


class Clock(Instrument):
    """
    Virtual clock for time keeping; works like a standard stopwatch
    """

    name = "Clock"

    supported_adapters = ((Adapter, {}),)

    knobs = ("state",)
    meters = ("time",)

    @property
    def _time(self):
        if self.stop_time:
            elapsed_time = self.stop_time - self.start_time - self.stoppage
        else:
            elapsed_time = time.time() - self.start_time - self.stoppage

        return elapsed_time

    def __init__(self, *args, **kwargs):
        Instrument.__init__(self, *args, **kwargs)

        # Initially stopped
        self.state = "STOP"
        self.start_time = self.stop_time = time.time()

        self.stoppage = 0  # total time during which the clock has been stopped

    @setter
    def set_state(self, state: String):
        """
        Set the clock state:

        * 'START': setting to this state starts the clock, if it is stopped.
        * 'STOP': setting to this state stops the clock, if it is running.
        * 'RESET': setting to this state resets the clock time to zero.
        """

        if state == "START":
            if self.stop_time:
                self.stoppage += time.time() - self.stop_time
                self.stop_time = False

            self.state = "START"

        elif state == "STOP":
            if not self.stop_time:
                self.stop_time = time.time()

            self.state = "START"

        elif state == "RESET":
            self.start_time = time.time()
            self.stoppage = 0

            if self.stop_time:
                self.stop_time = self.start_time

            return self.state  # return to START or STOP state once reset

    @measurer
    def measure_time(self) -> Float:
        """Measure the clock time"""
        return self._time


class Echo(Instrument):
    """
    Virtual instrument with a single knob "input" and single meter "output",
    useful for testing.

    The "output" meter simply returns the value of the "input" knob.
    """

    name = "Echo"

    supported_adapters = ((Adapter, {}),)

    knobs = ("input",)
    presets = {"input": 0}

    meters = ("output",)

    @setter
    def set_input(self, _input: Float):
        pass

    @measurer
    def measure_output(self) -> Float:
        return self.input


class HenonMapper(Instrument):
    """
    Virtual instrument based on the behavior of a 2D Henon Map:

    x_{n+1} = 1 - a * x_n^2 + y_n

    y_{n+1} = b * x_n

    It has two virtual knobs (a,b) and two virtual meters (x,y)
    """

    name = "HenonMapper"

    supported_adapters = ((Adapter, {}),)

    knobs = ("a", "b")
    presets = {"a": 1.4, "b": 0.3}

    meters = ("x", "y")

    _a = 1.4
    _b = 0.3

    _x, _y = 0.63, 0.19  # near the unstable fixed point

    @setter
    def set_a(self, value: Float):
        """
        Set the parameter a

        :param value: (float) new value for a
        :return: None
        """

        self._a = value

    @setter
    def set_b(self, value: Float):
        """
        Set the parameter b

        :param value: (float) new value for b
        :return: None
        """

        self._b = value

    @measurer
    def measure_x(self) -> Float:
        """
        Measure the coordinate x.
        Each call triggers a new iteration, with new values set for x and y
        based on the Henon Map. Therefore, each call to ``measure_x`` should
        be followed by a call to ``measure_y``.

        :return: (float) current value of x
        """

        x_new = 1.0 - self._a * self._x**2 + self._y
        y_new = self._b * self._x

        self._x = x_new
        self._y = y_new

        return self._x

    @measurer
    def measure_y(self) -> Float:
        """
        Measure the coordinate y.
        Each call to ``measure_y`` should be preceded by a call to
        ``measure_x``.

        :return: (float) current value of y
        """

        time.sleep(0.25)  # make sure x is evaluated first

        return self._y


class PIDController(Instrument):
    """
    Virtual PID controller

    """

    name = "PIDController"

    supported_adapters = ((Adapter, {}),)

    knobs = ("setpoint", "proportional gain", "derivative time", "integral time", "input")

    presets = {"proportional gain": 1, "derivative time": 12, "integral time": 180}

    meters = ("output",)

    def __init__(self, *args, **kwargs):
        self.setpoint = None

        Instrument.__init__(self, *args, **kwargs)
        self.clock = Clock()

        self.times = np.array([])
        self.setpoints = np.array([])
        self.inputs = np.array([])
        self.outputs = np.array([])

    @setter
    def set_setpoint(self, setpoint: Float):
        """Set the process setpoint"""
        pass

    @setter
    def set_proportional_gain(self, gain: Float):
        """Set the proportional gain"""
        pass

    @setter
    def set_derivative_time(self, _time: Float):
        """Set the derivative time"""
        pass

    @setter
    def set_integral_time(self, _time: Float):
        """Set the integral time"""
        pass

    @setter
    def set_input(self, input: Float):
        """Input the process value"""

        self.clock.set_state('START')

        if len(self.outputs) == len(self.inputs):
            self.times = np.concatenate([self.times, [self.clock.measure_time()]])
            self.setpoints = np.concatenate([self.setpoints, [self.setpoint]])
            self.inputs = np.concatenate([self.inputs, [input]])

    @measurer
    def measure_output(self) -> Float:
        """Get the controller output"""
        if self.setpoint is None:
            # Don't output anything unless the setpoint is defined
            return None

        if len(self.outputs) < len(self.inputs):  # if input has been updated
            # Proportional term
            error = self.setpoint - self.input

            # Integral and derivative terms
            if len(self.times) > 1:
                interval = np.argwhere(
                    self.times >= self.times[-1] - self.integral_time
                ).flatten()

                dt = np.diff(self.times[interval])
                errors = (self.setpoints - self.inputs)[interval[1:]]

                integral = np.sum(dt * errors)

                if len(self.times) > 1:
                    derivative = -(self.inputs[-1] - self.inputs[-2]) / (
                        self.times[-1] - self.times[-2]
                    )
                else:
                    derivative = 0.0
            else:
                integral = 0
                derivative = 0

            tD = self.derivative_time
            tI = self.integral_time

            output = self.proportional_gain * (error + tD * derivative + integral / tI)

            self.outputs = np.concatenate([self.outputs, [output]])

            return output
        elif np.any(self.outputs):
            return self.outputs[-1]
        else:
            return 0.0


class RandomWalk(Instrument):
    """
    Virtual random walk process for testing controllers

    Dynamics of the process value is determined by the mean, step and affinity
    knobs. The mean is the mean value of the process in steady state, the step
    is the size of the step that the process can take in either direction upon
    each measurement of the process value, and the affinity is the tendancy of
    the process value to return to its mean value at each step.
    """

    name = "RandomWalk"

    supported_adapters = ((Adapter, {}),)

    knobs = ("mean", "step", "affinity")

    meters = ("value",)

    _mean = 0.0
    _step = 1.0
    _affinity = 0.01
    _value = 0.0

    @setter
    def set_mean(self, mean: Float):
        self._mean = mean

    @setter
    def set_step(self, step: Float):
        self._step = step

    @setter
    def set_affinity(self, affinity: Float):
        self._affinity = affinity

    @measurer
    def measure_value(self) -> Float:
        self._value += np.random.choice([-self._step, self._step]) + self._affinity * (
            self._mean - self._value
        )

        return self._value


class SimpleProcess(Instrument):
    """
    Virtual process that mimics the behavior of a heating process
    """

    name = "SimpleProcess"

    supported_adapters = ((Adapter, {}),)

    knobs = ("setpoint", "noise level", "response time")

    presets = {"setpoint": 0.0, "noise level": 0.1, "response time": 10.0}

    meters = ("value",)

    def __init__(self, *args, **kwargs):
        Instrument.__init__(self, *args, **kwargs)

        self._clock = Clock()
        self._clock.set_state("START")
        self._time = self._clock.measure_time()

    @setter
    def set_setpoint(self, setpoint: Float):
        if hasattr(self, "_time"):
            self.measure_value()
            self._clock.set_state("RESET")
        else:
            self._value = setpoint

    @setter
    def set_noise_level(self, noise_level: Float):
        pass

    @setter
    def set_response_time(self, response_time: Float):
        pass

    @measurer
    def measure_value(self) -> Float:
        last_value = self._value
        t = self._clock.measure_time()  # time since last setpoint change
        self._value = self.setpoint + (last_value - self.setpoint) * np.exp(
            -t / self.response_time
        )

        return self._value + self.noise_level * (2 * np.random.rand() - 1)


class ModbusClient(Instrument):
    """
    Counterpart to the ModbusServer routine. Communicates with a ModbusServer
    instance in other experiments to control variables.
    """

    name = "ModbusClient"

    supported_adapters = ((Modbus, {}),)
