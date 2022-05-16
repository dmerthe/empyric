import numpy as np
from numbers import Number
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
        returned_value = method(*args, **kwargs)
        self = args[0]
        value = args[1]

        # The knob attribute is set to the returned value of the method, or the value argument if returned value is None
        if returned_value is not None:
            self.__setattr__(knob, returned_value)
        else:
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

    Each instrument has the following attributes:

    * ``name``: the name of the instrument. Once connected via  an adapter, this is converted to
      ``name + '@' + address``.
    * ``supported adapters``: tuple of 2-element tuples. Each 2-element tuple contains an adapter class that the
      instrument can be used with and a dictionary of adapter settings.
    * ``knobs``: tuple of the names of all knobs that can be set on the instrument.
    * ``presets``: dictionary of knob settings to apply when the instrument is instantiated.
      The keys are the names of the knobs and the values are the knob values.
    * ``postsets``: dictionary of knob settings (same format as ``presets``) to apply when the instrument is deleted.
    * ``meters``: tuple of the names of all meters that can be measured on this instrument.

    """

    name = 'Instrument'

    supported_adapters = (
        (Adapter, {}),
    )

    knobs = tuple()

    presets = {}

    postsets = {}

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

        :param args: any arguments for the adapter's query method, usually including a query string
        :param kwargs: any arguments for the adapter's query method
        :return: whatever is returned by the adapter's query method, usually a response string
        """

        return self.adapter.query(*args, **kwargs)

    def set(self, knob, value):
        """
        Set the value of a knob on the instrument

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
        """
        Get the value of a knob on the instrument. If the instrument has a get method for the knob, a command will be
        sent to the instrument to retrieve the actual value of the knob. If it does not have a get method for the knob,
        the last known value, stored as an instance attribute, will be return (possibly being ``nan`` if no value has
        yet been set)

        """

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
