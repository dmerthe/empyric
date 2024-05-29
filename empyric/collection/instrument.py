import typing
from threading import RLock
from functools import wraps
from empyric.adapters import *
from empyric.types import recast, Type, ON, OFF, Toggle


def setter(method):
    """
    Utility function that wraps all set_[knob] methods and records the new
    knob values.

    If the wrapped method returns a value, this value is assigned to the
    corresponding knob attribute of the instrument. This is convenient for
    cases where the set value maps to another value which is more relevant.
    Otherwise, the value of the method's first argument is assigned to the
    attribute.

    :param method: (callable) method to be wrapped

    :return: wrapped method
    """

    knob = "_".join(method.__name__.split("_")[1:])

    type_hints = typing.get_type_hints(method)
    type_hints.pop("self", None)
    type_hints.pop("return", None)

    if type_hints:
        dtype = type_hints[list(type_hints)[0]]
    else:
        dtype = Type

    @wraps(method)
    def wrapped_method(*args, **kwargs):

        self = args[0]
        value = args[1]

        if not self.adapter.connected and knob != "connected":
            print(f"Instrument {self.name} is disconnected; unable to set {knob}")
            self.__setattr__(knob, None)
            return

        self.lock.acquire()

        try:

            args = list(args)
            args[1] = recast(args[1], to=dtype)

            returned_value = method(*args, **kwargs)

            # The knob attribute is set to the returned value of the method, or
            # the value argument if the returned value is None
            if returned_value is not None:
                self.__setattr__(knob, recast(returned_value, to=dtype))
            else:
                self.__setattr__(knob, recast(value, to=dtype))
        finally:
            self.lock.release()

    return wrapped_method


def getter(method):
    """
    Utility function that wraps all get_[knob] methods and records the
    retrieved knob values.

    :param method: (callable) method to be wrapped

    :return: wrapped method
    """

    knob = "_".join(method.__name__.split("_")[1:])

    dtype = typing.get_type_hints(method).get("return", Type)

    @wraps(method)
    def wrapped_method(*args, **kwargs):
        self = args[0]

        if not self.adapter.connected and knob != "connected":
            self.__setattr__(knob, None)
            print(f"Instrument {self.name} is disconnected; unable to get {knob}")
            return

        self.lock.acquire()

        try:
            value = recast(method(*args, **kwargs), to=dtype)
        except AttributeError as err:
            # catches most errors caused by the adapter returning None
            if "NoneType" in str(err):
                value = None
            else:
                raise AttributeError(err)
        finally:
            self.lock.release()

        self.__setattr__(knob, value)

        return value

    return wrapped_method


def measurer(method):
    """
    Utility function that wraps all measure_[meter] methods and records the
    measured value.

    :param method: (callable) method to be wrapped

    :return: wrapped method
    """

    meter = "_".join(method.__name__.split("_")[1:])

    dtype = typing.get_type_hints(method).get("return", Type)

    @wraps(method)
    def wrapped_method(*args, **kwargs):
        self = args[0]

        if not self.adapter.connected:
            self.__setattr__(meter, None)
            print(f"Instrument {self.name} is disconnected; unable to measure {meter}")
            return

        self.lock.acquire()

        try:
            value = recast(method(*args, **kwargs), to=dtype)
        except AttributeError as err:
            # catches most errors caused by the adapter returning None
            if "NoneType" in str(err):
                value = None
            else:
                raise AttributeError(err)
        finally:
            self.lock.release()

        self.__setattr__(meter, value)

        return value

    return wrapped_method


class Instrument:
    """
    Basic representation of an instrument, essentially a set of knobs and meters

    Each instrument has the following attributes:

    * ``name``: the name of the instrument. Once connected via  an adapter,
      this is converted to
      ``name + '@' + address``.
    * ``supported adapters``: tuple of 2-element tuples. Each 2-element tuple
      contains an adapter class that the instrument can be used with and a
      dictionary of adapter settings.
    * ``knobs``: tuple of the names of all knobs that can be set on the
      instrument. Every instrument has a ``connected`` (``Toggle``) knob, for
      convenience, whose set method calls the instruments ``connect`` or ``disconnect``
      methods, if set to ``ON`` or ``OFF`` respectively.
    * ``presets``: dictionary of knob settings to apply when the instrument is
      instantiated.
      The keys are the names of the knobs and the values are the knob values.
    * ``postsets``: dictionary of knob settings (same format as ``presets``)
      to apply when the instrument is deleted.
    * ``meters``: tuple of the names of all meters that can be measured on
      this instrument.

    Every knob of an instrument has an associated ``set_[knob]`` method, which sends
    commands to the physical instrument that change the value of the knob to the given
    value. Each ``set_[knob]`` method should be wrapped by the ``setter`` function
    defined above.

    Every knob may also have an associated ``get_[knob]`` method, which queries the
    value of the knob from the physical instrument, and should be wrapped by the
    ``getter`` function defined above.

    Every meter of an instrument has an associated ``measure_[meter]`` method, which
    queries the value of a quantity measured by the physical instrument, and should be
    wrapped by the ``measurer`` function defined above.

    For convenience, the ``setter``, ``getter`` and ```measurer`` functions augment the
    corresponding methods primarily by enforcing typing on the method arguments and the
    returned values, and storing the last known values of knobs and meters in the
    corresponding attribute of the Instrument instance. For example, if a meter called
    ""temperature" is retrieved via the corresponding ``measure_temperature`` method of
    the instrument ``thermometer``, the wrapping ``measurer`` function will assign that
    temperature value to ``thermometer.temperature``. If the expected data type is a
    floating point number, the ``measurer`` function additionally converts whatever the
    bare ``measure_temperature`` method returns to a 64-bit floating point value.

    """

    name = "Instrument"

    supported_adapters = ((Adapter, {}),)

    knobs = tuple()

    presets = {}

    postsets = {}

    meters = tuple()

    # This lock is used to prevent commands executed in separate threads from
    # interfering with each other. The lock is acquired in the setter, getter
    # and measurer wrapper functions and then released when the wrapped
    # operation is complete. Using an RLock allows set, get and measure
    # methods to call other such methods without blocking, as long as it
    # happens in the same thread, which is the norm.
    lock = RLock()

    def __init__(
        self, address=None, adapter=None, presets=None, postsets=None, **kwargs
    ):
        """

        :param address: (str/int) address of instrument
        :param adapter: (Adapter) desired adapter to use for communications
        with the instrument
        :param presets: (dict) dictionary of instrument presets of the form
        {..., knob: value, ...}
        :param presets: (dict) dictionary of instrument postsets of the form
        {..., knob: value, ...}
        :param kwargs: (dict) any keyword args for the adapter
        """

        self.address = address

        self.knobs = ("connected",) + self.knobs

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
                    break
                except BaseException as error:
                    msg = (
                        f"in trying {_adapter.__name__} adapter, "
                        f"got {type(error).__name__}: {error}"
                    )
                    errors.append(msg)

            if not adapter_connected:
                message = (
                    f"unable to connect an adapter to "
                    f"instrument {self.name} at address {address}:\n"
                )
                for error in errors:
                    message = message + f"{error}\n"
                raise ConnectionError(message)

        if self.address:
            self.name = self.name + "@" + str(self.address)
        else:
            self.name = self.name + "@" + hex(id(self))

        # Get existing knob settings, if possible
        for knob in self.knobs:
            if hasattr(self, "get_" + knob.replace(" ", "_")):
                # retrieves the knob value from the instrument
                self.__getattribute__("get_" + knob.replace(" ", "_"))()
            else:
                # knob value is unknown until it is set
                self.__setattr__(knob.replace(" ", "_"), None)

        # Apply presets
        if presets:
            self.presets = {**self.presets, **presets}

        for knob, value in self.presets.items():
            self.set(knob, value)

        # Get postsets
        if postsets:
            self.postsets = {**self.postsets, **postsets}

        self.kwargs = kwargs

    def __repr__(self):
        return self.name

    # map write, read and query methods to the adapter's
    def write(self, *args, **kwargs):
        """
        Alias for the adapter's write method

        :param args: any arguments for the adapter's write method, usually
                     including a command string
        :param kwargs: any arguments for the adapter's write method
        :return: whatever is returned by the adapter's write method
        """
        return self.adapter.write(*args, **kwargs)

    def read(self, *args, **kwargs):
        """
        Alias for the adapter's read method

        :param args: any arguments for the adapter's read method
        :param kwargs: any arguments for the adapter's read method
        :return: whatever is returned by the adapter's read method
        """

        return self.adapter.read(*args, **kwargs)

    def query(self, *args, **kwargs):
        """
        Alias for the adapter's query method, if it has one

        :param args: any arguments for the adapter's query method
        :param kwargs: any arguments for the adapter's query method
        :return: whatever is returned by the adapter's query method
        """

        return self.adapter.query(*args, **kwargs)

    def set(self, knob: str, value):
        """
        Set the value of a knob on the instrument

        :param knob: (string) name of variable to be set
        :param value: (float/string) value of new variable setting
        :return: None
        """

        try:
            set_method = getattr(self, "set_" + knob.replace(" ", "_"))
        except AttributeError as err:
            raise AttributeError(f"{knob} cannot be set on {self.name}\n{err}")

        set_method(value)

    def get(self, knob: str):
        """
        Get the value of a knob on the instrument. If the instrument has a get
        method for the knob, a command will be sent to the instrument to
        retrieve the actual value of the knob. If it does not have a get method
        for the knob, the last known value, stored as an instance attribute,
        will be return (possibly being ``nan`` if no value has yet been set)

        """

        if hasattr(self, "get_" + knob.replace(" ", "_")):
            return getattr(self, "get_" + knob.replace(" ", "_"))()
        else:
            return getattr(self, knob.replace(" ", "_"))

    def measure(self, meter: str):
        """
        Measure the value of a variable associated with this instrument

        :param meter: (string) name of the variable to be measured
        :return: (float/string) measured value of the variable
        """

        try:
            measure_method = self.__getattribute__("measure_" + meter.replace(" ", "_"))
        except AttributeError:
            raise AttributeError(f"{meter} cannot be measured on {self.name}")

        measurement = measure_method()

        return measurement

    def connect(self):
        """
        (Re)Connect to the instrument. This is useful when communications are lost and
        a new connection is required.

        :return: None
        """

        if self.adapter.connected:
            self.adapter.disconnect()

        self.__init__(
            address=self.address,
            adapter=self.adapter if self.address is None else None,
            presets=self.presets,
            postsets=self.postsets,
            **self.kwargs,
        )

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

    @setter
    def set_connected(self, state: Toggle):
        if state == ON:
            if self.adapter.connected:
                print(f"{self.name} is already connected")
            else:
                self.connect()
        elif state == OFF:
            if self.adapter.connected:
                self.disconnect()
            else:
                print(f"{self.name} is already disconnected")

    @getter
    def get_connected(self) -> Toggle:
        if self.adapter.connected:
            return ON
        else:
            return OFF
