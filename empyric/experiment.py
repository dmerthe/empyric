# This submodule defines the basic behavior of the key features of the empyric package

import os
from math import *
import time
import datetime
import numbers
import importlib
from scipy.interpolate import interp1d
import numpy as np
import pandas as pd
import warnings
import threading
import queue
import tkinter as tk
from tkinter.filedialog import askopenfilename
from ruamel.yaml import YAML
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

        :param instrument: (Instrument) instrument with the corresponding knob or meter
        :param knob: (str) instrument knob label, if variable is a knob
        :param meter: (str) instrument meter label, if variable is a meter
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
        if hasattr(self, 'knob') and value is not None and value is not np.nan:
            self.instrument.set(self.knob, value)
            self._value = self.instrument.__getattribute__(self.knob)
        else:
            pass


def convert_time(time_value):
    """
    If time_value is a string, converts a time of the form "number units" (e.g. "3.5 hours") to the time in seconds.
    If time_value is a number, just returns the same number
    If time_value is an array, it iterates through the array doing either of the previous two operations on every element.

    :param time_value: (str/float) time value, possibly including units such as 'hours'
    :return: (int) time in seconds
    """

    if np.size(time_value) > 1:
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

    def __init__(self, knobs=None, values=None, start=0, end=np.inf):
        """

        :param knobs: (1D array) knobs to be controlled
        :param values: (1D/2D array) array or list of values for each variable; can only be 1D if there is only one variable
        :param start: (float) time to start the routine
        :param stop: (float) time to end the routine
        """

        if knobs:
            self.knobs = knobs
        else:
            raise AttributeError(f'{self.__name__} routine requires knobs!')

        if values:

            self.values = np.array(values, dtype=object).reshape((len(self.knobs),-1))

            # Values can be stored in a CSV file
            for i, element in enumerate(self.values):
                if type(element[0]) == str:
                    if '.csv' in element[0]:
                        df = pd.read_csv(element[0])
                        self.values[i] = df[df.columns[-1]].values.reshape(len(df))

        else:
            raise AttributeError(f'{self.__name__} routine requires values')


        self.start = convert_time(start)
        self.end = convert_time(end)

    def update(self, state):
        """
        Updates the knobs controlled by the routine

        :param state: (dict/Series) state of the calling experiment or process in the form, {..., variable: value, ...}
        :return: None
        """

        pass


class Hold(Routine):
    """
    Holds a fixed value
    """

    def update(self, state):

        if state['time'] < self.start or state['time'] > self.end:
            return  # no change

        for variable, value in zip(self.knobs.values(), self.values):
            variable.value = value[0]


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

            self.times = np.array(times, dtype=object).reshape((len(self.knobs), -1))

            # Values can be stored in a CSV file
            for i, element in enumerate(self.times):
                if type(element[0]) == str:
                    if '.csv' in element[0]:
                        df = pd.read_csv(element[0])
                        self.times[i] = df[df.columns[0]].values.reshape(len(df))

            self.times = np.array(convert_time(self.times)).astype(float)

        else:
            raise AttributeError('Timecourse routine requires times!')

        self.interpolators = [interp1d(t, vals, bounds_error=False) for t, vals in zip(self.times, self.values)]

        self.start = np.min(self.times)
        self.end = np.max(self.times)

    def update(self, state):

        if state['time'] < self.start or state['time'] > self.end:
            return  # no change

        for variable, interpolator in zip(self.knobs.values(), self.interpolators):
            value = interpolator(state['time'] - self.start)
            variable.value = value


class Sequence(Routine):
    """
    Passes through a series of values regardless of time
    """

    def __init__(self, **kwargs):
        Routine.__init__(self, **kwargs)

        self.iteration = 0

    def update(self, state):

        if state['time'] < self.start or state['time'] > self.end:
            return  # no change

        for variable, values in zip(self.knobs.values(), self.values):
            value = values[self.iteration]
            variable.value = value

        self.iteration = (self.iteration + 1) % len(values)


class Set(Routine):
    """
    Sets a knob based on the value of another variable
    """

    def __init__(self, input=None, **kwargs):

        Routine.__init__(self, **kwargs)

        if inputs:
            self.inputs = inputs
        else:
            raise AttributeError('Set routine requires inputs!')

    def update(self, state):

        if state['time'] < self.start or state['time'] > self.end:
            return  # no change

        for variable, input in zip(self.knobs.values(), self.inputs):
            value = state[input]
            variable.value = value


class Minimize(Routine):
    """
    Minimize a set of meters (by some metric) influenced by a set of knobs, using simulated annealing

    Possible metrics include 'sum', 'norm', 'prod' (product).
    """


    def __init__(self, meters=None, max_deltas=None, T0=0.1, T1=0, metric='sum', **kwargs):

        Routine.__init__(self, **kwargs)

        if meters:
            self.meters = np.array([meters]).flatten()
        else:
            raise AttributeError(f'{self.__name__} routine requires meters for feedback')

        if max_deltas:
            self.max_deltas = np.array([max_deltas]).flatten()
        else:
            self.max_deltas = np.ones(len(self.knobs))

        self.T = T0
        self.T0 = T0
        self.T1 = T1
        self.metric = metric
        self.last_knobs = [np.nan]*len(self.knobs)
        self.last_meters = [np.nan]*len(self.controls)

    def update(self, state):

        # Get meter values
        meter_values = np.array([state[meter] for meter in self.meters])

        # Update temperature
        self.T = self.T0 + self.T1*(state['time'] - self.start)/(self.end - self.start)

        if self.better(meter_values):

            # Record this new optimal state
            self.last_knobs = [state[knob] for knob in self.knobs]
            self.last_meters = [state[meter] for meter in self.meters]

            # Generate and apply new knob settings
            new_knobs = self.last_knobs + self.max_deltas*np.random.rand(len(self.knobs))
            for knob, new_value in zip(self.knobs.values(), new_knobs):
                knob.value = new_value

        else:  # go back
            for knob, last_value in zip(self.knobs.values(), self.last_knobs):
                knob.value = last_value

    def better(self, meter_values):

        if np.prod(self.last_meters) != np.nan:

            if self.metric == 'sum':
                change = np.sum(meter_values) - np.sum(self.last_meters)
            elif self.metric == 'norm':
                change = np.linalg.norm(meter_values) - np.linalg.norm(self.last_meters)
            elif self.metric == 'prod':
                change = np.prod(meter_values) - np.prod(self.last_meters)

            return (change < 0) or (np.exp(-change/self.T) > np.random.rand())
        else:
            return True


class Maximize(Minimize):
    """
    Maximize a set of meters (by some metric) influenced by a set of knobs; works the same way as Minimize.
    """

    def better(self, meter_values):

        if np.prod(self.last_meters) != np.nan:

            if self.metric == 'sum':
                change = np.sum(meter_values) - np.sum(self.last_meters)
            elif self.metric == 'norm':
                change = np.linalg.norm(meter_values) - np.linalg.norm(self.last_meters)
            elif self.metric == 'prod':
                change = np.prod(meter_values) - np.prod(self.last_meters)

            return (change > 0) or (np.exp(change / self.T) > np.random.rand())
        else:
            return True


class ModelPredictiveControl(Routine):
    """
    (NOT IMPLEMENTED)
    Simple model predictive control; learns the relationship between knob x and meter y, assuming a linear model,

    y(t) = y0 + int_{-inf}^{t} dt' m(t-t') x(t')

    then sets x to minimize the error in y relative to setpoint, over some time interval defined by cutoff.

    """

    def __init__(self, controls=None, **kwargs):

        Routine.__init__(self, **kwargs)
        self.controls = controls

    def update(self, state):
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
    READY = 'Ready'  # Experiment is waiting to start
    RUNNING = 'Running'  # Experiment is running
    HOLDING = 'Holding'  # Routines are stopped, but measurements are ongoing
    STOPPED = 'Stopped'  # Both routines and measurements are stopped
    TERMINATED = 'Terminated'  # Experiment has either finished or has been terminated by the user

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, status):
        prior_base_status = self._status.split(':')[0]
        new_base_status =  status.split(':')[0]

        # Only allow change if the status is unlocked, or if the base status is the same
        if not self.status_locked or new_base_status == prior_base_status:
            self._status = status

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

        self._status = Experiment.READY
        status_locked = True  # can only be unlocked by the start, hold, stop and terminate methods

    def __next__(self):

        # Start the clock on first call
        if self.state.name is None:  # indicates that this is the first step of the experiment
            self.start()
            self.status = Experiment.RUNNING + ': initializing...'

        # Update time
        self.state['time'] = self.clock.time
        self.state.name = datetime.datetime.now()

        # If experiment is stopped, just return the last knob settings and nullify meter & expression values
        if Experiment.STOPPED in self.status:
            for name, variable in self.variables.items():
                if variable.type in ['meter', 'expression']:
                    self.state[name] = None
            return self.state

        # If the experiment is running, apply new settings to knobs according to the routines (if there are any)
        if Experiment.RUNNING in self.status:

            # Update each routine in its own thread
            threads = {}
            for name, routine in self.routines.items():
                threads[name] = threading.Thread(target=routine.update, args=(self.state,))
                threads[name].start()

            # Wait for all routine threads to finish
            for name, thread in threads.items():
                self.status = Experiment.RUNNING + f': executing {name}'
                thread.join()

            self.status = Experiment.RUNNING

        # Get all variable values if experiment is running or holding
        if Experiment.RUNNING in self.status or Experiment.HOLDING in self.status:

            # Run each measure / get operation in its own thread
            threads = {}
            for name in self.variables:
                threads[name] = threading.Thread(target=self._update_variable, args=(name,))
                threads[name].start()

            base_status = self.status

            # Wait for all threads to finish
            for name, thread in threads.items():
                self.status = base_status + f': retrieving {name}'
                thread.join()

            self.status = base_status

            # Append new state to experiment data set
            self.data.loc[self.state.name] = self.state

        # End the experiment, if the duration of the experiment has passed
        if self.clock.time > self.end:
            self.terminate()

        if Experiment.TERMINATED in self.status:
            raise StopIteration

        return self.state

    def __iter__(self):
        return self

    def _update_variable(self, name):

        value = self.variables[name].value

        if np.size(value) > 1:  # store array data as CSV files
            dataframe = pd.DataFrame({name: value}, index=[self.state.name] * len(value))
            path = name.replace(' ', '_') + '_' + self.state.name.strftime('%Y%m%d-%H%M%S') + '.csv'
            dataframe.to_csv(path)
            self.state[name] = path
        else:
            self.state[name] = value


    def save(self, directory=None):
        """
        Save the experiment dataframe to a CSV file

        :param directory: (path) (optional) directory to save data to, if different from working directory
        :return: None
        """

        base_status = self.status
        self.status = base_status + ': saving data'

        path = f"data_{self.timestamp}.csv"

        if directory:
            path = os.path.join(directory, path)

        self.data.to_csv(path)
        self.status = base_status

    def start(self):
        """
        Start the experiment: clock starts/resumes, routines resume, measurements continue

        :return: None
        """
        self.clock.start()

        self.status_locked = False
        self.status = Experiment.RUNNING
        self.status_locked = True

    def hold(self):
        """
        Hold the experiment: clock stops, routines stop, measurements continue

        :return: None
        """
        self.clock.stop()

        self.status_locked = False
        self.status = Experiment.HOLDING
        self.status_locked = True

    def stop(self):
        """
        Stop the experiment: clock stops, routines stop, measurements stop

        :return: None
        """
        self.clock.stop()

        self.status_locked = False
        self.status = Experiment.STOPPED
        self.status_locked = True

    def terminate(self):
        """
        Terminate the experiment: clock, routines and measurements stop, data is saved and StopIteration is raised

        :return: None
        """
        self.stop()
        self.save()

        self.status_locked = False
        self.status = Experiment.TERMINATED
        self.status_locked = True


def build_experiment(runcard, settings=None, instruments=None, alarms=None):
    """
    Build an Experiment object based on a runcard, in the form of a .yaml file or a dictionary

    :param runcard: (dict/str) description of the experiment in the runcard format
    :param settings: (dict) dictionary of settings to be populated
    :param instruments: (dict) dictionary instruments to be populated
    :param alarms: (dict) dictionary of alarms to be populated

    :return: (Experiment) the experiment described by the runcard
    """

    if instruments is None:
        instruments = {}

    # If given a settings keyword argument, get settings from runcard and store it there
    if 'Settings' in runcard and settings is not None:
        settings.update(runcard['Settings'])

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
        presets = specs.get('presets', {})
        postsets = specs.get('postsets', {})

        instrument_class = instr.__dict__[instrument_name]
        instruments[name] = instrument_class(address=address, presets=presets, postsets=postsets, **adapter_kwargs)

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
            specs['knobs'] = {name: variables[name] for name in np.array([specs['knobs']]).flatten()}
            routines[name] = routines_dict[_type](**specs)

    # Set up any alarms
    if 'Alarms' in runcard and alarms is not None:
        alarms.update({
            name: Alarm(
                variables[specs['variable']], specs['condition'],
                protocol=specs.get('protocol', None)
            ) for name, specs in runcard['Alarms'].items()
        })

    experiment = Experiment(variables, routines=routines)

    if 'end' in settings:
        experiment.end = convert_time(settings['end'])

    return experiment


class Manager:
    """
    Utility class which sets up and manages the above experiments
    """

    def __init__(self, runcard=None):
        """

        :param runcard: (dict/str) runcard as a dictionary or path pointing to a runcard
        """

        if not runcard:
            # Have user locate runcard
            root = tk.Tk()
            root.withdraw()
            self.runcard = askopenfilename(parent=root, title='Select Runcard', filetypes=[('YAML files', '*.yaml')])
        else:
            self.runcard = runcard

        if type(self.runcard) == str:

            os.chdir(os.path.dirname(self.runcard))  # go to runcard directory to put data in same location

            with open(self.runcard, 'rb') as runcard_file:
                self.runcard = yaml.load(runcard_file)  # load the runcard

        self.instruments = {}  # instruments will be stored here, so that they can be disconnected after the experiment
        self.alarms = {}
        self.settings = {}
        self.experiment = build_experiment(self.runcard, settings=self.settings, instruments=self.instruments, alarms=self.alarms)

        # Unpack settings
        self.step_interval = self.settings.get('step interval', 0.1)
        self.save_interval = self.settings.get('save interval', 60)
        self.plot_interval = self.settings.get('plot interval', 0)
        self.last_step = self.last_save = float('-inf')

        self.followup = self.settings.get('follow-up', None)  # Register settings
        self.settings = self.runcard.get('Settings', {})

        self.step_interval = self.settings.get('step interval', 0.1)
        self.save_interval = self.settings.get('save interval', 60)
        self.last_step = self.last_save = float('-inf')

        self.followup = self.settings.get('follow-up', None)

        # For use with alarms
        self.awaiting_alarms = False

    def run(self, directory=None):
        """
        Run the experiment defined by the runcard. A GUI shows experiment status, while the experiment is run in a separate thread.

        :param directory: (path) (optional) directory in which to run the experiment if different from the working directory
        :return: None
        """

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
        from ruamel.yaml import YAML
        yaml = YAML()

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
                                          save_interval=self.save_interval,
                                          plot_interval=self.plot_interval)

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
        # Run in a separate thread

        for state in self.experiment:

            step_start = time.time()

            # Save experimental data periodically
            if time.time() >= self.last_save + self.save_interval and Experiment.STOPPED not in self.experiment.status:
                self.experiment.save()

            # Check if any alarms are triggered and handle them
            alarms_triggered = [alarm for alarm in self.alarms.values() if alarm.triggered]
            if len(alarms_triggered) > 0:

                alarm = alarms_triggered[0]  # highest priority alarm is handled first

                if alarm.protocol:
                    if 'yaml' in alarm.protocol:
                        self.experiment.terminate()
                        self.followup = alarm.protocol
                    elif 'hold' in alarm.protocol:
                        self.experiment.hold()  # stop routines but keep measuring, and wait for alarm to clear
                        self.awaiting_alarms = True
                    elif 'stop' in alarm.protocol:
                        self.experiment.stop()  # stop routines and measurements, and wait for alarm to clear
                        self.awaiting_alarms = True
                    elif 'check' in alarm.protocol:
                        self.experiment.stop()
                        self.experiment.status = self.experiment.STOPPED + ': waiting for alarm check'
                        self.awaiting_alarms = 'check'
                    elif 'terminate' in alarm.protocol:
                        self.experiment.terminate()
                        self.awaiting_alarms = True

            elif self.awaiting_alarms == 'check':
                if self.experiment.STOPPED not in self.experiment.status:
                    self.awaiting_alarms = False

            elif self.awaiting_alarms:
                # If no alarms are triggered, resume experiment if holding or stopped
                self.awaiting_alarms = False
                self.experiment.start()

            step_end = time.time()

            remaining_time = np.max([self.step_interval - (step_end - step_start), 0])

            time.sleep(remaining_time)
