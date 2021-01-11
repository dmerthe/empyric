import numpy as np
from empyric.adapters import *


def setter(method):
    """
    Utility function which wraps all set_[knob] methods and records the new knob values

    :param method: (callable) method to be wrapped
    :return: wrapped method
    """

    knob = method.__name__.split('_')[1:]

    def wrapped_method(self, *args, **kwargs):
        method(self, *args, **kwargs)
        self.__setattr__(knob, args[-1])

    return wrapped_method


def getter(method):
    """
    Utility function which wraps all get_[knob] methods and records the retrieved knob values

    :param method: (callable) method to be wrapped
    :return: wrapped method
    """

    knob = method.__name__.split('_')[1:]

    def wrapped_method(self, *args, **kwargs):

        value = method(self, *args, **kwargs)
        self.__setattr__(knob, value)

        return value

    return wrapped_method


class Instrument:
    """
    Basic representation of an instrument, essentially a set of knobs and meters
    """

    name = 'Instrument'

    supported_adapters = (
        (Adapter, {}),
    )

    knobs = tuple()
    presets = {}
    postsets = {}

    meters = tuple()

    presets = {}  # values knobs should be when instrument is connected
    postsets = {}  # values knobs should be when instrument is disconnected

    def __init__(self, address, adapter=None, presets=None, postsets=None, **kwargs):
        """

        :param address: (str/int) the default adapter of the instrument can be set up with default settings based on an address
        :param adapter: (Adapter) desired adapter to use for communications with the instrument
        :param presets: (dict) dictionary of instrument presets of the form {..., knob: value, ...} to apply upon initialization
        :param presets: (dict) dictionary of instrument postsets of the form {..., knob: value, ...} to apply upon disconnection
        :param kwargs: (dict) any settings for the selected adapter
        """

        self.address = address

        adapter_connected = False

        if adapter:
            self.adapter = adapter(self, **kwargs)
        else:
            errors = []
            for _adapter, settings in self.supported_adapters:
                settings.update(kwargs)
                try:
                    self.adapter = _adapter(self, **settings)
                    adapter_connected = True
                except BaseException as error:
                    errors.append('in trying '+_adapter.__name__+' adapter, got '+type(error).__name__ +': '+ str(error))

            if not adapter_connected:
                message = f'unable to connect an adapter to instrument {self.name} at address {address}:\n'
                for error in errors:
                    message = message + f"{error}\n"
                raise ConnectionError(message)

        self.name = self.name + '@' + str(self.address)

        # Wrap setting and getting functions
        for name, method in self.__dict__.items():
            if 'set_' in name:
                self.__setattr__(name, setter(method))
            if 'get_' in name:
                self.__setattr__(name, getter(method))

        # Get existing knob settings, if possible
        for knob in self.knobs:
            if hasattr(self, 'get_'+knob.replace(' ','_')):
                self.__getattribute__('get_'+knob.replace(' ','_'))()  # retrieves the knob value from the instrument and stores as instrument attribute
            else:
                self.__setattr__(knob.replace(' ','_'), None)  # knob value is unknown until it is set

        # Apply presets
        if presets:
            self.presets.update(presets)

        for knob, value in self.presets.items():
            self.set(knob, value)

        # Get postsets
        if postsets:
            self.postsets.update(postsets)

    def __repr__(self):
        return self.name

    # map write, read and query methods to the adapter's
    def write(self, *args, **kwargs):
        return self.adapter.write(*args, **kwargs)

    def read(self, *args, **kwargs):
        return self.adapter.read(*args, **kwargs)

    def query(self, *args, **kwargs):
        return self.adapter.query(*args, **kwargs)

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

    def get(self, knob):

        if hasattr(self,'get_'+knob.replace(' ','_')):
            return self.__getattribute__('get_'+knob.replace(' ','_'))()
        else:
            return self.__getattribute__(knob.replace(' ','_'))

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


class HenonMapper(Instrument):
    """
    Simulation of an instrument based on the behavior of a 2D Henon Map
    It has two knobs and two meters, useful for testing in the absence of actual instruments.
    """

    name = 'HenonMapper'

    supported_adapters = (
        (Adapter, {}),
    )

    knobs = ('a','b')
    presets = {'a': 1.4, 'b': 0.3}

    meters = ('x', 'y')

    a = 1.4
    b = 0.3

    x, y = 2*np.random.rand() - 1, 0.5*np.random.rand() - 0.25

    measured = {'x': False, 'y': False}

    def set_a(self, value):
        self.a = value  # actually, redundant because method wrapper by setter above

    def set_b(self, value):
        self.b = value  # actually, redundant because method wrapper by setter above

    def measure_x(self):

        x_new = 1 - self.a * self.x ** 2 + self.y
        y_new = self.b * self.x

        self.x = x_new
        self.y = y_new

        return self.x

    def measure_y(self):

        return self.y
