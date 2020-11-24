# Some basic stuff
import time
from scipy.interpolate import interp1d
import datetime
import pandas as pd

from ruamel.yaml import YAML
yaml = YAML()

class Instrument:
    """
    Basic representation of an instrument
    """

    name = 'Instrument'

    knobs = tuple()
    meters = tuple()

    knob_values = dict()

    def __init__(self, adapter, presets=None, postsets=None):
        """

        :param adapter: (Adapter) handles communcations with the instrument
        :param presets: (dict) dictionary of instrument presets of the form {..., knob: value, ...} to apply upon initialization
        :param presets: (dict) dictionary of instrument postsets of the form {..., knob: value, ...} to apply upon disconnection
        """

        # Connect to instrument with an adapter
        self.adapter = adapter

        # Get and apply presets
        if presets:
            self.presets = presets
        else:
            self.presets = {}

        for knob, value in self.presets:
            self.set(knob, value)

        # Get postsets
        if postsets:
            self.postsets = postsets
        else:
            self.postsets = {}

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
            set_method = self.__getattribute__('set_ ' +knob.replace(' ' ,'_'))
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
            measure_method = self.__getattribute__('measure_ ' +meter.replace(' ' ,'_'))
        except AttributeError:
            raise AttributeError(f"{meter} cannot be measured on {self.name}")

        measurement = measure_method()

        return measurement

    def __del__(self):
        """
        Make sure instrument communication is properly closed upon instrument deletion

        :return: None
        """

        for knob, value in self.postsets.items():
            self.set(knob, value)

        self.adapter.disconnect()


class Variable:
    """
    Basic representation of an experimental variable; comes in 3 kinds: knob, meter and dependent.
    Knobs can only be set; meters and dependents can only be measured.

    A knob is a variable corresponding to something on an instrument that can be controlled, e.g. the voltage of a power supply.

    A meter is a variable that is measured, such as temperature. Some meters can be controlled directly or indirectly through an associated knob, but a meter can not be set.

    A dependent is a variable that is not directly measured, but is calculated based on other variables of the experiment.
    An example would be power output from a power supply, where voltage is a knob and current is a meter: power = voltage * current.
    """

    def __init__(self, arg1, arg2, type=None):
        """

        :param arg1: (Instrument/str) If type is knob or meter, this is the instrument with the corresponding knob or meter.
        If type is dependent, this is the expression for the dependent variable in terms of the parents.

        :param arg2: (str/dict) If type is knob or meter, this is the name of the knob or meter on the instrument.
        If type is dependent, this is a dictionary of the form {..., symbol: variable, ...} mapping the symbols in the expression to the parent variable objects.

        :param type: (str) type of variable; can be either 'knob', 'meter' or 'dependent'.
        """

        if 'type' is None:
            raise AttributeError("variable type not defined!")

        self.type = type
        self._value = None  # This is the last known value of this variable

        if self.type == 'meter':
            self.instrument = args[0]
            self.meter = args[1]

        if self.type == 'knob':
            self.instrument = args[0]
            self.knob = args[1]

        elif self.type == 'dependent':
            self.expression = args[0]
            self.parents = args[1]

    @property
    def value(self):
        if self.type == 'knob':
            self._value = self.instrument.knob_values[self.knob]
        elif self.type == 'meter':
            self._value = self.instrument.measure(self.meter)
        elif self.type == 'dependent':
            expression = self.expression

            for symbol, parent in self.parents.items():
                expression = expression.replace(symbol, str(parent._value))

            self._value = eval(expression)

        return self._value

    @value.setter
    def value(self, value):
        # value property can only be set if variable is a knob
        if self.type == 'knob' and value is not None:
            self.instrument.set(self.knob, value)
            self._value = self.instrument.knob_values[self.label]


class Alarm:
    """
    Monitors a variable a raises an alarm if a condition is met
    """

    def __init__(self, variable, condition, protocol):

        self.variable = variable  # variable being monitored
        self.condition = condition  # condition which triggers the alarm
        self.protocol = protocol  # what to do when the alarm is triggered

    @property
    def signal(self):
        value = self.variable.value
        if eval('value' + self.condition):
            return self.protocol
        else:
            return None


class Clock:
    """
    Clock object for tracking elapsed time
    """

    def __init__(self):

        self.start_time = time.time()
        self.stop_time = time.time()  # clock is initially stopped
        self.stoppage = 0

    def start(self):
        if self.stop_time:
            self.stoppage += time.time() - self.stop_time
            self.stop_time = False

    def stop(self):
        if not self.stop_time:
            self.stop_time = time.time()

    def reset(self):
        self.__init__()

    @property
    def time(self):
        if self.stop_time:
            elapsed_time = self.stop_time - self.start_time - self.stoppage
        else:
            elapsed_time = time.time() - self.start_time - self.stoppage

        return elapsed_time


class Experiment:

    def __init__(self, variables, routines=None):

        self.variables = variables  # dict of the form {..., name: variable, ...}

        if routines:
            self.routines = routines  # dictionary of experimental routines of the form {..., variable_name: routine, ...}
        else:
            self.routines = {}

        self.clock = Clock()
        self.clock.start()

        self.data = pd.DataFrame(columns=['time'] + list(variables.keys()))

        self.state = pd.Series({column: None for column in self.data.columns})
        self.state['time'] = self.clock.time
        self.name = datetime.datetime.now()

    def __next__(self):

        # Update time
        self.state['time'] = self.clock.time
        self.name = datetime.datetime.now()

        # Apply new settings to knobs according to the routines (if there are any)
        for name, routine in self.routines:
            self.variables[name].value = routine(self.state)

        # Read meters and calculate dependents
        for name, variable in self.variables.items():
            self.state[name] = variable.value

        # Append new state to experiment data set
        self.data.loc[timestamp] = self.state

        return self.state

    def __iter__(self):
        return self

    def stop(self):
        self.clock.stop()

    def start(self):
        self.clock.start()