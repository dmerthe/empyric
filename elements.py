import time
import datetime
import numbers
from ruamel.yaml import YAML
import re
import numpy as np
import pandas as pd

from mercury import instrumentation
from mercury.utilities import *

yaml = YAML()


class Clock:
    """
    Clock for keeping time
    """

    def __init__(self):
        self.start()

    def start(self):
        self.start_time = time.time()

        self.stop_time = None  # if paused, the time when the clock was paused
        self.total_stoppage = 0  # amount of stoppage time, or total time while paused

    def time(self):
        if not self.stop_time:
            return time.time() - self.start_time - self.total_stoppage
        else:
            return self.stop_time - self.start_time - self.total_stoppage

    def stop(self):
        if not self.stop_time:
            self.stop_time = time.time()

    def resume(self):
        if self.stop_time:
            self.total_stoppage += time.time() - self.stop_time
            self.stop_time = None


class MappedVariable:
    """
    A variable directly associated with a knob or meter of a connected instrument
    """

    def __init__(self, instrument, knob=None, meter=None):

        if knob is None and meter is None:
            raise TypeError('Need either a knob or meter specification!')

        self.instrument = instrument

        self.knob = knob
        if knob.lower() == 'none':
            self.knob = None

        self.meter = meter
        if meter.lower() == 'none':
            self.meter = None

    def set(self, value):

        if self.knob is None:
            raise TypeError("Cannot set this variable, because it has no associated knob!")

        self.instrument.set(self.knob, value)

    def get(self):

        if self.knob is None:
            raise TypeError("Get method is for knobs only!")

        return self.instrument.knob_values[self.knob]

    def measure(self, sample_number=1):

        if self.meter is None:
            raise TypeError("Cannot measure this variable, because it has no associated meter!")

        value = self.instrument.measure(self.meter, sample_number=sample_number)

        return value


class InstrumentSet:
    """
    Set of instruments to be used in an experiment, including presets, knob and meter specs and alarm protocols
    """

    # Alarm trigger classifications
    alarm_map = {
        'IS': lambda val, thres: val == thres,
        'NOT': lambda val, thres: val != thres,
        'GREATER': lambda val, thres: val > thres,
        'GEQ': lambda val, thres: val > thres,
        'LESS': lambda val, thres: val < thres,
        'LEQ': lambda val, thres: val <= thres,
    }

    def __init__(self, specs=None, variables=None, alarms=None, presets=None, postsets=None):

        self.instruments = {}  # Will contain a list of instrument instances from the instrumentation submodule
        if specs:
            self.connect(specs)

        self.mapped_variables = {}
        if variables:
            self.map_variables(variables)

        if alarms:
            self.alarms = { name: {**alarm, 'triggered': False} for name, alarm in alarms.items() }
        else:
            self.alarms = {}

        if presets:
            self.presets = presets
        else:
            self.presets = {}

        if postsets:
            self.postsets = postsets
        else:
            self.postsets = {}

        self.apply(self.presets)

    def connect(self, specs):
        """
        Establishes communications with instruments according to specs

        :param specs: (iterable) list or array, whose rows are 4-element instrument specifications, including name, kind, backend and address
        :return: None
        """

        for name, spec in specs.items():

            kind, backend, address = spec['kind'], spec['backend'], spec['address']

            if backend not in instrumentation.available_backends:
                raise instrumentation.ConnectionError(f'{backend} is not a valid instrument communication backend!')

            instrument = instrumentation.__dict__[kind](address, backend=backend.lower())
            instrument.name = name
            instrument.mapped_variables = {}

            self.instruments[name] = instrument

            # Apply quicksets
            for knob in instrument.knobs:
                if knob in spec:
                    instrument.set(knob, spec[knob])

    def map_variables(self, variables):

        for name, mapping in variables.items():

            instrument, knob, meter = mapping['instrument'], mapping.get('knob', 'none'), mapping.get('meter', 'none')
            self.mapped_variables.update({name: MappedVariable(self.instruments[instrument], knob=knob, meter=meter)})
            if knob:
                self.instruments[instrument].mapped_variables[knob] = name
            if meter:
                self.instruments[instrument].mapped_variables[meter] = name

    def disconnect(self):
        """
        Disconnects communications with all instruments

        :return: None
        """

        self.apply(self.postsets)

        for instrument in self.instruments.values():
            instrument.disconnect()

        self.instruments = []


    def apply(self, knob_settings):
        """
        Apply settings to knobs of the instruments

        :param knob_settings: (dict) dictionary of knob settings in the form, knob_name: value
        :return: None

        To set a mapped variable knob, simply use its name here. Otherwise, set the knob_name to a 2-element tuple of the form (instrument_name, knob_name).
        """

        for knob_name, value in knob_settings.items():

            if type(knob_name) is str:  # for mapped variables
                self.mapped_variables[knob_name].set(value)
            else:  # for unmapped variables
                instrument_name, knob_name = knob_name
                instrument = self.instruments[instrument_name]
                instrument.set(knob_name, value)

    def read(self, meters=None):
        """
        Read meters of the instruments.

        :param meters: (list) list of meters to be read; if unspecified, this method measures and returns all mapped variable meter values.
        :return: (dictionary) dictionary of measured values in the form, meter_name: value
        """

        readings = {}

        if meters is None:
            return {name: var.measure() for name, var in self.mapped_variables.items() if var.meter}

        for meter in meters:

            if type(meter) is str:  # if meter is a mapped variable
                readings[meter] = self.mapped_variables[meter].measure()
            else:  # otherwise, the meter can be specified by the corresponding (instrument, meter) tuple
                instrument_name, meter_name = meter
                instrument = self.instruments[instrument_name]
                readings[meter] = instrument.measure(meter_name)

        self.check_alarms(readings)

        return readings

    def check_alarms(self, readings):
        """
        Checks alarms, as specified by the alarms attribute.

        :param readings: (dict) dictionary of readings
        :return: (dict) dictionary of alarms triggered (as keys) and protocols (as values)
        """

        for alarm, config in self.alarms.items():

            meter, condition, threshold = config['meter'], config['condition'], config['threshold']

            value = readings.get(meter, None)

            if value is None:
                continue

            alarm_triggered = self.alarm_map[condition](value, threshold)
            if alarm_triggered:
                self.alarms[alarm]['triggered'] = True


class Routine:
    """
    Base class for the routines.
    """

    def __init__(self, times, values, clock=None):

        self.times = times
        self.values = values
        try:
            self.values_iter = iter(values)  # for use in the Path and Sweep subclasses
        except TypeError:
            pass

        if clock:
            self.clock = clock
        else:
            self.clock = Clock()

    def start(self):
        self.clock.start()

    def __iter__(self):
        return self


class Idle(Routine):
    """
    Holds a value, given by the 'values' argument (1-element list or number), from the first time in 'times' to the second.

    """

    def __next__(self):

        try:
            if len(self.times) == 1:
                start = self.times[0]
                end = np.inf
            elif len(self.times) == 2:
                start, end = self.times[:2]
            else:
                raise IndexError("The times argument must be either a 1- or 2- element list, or a number!")
        except TypeError:
            start = self.times
            end = np.inf

        value = np.array([self.values]).flatten()[0]

        now = self.clock.time()

        if start <= now <= end:
            return value


class Ramp(Routine):
    """
    Linearly ramps a value from the first value in 'values' to the second, from the first time in 'times' to the second.
    """

    def __next__(self):

        if len(self.times) == 1:
            start = self.times[0]
            end = np.inf
        elif len(self.times) == 2:
            start, end = self.times[:2]
        else:
            raise IndexError("The times argument must be either a 1- or 2-element list!")

        start_value, end_value = self.values

        now = self.clock.time()

        if start <= now <= end:
            return start_value + (end_value - start_value)*(now - start) / (end - start)


class Transit(Routine):
    """
    Sequentially and immediately passes a value once through the 'values' list argument, cutting it off at the single value of the 'times' argument.
    """

    def __next__(self):

        try:
            if len(self.times) == 1:
                end = self.times[0]
            else:
                raise IndexError("The times argument must be either a 1-element list, or a number!")
        except TypeError:
            end = self.times

        self.time = self.clock.time()

        if self.time <= end:
            return next(self.values_iter, None)


class Sweep(Routine):
    """
    Sequentially and cyclically sweeps a value through the 'values' list argument, starting at the first time in 'times' and ending at the last.
    """

    def __next__(self):

        if len(self.times) == 1:
            start = self.times[0]
            end = np.inf
        elif len(self.times) == 2:
            start, end = self.times[:2]
        else:
            raise IndexError("The times argument must be either a 1- or 2-element list!")

        now = self.clock.time()

        if start <= now <= end:
            try:
                return next(self.values_iter)
            except StopIteration:
                self.values_iter = iter(self.values)  # restart the sweep
                return next(self.values_iter)

class Schedule:
    """
    Schedule of settings to be applied to knobs, implemented as an iterable to allow for flexibility in combining different kinds of routines
    """

    def __init__(self, routines=None):
        """

        :param routines: (dict) dictionary of routine specifications (following the runcard yaml format).
        """

        self.clock = Clock()

        self.routines = {}
        if routines:
            self.add(routines)

    def add(self, routines):
        """
        Adds routines to the schedule, based on the given dictionary of specifications (following the runcard yaml format)

        :param routines: (dict) dictionary of routine specifications.
        :return: None
        """

        for name, spec in routines.items():
            kind, variable = spec['routine'], spec['variable']
            values = spec['values']

            times = []
            for time_value in spec['times']:
                times.append(convert_time(time_value))

            routine = {
                'Idle': Idle,
                'Ramp': Ramp,
                'Sweep': Sweep,
                'Transit': Transit
            }[kind](times, values, self.clock)

            self.routines.update({name: (variable, routine)})

    def start(self):
        self.clock.start()

    def stop(self):
        self.clock.stop()

    def resume(self):
        self.clock.resume()

    def __iter__(self):
        return self

    def __next__(self):

        output = {}
        for pair in self.routines.values():
            knob, routine = pair
            next_value = next(routine)
            if next_value is not None:
                output.update({knob: next_value})

        return output


class Experiment:

    default_settings = {'duration': np.inf,
                        'follow-up': None,
                        'step interval': 0,
                        'plot interval': 10,
                        'save interval': 60}

    def __init__(self, runcard):
        """

        :param runcard: (file) runcard file
        """

        self.clock = Clock()  # used for save timing
        self.clock.start()

        self.last_step = -np.inf  # time of last step taken
        self.last_save = -np.inf  # time of last save

        self.runcard = runcard
        self.description = runcard["Description"]

        self.instruments = InstrumentSet(
            runcard['Instruments'],
            runcard['Variables'],
            runcard.get('Alarms', None),  # Optional
            runcard.get('Presets', None),  # Optional
            runcard.get('Postsets', None)  # Optional
        )

        self.settings = runcard.get('Settings', self.default_settings)  # Optional; if given use default settings above
        self.plotting = runcard.get('Plotting', None)  # Optional
        self.schedule = Schedule(runcard['Schedule'])

        data_columns = list(self.instruments.mapped_variables.keys())
        data_columns += ['Total Time', 'Schedule Time']
        self.data = pd.DataFrame(columns=data_columns)  # Will contain history of knob settings and meter readings for the experiment.

        self.status = 'Not Started'
        self.followup = self.settings.get('follow-up', None)  # What to do when the experiment ends

        # Make a list of follow-ups
        if self.followup in [None, 'None']:
            self.followup = []
        elif isinstance(self.followup, str):
            self.followup = [self.followup]

    def save(self, save_now=False):
        """
        Save data, but at a maximum frequency set by the given save interval, unless overridden by the save_now keyword.

        :param save_now: (bool/str) If False, saves will only occur at a maximum frequency defined by the 'save interval' experimt setting. Otherwise, experiment data is saved immediately.
        :return: None
        """

        now = self.clock.time()
        save_interval = self.settings.get('save interval', 60)

        if now >= self.last_save + save_interval or save_now:
            self.data.to_csv(timestamp_path('data.csv', timestamp=self.timestamp))
            self.last_save = self.clock.time()

    def __iter__(self):
        return self

    def __next__(self):

        # Start the schedule clock on first call
        if self.status == 'Not Started':
            self.schedule.clock.start()  # start the schedule clock
            self.status = 'Running'
            self.timestamp = get_timestamp()

        # Stop if finished
        if self.status == 'Finished':
            self.save('now')
            self.schedule.clock.stop()
            self.instruments.disconnect()
            raise StopIteration

        # Take the next step in the experiment
        if self.clock.time() < self.last_step + float(self.settings['step interval']):
            return self.state  # Only apply settings at frequency limited by 'step interval' setting

        self.last_step = self.clock.time()

        configuration = next(self.schedule)  # Get the next step from the schedule

        self.instruments.apply(configuration)  # apply settings to knobs
        readings = self.instruments.read()  # checking meter readings
        state = readings  # will contain knob values + meter readings + time values

        # Get previously set knob values if no corresponding routines are running
        for name, variable in self.instruments.mapped_variables.items():
            if variable.knob and name not in configuration:
                configuration[name] = variable.get()

        state.update(configuration)

        times = {'Total Time': self.clock.time(), 'Schedule Time': self.schedule.clock.time()}
        state.update(times)

        self.state = pd.Series(state, name=datetime.datetime.now())
        self.data.loc[self.state.name] = self.state

        self.save()

        # Flag for termination if time has exceeded experiment duration
        duration = convert_time(self.settings['duration'])
        if self.schedule.clock.time() > duration:
            self.status = 'Finished'

        # Flag for termination if any alarms have been raised
        for alarm in self.instruments.alarms.values():
            if alarm['triggered']:
                for task in self.followup:
                    if task.lower() == 'repeat':
                        self.followup.remove(task)  # Cancel repeat if alarm triggered
                self.followup.insert(0, alarm['protocol']) # put any triggered alarm protocols at top of follow-up list
                self.status = 'Finished'

        return self.state
