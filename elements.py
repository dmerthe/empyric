

class Instrument:
    """
    Basic representation of an instrument
    """

    name = 'Instrument'

    knobs = tuple()
    meters = tuple()

    knob_values = dict()

    def __init__(self, adapter, **kwargs):

        # Connect to instrument
        self.adapter = adapter

        # Apply presets
        self.presets = kwargs.get('presets', [])

        for knob, value in self.presets:
            self.set(knob, value)

        # Get postsets
        self.postsets = kwargs.get('postsets', [])

    def write(self, message):
        return self.adapter.write(message)

    def read(self):
        return self.adapter.read()

    def query(self, question):
        return self.adapter.query(question)

    def set(self, knob, value):
        """
        Set the value of a variable associated with this instrument

        :param knob: (string) name of variable to be set
        :param value: (float/string) value of new variable setting
        :return: None
        """

        try:
            set_method = self.__getattribute__('set_ ' +knob.replace(' ' ,'_'))
        except AttributeError:
            raise SetError(f"'{knob}' cannot be set on {self.name}")

        if value is None:  # A None value passed into this function indicates that no change in setting is to be made
            return

        set_method(value)

    def measure(self, meter):
        """
        Measure the value of a variable associated with this instrument

        :param meter: (string) name of the variable to be measured
        :return: (float/string) measured value of the variable
        """

        try:
            measurement_method = self.__getattribute__('measure_ ' +meter.replace(' ' ,'_'))
        except AttributeError:
            raise MeasurementError(f"'{meter}' cannot be measured on {self.name}")

        measurement = measurement_method()

        return measurement

    def __del__(self):

        for knob, value in self.postsets.items():
            self.set(knob, value)

        self.adapter.disconnect()


class Knob:
    """
    Representation of an experiment variable that can be set directly
    """

    def __init__(self, instrument, label):

        self.instrument = instrument
        self.label = label
        self._value = None

    @property
    def value(self):
        self._value = self.instrument.knob_values[self.label]
        return self._value

    @value.setter
    def value(self, value):
        self.instrument.set(knob, value)
        self._value = self.instrument.knob_values[self.label]


class Meter:
    """
    Representation of an experiment variable that can be measured directly
    """

    def __init__(self, instrument, label):

        self.instrument = instrument
        self.label = label
        self._value = None

    @property
    def value(self):
        self._value = self.instrument.measure(self.label)
        return self._value


class Dependent:
    """
    Representation of a experimental variable that depends on other experiment variables
    """

    def __init__(self, expression, parents):
        """

        :param expression: (str) mathematical expression of the variable in terms of the parent variables
        :param parents: (dict) dictionary of the form {..., variable symbol, knob/meter/dependent object, ....}
        """

        self.expression = expression
        self.parents = parents
        self._value = None

    @property
    def value(self):

        expression = self.expression

        for symbol, parent in parents.items():
            expression = expression.replace(symbol, str(parent._value))

        self._value = eval(expression)

        return self._value
