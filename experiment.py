# This submodule defines the basic behavior of the key features in the mercury package

import os
import time
import datetime
import pandas as pd
import warnings
import threading
import queue
from ruamel.yaml import YAML

yaml = YAML()

from mercury import instruments as _instruments
from mercury import routines as _routines
from mercury import adapters, graphics


class Clock:
    """
    Clock for keeping time in an experiment; works like a standard stopwatch
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


class Variable:
    """
    Basic representation of an experimental variable; comes in 3 kinds: knob, meter and dependent.
    Knobs can only be set; meters and dependents can only be measured.

    A knob is a variable corresponding to something on an instrument that can be directly controlled, e.g. the voltage of a power supply.

    A meter is a variable that is measured, such as temperature. Some meters can be controlled directly or indirectly through an associated knob, but a meter can not be set.

    A dependent is a variable that is not directly measured, but is calculated based on other variables of the experiment.
    An example of a dependent is the output power of a power supply, where voltage is a knob and current is a meter: power = voltage * current.
    """

    def __init__(self, _type, instrument=None, label=None, expression=None, parents=None, preset=None, postset=None):
        """

        :param _type: (str) type of variable; can be either 'knob', 'meter' or 'dependent'.

        :param instrument: (Instrument) instrument with the corresponding knob or meter; only used if type is 'knob' or 'meter'

        :param label: (str) label of the knob or meter on the instrument; only used if type is 'knob' or 'meter'

        :param expression: (str) expression for the dependent variable in terms of the parents; only used if type is 'dependent'

        :param parents: (dict) dictionary of the form {..., symbol: variable, ...} mapping the symbols in the expression to the parent variable objects; only used if type is 'dependent'

        :param preset: (int/float/str) value variable should have upon definition

        :param postset: (int/float/str) value variable shoiuld have upon deletion
        """

        self.type = _type
        self._value = None  # This is the last known value of this variable

        if self.type in ['knob', 'meter']:

            if not instrument:
                raise AttributeError(f'{_type} variable definition requires an associated instrument!')

            self.instrument = instrument

            if not label:
                raise AttributeError(f'{_type} variable definition requires an a label!')

            self.__setattr__(_type, label)

            if _type == 'knob':
                self.preset = preset
                if preset:
                    self.value = preset

                self.postset = postset

        elif self.type == 'dependent':

            if not expression:
                raise AttributeError('dependent definition requires an expression!')
            if not parents:
                raise AttributeError('dependent definition requires parents!')

            self.expression = expression
            self.parents = parents

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
            self._value = self.instrument.knob_values[self.knob]

    def __del__(self):
        if self.postset:
            self.value = self.postset


class Alarm:
    """
    Monitors a variable, raises an alarm if a condition is met and signals the response protocol
    """

    def __init__(self, variable, condition, protocol):

        self.variable = variable  # variable being monitored
        self.condition = condition  # condition which triggers the alarm
        self.protocol = protocol  # what to do when the alarm is triggered

        self._signal = False

    @property
    def signal(self):
        value = self.variable.value
        self._signal = eval('value' + self.condition)
        return self._signal


class Experiment:

    RUNNING = 'Running'
    STOPPED = 'Stopper'
    TERMINATED = 'Terminated'

    def __init__(self, variables, routines=None):

        self.variables = variables  # dict of the form {..., name: variable, ...}

        if routines:
            self.routines = routines  # dictionary of experimental routines of the form {..., name: routine, ...}
        else:
            self.routines = {}

        self.clock = Clock()
        self.clock.start()

        self.timestamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')

        self.data = pd.DataFrame(columns=['time'] + list(variables.keys()))

        self.state = pd.Series({column: None for column in self.data.columns})
        self.status = 'Ready'

    def __next__(self):

        # Start the clock
        if self.state.name is None:  # indicates that this is the first step of the experiment
            self.clock.start()

        # Update time
        self.state['time'] = self.clock.time
        self.state.name = datetime.datetime.now()

        # Apply new settings to knobs according to the routines (if there are any and the experiment is running)
        if self.status is Experiment.RUNNING:
            for name, routine in self.routines:
                self.variables[name].value = routine(self.state)

        # Get all variable values
        for name, variable in self.variables.items():
            self.state[name] = variable.value

        # Append new state to experiment data set
        self.data.loc[self.state.name] = self.state

        return self.state

    def __iter__(self):
        return self

    def save(self):

        self.data.to_csv(
            f"data_{self.timestamp}.csv"
        )

    def stop(self):
        self.status = Experiment.STOPPED
        self.clock.stop()

    def start(self):
        self.status = Experiment.RUNNING
        self.clock.start()

    def terminate(self):
        self.status = Experiment.TERMINATED


class Manager:
    """
    Sets up and runs an experiment, defined by a runcard, and interacts with the user
    """

    def __init__(self, runcard):

        # Get the runcard
        if isinstance(runcard, str):  # runcard argument can be a path string
            with open(runcard, 'rb') as runcard_file:
                self.runcard = yaml.load(runcard_file)  # load runcard in dictionary form
        elif isinstance(runcard, dict):
            self.runcard = runcard
        else:
            raise ValueError('runcard not recognized!')

        self.settings = runcard.get('Settings', None)  # global settings

        self.step_period = self.settings.get('step period', 0)
        self.plot_period = self.settings.get('plot period', 10)
        self.save_period = self.settings.get('save period', 60)

        self.last_step = self.last_plot = self.last_save = float('-inf')

        self.followup = self.settings.get('follow-up', None)

        self.experiment = self.build_experiment(self.runcard)  # use the runcard to build the experiment

        if 'Alarms' in self.runcard:
            self.alarms = {
                name: Alarm(
                    self.experiment.variables[specs['variable']], specs['condition'], specs['protocol']
                ) for name, specs in self.runcard['Alarms'].items()
            }
        else:
            self.alarms = {}

        if 'Plots' in self.runcard:
            self.plotter = graphics.Plotter(self.experiment.data, settings=self.runcard['Plots'])
        else:
            self.plotter = None

        self.gui = graphics.GUI(self.experiment, alarms=self.alarms, title=self.runcard['Description']['name'])  # GUI for user interaction
        self.gui_thread = threading.Thread(target=self.gui.run)
        self.gui_thread.start()  # run the GUI in a separate thread

        self.run()

    @staticmethod
    def build_experiment(runcard):

        instruments = {}  # instruments to be used in this experiment
        for name, specs in runcard['Instruments']:
            instrument_type = _instruments.__dict__[specs.pop('type')]
            address = specs.pop('address')
            instruments[name] = instrument_type(address=address, presets=specs)

        variables = {}
        for name, specs in runcard['Variables']:
            if 'meter' in specs:
                variables[name] = Variable('meter', instruments[specs['instrument']], specs['meter'])
            elif 'knob' in specs:
                variables[name] = Variable('knob', instruments[specs['instrument']], specs['knob'])
            elif 'dependent' in specs:
                variables[name] = Variable('dependent', expression=specs['expression'],
                                            parents={symbol: variables[var_name]
                                                     for symbol, var_name in specs['parents'].items()}
                                            )

        if 'Routines' in runcard:
            for name, specs in runcard['Routines']:

                _type = specs.pop('type')
                values = specs.pop('values')
                variable = variables[specs.pop('variable')]

                if 'feedback' in specs:
                    specs['feedback'] = variables[specs['feedback']]

                routines = {
                    name: _routines.__dict__[_type](values, variable=variable, **specs)
                }
        else:
            routines = {}

        return Experiment(variables, routines=routines)

    def run(self):

        # Create a new directory and store a copy of executed runcard there
        name = self.runcard['Description'].get('name', 'experiment')
        timestamp = self.experiment.timestamp
        current_dir = os.getcwd()
        working_dir = os.path.join(current_dir, name + '-' + timestamp)
        os.mkdir(working_dir)
        os.chdir(working_dir)

        with open(f"{name}_{self.experiment.timestamp}.yaml", 'w') as runcard_file:
            yaml.dump(self.runcard, runcard_file)  # save executed runcard for record keeping

        # Run the experiment
        alarms_waiting = []  # list of alarms waiting to be untriggered
        for state in self.experiment:

            if time.time() >= self.last_plot + self.plot_period:
                plotting_thread = threading.Thread(target=self.plotter.plot)
                plotting_thread.start()
                self.last_plot = time.time()

            if time.time() >= self.last_save + self.save_period:
                self.experiment.save()

            alarms_triggered = [alarm for name, alarm in self.alarms if alarm.signal is not None]

            if len(alarms_triggered) > 0:

                alarm = alarms_triggered[0]

                if 'yaml' in alarm.protocol:
                    self.experiment.terminate()
                    self.followup = alarm.protocol
                    break
                elif 'wait' in alarm.protocol and alarm not in alarms_waiting:
                    alarms_waiting.append(alarm)
                    self.experiment.stop()

            elif len(alarms_waiting) > 0:  #
                alarms_waiting = []  # if no alarms are triggered, empty the waiting list
                self.experiment.start()  # and restart the experiment


            if self.experiment.status is Experiment.TERMINATED:
                break

            time.sleep(self.step_period)

        os.chdir('..')

        if self.followup:
            self.__init__(self.followup)
