from functools import wraps
from empyric.adapters import *


def setter(method):
    """
    Utility function which wraps all set_[knob] methods and records the new knob values

    :param method: (callable) method to be wrapped
    :return: wrapped method
    """

    knob = '_'.join(method.__name__.split('_')[1:])

    @wraps(method)
    def wrapped_method(*args, **kwargs):
        method(*args, **kwargs)
        self = args[0]
        value = args[1]
        self.__setattr__(knob, value)

    return wrapped_method


def getter(method):
    """
    Utility function which wraps all get_[knob] methods and records the retrieved knob values

    :param method: (callable) method to be wrapped
    :return: wrapped method
    """

    knob = '_'.join(method.__name__.split('_')[1:])

    @wraps(method)
    def wrapped_method(*args, **kwargs):
        self = args[0]
        value = method(*args, **kwargs)
        self.__setattr__(knob, value)

        return value

    return wrapped_method


def measurer(method):
    """
    Utility function that wraps all measure_[meter] methods; right now does nothing

    :param method: (callable) method to be wrapped
    :return: wrapped method
    """

    meter = '_'.join(method.__name__.split('_')[1:])

    @wraps(method)
    def wrapped_method(*args, **kwargs):
        self = args[0]
        value = method(*args, **kwargs)
        self.__setattr__('measured_'+meter, value)

        return value

    return wrapped_method


class Instrument:
    """
    Basic representation of an instrument, essentially a set of knobs and meters
    """

    #: Once connected via an adapter, the name of the instrument is converted to ``self.name + '@' + self.address``
    name = 'Instrument'

    #: Each instrument has a set of supported adapters, e.g. serial, GPIB or USB
    supported_adapters = (
        (Adapter, {}),
    )

    #: Each instrument has a set of knobs
    knobs = tuple()

    #: The presets attribute indicate how the instrument should be configured upon connection
    presets = {}

    #: The postsets attribute indicate how the instrument should be configured upon disconnection
    postsets = {}  # values knobs should be when instrument is disconnected

    #: Each instrument has a set of meters
    meters = tuple()

    def __init__(self, address=None, adapter=None, presets=None, postsets=None, **kwargs):
        """

        :param address: (str/int) address of instrument
        :param adapter: (Adapter) desired adapter to use for communications with the instrument
        :param presets: (dict) dictionary of instrument presets of the form {..., knob: value, ...}
        :param presets: (dict) dictionary of instrument postsets of the form {..., knob: value, ...}
        :param kwargs: (dict) any keyword args for the adapter
        """

        if address:
            self.address = address
        else:
            self.address = None

        adapter_connected = False
        if adapter:
            self.adapter = adapter
        else:
            errors = []
            for _adapter, settings in self.supported_adapters:
                settings.update(kwargs)
                try:
                    self.adapter = _adapter(self, **settings)
                    adapter_connected = True
                    break
                except BaseException as error:
                    errors.append('in trying ' + _adapter.__name__ + ' adapter, got '
                                  + type(error).__name__ + ': ' + str(error))

            if not adapter_connected:
                message = f'unable to connect an adapter to instrument {self.name} at address {address}:\n'
                for error in errors:
                    message = message + f"{error}\n"
                raise ConnectionError(message)

        if self.address:
            self.name = self.name + '@' + str(self.address)

        # Get existing knob settings, if possible
        for knob in self.knobs:
            if hasattr(self, 'get_'+knob.replace(' ', '_')):
                self.__getattribute__('get_'+knob.replace(' ', '_'))()  # retrieves the knob value from the instrument
            else:
                self.__setattr__(knob.replace(' ', '_'), None)  # knob value is unknown until it is set

        # Apply presets
        if presets:
            self.presets = {**self.presets, **presets}

        for knob, value in self.presets.items():
            self.set(knob, value)

        # Get postsets
        if postsets:
            self.postsets = {**self.postsets, **postsets}

    def __repr__(self):
        return self.name

    # map write, read and query methods to the adapter's
    def write(self, *args, **kwargs):
        """
        Alias for the adapter's write method

        :param args: any arguments for the adapter's write method, usually including a command string
        :param kwargs: any arguments for the adapter's write method
        :return: whatever is returned by the adapter's write method, usually None
        """
        return self.adapter.write(*args, **kwargs)

    def read(self, *args, **kwargs):
        """
        Alias for the adapter's read method

        :param args: any arguments for the adapter's read method, usually empty
        :param kwargs: any arguments for the adapter's write method
        :return: whatever is returned by the adapter's write method, usually a response string
        """

        return self.adapter.read(*args, **kwargs)

    def query(self, *args, **kwargs):
        """
        Alias for the adapter's query method, if it has one

        :param args: any arguments for the adapter's read method, usually including a query string
        :param kwargs: any arguments for the adapter's write method
        :return: whatever is returned by the adapter's write method, usually a response string
        """

        return self.adapter.query(*args, **kwargs)

    def set(self, knob, value):
        """
        Set the value of a variable associated with the instrument

        :param knob: (string) name of variable to be set
        :param value: (float/string) value of new variable setting
        :return: None
        """

        try:
            set_method = getattr(self, 'set_' + knob.replace(' ', '_'))
        except AttributeError as err:
            raise AttributeError(f"{knob} cannot be set on {self.name}\n{err}")

        set_method(value)

    def get(self, knob):

        if hasattr(self, 'get_'+knob.replace(' ', '_')):
            return getattr(self, 'get_'+knob.replace(' ', '_'))()
        else:
            return getattr(self, knob.replace(' ', '_'))

    def measure(self, meter):
        """
        Measure the value of a variable associated with this instrument

        :param meter: (string) name of the variable to be measured
        :return: (float/string) measured value of the variable
        """

        try:
            measure_method = self.__getattribute__('measure_' + meter.replace(' ', '_'))
        except AttributeError:
            raise AttributeError(f"{meter} cannot be measured on {self.name}")

        measurement = measure_method()

        return measurement

    def disconnect(self):
        """
        Apply any postsets to the instrument and disconnect the adapter

        :return: None
        """

        if self.adapter.connected:
            for knob, value in self.postsets.items():
                self.set(knob, value)

            self.adapter.disconnect()
        else:
            raise ConnectionError(f"adapter for {self.name} is not connected!")
