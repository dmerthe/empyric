# Some basic stuff
import time
import datetime
import numpy as np
import pandas as pd

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


class Variable:
    """
    Basic representation of an experimental variable; comes in 3 kinds: knob, meter and dependent

    Knobs can only be set; meters and dependents can only be measured
    """

    def __init__(self, *args, **kwargs):

        if 'type' not in kwargs:
            raise AttributeError("Variable type not defined!")

        self.type = kwargs['type']
        self._value = None

        if self.type in ['knob', 'meter']:
            self.instrument = args[0]
            self.label = args[1]

        elif self.type == 'dependent':
            self.expression = args[0]
            self.parents = args[1]

    @property
    def value(self):
        if self.type == 'knob':
            self._value = self.instrument.knob_values[self.label]
        elif self.type == 'meter':
            self._value = self.instrument.measure(self.label)
        elif self.type == 'dependent':
            expression = self.expression

            for symbol, parent in parents.items():
                expression = expression.replace(symbol, str(parent._value))

            self._value = eval(expression)

        return self._value

    @value.setter
    def value(self, value):
        if self.type == 'knob':
            self.instrument.set(knob, value)
            self._value = self.instrument.knob_values[self.label]


class Alarm:
    """
    Monitors a variable a raises an alarm if a condition is met
    """

    def __init__(self, variable, condition, protocol):

        self.variable = variable
        self.condition = condition
        self.protocol = protocol

    @property
    def signal(self):
        value = self.variable.value
        if eval('value'+condition):
            return self.protocol
        else:
            return None


class Clock:
    """
    Clock object for tracking elapsed time.
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


class Schedule:

    def __init__(self):

        self.clock = Clock()


    def __next__(self):
        pass


class Experiment:

    def __init__(self, variables, schedule=None):

        self.variables = variables  # dict of the form [..., name: variable, ...]
        self.schedule = schedule  # Schedule object

        self.data = pd.DataFrame(columns = ['time'] + list(variables.keys()))

    def __next__(self):

        state = pd.Series({'time': self.schedule.clock.time}, name=datetime.datetime.now())

        # Apply new settings to knobs as determined by the schedule, if there is one
        if self.schedule:
            settings = next(self.schedule)

            for name, value in settings.items():
                self.variables[name].value = value
                state[name] = value

        # Read meters and calculate dependents
        for name, variable in self.variables.items():
            if variable.type in ['meter', 'dependent']:
                state[name] = variable.value

        self.data.loc[state.name] = state

        return state

    def stop(self):
        self.schedule.clock.stop()

    def start(self):
        self.schedule.clock.start()


class Runcard:
    """
    Runcard encodes all the parameters of the experiment, as described by the user in the corresponding YAML document
    """
    def __init__(self, path):
        pass


class Controller:
    """
    Runs experiments and handles alarms
    """
    def __init__(self, runcard):
        pass
