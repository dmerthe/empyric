# This submodule defines the basic behavior of the key features of the empyric package

import os, sys, shutil, importlib, threading, time, datetime, numbers
from scipy.interpolate import interp1d
import numpy as np
import pandas as pd
import tkinter as tk
from tkinter.filedialog import askopenfilename
from ruamel.yaml import YAML

from empyric import instruments as instr
from empyric import adapters, graphics


def convert_time(time_value):
    """
    If time_value is a string, converts a time of the form "[number] [units]" (e.g. "3.5 hours") to the time in seconds.
    If time_value is a number, just returns the same number
    If time_value is an array, iterates through the array doing either of the previous two operations on every element.

    :param time_value: (str/float) time value, possibly including units such as "hours"
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
                'seconds': 1, 'second': 1,
                'minutes': 60, 'minute': 60,
                'hours': 3600, 'hour': 3600,
                'days': 86400, 'day': 86400
            }[unit]
        else:
            raise ValueError(f'Unrecognized time format for {time_value}!')


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
    Basic representation of an experimental variable that comes in 4 kinds: knob, meter, expression and parameter.

    A knob is a variable that can be directly controlled by an instrument, e.g. the voltage of a power supply.

    A meter is a variable that is measured by an instrument, such as temperature. Some meters can be controlled directly
    or indirectly through an associated (but distinct) knob.

    An expression is a variable that is not directly measured, but is calculated based on other variables of the
    experiment. An example of an expression is the output power of a power supply, where voltage is a knob and current
    is a meter: power = voltage * current.

    A parameter is a variable whose value is assigned directly by the user. An example is a unit conversion factor such
    as 2.54 cm per inch, a numerical constant like pi or a setpoint for a control routine.
    """

    # Some abbreviated functions that can be used to evaluate expression variables
    expression_functions = {
        'sqrt': 'np.sqrt',
        'exp': 'np.exp',
        'sin': 'np.sin',
        'cos': 'np.cos',
        'tan': 'np.tan',
        'sum': 'np.nansum',
        'mean': 'np.nanmean',
        'rms': 'np.nanstd',
        'std': 'np.nanstd',
        'var': 'np.nanvar',
        'diff': 'np.diff',
        'max': 'np.nanmax',
        'min': 'np.nanmin'
    }

    def __init__(self, instrument=None, knob=None, meter=None, expression=None, definitions=None, parameter=None):
        """
        One of either the knob, meter or expression keyword arguments must be supplied along with the respective
        instrument or definitions.

        :param instrument: (Instrument) instrument with the corresponding knob or meter
        :param knob: (str) instrument knob label, if variable is a knob
        :param meter: (str) instrument meter label, if variable is a meter
        :param expression: (str) expression for the variable in terms of other variables, if variable is an expression
        :param definitions: (dict) dictionary of the form {..., symbol: variable, ...} mapping the symbols in the expression to other variable objects; only used if type is 'expression'
        :param parameter (str) value of a user controlled parameter

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
        elif parameter:
            self.parameter = parameter
            self.type = 'parameter'
        else:
            raise ValueError('variable object must have a specified knob, meter or expression, or assigned a value if a parameter!')

        self._value = None  # last known value of this variable
        self.last_evaluation = np.nan  # time of last evaluation; used for expressions

        if hasattr(self, 'knob') or hasattr(self, 'meter'):
            if not instrument:
                raise AttributeError(f'{self.type} variable definition requires an instrument!')
            self.instrument = instrument

        elif hasattr(self, 'expression'):
            if definitions:
                self.definitions = definitions
            else:
                self.definitions = {}

    @property
    def value(self):

        if hasattr(self, 'knob'):
            self._value = self.instrument.get(self.knob)
            self.last_evaluation = time.time()

        elif hasattr(self, 'meter'):
            self._value = self.instrument.measure(self.meter)
            self.last_evaluation = time.time()

        elif hasattr(self, 'expression'):

            expression = self.expression
            expression = expression.replace('^', '**')  # carets represent exponents

            for symbol, variable in self.definitions.items():
                if variable._value is None:
                    expression = expression.replace(symbol, '(' + str(variable.value) + ')')  # evaluate the parent variable
                elif 'nan' in str(variable._value):
                    expression = 'np.nan'
                    break
                else:
                    expression = expression.replace(symbol, '(' + str(variable._value) + ')') # take the last known value

            for shorthand, longhand in self.expression_functions.items():
                if shorthand in expression:
                    expression = expression.replace(shorthand, longhand)

            try:
                self._value = eval(expression)
            except BaseException as err:
                print(f'Error while trying to evaluate expression {self.expression}:', err)
                self._value = float('nan')

            self.last_evaluation = time.time()

        elif hasattr(self, 'parameter'):

            try:
                self._value = float(self.parameter)  # try cast to float
            except ValueError:
                if self.parameter == 'True':  # try boolean type cast
                    self._value = True
                elif self.parameter == 'False':
                    self._value = False
                else:
                    self._value = self.parameter  # otherwise, keep as given

        return self._value

    @value.setter
    def value(self, value):
        # value property can only be set if variable is a knob; None or nan value indicates no setting should be applied
        if hasattr(self, 'knob') and value is not None and value is not np.nan:
            self.instrument.set(self.knob, value)
            self._value = self.instrument.__getattribute__(self.knob.replace(' ', '_'))
        elif hasattr(self, 'parameter'):
            self.parameter = value
        else:
            raise ValueError(f'Attempt to set {self.type}! Only knobs and parameters can be set.')


# Routines
class Routine:
    """
    Base class for all routines
    """

    def __init__(self, knobs=None, values=None, start=0, end=np.inf):
        """

        :param knobs: (Variable/1D array) knob variable(s) to be controlled
        :param values: (1D/2D array) array or list of values for each variable; can be 1D iff there is one knob
        :param start: (float) time to start the routine
        :param end: (float) time to end the routine
        """

        if knobs is not None:
            self.knobs = knobs  # dictionary of the form, {..., name: variable, ...}
            for knob in self.knobs.values():
                knob.controller = None  # for keeping track of which routines are controlling knobs

        if values is not None:

            if len(self.knobs) > 1:
                if np.ndim(values) == 1:  # single list of values for all knobs
                    values = [values]*len(self.knobs)
                elif np.shape(values)[0] == 1: # 1xN array with one N-element list of times for all knobs
                    values = [values[0]]*len(self.knobs)

            self.values = np.array(values, dtype=object).reshape((len(self.knobs), -1))

        self.start = convert_time(start)
        self.end = convert_time(end)

    def update(self, state):
        """
        Updates the knobs controlled by the routine

        :param state: (dict/Series) state of the calling experiment or process in the form, {..., variable: value, ...}
        :return: None
        """

        pass


class Set(Routine):
    """
    Sets and keeps knobs at fixed values
    """

    def update(self, state):

        if state['Time'] < self.start or state['Time'] > self.end:
            return  # no change

        for knob, value in zip(self.knobs.values(), self.values):

            if isinstance(value, Variable):
                knob.value = value._value
            else:
                knob.value = value[0]


class Timecourse(Routine):
    """
    Ramps linearly through a series of values at given times
    """

    def __init__(self, times=None, **kwargs):
        """

        :param times: (1D/2D array) array or list of times relative to the start time
        :param kwargs: keyword arguments for Routine
        """

        Routine.__init__(self, **kwargs)

        if times:

            if len(self.knobs) > 1:
                if np.ndim(times) == 1:  # single list of times for all knobs
                    times = [times]*len(self.knobs)
                elif np.shape(times)[0] == 1: # 1xN array with one N-element list of times for all knobs
                    times = [times[0]]*len(self.knobs)

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

        self.start = np.min(self.times)
        self.end = np.max(self.times)
        self.finished = False

    def update(self, state):

        if state['Time'] < self.start:
            return
        elif state['Time'] > self.end:
            if not self.finished:
                for knob, values in zip(self.knobs.values(), self.values):
                    if knob.controller == self:
                        knob.value = values[-1]  # make sure to set the end value

                    knob.controller = None

                self.finished = True

            return
        else:
            for name, knob in self.knobs.items():

                if isinstance(knob.controller, Routine) and knob.controller != self:
                    controller = knob.controller
                    if controller.start < state['Time'] < controller.end:
                        raise RuntimeError(f"Knob {name} has more than one controlling routine at time = {state['Time']} seconds!")
                else:
                    knob.controller = self

        for variable, times, values, i in zip(self.knobs.values(), self.times, self.values,  np.arange(len(self.times))):

            j_last = np.argwhere(times <= state['Time']).flatten()[-1]
            j_next = np.argwhere(times > state['Time']).flatten()[0]

            last_time = times[j_last]
            next_time = times[j_next]

            last_value = values[j_last]
            next_value = values[j_next]

            if isinstance(last_value, Variable):
                last_value = self.values[i, j_last] = last_value.value  # replace variable with value for past times

            if isinstance(next_value, Variable):
                value = last_value  # stay at last value until next time, when value variable will be evaluated
            else:
                # ramp linearly between numerical values
                value = last_value + (next_value - last_value) * (state['Time'] - last_time) / (next_time - last_time)

            variable.value = value


class Sequence(Routine):
    """
    Passes knobs through a series of values regardless of time; each series for each knob must have the same length
    """

    def __init__(self, **kwargs):
        Routine.__init__(self, **kwargs)

        self.iteration = 0

    def update(self, state):

        if state['Time'] < self.start or state['Time'] > self.end:
            return  # no change

        for knob, values in zip(self.knobs.values(), self.values):
            value = values[self.iteration]
            knob.value = value

        self.iteration = (self.iteration + 1) % len(self.values[0])


class Minimization(Routine):
    """
    Minimize the sum of a set of meters/expressions influenced by a set of knobs, using simulated annealing.
    """

    def __init__(self, meters=None, max_deltas=None, T0=0.1, T1=0, **kwargs):

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
        self.last_knobs = [np.nan]*len(self.knobs)
        self.last_meters = [np.nan]*len(self.meters)

    def update(self, state):

        # Get meter values
        meter_values = np.array([state[meter] for meter in self.meters])

        # Update temperature
        self.T = self.T0 + self.T1*(state['Time'] - self.start)/(self.end - self.start)

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
            change = np.sum(meter_values) - np.sum(self.last_meters)
            return (change < 0) or (np.exp(-change/self.T) > np.random.rand())
        else:
            return False


class Maximization(Minimization):
    """
    Maximize a set of meters/expressions influenced by a set of knobs; works the same way as Minimize.
    """

    def better(self, meter_values):

        if np.prod(self.last_meters) != np.nan:
            change = np.sum(meter_values) - np.sum(self.last_meters)
            return (change > 0) or (np.exp(change / self.T) > np.random.rand())
        else:
            return False


class ModelPredictiveControl(Routine):
    """
    (NOT IMPLEMENTED)
    Simple model predictive control; learns the relationship between knob x and meter y, assuming a linear model,

    y(t) = y0 + int_{-inf}^{t} dt' m(t-t') x(t')

    then sets x to minimize the error in y relative to setpoint, over some time interval defined by cutoff.

    """

    def __init__(self, meters=None, **kwargs):

        Routine.__init__(self, **kwargs)
        self.meters = meters

    def update(self, state):
        pass


class Alarm:
    """
    Triggers if a condition among variables is met and indicates the response protocol
    """

    def __init__(self, condition, variables, protocol=None):
        self.trigger_variable = Variable(expression=condition, definitions=variables)
        
        if protocol:
            self.protocol = protocol
        else:
            self.protocol = 'none'

    @property
    def triggered(self):
        return self.trigger_variable.value == True


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
        new_base_status = status.split(':')[0]

        # Only allow change if the status is unlocked, or if the base status is the same
        if not self.status_locked or new_base_status == prior_base_status:
            self._status = status

    @property
    def ready(self):
        return 'Ready' in self.status

    @property
    def running(self):
        return 'Running' in self.status

    @property
    def holding(self):
        return 'Holding' in self.status

    @property
    def stopped(self):
        return 'Stopped' in self.status

    @property
    def terminated(self):
        return 'Terminated' in self.status

    def __init__(self, variables, routines=None):

        self.variables = variables  # dict of the form {..., name: variable, ...}
        self.eval_events = {name: threading.Event() for name in variables}

        if routines:
            self.routines = routines  # dictionary of the form {..., name: (variable_name, routine), ...}
            self.end = max([routine.end for routine in routines.values()])  # time at which all routines are exhausted
        else:
            self.routines = {}
            self.end = float('inf')

        self.clock = Clock()
        self.clock.start()

        self.timestamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')

        self.data = pd.DataFrame(columns=['Time'] + list(variables.keys()))

        self.state = pd.Series({column: None for column in self.data.columns})
        self.state['Time'] = 0

        self._status = Experiment.READY
        self.status_locked = True  # can only be unlocked by the start, hold, stop and terminate methods

    def __next__(self):

        # Start the clock on first call
        if self.state.name is None:  # indicates that this is the first step of the experiment
            self.start()
            self.status = Experiment.RUNNING + ': initializing...'

        # Update time
        self.state['Time'] = self.clock.time
        self.state.name = datetime.datetime.now()

        # If experiment is stopped, just return the knob & parameter values, and nullify meter & expression values
        if Experiment.STOPPED in self.status:

            threads = {}
            for name, variable in self.variables.items():
                if variable.type in ['knob', 'parameter']:
                    threads[name] = threading.Thread(target=self._update_variable, args=(name,))
                    threads[name].start()
                else:
                    self.state[name] = None

            # Wait for all routine threads to finish
            for name, thread in threads.items():
                self.status = Experiment.RUNNING + f': retrieving {name}'
                thread.join()

            return self.state

        # If the experiment is running, apply new settings to knobs according to the routines (if there are any)
        if Experiment.RUNNING in self.status:

            # Update each routine in its own thread
            threads = {}
            for name, routine in self.routines.items():
                threads[name] = threading.Thread(target=self._update_routine, args=(name,))
                threads[name].start()

            # Wait for all routine threads to finish
            for name, thread in threads.items():
                self.status = Experiment.RUNNING + f': executing {name}'
                thread.join()

            self.status = Experiment.RUNNING

        # Get all variable values if experiment is running or holding
        if Experiment.RUNNING in self.status or Experiment.HOLDING in self.status:

            for event in self.eval_events.values():
                event.clear()

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
        """Retrieve and store a variable value"""

        try:

            if self.variables[name].type == 'expression':
                for dependee in self.variables[name].definitions:
                    event = self.eval_events[dependee]
                    event.wait()  # wait for dependee to be evaluated

            value = self.variables[name].value

            self.eval_events[name].set()  # unblock threads evaluating dependents

            if np.size(value) > 1:  # store array data as CSV files
                dataframe = pd.DataFrame({name: value}, index=[self.state.name] * len(value))
                path = name.replace(' ', '_') + '_' + self.state.name.strftime('%Y%m%d-%H%M%S') + '.csv'
                dataframe.to_csv(path)
                self.state[name] = path
            else:
                self.state[name] = value
        except BaseException as err:
            self.terminate()
            raise err

    def _update_routine(self, name):
        """Update a routine according to the current state"""

        try:
            self.routines[name].update(self.state)
        except BaseException as err:
            self.terminate()
            raise err

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

        if not hasattr(self, 'saved'):
            self.saved = []

        if not os.path.exists(path):  # if this is a new file, write column headers
            with open(path, 'a') as data_file:
                data_file.write(','+','.join(self.data.columns) +'\n')

        unsaved = np.setdiff1d(self.data.index, self.saved)

        with open(path, 'a') as data_file:
            for line in unsaved:
                line_data = ','.join(map(str, list(self.data.loc[line])))
                data_file.write(str(line)+','+line_data+'\n')

        self.saved = self.saved + list(unsaved)

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

    def hold(self, reason=None):
        """
        Hold the experiment: clock stops, routines stop, measurements continue

        :return: None
        """
        self.clock.stop()

        self.status_locked = False
        self.status = Experiment.HOLDING
        if reason:
            self.status = self.status + ': ' + reason
        self.status_locked = True

    def stop(self, reason=None):
        """
        Stop the experiment: clock stops, routines stop, measurements stop

        :return: None
        """
        self.clock.stop()

        self.status_locked = False
        self.status = Experiment.STOPPED
        if reason:
            self.status = self.status + ': ' + reason
        self.status_locked = True

    def terminate(self, reason=None):
        """
        Terminate the experiment: clock, routines and measurements stop, data is saved and StopIteration is raised

        :return: None
        """
        self.stop()
        self.save()

        self.status_locked = False
        self.status = Experiment.TERMINATED
        if reason:
            self.status = self.status + ': ' + reason
        self.status_locked = True

    @staticmethod
    def build(runcard, settings=None, instruments=None, alarms=None):
        """
        Build an Experiment object based on a runcard, in the form of a YAML file or a dictionary

        :param runcard: (dict/str) description of the experiment in the runcard format
        :param settings: (dict) dictionary of settings to be populated
        :param instruments: (dict) dictionary instruments to be populated
        :param alarms: (dict) dictionary of alarms to be populated

        :return: (Experiment) the experiment described by the runcard
        """

        if instruments is None:
            instruments = {}

        if type(runcard) == str:  # if runcard argument is a path to a YAML file

            dirname = os.path.dirname(runcard)
            if dirname != '':
                os.chdir(os.path.dirname(runcard))  # go to runcard directory to put data in same location

            yaml = YAML()
            with open(runcard, 'rb') as runcard_file:
                runcard = yaml.load(runcard_file)  # load the runcard into a dictionary

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
                    adapter_kwargs[kwarg] = specs.pop(kwarg.replace('_', ' '))

            # Any remaining keywords are instrument presets
            presets = specs.get('presets', {})
            postsets = specs.get('postsets', {})

            instrument_class = instr.__dict__[instrument_name]
            instruments[name] = instrument_class(address=address, presets=presets, postsets=postsets, **adapter_kwargs)
            instruments[name].name = name

        variables = {}  # experiment variables, associated with the instruments above
        for name, specs in runcard['Variables'].items():
            if 'meter' in specs:

                if specs['instrument'] not in instruments:
                    raise KeyError(f'instrument {specs["instrument"]} specificed for variable {name} not in Instruments!')

                variables[name] = Variable(meter=specs['meter'], instrument=instruments[specs['instrument']])
            elif 'knob' in specs:

                if specs['instrument'] not in instruments:
                    raise KeyError(f'instrument {specs["instrument"]} specificed for variable {name} not in Instruments!')

                variables[name] = Variable(knob=specs['knob'], instrument=instruments[specs['instrument']])
            elif 'expression' in specs:
                expression = specs['expression']
                definitions = {}

                for symbol, var_name in specs['definitions'].items():
                    expression = expression.replace(symbol, var_name)
                    definitions[var_name] = variables[var_name]

                variables[name] = Variable(expression=expression, definitions=definitions)
            elif 'parameter' in specs:
                variables[name] = Variable(parameter=specs['parameter'])

        routines = {}  # experiment routines

        builtin_routines = {routine.__name__: routine for routine in Routine.__subclasses__()} # standard routines

        if 'custom.py' in os.listdir(): # user can define custom routines in the runcard directory
            sys.path.insert(1, os.getcwd())
            cust_rout = importlib.import_module('custom')
            custom_routines = {
                routine.__name__: routine for routine in cust_rout.__dict__.values()
                if type(routine) is type and issubclass(routine, Routine)
            }
        else:
            custom_routines = {}

        available_routines = {**builtin_routines, **custom_routines}

        if 'Routines' in runcard:
            for name, specs in runcard['Routines'].items():
                specs = specs.copy()  # avoids modifying the runcard
                _type = specs.pop('type')

                knobs = np.array([specs.get('knobs', [])]).flatten()
                if knobs:
                    for knob in knobs:
                        if knob not in variables:
                            raise KeyError(f'knob {knob} specified for routine {name} is not in Variables!')

                    specs['knobs'] = {name: variables[name] for name in knobs}

                meters = np.array([specs.get('meters', [])]).flatten()
                if meters:
                    for meter in meters:
                        if meter not in variables:
                            raise KeyError(f'meter {meter} specified for routine {name} is not in Variables!')

                    specs['meters'] = {name: variables[name] for name in meters}

                if 'values' in specs:
                    specs['values'] = np.array(specs['values'], dtype=object).reshape((len(knobs), -1))

                    # Values can be variables, specified by their names
                    for var_name in variables:
                        where_variable = (specs['values'] == var_name)  # locate names of variables
                        specs['values'][where_variable] = variables[var_name]  # replace variable names with variables

                    # Values can be specified in a CSV file
                    def is_csv(item):
                        if type(item) == str:
                            return '.csv' in item
                        else:
                            return False

                    def get_csv(path, column):
                        df = pd.read_csv(path)
                        return df[column].values.flatten()

                    specs['values'] = np.array([
                        get_csv(values[0], knob) if is_csv(values[0]) else values
                        for knob, values in zip(specs['knobs'].keys(), specs['values'])
                    ], dtype=object)

                routines[name] = available_routines[_type](**specs)

        # Set up any alarms
        if 'Alarms' in runcard and alarms is not None:

            for name, specs in runcard['Alarms'].items():

                alarm_variables = specs.copy().get('variables',{})
                condition = specs.copy()['condition']

                for variable in specs.get('variables', {}):
                    if variable not in variables:
                        raise KeyError(f'variable {variable} specified for alarm {name} is not in Variables!')

                alphabet = 'abcdefghijklmnopqrstuvwxyz'
                for var_name, variable in variables.items():

                    # Variables can be called by name in the condition
                    if var_name in condition:
                        temp_name = ''.join([alphabet[np.random.randint(0, len(alphabet))] for i in range(3)])
                        while temp_name in alarm_variables:  # make sure temp_name is not repeated
                            temp_name = ''.join([alphabet[np.random.randint(0, len(alphabet))] for i in range(3)])

                        alarm_variables.update({temp_name: variable})
                        condition = condition.replace(var_name, temp_name)

                    # Otherwise, they are defined in the alarm_variables
                    for symbol, alarm_variable_name in alarm_variables.items():
                        if alarm_variable_name == var_name:
                            alarm_variables[symbol] = variable

                alarms.update({name: Alarm(condition, alarm_variables, protocol=specs.get('protocol', None))})

        experiment = Experiment(variables, routines=routines)

        if 'end' in settings:
            experiment.end = convert_time(settings['end'])

        return experiment


class Manager:
    """
    Utility class which sets up and manages experiments, based on runcards. When initallized, it uses the given runcard
    to construct an experiment and run it in a separate thread. The Manager also handles alarms as specified by the
    runcard.
    """

    def __init__(self, runcard=None):
        """

        :param runcard: (dict/str) runcard as a dictionary or path pointing to a YAML file
        """

        if runcard:
            self.runcard = runcard
        else:
            # Have user locate runcard, if none given
            root = tk.Tk()
            root.withdraw()
            self.runcard = askopenfilename(parent=root, title='Select Runcard', filetypes=[('YAML files', '*.yaml')])

            if self.runcard == '':
                raise ValueError('a valid runcard was not selected!')

        if isinstance(self.runcard, str) and os.path.exists(self.runcard):

            dirname = os.path.dirname(self.runcard)
            if dirname != '':
                os.chdir(os.path.dirname(self.runcard))  # go to runcard directory to put data in same location

            yaml = YAML()
            with open(self.runcard, 'rb') as runcard_file:
                self.runcard = yaml.load(runcard_file)  # load the runcard

        elif isinstance(self.runcard, dict):
            pass
        else:
            raise TypeError(f'runcard given to Manager must be a path to a YAML file or a dictionary, ' +
                            f'not {type(self.runcard)}!')

        # Build experiment
        self.settings = {}  # placeholder for the experiment settings; populated by Experiment.build below
        self.instruments = {}  # placeholder for the experiment instruments; populated below
        self.alarms = {}  # placeholder for the experiment alarms; populated below

        self.experiment = Experiment.build(self.runcard,
                                           settings=self.settings,
                                           instruments=self.instruments,
                                           alarms=self.alarms)

        # Unpack settings
        self.followup = self.settings.get('follow-up', None)
        self.step_interval = convert_time(self.settings.get('step interval', 0.1))
        self.save_interval = convert_time(self.settings.get('save interval', 60))
        self.plot_interval = convert_time(self.settings.get('plot interval', 0.1))

        self.last_save = 0

        self.awaiting_alarms = {}  # dictionary of alarms that are triggered

    def run(self, directory=None):
        """
        Run the experiment defined by the runcard. A GUI shows experiment status, while the experiment is run in a
        separate thread.

        :param directory: (path) (optional) directory in which to run the experiment if different from the working directory
        :return: None

        """

        top_dir = os.getcwd()

        if directory:
            os.chdir(directory)

        # Create a new directory for data storage
        experiment_name = self.runcard['Description'].get('name', 'Experiment')
        working_dir = experiment_name + '-' + self.experiment.timestamp
        os.mkdir(working_dir)
        os.chdir(working_dir)

        # Save executed runcard alongside data for record keeping
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
        if self.followup in [None, 'None'] or 'user terminated' in self.experiment.status:
            return
        elif 'yaml' in self.followup:
            self.__init__(self.followup)
            self.run(directory=directory)
        elif 'repeat' in self.followup:
            self.__init__(self.runcard)
            self.run(directory=directory)

    def _run(self):
        # Run in a separate thread

        for state in self.experiment:

            step_start = time.time()

            # Save experimental data periodically
            if self.experiment.clock.time >= self.last_save + self.save_interval:
                save_thread = threading.Thread(target=self.experiment.save)
                save_thread.start()
                self.last_save = self.experiment.clock.time

            # Check if any alarms are triggered and handle them
            for name, alarm in self.alarms.items():
                if alarm.triggered:

                    # Add to dictionary of triggered alarms
                    self.awaiting_alarms[name] = {
                        'time': self.experiment.data['Time'],
                        'status': self.experiment.status,
                    }
                    
                    if 'none' in alarm.protocol:
                        # do nothing (but GUI will indicate that alarm is triggered)
                        break
                    if 'hold' in alarm.protocol:
                        # stop routines but keep measuring, and wait for alarm to clear
                        self.experiment.hold(reason=name)
                        break
                    elif 'stop' in alarm.protocol:
                        # stop routines and measurements, and wait for alarm to clear
                        self.experiment.stop(reason=name)
                        break
                    elif 'terminate' in alarm.protocol:
                        # terminate the experiment
                        self.experiment.terminate(reason=name)
                        break
                    elif 'yaml' in alarm.protocol:
                        # terminate the experiment and run another
                        self.experiment.terminate(reason=name)
                        self.followup = alarm.protocol
                        break
                    elif 'check' in alarm.protocol:
                        # stop routines and measurements, and wait for the user to resume
                        self.experiment.stop(reason=name)
                        break
                    else:
                        # terminate the experiment
                        self.experiment.terminate(reason=name)
                        break

                elif name in self.awaiting_alarms:
                    # Alarm was previously triggered but is now clear

                    if 'check' not in alarm.protocol: # alarm is not waiting for user to check

                        info = self.awaiting_alarms.pop(name)  # remove from dictionary of triggered alarms
                        prior_status = info['status']

                        if len(self.awaiting_alarms) == 0:
                            # there are no more triggered alarms; return to state of experiment prior to trigger
                            if 'Running' in prior_status:
                                self.experiment.start()
                            if 'Holding' in prior_status:
                                self.experiment.hold(reason=name+' cleared')
                            if 'Stopped' in prior_status:
                                self.experiment.stop(reason=name+' cleared')

            step_end = time.time()
            remaining_time = np.max([self.step_interval - (step_end - step_start), 0])
            time.sleep(remaining_time)
