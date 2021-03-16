# This submodule defines the basic behavior of the key features of the empyric package

import os
from math import *
import time
import datetime
import numbers
from scipy.interpolate import interp1d
import numpy as np
import pandas as pd
import warnings
import threading
import queue
from ruamel.yaml import YAML
import tkinter as tk
from tkinter.filedialog import askopenfilename

yaml = YAML()

from empyric import instruments as instr
from empyric import adapters, graphics


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
    Basic representation of an experimental variable; comes in 3 kinds: knob, meter and expression.
    Knobs can be set, meters can be measured and expressions can be calculated.

    A knob is a variable that can be directly controlled by an instrument, e.g. the voltage of a power supply.

    A meter is a variable that is measured by an instrument, such as temperature. Some meters can be controlled directly or indirectly through an associated (but distinct) knob.

    An expression is a variable that is not directly measured, but is calculated based on other variables of the experiment.
    An example of an expression is the output power of a power supply, where voltage is a knob and current is a meter: power = voltage * current.
    """

    def __init__(self, instrument=None, knob=None, meter=None, expression=None, definitions=None):
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
                raise AttributeError(f'{self.type} variable definition requires an instrument!')
            self.instrument = instrument

        elif hasattr(self, 'expression'):
            if not definitions:
                raise AttributeError('expression definition requires definitions!')
            self.definitions = definitions

    @property
    def value(self):
        if hasattr(self, 'knob'):
            self._value = self.instrument.get(self.knob)
        elif hasattr(self, 'meter'):
            self._value = self.instrument.measure(self.meter)
        elif hasattr(self, 'expression'):
            expression = self.expression
            expression = expression.replace('^', '**')  # carets represent exponents to everyone except for Guido van Rossum

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
        if hasattr(self, 'knob') and value is not None and value != np.nan:
            self.instrument.set(self.knob, value)
            self._value = self.instrument.__getattribute__(self.knob)
        elif value is None:
            pass
        else:
            raise AssertionError(f'cannot set {self.type}!')

## Routines

def convert_time(time_value):
    """
    Converts a time of the form "number units" (e.g. "3.5 hours") to the time in seconds.

    :param time_value: (str/float) time value, possibly including units such as 'hours'
    :return: (int) time in seconds
    """

    if hasattr(time_value, '__len__') and not isinstance(time_value, str):
        return [convert_time(t) for t in time_value]

    if isinstance(time_value, numbers.Number):
        return time_value
    elif isinstance(time_value, str):
        # times can be specified in the runcard with units, such as minutes, hours or days, e.g.  "6 hours"
        time_parts = time_value.split(' ')

        if len(time_parts) == 1:
            return float(time_parts[0])
        elif len(time_parts) == 2:
            value, unit = time_parts
            value = float(value)
            return value * {
                'seconds': 1, 'second':1,
                'minutes': 60, 'minute': 60,
                'hours': 3600, 'hour': 3600,
                'days': 86400, 'day':86400
            }[unit]
        else:
            raise ValueError(f'Unrecognized time format for {time_value}!')

## Routines ##

class Routine:
    """
    Base class for all routines
    """

    def __init__(self, variables=None, values=None, start=0, end=np.inf):
        """

        :param variables: (1D array) array or list of variables to be controlled
        :param values: (1D/2D array) array or list of values for each variable
        :param start: (float) time to start the routine
        :param stop: (float) time to end the routine
        """

        if variables:
            self.variables = variables
        else:
            raise AttributeError(f'{self.__name__} routine requires variables!')

        if values:
            self.values = values

            # values can be specified in a CSV file
            for i, values_i in enumerate(self.values):
                if values_i == 'csv':
                    df = pd.read_csv(values_i)
                    self.values[i] = df[df.columns[-1]].values

            self.values = np.array([self.values]).flatten().reshape((len(self.variables),-1)) # make rows match self.variables
        else:
            raise AttributeError(f'{self.__name__} routine requires values!')


        self.start = start
        self.end = end


class Hold(Routine):
    """
    Holds a fixed value
    """

    def update(self, state):

        update = {name: value for name, value in state.items() if name in self.variables}
        if state['time'] < self.start or state['time'] > self.end:
            return update  # no change

        for name, variable, value in zip(self.variables, self.variables.values(), self.values):
            variable.value = value
            update[name] = value

        return update


class Timecourse(Routine):
    """
    Ramps linearly through a series of values at given times
    """

    def __init__(self, times=None, **kwargs):
        """

        :param times: (1D/2D array) array or list of times, relative to the start time, to set each variable to each value
        :param kwargs: keyword arguments for Routine
        """

        Routine.__init__(self, **kwargs)

        if times:
            self.times = times

            # times can be specified in a CSV file
            for i, times_i in enumerate(times):
                if times_i == 'csv':
                    df = pd.read_csv(times_i)
                    self.times[i] = df[df.columns[-1]].values

            self.times = np.array([self.times]).flatten().reshape((len(self.variables), -1))  # make rows match self.variables
        else:
            raise AttributeError('Timecourse routine requires times!')

        self.interpolators = {variable: interp1d(times, values, bounds_error=False) for variable, times, values
                              in zip(self.variables, self.times, self.values)}

    def update(self, state):

        update = {name: value for name, value in state.items() if name in self.variables}
        if state['time'] < self.start or state['time'] > self.end:
            return update  # no change

        for name, variable in zip(self.variables, self.variables.values()):
            value = self.interpolators[name](state['time']-self.start)
            variable.value = value
            update[name] = value

        return update


class Sequence(Routine):
    """
    Passes through a series of values regardless of time
    """

    def __init__(self, **kwargs):
        Routine.__init__(**kwargs)

        self.iteration = 0

    def update(self, state):

        update = {name: value for name, value in state.items() if name in self.variables}
        if state['time'] < self.start or state['time'] > self.end:
            return update  # no change

        for name, variable, values in zip(self.variables, self.variables.values(), self.values):
            value = values[self.iteration]
            variable.value = value
            update[name] = value

        self.iteration = (self.iteration + 1) % len(self.values)

        return update


class Set(Routine):
    """
    Sets a knob based on the value of another variable
    """

    def __init__(self, input=None, **kwargs):

        Routine.__init__(**kwargs)

        if inputs:
            self.inputs = inputs
        else:
            raise AttributeError('Set routine requires inputs!')

    def update(self, state):

        update = {name: value for name, value in state.items() if name in self.variables}
        if state['time'] < self.start or state['time'] > self.end:
            return update  # no change

        for name, variable, input in zip(self.variables, self.variables.values(), self.inputs):
            value = state[input]
            variable.value = value
            update[name] = value

        return update


class Minimize(Routine):
    """
    Minimize a variable influenced by a knob
    """
    pass


class Maximize(Routine):
    """
    Mazimize a variable influenced by a knob
    """
    pass

routines_dict = {
    routine.__name__: routine for routine in Routine.__subclasses__()
}


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
        if not (value == None or value == float('nan') or value == ''):
            self._triggered = eval('value' + self.condition)

        return self._triggered


class Experiment:
    """
    An iterable class which represents an experiment; iterates through any assigned routines,
    and retrieves and stores the values of all experiment variables.
    """

    # Possible statuses of an experiment
    READY = 'Ready'  # Experiment is initialized but not yet started
    RUNNING = 'Running'  # Experiment is running
    HOLDING = 'Holding'  # Routines are stopped, but measurements are ongoing
    STOPPED = 'Stopped'  # Both routines and measurements are stopped
    TERMINATED = 'Terminated'  # Experiment has either finished or has been terminated by the user

    def __init__(self, variables, routines=None):

        self.variables = variables  # dict of the form {..., name: variable, ...}

        if routines:
            self.routines = routines  # dictionary of experimental routines of the form {..., name: (variable_name, routine), ...}
            self.end = max([routine.end for routine in routines.values()])  # time at which all routines are exhausted
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

        # Update time
        self.state['time'] = self.clock.time
        self.state.name = datetime.datetime.now()

        # Apply new settings to knobs according to the routines (if there are any and the experiment is running)
        if self.status is Experiment.RUNNING:
            for routine in self.routines.values():
                self.state.update(routine.update(self.state))

        elif self.status == Experiment.STOPPED:
            for name, variable in self.variables.items():
                if variable.type in ['meter', 'expression']:
                    self.state[name] = None
            return self.state

        # Get all variable values
        for name, variable in self.variables.items():

            value = variable.value

            if np.size(value) > 1: # store array data as CSV files
                dataframe = pd.DataFrame({name: value}, index=[self.state.name]*len(value))
                path = name.replace(' ','_') +'_' + self.state.name.strftime('%Y%m%d-%H%M%S') + '.csv'
                dataframe.to_csv(path)
                self.state[name] = path
            else:
                self.state[name] = value

        # Append new state to experiment data set
        self.data.loc[self.state.name] = self.state

        # End the experiment, if the duration of the experiment has passed
        if self.clock.time > self.end:
            self.terminate()

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

    def start(self):
        self.clock.start()
        self.status = Experiment.RUNNING

    def hold(self):  # stops routines only
        self.clock.stop()
        self.status = Experiment.HOLDING

    def stop(self):  # stops routines and measurements
        self.clock.stop()
        self.status = Experiment.STOPPED

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

        # Grab any keyword arguments for the adapter
        adapter_kwargs = {}
        for kwarg in adapters.Adapter.kwargs:
            if kwarg.replace('_', ' ') in specs:
                adapter_kwargs[kwarg] = specs.pop(kwargs)

        # Any remaining keywards are instrument presets
        presets = specs

        instrument_class = instr.__dict__[instrument_name]
        instruments[name] = instrument_class(address=address, presets=presets, **adapter_kwargs)

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
            specs['variables'] = {name: variables[name] for name in np.array([specs['variables']]).flatten()}
            routines[name] = routines_dict[_type](**specs)

    return Experiment(variables, routines=routines)


class Manager:
    """
    Utility class which sets up and manages the above experiments
    """

    @property
    def runcard(self):
        return self._runcard

    @runcard.setter
    def runcard(self, runcard):

        if isinstance(runcard, str):  # runcard argument can be a path string
            with open(runcard, 'rb') as runcard_file:
                self._runcard = yaml.load(runcard_file)

            os.chdir(os.path.dirname(runcard))
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

        if runcard:
            self.runcard = runcard
        else:
            # Have user locate runcard
            root = tk.Tk()
            root.withdraw()
            self.runcard = askopenfilename(parent=root, title='Select Runcard', filetypes=[('YAML files', '*.yaml')])

        # For use with alarms
        self.awaiting_alarms = False

    def run(self, directory=None):

        # Create a new directory for data storage
        if directory:
            os.chdir(directory)

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
                    elif 'hold' in alarm.protocol:
                        self.experiment.hold()  # stop routines but keep measuring, and wait for alarm to clear
                        self.awaiting_alarms = True
                    elif 'stop' in alarm.protocol:
                        self.experiment.stop()  # stop routines and measurements, and wait for user action
                        self.awaiting_alarms = True

            elif self.awaiting_alarms:
                # If no alarms are triggered, resume experiment if holding or stopped
                self.awaiting_alarms = False
                self.experiment.start()

            time.sleep(self.step_interval)
