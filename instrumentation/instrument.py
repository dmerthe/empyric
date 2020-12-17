import numpy as np
from mercury.adapters import *

class Instrument:
    """
    Basic representation of an instrument, essentially a set of knobs and meters
    """

    name = 'Instrument'

    supported_adapters = [Adapter]
    adapter_settings = {}

    knobs = tuple()
    presets = {}
    postsets = {}

    meters = tuple()

    presets = {}  # values knobs should be when instrument is connected
    postsets = {}  # values knobs should be when instrument is disconnected

    def __init__(self, adapter=None, address=None, presets=None, postsets=None):
        """

        :param adapter: (Adapter) handles communcations with the instrument via the appropriate backend
        :param address: (str/int) the default adapter of the instrument can be set up with default settings based on an address
        :param presets: (dict) dictionary of instrument presets of the form {..., knob: value, ...} to apply upon initialization
        :param presets: (dict) dictionary of instrument postsets of the form {..., knob: value, ...} to apply upon disconnection
        """

        if adapter:
            self.adapter = adapter
        elif address:
            adapter_connected = False
            errors = []
            for _adapter in self.supported_adapters:
                try:
                    self.adapter = _adapter(address, **self.adapter_settings)
                    adapter_connected = True
                except BaseException as error:
                    errors.append(type(error).__name__ +': '+ str(error))

            if not adapter_connected:
                message = f'unable to connect an adapter to instrument {self.name} at address {address}:\n'
                for error in errors:
                    message.append(f"{error}\n")
                raise ConnectionError(message)

        else:
            ConnectionError('instrument definition requires either an adapter or an address!')

        self.name = self.name + '-' + str(self.adapter.address)

        self.knob_values = {knob: None for knob in self.knobs}

        # Apply presets
        if presets:
            self.presets.update(presets)

        for knob, value in self.presets.items():
            self.set(knob, value)

        # Get postsets
        if postsets:
            self.postsets.update(postsets)

    def __repr__(self):
        return self.name + '-' + str(self.adapter.address)

    def write(self, message):
        return self.adapter.write(message)

    def read(self):
        return self.adapter.read()

    def query(self, question):
        return self.adapter.query(question)

    def set(self, knob, value):
        """
        Set the value of a variable associated with the instrument

        :param knob: (string) name of variable to be set
        :param value: (float/string) value of new variable setting
        :return: None
        """

        try:
            set_method = self.__getattribute__('set_' + knob.replace(' ' ,'_'))
        except AttributeError:
            raise AttributeError(f"{knob} cannot be set on {self.name}")

        set_method(value)

    def measure(self, meter):
        """
        Measure the value of a variable associated with this instrument

        :param meter: (string) name of the variable to be measured
        :return: (float/string) measured value of the variable
        """

        try:
            measure_method = self.__getattribute__('measure_' + meter.replace(' ' ,'_'))
        except AttributeError:
            raise AttributeError(f"{meter} cannot be measured on {self.name}")

        measurement = measure_method()

        return measurement

    def disconnect(self):

        if self.adapter.connected:
            for knob, value in self.postsets.items():
                self.set(knob, value)

            self.adapter.disconnect()
        else:
            raise ConnectionError(f"adapter for {self.name} is not connected!")

    def __del__(self):
        self.disconnect()


class Henon(Instrument):
    """
    Simulation of an instrument based on the behavior of a 2D Henon Machine
    It has two knobs and two meters, useful for testing in the absence of real instruments.
    """

    name = 'Henon'

    knobs = ('a','b')
    presets = {'a': 1.4, 'b': 0.3}

    meters = ('x', 'y', 'pseudostep')

    def set_a(self, value):
        if self.knob_values['a'] == value:
            return

        a = value
        self.knob_values['a'] = a
        b  = self.knob_values['b']
        if b is None:
            b = 0.3

        x, y = 2*np.random.rand() - 1, 0.5*np.random.rand() - 0.25
        self.step = 0

        self.x_values = [x]
        self.y_values = [y]
        N = int(1e3)
        for i in range(N):
            x_new = 1 - a * x ** 2 + y
            y_new = b * x
            x = x_new
            y = y_new
            self.x_values.append(x)
            self.y_values.append(y)

    def set_b(self, value):
        if self.knob_values['b'] == value:
            return

        a = self.knob_values['a']
        if a is None:
            a = 1.4
        b = value
        self.knob_values['b'] = b

        x, y = 2 * np.random.rand() - 1, 0.5 * np.random.rand() - 0.25
        self.step = 0

        self.x_values = [x]
        self.y_values = [y]
        N = int(1e3)
        for i in range(N):
            x_new = 1 - a * x ** 2 + y
            y_new = b * x
            x = x_new
            y = y_new
            self.x_values.append(x)
            self.y_values.append(y)

    def measure_x(self):

        x = self.x_values[int(0.5*self.step)]

        self.step += 1

        return x

    def measure_y(self):

        y = self.y_values[int(0.5*self.step)]

        self.step += 1

        return y

    def measure_pseudostep(self):

        return int(0.5*self.step) % 10
