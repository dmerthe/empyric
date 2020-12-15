import numpy as np

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

    def __init__(self, setpoint=0, sample_time=0.01, Kp=0, Ki=0, Kd=0):

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
