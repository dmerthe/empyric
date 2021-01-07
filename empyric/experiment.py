# This submodule defines the basic behavior of the key features of the empyric package

import os
from math import *
import time
import datetime
import pandas as pd
import warnings
import threading
import queue
from ruamel.yaml import YAML
import tkinter as tk
from tkinter.filedialog import askopenfilename

yaml = YAML()

from empyric import instruments as instr
from empyric import routines as rout
from empyric import adapters, graphics, control


class Clock:
    """
    Clock for keeping time in an experiment; works like a standard stopwatch
    """

    def __init__(self):

        self.start_time = self.stop_time = time.time()  # clock is initially stopped
        self.stoppage = 0  # total time during which the clock has been stopped

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
    Basic representation of an experimental variable; comes in 3 kinds: knob, meter and expressions.
    Knobs can be set, meters can be measured and expressions can be calculated.

    A knob is a variable that can be directly controlled by an instrument, e.g. the voltage of a power supply.

    A meter is a variable that is measured by an instrument, such as temperature. Some meters can be controlled directly or indirectly through an associated (but distinct) knob.

    An expression is a variable that is not directly measured, but is calculated based on other variables of the experiment.
    An example of an expression is the output power of a power supply, where voltage is a knob and current is a meter: power = voltage * current.
    """

    def __init__(self, knob=None, meter=None, instrument=None, expression=None, definitions=None):
        """
        One of either the knob, meter or expression keyword arguments must be supplied along with the respective instrument or definitions.

        :param knob: (str) instrument knob label, if variable is a knob
        :param meter: (str) instrument meter label, if variable is a meter
        :param instrument: (Instrument) instrument with the corresponding knob or meter
        :param expression: (str) expression for the variable in terms of other variables, if variable is an expression
        :param definitions: (dict) dictionary of the form {..., symbol: variable, ...} mapping the symbols in the expression to other variable objects; only used if type is 'expression'
        """

        if meter:
            self.meter = meter
            self.type = 'meter'
        elif knob:
            self.knob = knob
            self.type = 'knob'
        elif expression:
            self.expression = expression
            self.type = 'expression'
        else:
            raise ValueError('variable object must have a specified knob, meter or expression!')

        self._value = None  # last known value of this variable

        if hasattr(self, 'knob') or hasattr(self, 'meter'):
            if not instrument:
                raise AttributeError(f'{_type} variable definition requires an instrument!')
            self.instrument = instrument

        elif hasattr(self, 'expression'):
            if not definitions:
                raise AttributeError('expression definition requires definitions!')
            self.definitions = definitions

    @property
    def value(self):
        if hasattr(self, 'knob'):
            self._value = self.instrument.knob_values[self.knob]
        elif hasattr(self, 'meter'):
            self._value = self.instrument.measure(self.meter)
        elif hasattr(self, 'expression'):
            expression = self.expression
            expression = expression.replace('^', '**')

            for symbol, variable in self.definitions.items():
                expression = expression.replace(symbol, '(' + str(variable._value) + ')')

            try:
                self._value = eval(expression)
            except BaseException:
                self._value = float('nan')

        return self._value

    @value.setter
    def value(self, value):
        # value property can only be set if variable is a knob; None value indicates no setting should be applied
        if hasattr(self, 'knob') and value is not None:
            self.instrument.set(self.knob, value)
            self._value = self.instrument.knob_values[self.knob]


class Alarm:
    """
    Monitors a variable, triggers if a condition is met and indicates the response protocol
    """

    def __init__(self, variable, condition, protocol=None):
        self.variable = variable  # variable being monitored
        self.condition = condition  # condition which triggers the alarm
        self.protocol = protocol  # what to do when the alarm is triggered

        self._triggered = False

    @property
    def triggered(self):
        value = self.variable._value  # get last know variable value
        if value == None or value == float('nan') or value == '':
            self._triggered = False
        else:
            self._triggered = eval('value' + self.condition)

        return self._triggered


class Experiment:
    # Possible statuses of an experiment
    READY = 'Ready'  # Experiment is initialized but not yet started
    RUNNING = 'Running'  # Experiment is running
    WAITING = 'Waiting'  # Routines are stopped, but measurements are ongoing
    STOPPED = 'Stopped'  # Both routines and measurements are stopped
    TERMINATED = 'Terminated'  # Experiment has either finished or has been terminated by the user

    def __init__(self, variables, routines=None):

        self.variables = variables  # dict of the form {..., name: variable, ...}

        if routines:
            self.routines = routines  # dictionary of experimental routines of the form {..., name: (variable_name, routine), ...}
            self.end = max(
                [routine.end for _, routine in routines.values()])  # time at which all routines are exhausted
        else:
            self.routines = {}
            self.end = float('inf')

        self.clock = Clock()
        self.clock.start()

        self.timestamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')

        self.data = pd.DataFrame(columns=['time'] + list(variables.keys()))

        self.state = pd.Series({column: None for column in self.data.columns})
        self.state['time'] = 0
        self.status = Experiment.READY

    def __next__(self):

        # Start the clock on first call
        if self.state.name is None:  # indicates that this is the first step of the experiment
            self.status = Experiment.RUNNING
            self.clock.start()

        # End the experiment, if the duration of the experiment has passed
        if self.clock.time > self.end:
            self.terminate()

        # Update time
        self.state['time'] = self.clock.time
        self.state.name = datetime.datetime.now()

        # Apply new settings to knobs according to the routines (if there are any and the experiment is running)
        if self.status is Experiment.RUNNING:
            for name, routine in self.routines.values():
                self.variables[name].value = routine(self.state)
        elif self.status == Experiment.STOPPED:
            for name, variable in self.variables.items():
                if variable.type in ['meter', 'expression']:
                    self.state[name] = None
            return self.state

        # Get all variable values
        for name, variable in self.variables.items():
            self.state[name] = variable.value

        # Append new state to experiment data set
        self.data.loc[self.state.name] = self.state

        if self.status is Experiment.TERMINATED:
            raise StopIteration

        return self.state

    def __iter__(self):
        return self

    def save(self, directory=None):

        path = f"data_{self.timestamp}.csv"

        if directory:
            path = os.path.join(directory, path)

        self.data.to_csv(path)

    def wait(self):  # stops routines
        self.clock.stop()
        self.status = Experiment.WAITING

    def stop(self):  # stops routines and measurements
        self.clock.stop()
        self.status = Experiment.STOPPED

    def start(self):
        self.clock.start()
        self.status = Experiment.RUNNING

    def terminate(self):
        self.stop()
        self.save()
        self.status = Experiment.TERMINATED


def build_experiment(runcard, instruments=None):
    """
    Build an Experiment object based on a runcard, in the form of a .yaml file or a dictionary

    :param runcard: (str/dict) the description of the experiment in the runcard format
    :param instruments: (None) variable pointing to instruments, if needed
    :return: (Experiment) the experiment described by the runcard
    """

    if instruments is None:
        instruments = {}

    for name, specs in runcard['Instruments'].items():

        specs = specs.copy()  # avoids modifying the runcard

        instrument_name = specs.pop('type')
        address = specs.pop('address')

        # adapter keywords
        adapter_kwargs = {}
        if 'baud rate' in specs:
            adapter_kwargs['baud_rate'] = specs.pop('baud rate')
        if 'timeout' in specs:
            adapter_kwargs['timeout'] = specs.pop('timeout')
        if 'delay' in specs:
            adapter_kwargs['delay'] = specs.pop('delay')

        # Any remaining keywards are instrument presets
        presets = specs

        instrument_class = instr.__dict__[instrument_name]
        instruments[name] = instrument_class(address, presets=presets, **adapter_kwargs)

    variables = {}  # experiment variables, associated with the instruments above
    for name, specs in runcard['Variables'].items():
        if 'meter' in specs:
            variables[name] = Variable(meter=specs['meter'], instrument=instruments[specs['instrument']])
        elif 'knob' in specs:
            variables[name] = Variable(knob=specs['knob'], instrument=instruments[specs['instrument']])
        elif 'expression' in specs:
            variables[name] = Variable(expression=specs['expression'],
                                       definitions={symbol: variables[var_name]
                                                    for symbol, var_name in specs['definitions'].items()})

    routines = {}
    if 'Routines' in runcard:
        for name, specs in runcard['Routines'].items():

            specs = specs.copy()  # avoids modifying the runcard

            _type = specs.pop('type')
            variable_name = specs.pop('variable')

            if 'feedback' in specs:
                # Get the feedback variable
                specs['feedback'] = variables[specs['feedback']]

                if 'controller' in specs:
                    # Initialize a controller based on the controller specs
                    contr_type = specs['controller'].pop('type')
                    contr_kwargs = specs['controller']
                    specs['controller'] = controllers.__dict__[contr_type](**contr_kwargs)

            routines[name] = (variable_name, rout.__dict__[_type](**specs))

    return Experiment(variables, routines=routines)


class Manager:
    """
    Manages the experiments
    """

    @property
    def runcard(self):
        return self._runcard

    @runcard.setter
    def runcard(self, runcard):

        if isinstance(runcard, str):  # runcard argument can be a path string
            with open(runcard, 'rb') as runcard_file:
                self._runcard = yaml.load(runcard_file)
        elif isinstance(runcard, dict):  # ... or a properly formatted dictionary
            self._runcard = runcard
        else:
            raise ValueError('runcard not recognized!')

        # Register settings
        self.settings = self._runcard.get('Settings', {})

        self.step_interval = self.settings.get('step interval', 0.1)
        self.save_interval = self.settings.get('save interval', 60)
        self.last_step = self.last_save = float('-inf')

        self.followup = self.settings.get('follow-up', None)        # Register settings
        self.settings = self.runcard.get('Settings', {})

        self.step_interval = self.settings.get('step interval', 0.1)
        self.save_interval = self.settings.get('save interval', 60)
        self.last_step = self.last_save = float('-inf')

        self.followup = self.settings.get('follow-up', None)

        # Rebuild the experiment based on the new runcard
        self.instruments = {}  # experiment instruments will be stored here
        self.experiment = build_experiment(self._runcard, instruments=self.instruments)

        # Set up any alarms
        if 'Alarms' in self._runcard:
            self.alarms = {
                name: Alarm(
                    self.experiment.variables[specs['variable']], specs['condition'],
                    protocol=specs.get('protocol', None)
                ) for name, specs in self._runcard['Alarms'].items()
            }
        else:
            self.alarms = {}

    def __init__(self, runcard=None):

        if not runcard:
            # Have user locate runcard file
            root = tk.Tk()
            root.withdraw()
            runcard_path = askopenfilename(parent=root, title='Select Runcard')

            with open(runcard_path, 'rb') as runcard_file:
                self.runcard = yaml.load(runcard_file)
        else:
            self.runcard = runcard

    def run(self):

        # Create a new directory for data storage
        experiment_name = self.runcard['Description'].get('name', 'Experiment')
        timestamp = self.experiment.timestamp
        top_dir = os.getcwd()
        working_dir = os.path.join(top_dir, experiment_name + '-' + timestamp)
        os.mkdir(working_dir)
        os.chdir(working_dir)

        # Save executed runcard alongside data for record keeping
        with open(f"{experiment_name}_{self.experiment.timestamp}.yaml", 'w') as runcard_file:
            yaml.dump(self.runcard, runcard_file)

        # Run experiment loop in separate thread
        experiment_thread = threading.Thread(target=self._run)
        experiment_thread.start()

        # Set up the GUI for user interaction
        self.gui = graphics.ExperimentGUI(self.experiment,
                                          alarms=self.alarms,
                                          instruments=self.instruments,
                                          title=self.runcard['Description'].get('name', 'Experiment'),
                                          plots=self.runcard.get('Plots', None),
                                          save_interval=self.save_interval)

        self.gui.run()

        experiment_thread.join()

        # Disconnect instruments
        for instrument in self.instruments.values():
            instrument.disconnect()

        os.chdir(top_dir)  # return to the parent directory

        # Execute the follow-up experiment if there is one
        if self.followup in [None, 'None'] or self.gui.terminated:
            return
        elif 'yaml' in self.followup:
            self.__init__(self.followup)
            self.run()
        elif 'repeat' in self.followup:
            self.__init__(self.runcard)
            self.run()


    def _run(self):

        for state in self.experiment:

            # Save experimental data periodically
            if time.time() >= self.last_save + self.save_interval:
                self.experiment.save()

            # Check if any alarms are triggered and handle them
            alarms_triggered = [alarm for alarm in self.alarms.values() if alarm.triggered]
            if len(alarms_triggered) > 0:

                alarm = alarms_triggered[0]  # highest priority alarm goes first

                if alarm.protocol:
                    if 'yaml' in alarm.protocol:
                        self.experiment.terminate()
                        self.followup = alarm.protocol
                    elif 'wait' in alarm.protocol:
                        self.experiment.wait()  # stop routines but keep measuring, and wait for alarm to clear
                    elif 'stop' in alarm.protocol:
                        self.experiment.stop()  # stop routines and measurements, and wait for user action

            elif self.experiment.status == Experiment.WAITING and not self.gui.paused:
                # If no alarms are triggered, resume experiment if stopped
                self.experiment.start()

            time.sleep(self.step_interval)
