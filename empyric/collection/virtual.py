import time
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

    It has two virtual knobs (a,b) and two virtual meters (x,y), useful for testing in the absence of actual instruments
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

        return self.y
