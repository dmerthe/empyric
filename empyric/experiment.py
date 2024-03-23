# Tools for defining and running experiments
import asyncio
import collections
import datetime
import importlib
import logging
import numbers
import os
import pathlib
import sys
import threading
import time
import tkinter as tk
from tkinter.filedialog import askopenfilename
from typing import Union

import numpy as np
import pandas as pd
import pykwalify.errors
from pykwalify.core import Core as YamlValidator
from ruamel.yaml import YAML

from empyric import variables as _variables
from empyric import adapters as _adapters
from empyric import graphics as _graphics
from empyric import instruments as _instruments
from empyric import routines as _routines
from empyric.adapters import AdapterError
from empyric.tools import convert_time, Clock
from empyric.types import recast, Boolean, Toggle, Integer, Float, ON

logger = logging.getLogger()


class Experiment:
    """
    An iterable class which represents an experiment; iterates through any
    assigned routines, and retrieves and stores the values of all experiment
    variables. Each variable and routine is updated once per iteration, and each
    iteration blocks until all variables and routines are updated.

    The constructor take a `variables` argument in the form of a dictionary with the
    format {..., name: variable, ...}, which contains all of the variables controlled
    and monitored by the experiment. The optional `routines` argument is a dictionary
    of the form {..., name: routine, ...} containing any routines to run within
    the loop of the experiment. The optional `end` argument indicates when the
    experiment should end (i.e. raise `StopIteration` on subsequent call to `__next__`)
    , and can either be a number, a string of the form "[number] [time unit, e.g.
    seconds, minutes or hours]" or "with routines" to end the experiment after the
    last routine has ended.
    """

    # Possible statuses of an experiment
    READY = "Ready"  # Experiment is waiting to start
    RUNNING = "Running"  # Experiment is running
    HOLDING = "Holding"  # Routines are stopped, but measurements are ongoing
    STOPPED = "Stopped"  # Both routines and measurements are stopped
    TERMINATED = "Terminated"

    # Experiment has either finished or has been terminated by the user

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, status):
        prior_base_status = self._status.split(":")[0]
        new_base_status = status.split(":")[0]

        # Only allow change if the status is unlocked,
        # or if the base status is the same
        if not self.status_locked or new_base_status == prior_base_status:
            self._status = status

    @property
    def ready(self):
        return "Ready" in self.status

    @property
    def running(self):
        return "Running" in self.status

    @property
    def holding(self):
        return "Holding" in self.status

    @property
    def stopped(self):
        return "Stopped" in self.status

    @property
    def terminated(self):
        return "Terminated" in self.status

    def __init__(
            self,
            variables: dict,
            routines: dict = None,
            end: Union[numbers.Number, str, None] = None,
    ):
        self.variables = variables
        # dict of the form {..., name: variable, ...}

        # Used to block evaluation of expressions
        # until their dependee variables are evaluated
        for variable in self.variables.values():
            variable._eval_event = threading.Event()

        if routines:
            self.routines = routines
            # dictionary of the form {..., name: (variable_name, routine), ...}
        else:
            self.routines = {}

        if end:
            if type(end) is str:
                if end.lower() == "with routines":
                    self.end = max([routine.end for routine in routines.values()])
                else:
                    self.end = convert_time(end)
            elif isinstance(end, numbers.Number):
                self.end = end
            else:
                raise ValueError("invalid value for end keyword argument")
        else:
            self.end = np.inf

        self.clock = Clock()
        self.clock.start()

        self.timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

        self.data = pd.DataFrame(columns=["Time"] + list(variables.keys()))

        self.state = pd.Series({column: None for column in self.data.columns})
        self.state["Time"] = 0

        self._status = Experiment.READY
        self.status_locked = True
        # can only be unlocked by the start, hold, stop and terminate methods

        self.saved = []  # list of saved data entries

    def __next__(self):
        # Start the clock on first call
        if self.state.name is None:  # first step of the experiment
            self.start()
            self.status = Experiment.RUNNING + ": initializing..."

        # Update time
        self.state["Time"] = self.clock.time
        self.state.name = datetime.datetime.now()

        if self.stopped:
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
                self.status = Experiment.RUNNING + f": executing {name}"
                thread.join()

            self.status = Experiment.RUNNING

        # Get all variable values if experiment is running or holding
        if self.running or self.holding:
            for variable in self.variables.values():
                variable._eval_event.clear()

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
                self.status = base_status + f": retrieving {name}"
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
            if isinstance(self.variables[name], _variables.Expression):
                for symbol, dependee in self.variables[name].definitions.items():
                    if hasattr(dependee, "_eval_event"):
                        # wait for dependee to be evaluated
                        dependee._eval_event.wait()

            try:
                value = self.variables[name].value
            except AdapterError:
                value = None
            except ValueError:
                value = None

            self.variables[name]._eval_event.set()
            # unblock threads evaluating dependents

            if np.size(value) > 1:  # store array data as CSV files
                if np.any(value):
                    # only save non-empty arrays
                    dataframe = pd.DataFrame(
                        {name: value}, index=[self.state.name] * len(value)
                    )
                    path = name.replace(" ", "_") + "_"
                    path += self.state.name.strftime("%Y%m%d-%H%M%S") + ".csv"
                    dataframe.to_csv(path)

                    self.state[name] = os.path.abspath(path)
                else:
                    self.state[name] = None
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
        self.status = base_status + ": saving data"

        path = f"data_{self.timestamp}.csv"

        if directory:
            path = os.path.join(directory, path)

        if not os.path.exists(path):
            # if this is a new file, write column headers
            with open(path, "a") as data_file:
                data_file.write("," + ",".join(self.data.columns) + "\n")

        unsaved = np.setdiff1d(self.data.index, self.saved)

        with open(path, "a") as data_file:
            for line in unsaved:
                line_data = ",".join(map(str, list(self.data.loc[line])))
                data_file.write(str(line) + "," + line_data + "\n")

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
            self.status = self.status + ": " + reason
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
            self.status = self.status + ": " + reason
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
            self.status = self.status + ": " + reason
        self.status_locked = True

        # End routines
        for routine in self.routines.values():
            routine.terminate()

    def __repr__(self):
        return "Experiment"


class AsyncExperiment(Experiment):
    """
    Asynchronous version of Experiment

    Each variable and routine is updated as quickly as possible independent of the
    experiment iteration. Every time a variable is updated, the corresponding entry in
    `state` is also updated.
    """

    def __init__(
            self,
            variables: dict,
            routines: dict = None,
            end: Union[numbers.Number, str, None] = None,
    ):
        super().__init__(variables, routines, end)
        self._thread = None

    def __next__(self):

        # Start the clock and loop on first call
        if self.state.name is None:  # first step of the experiment
            self.start()
            self.status = Experiment.RUNNING + ": initializing..."

        # Update time
        self.state["Time"] = self.clock.time
        self.state.name = datetime.datetime.now()

        # End the experiment, if the duration of the experiment has passed
        if self.clock.time > self.end:
            self.terminate()

        if self.terminated:
            raise StopIteration

        if self.running or self.holding:
            # Append new state to experiment data set
            self.data.loc[self.state.name] = self.state

        return self.state

    async def _update_variable(self, name):
        """Update named variable"""
        if self.running or self.holding:
            super()._update_variable(name)

        if not self.terminated:
            asyncio.create_task(self._update_variable(name))

    async def _update_routine(self, name):
        """Update named routine"""
        if self.running:
            super()._update_routine(name)

        if not self.terminated:
            asyncio.create_task(self._update_routine(name))

    async def _run_loop(self):
        """Set up and run updating loop"""

        await asyncio.gather(
            *([self._update_variable(name) for name in self.variables]
              + [self._update_routine(name) for name in self.routines])
        )

        async def experiment_loop():
            while not self.terminated:
                await asyncio.sleep(0.1)

        await experiment_loop()

    def start(self):

        super().start()

        self._thread = threading.Thread(
            target=asyncio.run, args=(self._run_loop(),)
        )

        self._thread.start()

    def terminate(self, reason=None):

        super().terminate(reason=reason)

        if self._thread is not None:
            self._thread.join()


class Alarm:
    """
    Triggers if a condition among variables is met and indicates the response
    protocol
    """

    def __init__(self, condition, definitions, protocol=None):
        self.trigger_variable = _variables.Expression(
            expression=condition, definitions=definitions
        )

        if protocol:
            self.protocol = protocol
        else:
            self.protocol = "none"

    @property
    def triggered(self):
        return bool(self.trigger_variable.value)

    def __repr__(self):
        return "Alarm"


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
                parent=root,
                title="Select Runcard",
                filetypes=[("YAML files", "*.yaml")],
            )

            if self.runcard == "":
                raise ValueError("a valid runcard was not selected!")

        if isinstance(self.runcard, str):
            if os.path.exists(self.runcard):
                dirname = os.path.dirname(self.runcard)
                if dirname != "":
                    os.chdir(os.path.dirname(self.runcard))
                    # go to runcard directory to put data in same location

                yaml = YAML()
                with open(self.runcard, "rb") as runcard_file:
                    self.runcard = yaml.load(runcard_file)  # load the runcard
            else:
                raise FileNotFoundError(f'invalid runcard path "{self.runcard}"')
        elif isinstance(self.runcard, dict):
            pass
        else:
            raise TypeError(
                f"runcard given to Manager must be a path to a YAML file "
                f"or a dictionary, not {type(self.runcard)}!"
            )

        converted_runcard = convert_runcard(self.runcard)

        self.description = converted_runcard["Description"]
        self.settings = converted_runcard["Settings"]
        self.instruments = converted_runcard["Instruments"]
        self.alarms = converted_runcard["Alarms"]
        self.plotter = converted_runcard.get("Plotter", None)

        self.experiment = converted_runcard["Experiment"]

        # Unpack settings
        self.followup = self.settings.get("follow-up", None)
        self.step_interval = convert_time(self.settings.get("step interval", 0.1))
        self.save_interval = convert_time(self.settings.get("save interval", 60))
        self.plot_interval = convert_time(self.settings.get("plot interval", 0.1))

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
        experiment_name = self.runcard["Description"].get("name", "Experiment")
        working_dir = experiment_name + "-" + self.experiment.timestamp
        os.mkdir(working_dir)
        os.chdir(working_dir)

        # Save executed runcard alongside data for record keeping
        yaml = YAML()

        timestamped_path = f"{experiment_name}_{self.experiment.timestamp}.yaml"
        with open(timestamped_path, "w") as runcard_file:
            yaml.dump(self.runcard, runcard_file)

        # Run experiment loop in separate thread
        experiment_thread = threading.Thread(target=self._run)
        experiment_thread.start()

        # Set up the GUI for user interaction
        self.gui = _graphics.ExperimentGUI(
            self.experiment,
            alarms=self.alarms,
            instruments=self.instruments,
            title=self.description.get("name", "Experiment"),
            plotter=self.plotter,
            save_interval=self.save_interval,
            plot_interval=self.plot_interval,
        )

        self.gui.run()

        experiment_thread.join()

        # Disconnect instruments
        for instrument in self.instruments.values():
            instrument.disconnect()

        os.chdir(top_dir)  # return to the parent directory

        # Cancel follow-up if experiment terminated by user
        if self.experiment.terminated and "user" in self.experiment.status:
            self.followup = None

        # Execute the follow-up experiment if there is one
        if self.followup:
            if "yaml" in self.followup:
                self.__init__(self.followup)
                self.run(directory=directory)
            elif "repeat" in self.followup:
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
                            "time": self.experiment.data["Time"].iloc[-1],
                            "status": self.experiment.status,
                        }

                    if "none" in alarm.protocol:
                        # do nothing (GUI will indicate that alarm is triggered)
                        break
                    if "hold" in alarm.protocol:
                        # stop routines but keep measuring until alarm is clear
                        self.experiment.hold(reason=name)
                        break
                    elif "stop" in alarm.protocol:
                        # stop routines and measurements until alarm is clear
                        self.experiment.stop(reason=name)
                        break
                    elif "terminate" in alarm.protocol:
                        # terminate the experiment
                        self.experiment.terminate(reason=name)
                        break
                    elif "yaml" in alarm.protocol:
                        # terminate the experiment and run another
                        self.experiment.terminate(reason=name)
                        self.followup = alarm.protocol
                        break
                    elif "check" in alarm.protocol:
                        # stop routines and measurements until user resumes
                        self.experiment.stop(reason=name)
                        break
                    else:
                        # terminate the experiment
                        self.experiment.terminate(reason=name)
                        break

                elif name in self.awaiting_alarms:
                    # Alarm was previously triggered but is now clear

                    if "check" not in alarm.protocol:
                        # alarm is not waiting for user to check

                        info = self.awaiting_alarms.pop(name)
                        # remove from dictionary of triggered alarms
                        prior_status = info["status"]

                        if len(self.awaiting_alarms) == 0:
                            # there are no more triggered alarms
                            # return to state of experiment prior to trigger
                            if "Running" in prior_status:
                                self.experiment.start()
                            if "Holding" in prior_status:
                                self.experiment.hold(reason=name + " cleared")
                            if "Stopped" in prior_status:
                                self.experiment.stop(reason=name + " cleared")

            step_end = time.time()

            remaining_time = self.step_interval - (step_end - step_start)

            if remaining_time > 0:
                time.sleep(remaining_time)

    def __repr__(self):
        return "Manager"


class RuncardError(BaseException):
    pass


def validate_runcard(runcard):
    is_dict = isinstance(runcard, dict)
    is_ordereddict = isinstance(runcard, collections.OrderedDict)

    if is_dict or is_ordereddict:
        # Create temporary runcard YAML file for PyKwalify to validate
        yaml = YAML()

        runcard_path = f"tmp_runcard_{time.time()}.yaml"

        with open(runcard_path, "w") as runcard_file:
            yaml.dump(runcard, runcard_file)

        try:
            validate_runcard(runcard_path)
        finally:
            # Wait until temporary file has write access, then delete
            while not os.access(runcard_path, os.W_OK):
                time.sleep(0.1)

            os.remove(runcard_path)

        return True

    elif type(runcard) is not str:
        raise ValueError("runcard must be either dict or str.")

    validator = YamlValidator(
        source_file=runcard,
        schema_files=[
            os.path.join(pathlib.Path(__file__).parent, "runcard_schema.yaml")
        ],
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
        with open(runcard, "rb") as runcard_file:
            runcard = yaml.load(runcard_file)

    # Validate runcard format and contents
    validate_runcard(runcard)

    converted_runcard = runcard.copy()

    # Load any custom components
    custom_routines = {}
    custom_instruments = {}

    if "custom.py" in os.listdir():
        sys.path.insert(1, os.getcwd())
        custom = importlib.import_module("custom")

        for name, thing in custom.__dict__.items():
            if type(thing) == type:
                if issubclass(thing, _routines.Routine):
                    custom_routines[name] = thing
                if issubclass(thing, _instruments.Instrument):
                    custom_instruments[name] = thing

    # Instruments section
    available_instruments = {**_instruments.supported, **custom_instruments}

    instruments = {}
    for name, specs in runcard.get("Instruments", {}).items():
        specs = specs.copy()
        _type = specs.pop("type")
        address = specs.get("address", None)

        # Grab any keyword arguments for the adapter
        adapter_kwargs = {}
        for kwarg in _adapters.kwargs:
            if kwarg.replace("_", " ") in specs:
                adapter_kwargs[kwarg] = specs.pop(kwarg.replace("_", " "))

        # Any remaining keywords are instrument presets
        presets = {
            key: recast(value) for key, value in specs.get("presets", {}).items()
        }
        postsets = {
            key: recast(value) for key, value in specs.get("postsets", {}).items()
        }

        instrument_class = available_instruments[_type]
        instruments[name] = instrument_class(
            address=address, presets=presets, postsets=postsets, **adapter_kwargs
        )
        instruments[name].name = name

    converted_runcard["Instruments"] = instruments

    # Variables section
    variables = {}
    for name, specs in runcard["Variables"].items():
        if "meter" in specs:
            instrument = converted_runcard["Instruments"][specs["instrument"]]
            gate = specs.get("gate", None)
            gate = variables[gate] if gate else None
            variables[name] = _variables.Meter(
                meter=specs["meter"],
                instrument=instrument,
                gate=gate,
                multiplier=specs.get("multiplier", 1),
                offset=specs.get("offset", 0),
            )
        elif "knob" in specs:
            instrument = converted_runcard["Instruments"][specs["instrument"]]
            variables[name] = _variables.Knob(
                knob=specs["knob"],
                instrument=instrument,
                lower_limit=specs.get("lower limit", None),
                upper_limit=specs.get("upper limit", None),
                multiplier=specs.get("multiplier", 1),
                offset=specs.get("offset", 0),
            )
        elif "expression" in specs:
            expression = specs["expression"]
            definitions = specs.get("definitions", {}).copy()

            for variable in definitions.values():
                if variable not in variables:
                    raise KeyError(
                        f"variable {variable} specified for alarm {name} "
                        f"is not in Variables!"
                    )

            definitions = {
                symbol: variables[name] for symbol, name in definitions.items()
            }

            variables[name] = _variables.Expression(
                expression=expression, definitions=definitions
            )
        elif "server" in specs:
            server = specs["server"]
            alias = specs.get("alias", name)
            protocol = specs.get("protocol", None)
            settable = specs.get("settable", False)

            variables[name] = _variables.Remote(
                server=server,
                alias=alias,
                protocol=protocol,
                settable=settable,
                multiplier=specs.get("multiplier", 1),
                offset=specs.get("offset", 0),
            )

        elif "parameter" in specs:
            variables[name] = _variables.Parameter(parameter=recast(specs["parameter"]))

        if name in variables and "hidden" in specs:
            # If hidden, the variable does not appear in the GUI
            if specs["hidden"]:
                variables[name]._hidden = True

    # Routines section
    available_routines = {**_routines.supported, **custom_routines}

    routines = {}
    if "Routines" in runcard:
        for name, specs in runcard["Routines"].items():
            specs = specs.copy()  # avoids modifying the runcard
            _type = specs.pop("type")

            specs = {key.replace(" ", "_"): value for key, value in specs.items()}

            # Convert list of knobs into dictionary
            knobs = np.array([specs.get("knobs", [])]).flatten()
            if knobs.size > 0:
                for knob in knobs:
                    if knob not in variables:
                        raise KeyError(
                            f"knob {knob} specified for routine {name} "
                            "is not in Variables!"
                        )

                specs["knobs"] = {name: variables[name] for name in knobs}

            routines[name] = available_routines[_type](**specs)

    # Create the experiment
    async_experiment = False
    if 'Settings' in runcard:
        if runcard['Settings'].get('async', False):
            async_experiment = True

    if async_experiment:
        converted_runcard["Experiment"] = AsyncExperiment(
            variables, routines=routines, end=runcard["Settings"].get("end", None)
        )
    else:
        converted_runcard["Experiment"] = Experiment(
            variables, routines=routines, end=runcard["Settings"].get("end", None)
        )

    # Alarms section
    alarms = {}
    if "Alarms" in runcard:
        for name, specs in runcard["Alarms"].items():
            condition = specs.copy()["condition"]
            definitions = specs.copy().get("definitions", {})

            for variable in definitions.values():
                if variable not in variables:
                    raise KeyError(
                        f"variable {variable} specified for alarm {name} "
                        f"is not in Variables!"
                    )

            definitions = {
                symbol: variables[name] for symbol, name in definitions.items()
            }

            alarms.update(
                {
                    name: Alarm(
                        condition, definitions, protocol=specs.get("protocol", None)
                    )
                }
            )

    converted_runcard["Alarms"] = alarms

    # Plots section
    if "Plots" in runcard:
        converted_runcard["Plotter"] = _graphics.Plotter(
            converted_runcard["Experiment"].data, settings=runcard["Plots"]
        )
    else:
        converted_runcard["Plotter"] = None

    return converted_runcard
