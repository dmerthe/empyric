# This submodule defines the basic behavior of the key features of the
# empyric package
import collections
import datetime
import importlib
import numbers
import os
import pathlib
import socket
import sys
import threading
import time
import tkinter as tk
from tkinter.filedialog import askopenfilename

import numpy as np
import pandas as pd
import pykwalify.errors
from pykwalify.core import Core as YamlValidator
from ruamel.yaml import YAML

from empyric import adapters as _adapters
from empyric import graphics as _graphics
from empyric import instruments as _instruments
from empyric import routines as _routines
from empyric.tools import convert_time, Clock, recast, write_to_socket, \
    read_from_socket


class Variable:
    """
    Basic representation of an experimental variable that comes in 4 kinds:
    knob, meter, expression and parameter.

    A knob is a variable that can be directly controlled by an instrument, e.g.
    the voltage of a power supply.

    A meter is a variable that is measured by an instrument, such as
    temperature. Some meters can be controlled directly or indirectly through
    an associated (but distinct) knob.

    An expression is a variable that is not directly measured, but is
    calculated based on other variables of the experiment. An example of an
    expression is the output power of a power supply, where voltage is a knob
    and current is a meter: power = voltage * current.

    A remote variable is a variable controlled by an experiment (running a
    server) on a different process or computer.

    A parameter is a variable whose value is assigned directly by the user. An
    example is a unit conversion factor such as 2.54 cm per inch, a numerical
    constant like pi or a setpoint for a control routine.

    The value types of variables are either numbers (floats and/or integers),
    booleans, strings or arrays (containing some combination of the previous
    three types).
    """

    # Abbreviated functions that can be used to evaluate expression variables
    # parentheses are included to facilitate search for functions in expressions
    expression_functions = {
        'sqrt(': 'np.sqrt(',
        'exp(': 'np.exp(',
        'sin(': 'np.sin(',
        'cos(': 'np.cos(',
        'tan(': 'np.tan(',
        'sum(': 'np.nansum(',
        'mean(': 'np.nanmean(',
        'rms(': 'np.nanstd(',
        'std(': 'np.nanstd(',
        'var(': 'np.nanvar(',
        'diff(': 'np.diff(',
        'max(': 'np.nanmax(',
        'min(': 'np.nanmin('
    }

    def __init__(self,
                 # Knobs and meters
                 instrument=None, knob=None, meter=None,
                 lower_limit=-np.inf, upper_limit=np.inf,

                 # Expressions
                 expression=None, definitions=None,

                 # Remote variables
                 remote=None, alias=None, protocol=None, dtype=None,
                 settable=False,

                 # Parameters
                 parameter=None
                 ):
        """
        For knobs or meters, either an instrument or a server argument must be
        given.

        If an expression is given with symbols/terms representing other
        variables, that mapping must be specified in the definitions argument.

        :param instrument: (Instrument) instrument with the corresponding knob
        or meter
        :param knob: (str) instrument knob label, if variable is a knob
        :param meter: (str) instrument meter label, if variable is a meter

        :param expression: (str) expression for the variable in terms of other
        variables, if variable is an expression
        :param definitions: (dict) dictionary of the form {..., symbol:
        variable, ...} mapping the symbols in the expression to other variable
        objects; only used if type is 'expression'

        :param remote: (str) address of the server of the variable controlling
        the variable, in the form '[host name/ip address]::[port]'.
        :param alias: (str) For a SocketServer, the name of the variable on the
        server; for a ModbusServer, the register address of the variable.
        :param protocol: (str) server communication protocol; set to 'modbus'
        if the server is a `ModbusServer`, otherwise no protocol (default)
        implies that the server is a `SocketServer`.
        :param dtype: (str) the data type of the remote variable. It is only
        relevant for ModbusServer variables which can be either boolean,
        integer or float.

        :param parameter (str) value of a user controlled parameter
        """

        self._value = None  # last known value of this variable

        if meter:
            self.meter = meter
            self.type = 'meter'
            self.settable = False

        elif knob:
            self.knob = knob
            self.type = 'knob'
            self.settable = True
            self.lower_limit = lower_limit
            self.upper_limit = upper_limit

        elif expression:
            self.expression = expression
            self.type = 'expression'
            self.settable = False

            if definitions:
                self.definitions = definitions
            else:
                self.definitions = {}

        elif remote:
            self.remote = remote
            self.alias = alias
            self.protocol = protocol
            self.dtype = '32bit_float' if dtype is None else dtype
            self.type = 'remote'

            if protocol == 'modbus':
                self._client = _instruments.ModbusClient(remote)
                self.settable = settable
            else:
                remote_ip, remote_port = remote.split('::')

                self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

                self._socket.connect((remote_ip, int(remote_port)))

                write_to_socket(self._socket, f'{self.alias} settable?')

                response = read_from_socket(self._socket, timeout=None)

                self.settable = response == f'{self.alias} settable'

        elif parameter:
            self.parameter = parameter
            self._value = parameter
            self.type = 'parameter'
            self.settable = True

        else:
            raise ValueError(
                'variable object must have a specified knob, meter or '
                'expression, or assigned a value if a parameter!'
            )

        # time of last evaluation; used for expressions
        self.last_evaluation = np.nan

        # Check that knob or meter has been assigned an instrument
        if hasattr(self, 'knob') or hasattr(self, 'meter'):
            if not instrument:
                raise AttributeError(
                    f'{self.type} variable definition requires an instrument!'
                )
            self.instrument = instrument

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

            # carets represent exponents
            expression = expression.replace('^', '**')

            expr_vals = {}
            for symbol, variable in self.definitions.items():
                # take last known value

                expr_vals[symbol] = variable._value

                expression = expression.replace(
                    symbol, f"expr_vals['{symbol}']"
                )

            for shorthand, longhand in self.expression_functions.items():
                if shorthand in expression:
                    expression = expression.replace(shorthand, longhand)

            try:
                if 'None' not in expression and 'nan' not in expression:
                    self._value = eval(expression)
                else:
                    self._value = None
            except BaseException as err:
                print(f'Unable to evaluate expression {self.expression}:', err)
                self._value = None

            self.last_evaluation = time.time()

        elif hasattr(self, 'remote'):

            if self.protocol == 'modbus':

                fcode = 3 if self.settable else 4

                self._value = self._client.read(
                    fcode, self.alias, count=2, dtype=self.dtype
                )

            else:
                write_to_socket(self._socket, f'{self.alias} ?')

                response = read_from_socket(self._socket)

                try:
                    self._value = recast(response.split(' ')[-1])
                except BaseException as error:
                    print(
                        f'Warning: unable to retrieve value of {self.alias} '
                        f'from server at {self.remote}; got error "{error}"'
                    )

        elif hasattr(self, 'parameter'):

            self._value = recast(self.parameter)

        return self._value

    @value.setter
    def value(self, value):

        if value is None:
            # Do nothing if value is null
            pass

        elif isinstance(value, numbers.Number) and np.isnan(value):
            pass

        elif hasattr(self, 'knob'):

            if value > self.upper_limit:
                self.instrument.set(self.knob, self.upper_limit)
            elif value < self.lower_limit:
                self.instrument.set(self.knob, self.lower_limit)
            else:
                self.instrument.set(self.knob, value)

            self._value = self.instrument.__getattribute__(
                self.knob.replace(' ', '_')
            )

        elif hasattr(self, 'remote') and self.settable:

            if self.protocol == 'modbus':

                self._client.write(16, self.alias, value, dtype=self.dtype)

            else:
                write_to_socket(self._socket, f'{self.alias} {value}')

                check = read_from_socket(self._socket)

                if check == '' or check is None:
                    print(
                        f'Warning: received no response from server at '
                        f'{self.remote} while trying to set {self.alias}'
                    )
                elif 'Error' in check:
                    print(
                        f'Warning: got response "{check}" while trying to set '
                        f'{self.alias} on server at {self.remote}'
                    )
                else:
                    try:

                        check_value = recast(check.split(f'{self.alias} ')[1])

                        if value != check_value:
                            print(
                                f'Warning: attempted to set {self.alias} on '
                                f'server at {self.remote} to {value} but '
                                f'checked value is {check_value}'
                            )

                    except ValueError as val_err:
                        print(
                            f'Warning: unable to check value while setting '
                            f'{self.alias} on server at {self.remote}; '
                            f'got error "{val_err}"'
                        )
                    except IndexError as ind_err:
                        print(
                            f'Warning: unable to check value while setting '
                            f'{self.alias} on server at {self.remote}; '
                            f'got error "{ind_err}"'
                        )

        elif hasattr(self, 'parameter'):
            self.parameter = value

        else:
            raise ValueError(
                f'Attempt to set {self.type}! '
                'Only knobs and parameters can be set.'
            )

    def __repr__(self):
        return self.type[0].upper() + self.type[1:] + 'Variable'

    def __del__(self):

        if hasattr(self, 'remote'):
            if self.protocol == 'modbus':
                self._client.disconnect()
            else:
                self._socket.shutdown(socket.SHUT_RDWR)
                self._socket.close()


class Experiment:
    """
    An iterable class which represents an experiment; iterates through any
    assigned routines,and retrieves and stores the values of all experiment
    variables.
    """

    # Possible statuses of an experiment
    READY = 'Ready'  # Experiment is waiting to start
    RUNNING = 'Running'  # Experiment is running
    HOLDING = 'Holding'  # Routines are stopped, but measurements are ongoing
    STOPPED = 'Stopped'  # Both routines and measurements are stopped
    TERMINATED = 'Terminated'

    # Experiment has either finished or has been terminated by the user

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, status):
        prior_base_status = self._status.split(':')[0]
        new_base_status = status.split(':')[0]

        # Only allow change if the status is unlocked,
        # or if the base status is the same
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

    def __init__(self, variables, routines=None, end=None):

        self.variables = variables
        # dict of the form {..., name: variable, ...}

        # Used to block evaluation of expressions
        # until their dependee variables are evaluated
        self.eval_events = {name: threading.Event() for name in variables}

        if routines:
            self.routines = routines
            # dictionary of the form {..., name: (variable_name, routine), ...}
        else:
            self.routines = {}

        if end:
            if end.lower() == 'with routines':
                self.end = max([routine.end for routine in routines.values()])
            else:
                self.end = end
        else:
            self.end = np.inf

        self.clock = Clock()
        self.clock.start()

        self.timestamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')

        self.data = pd.DataFrame(columns=['Time'] + list(variables.keys()))

        self.state = pd.Series({column: None for column in self.data.columns})
        self.state['Time'] = 0

        self._status = Experiment.READY
        self.status_locked = True
        # can only be unlocked by the start, hold, stop and terminate methods

        self.saved = []  # list of saved data entries

    def __next__(self):

        # Start the clock on first call
        if self.state.name is None:  # first step of the experiment
            self.start()
            self.status = Experiment.RUNNING + ': initializing...'

        # Update time
        self.state['Time'] = self.clock.time
        self.state.name = datetime.datetime.now()

        # If experiment is stopped, just return the knob & parameter values,
        # and nullify meter & expression values
        if self.stopped:

            threads = {}
            for name, variable in self.variables.items():
                if variable.type in ['knob', 'parameter']:
                    threads[name] = threading.Thread(
                        target=self._update_variable, args=(name,)
                    )
                    threads[name].start()
                else:
                    self.state[name] = None

            # Wait for all routine threads to finish
            for name, thread in threads.items():
                self.status = Experiment.RUNNING + f': retrieving {name}'
                thread.join()

            return self.state

        # If the experiment is running, apply new settings to knobs
        # according to the routines (if there are any)
        if self.running:

            # Update each routine in its own thread
            threads = {}
            for name, routine in self.routines.items():
                threads[name] = threading.Thread(
                    target=self._update_routine, args=(name,)
                )
                threads[name].start()

            # Wait for all routine threads to finish
            for name, thread in threads.items():
                self.status = Experiment.RUNNING + f': executing {name}'
                thread.join()

            self.status = Experiment.RUNNING

        # Get all variable values if experiment is running or holding
        if self.running or self.holding:

            for event in self.eval_events.values():
                event.clear()

            # Run each measure / get operation in its own thread
            threads = {}
            for name in self.variables:
                threads[name] = threading.Thread(
                    target=self._update_variable, args=(name,)
                )
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

        if self.terminated:
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

            self.eval_events[name].set()
            # unblock threads evaluating dependents

            if np.size(value) > 1:  # store array data as CSV files
                dataframe = pd.DataFrame(
                    {name: value}, index=[self.state.name] * len(value)
                )
                path = name.replace(' ', '_') + '_'
                path += self.state.name.strftime('%Y%m%d-%H%M%S') + '.csv'
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

        :param directory: (path) (optional) directory to save data to,
        if different from working directory
        :return: None
        """

        base_status = self.status
        self.status = base_status + ': saving data'

        path = f"data_{self.timestamp}.csv"

        if directory:
            path = os.path.join(directory, path)

        if not os.path.exists(path):
            # if this is a new file, write column headers
            with open(path, 'a') as data_file:
                data_file.write(',' + ','.join(self.data.columns) + '\n')

        unsaved = np.setdiff1d(self.data.index, self.saved)

        with open(path, 'a') as data_file:
            for line in unsaved:
                line_data = ','.join(map(str, list(self.data.loc[line])))
                data_file.write(str(line) + ',' + line_data + '\n')

        self.saved = self.saved + list(unsaved)

        self.status = base_status

    def start(self):
        """
        Start the experiment: clock starts/resumes, routines resume,
        measurements continue

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
        Terminate the experiment: clock, routines and measurements stop,
        data is saved and StopIteration is raised

        :return: None
        """
        self.stop()
        self.save()

        self.status_locked = False
        self.status = Experiment.TERMINATED
        if reason:
            self.status = self.status + ': ' + reason
        self.status_locked = True

        # End routines
        for routine in self.routines.values():
            routine.terminate()

    def __repr__(self):
        return 'Experiment'


class Alarm:
    """
    Triggers if a condition among variables is met and indicates the response
    protocol
    """

    def __init__(self, condition, variables, protocol=None):
        self.trigger_variable = Variable(
            expression=condition, definitions=variables
        )

        if protocol:
            self.protocol = protocol
        else:
            self.protocol = 'none'

    @property
    def triggered(self):
        return self.trigger_variable.value is True

    def __repr__(self):
        return 'Alarm'


class Manager:
    """
    Utility class which sets up and manages experiments, based on runcards.
    When initallized, it uses the given runcard to construct an experiment and
    run it in a separate thread. The Manager also handles alarms as specified
    by the runcard.
    """

    def __init__(self, runcard=None):
        """
        :param runcard: (dict/str) runcard as a dictionary or path pointing to
        a YAML file
        """

        if runcard:
            self.runcard = runcard
        else:
            # Have user locate runcard, if none given
            root = tk.Tk()
            root.withdraw()
            self.runcard = askopenfilename(
                parent=root, title='Select Runcard',
                filetypes=[('YAML files', '*.yaml')]
            )

            if self.runcard == '':
                raise ValueError('a valid runcard was not selected!')

        if isinstance(self.runcard, str) and os.path.exists(self.runcard):

            dirname = os.path.dirname(self.runcard)
            if dirname != '':
                os.chdir(os.path.dirname(self.runcard))
                # go to runcard directory to put data in same location

            yaml = YAML()
            with open(self.runcard, 'rb') as runcard_file:
                self.runcard = yaml.load(runcard_file)  # load the runcard

        elif isinstance(self.runcard, dict):
            pass
        else:
            raise TypeError(
                f'runcard given to Manager must be a path to a YAML file '
                f'or a dictionary, not {type(self.runcard)}!'
            )

        converted_runcard = convert_runcard(self.runcard)

        self.description = converted_runcard['Description']
        self.settings = converted_runcard['Settings']
        self.instruments = converted_runcard['Instruments']
        self.alarms = converted_runcard['Alarms']
        self.plotter = converted_runcard['Plotter']

        self.experiment = converted_runcard['Experiment']

        # Unpack settings
        self.followup = self.settings.get('follow-up', None)
        self.step_interval = convert_time(
            self.settings.get('step interval', 0.1)
        )
        self.save_interval = convert_time(
            self.settings.get('save interval', 60)
        )
        self.plot_interval = convert_time(
            self.settings.get('plot interval', 0.1)
        )
        self.end = convert_time(self.settings.get('end', np.inf))

        self.experiment.end = self.end

        self.last_save = 0

        self.awaiting_alarms = {}  # dictionary of alarms that are triggered

    def run(self, directory=None):
        """
        Run the experiment defined by the runcard. A GUI shows experiment
        status, while the experiment is run in a separate thread.

        :param directory: (path) (optional) directory in which to run the
        experiment if different from the working directory
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

        timestamped_path = f"{experiment_name}_{self.experiment.timestamp}.yaml"
        with open(timestamped_path, 'w') as runcard_file:
            yaml.dump(self.runcard, runcard_file)

        # Run experiment loop in separate thread
        experiment_thread = threading.Thread(target=self._run)
        experiment_thread.start()

        # Set up the GUI for user interaction
        self.gui = _graphics.ExperimentGUI(self.experiment,
                                           alarms=self.alarms,
                                           instruments=self.instruments,
                                           title=self.description.get(
                                               'name', 'Experiment'
                                           ),
                                           plotter=self.plotter,
                                           save_interval=self.save_interval,
                                           plot_interval=self.plot_interval)

        self.gui.run()

        experiment_thread.join()

        # Disconnect instruments
        for instrument in self.instruments.values():
            instrument.disconnect()

        os.chdir(top_dir)  # return to the parent directory

        # Cancel follow-up if experiment terminated by user
        if self.experiment.terminated and 'user' in self.experiment.status:
            self.followup = None

        # Execute the follow-up experiment if there is one
        if self.followup:
            if 'yaml' in self.followup:
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
            next_save = self.last_save + self.save_interval
            if self.experiment.clock.time >= next_save:
                save_thread = threading.Thread(target=self.experiment.save)
                save_thread.start()
                self.last_save = self.experiment.clock.time

            # Check if any alarms are triggered and handle them
            for name, alarm in self.alarms.items():
                if alarm.triggered:

                    # Add to dictionary of triggered alarms, if newly triggered
                    if name not in self.awaiting_alarms:
                        self.awaiting_alarms[name] = {
                            'time': self.experiment.data['Time'].iloc[-1],
                            'status': self.experiment.status,
                        }

                    if 'none' in alarm.protocol:
                        # do nothing (GUI will indicate that alarm is triggered)
                        break
                    if 'hold' in alarm.protocol:
                        # stop routines but keep measuring until alarm is clear
                        self.experiment.hold(reason=name)
                        break
                    elif 'stop' in alarm.protocol:
                        # stop routines and measurements until alarm is clear
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
                        # stop routines and measurements until user resumes
                        self.experiment.stop(reason=name)
                        break
                    else:
                        # terminate the experiment
                        self.experiment.terminate(reason=name)
                        break

                elif name in self.awaiting_alarms:
                    # Alarm was previously triggered but is now clear

                    if 'check' not in alarm.protocol:
                        # alarm is not waiting for user to check

                        info = self.awaiting_alarms.pop(name)
                        # remove from dictionary of triggered alarms
                        prior_status = info['status']

                        if len(self.awaiting_alarms) == 0:
                            # there are no more triggered alarms
                            # return to state of experiment prior to trigger
                            if 'Running' in prior_status:
                                self.experiment.start()
                            if 'Holding' in prior_status:
                                self.experiment.hold(reason=name + ' cleared')
                            if 'Stopped' in prior_status:
                                self.experiment.stop(reason=name + ' cleared')

            step_end = time.time()

            remaining_time = self.step_interval - (step_end - step_start)

            if remaining_time > 0:
                time.sleep(remaining_time)

    def __repr__(self):
        return 'Manager'


class RuncardError(BaseException):
    pass


def validate_runcard(runcard):
    is_dict = isinstance(runcard, dict)
    is_ordereddict = isinstance(runcard, collections.OrderedDict)

    if is_dict or is_ordereddict:
        # create temporary runcard YAML file
        yaml = YAML()

        runcard_path = f'tmp_runcard_{time.time()}.yaml'

        with open(runcard_path, 'w') as runcard_file:
            yaml.dump(runcard, runcard_file)

        validate_runcard(runcard_path)

        os.remove(runcard_path)

        return True

    elif type(runcard) is not str:
        raise ValueError('runcard must be either dict or str.')

    validator = YamlValidator(
        source_file=runcard,
        schema_files=[
            os.path.join(pathlib.Path(__file__).parent, "runcard_schema.yaml")
        ]
    )

    try:
        validator.validate(raise_exception=True)
    except pykwalify.errors.SchemaError as err:
        raise RuncardError(err)

    return True


def convert_runcard(runcard):
    """
    :param runcard: (dict/str) runcard dictionary or path string

    :return: (dict) converted runcard in the form described below.

    Converts the sections into the relevant objects:

    * The Descriptions and Settings sections are unchanged.
    * The Instruments section is converted into a dictionary of corresponding
      ``Instrument`` instances.
    * The Variables and Routines sections are combined into an ``Experiment``
      instance.
    * The Alarms section is  converted into a dictionary of corresponding
      ``Alarm`` objects.
    * The Plots section is converted into a corresponding ``Plotter`` instance.
    """

    # if runcard argument is a path to a YAML file, load into a dictionary
    if type(runcard) == str:
        yaml = YAML()
        with open(runcard, 'rb') as runcard_file:
            runcard = yaml.load(runcard_file)

    # Validate runcard format and contents
    validate_runcard(runcard)

    converted_runcard = runcard.copy()

    # Load any custom components
    custom_routines = {}
    custom_instruments = {}

    if 'custom.py' in os.listdir():
        sys.path.insert(1, os.getcwd())
        custom = importlib.import_module('custom')

        for name, thing in custom.__dict__.items():
            if type(thing) == type:
                if issubclass(thing, _routines.Routine):
                    custom_routines[name] = thing
                if issubclass(thing, _instruments.Instrument):
                    custom_instruments[name] = thing

    # Instruments section
    available_instruments = {**_instruments.supported, **custom_instruments}

    instruments = {}
    for name, specs in runcard.get('Instruments', {}).items():

        specs = specs.copy()
        _type = specs.pop('type')
        address = specs.get('address', None)

        # Grab any keyword arguments for the adapter
        adapter_kwargs = {}
        for kwarg in _adapters.kwargs:
            if kwarg.replace('_', ' ') in specs:
                adapter_kwargs[kwarg] = specs.pop(kwarg.replace('_', ' '))

        # Any remaining keywords are instrument presets
        presets = {
            key: recast(value) for key, value
            in specs.get('presets', {}).items()
        }
        postsets = {
            key: recast(value) for key, value
            in specs.get('postsets', {}).items()
        }

        instrument_class = available_instruments[_type]
        instruments[name] = instrument_class(
            address=address, presets=presets, postsets=postsets,
            **adapter_kwargs
        )
        instruments[name].name = name

    converted_runcard['Instruments'] = instruments

    # Variables section
    variables = {}
    for name, specs in runcard['Variables'].items():
        if 'meter' in specs:
            instrument = converted_runcard['Instruments'][specs['instrument']]
            variables[name] = Variable(
                meter=specs['meter'], instrument=instrument
            )
        elif 'knob' in specs:
            instrument = converted_runcard['Instruments'][specs['instrument']]
            variables[name] = Variable(
                knob=specs['knob'], instrument=instrument,
                lower_limit=specs.get('lower limit', -np.inf),
                upper_limit=specs.get('upper limit', np.inf)
            )
        elif 'expression' in specs:
            expression = specs['expression']
            definitions = {}

            for symbol, var_name in specs['definitions'].items():
                expression = expression.replace(symbol, var_name)

                try:
                    definitions[var_name] = variables[var_name]
                except KeyError as undefined:
                    raise KeyError(f"variable {undefined} is not defined for expression '{name}'")

            variables[name] = Variable(
                expression=expression, definitions=definitions
            )
        elif 'remote' in specs:
            remote = specs['remote']
            alias = specs.get('alias', name)
            protocol = specs.get('protocol', None)
            dtype = specs.get('dtype', None)
            settable = specs.get('settable', False)

            variables[name] = Variable(
                remote=remote, alias=alias, protocol=protocol,
                dtype=dtype, settable=settable
            )

        elif 'parameter' in specs:
            variables[name] = Variable(parameter=specs['parameter'])

    # Routines section
    available_routines = {**_routines.supported, **custom_routines}

    routines = {}
    if 'Routines' in runcard:
        for name, specs in runcard['Routines'].items():
            specs = specs.copy()  # avoids modifying the runcard
            _type = specs.pop('type')

            specs = {
                key.replace(' ', '_'): value for key, value in specs.items()
            }

            # For Set, Timecourse and Sequence routines
            knobs = np.array([specs.get('knobs', [])]).flatten()
            if knobs.size > 0:
                for knob in knobs:
                    if knob not in variables:
                        raise KeyError(
                            f'knob {knob} specified for routine {name} '
                            'is not in Variables!'
                        )

                specs['knobs'] = {name: variables[name] for name in knobs}

            meters = np.array([specs.get('meters', [])]).flatten()
            if meters.size > 0:
                for meter in meters:
                    if meter not in variables:
                        raise KeyError(
                            f'meter {meter} specified for routine {name} '
                            f'is not in Variables!'
                        )

                specs['meters'] = {name: variables[name] for name in meters}

            if 'values' in specs:
                specs['values'] = np.array(
                    specs['values'], dtype=object
                ).reshape((len(knobs), -1))

                # Values can be variables, specified by their names
                for var_name in variables:
                    where_variable = (specs['values'] == var_name)
                    # locate names of variables

                    specs['values'][where_variable] = variables[var_name]
                    # replace variable names with variables

                # Values can be specified in a CSV file
                def is_csv(item):
                    if type(item) == str:
                        return '.csv' in item
                    else:
                        return False

                def get_csv(path, column):
                    df = pd.read_csv(recast(path))
                    return df[column].values.flatten()

                specs['values'] = np.array([
                    get_csv(values[0], knob) if is_csv(values[0])
                    else values for knob, values
                    in zip(specs['knobs'].keys(), specs['values'])
                ], dtype=object)

            # For Server routines
            readwrite = np.array([specs.get('readwrite', [])]).flatten()
            if readwrite.size > 0:
                for variable in readwrite:
                    if variable not in variables:
                        raise KeyError(
                            f'Variable {variable} specified for routine {name} '
                            'is not in Variables!'
                        )

                specs['readwrite'] = {
                    name: variables[name] for name in readwrite
                }

            readonly = np.array([specs.get('readonly', [])]).flatten()
            if readonly.size > 0:
                for variable in readonly:
                    if variable not in variables:
                        raise KeyError(
                            f'Variable {variable} specified for routine {name} '
                            'is not in Variables!'
                        )

                specs['readonly'] = {
                    name: variables[name] for name in readonly
                }

            if 'Server' in _type and len(readonly) == 0 and len(readwrite) == 0:
                # Give readonly access to all variables if no variables
                # specified
                specs['readonly'] = variables

            routines[name] = available_routines[_type](**specs)

    converted_runcard['Experiment'] = Experiment(variables, routines=routines)

    # Alarms section
    alarms = {}
    if 'Alarms' in runcard:
        for name, specs in runcard['Alarms'].items():

            alarm_variables = specs.copy().get('variables', {})
            condition = specs.copy()['condition']

            for variable in specs.get('variables', {}):
                if variable not in variables:
                    raise KeyError(
                        f'variable {variable} specified for alarm {name} '
                        f'is not in Variables!'
                    )

            alphabet = 'abcdefghijklmnopqrstuvwxyz'
            for var_name, variable in variables.items():

                # Variables can be called by name in the condition
                if var_name in condition:
                    temp_name = ''.join(
                        [
                            alphabet[np.random.randint(0, len(alphabet))]
                            for i in range(3)
                        ]
                    )
                    while temp_name in alarm_variables:
                        # make sure temp_name is not repeated
                        temp_name = ''.join(
                            [
                                alphabet[np.random.randint(0, len(alphabet))]
                                for i in range(3)
                            ]
                        )

                    alarm_variables.update({temp_name: variable})
                    condition = condition.replace(var_name, temp_name)

                # Otherwise, they are defined in the alarm_variables
                for symbol, alarm_variable_name in alarm_variables.items():
                    if alarm_variable_name == var_name:
                        alarm_variables[symbol] = variable

            alarms.update(
                {
                    name: Alarm(
                        condition,
                        alarm_variables,
                        protocol=specs.get('protocol', None)
                    )
                }
            )

    converted_runcard['Alarms'] = alarms

    # Plots section
    if 'Plots' in runcard:
        converted_runcard['Plotter'] = _graphics.Plotter(
            converted_runcard['Experiment'].data, settings=runcard['Plots']
        )
    else:
        converted_runcard['Plotter'] = None

    return converted_runcard
