import copy


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
    Representation of a experimental variable that is evaluated based on other experiment variables
    """

    def __init__(self, expression, parents):

        self.expression = expression
        self.parents = parents
        self._value = None

    @property
    def value(self):

        expression = copy.copy(self.expression)

        for symbol, parent in parents.items():
            expression.replace(symbol, str(parent._value))

        self._value = eval(expression)

        return self._value
