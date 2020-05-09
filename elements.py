import time
import numbers
import yaml
import numpy as np
from pandas import DataFrame

import instrumentation


class Clock:
    """
    Clock for keeping time, capable of running splits and pausing
    """

    def __init__(self):
        self.start_clock()

    def start_clock(self):
        self.start = time.time()
        self.split_start = time.time()

        self.pause_time = None  # if paused, the time when the clock was paused

        self.total_stoppage = 0
        self.split_stoppage = 0

    def start_split(self):
        self.split_stoppage = 0
        self.split_start = time.time()

    def split_time(self):
        if not self.pause_time:
            return time.time() - self.split_start - self.split_stoppage
        else:
            return self.pause_time - self.split_start - self.split_stoppage

    def total_time(self):
        if not self.pause_time:
            return time.time() - self.start - self.total_stoppage
        else:
            return self.pause_time - self.start - self.total_stoppage

    def pause(self):
        if not self.pause_time:
            self.pause_time = time.time()

    def resume(self):
        if self.pause_time:
            self.total_stoppage += time.time() - self.pause_time
            self.split_stoppage += time.time() - self.pause_time
            self.pause_time = None


class MappedVariable:
    """
    A variable directly associated with a knob or meter of a connected instrument
    """

    def __init__(self, instrument, knob=None, meter=None):

        if knob is None and meter is None:
            raise TypeError('Need either a knob or meter specification!')

        self.instrument = instrument
        self.knobs = knob
        self.meter = meter

    def set(self, value):

        if self.knob is None:
            raise TypeError("Cannot set this variable, because it has no associated knob!")

        self.instrument.set(self.knob, value)

    def measure(self, sample_number=1):

        if self.meter is None:
            raise TypeError("Cannot measure this variable, because it has no associated meter!")

        value = self.instrument.measure(self.meter, sample_number=sample_number)

        return value


class InstrumentSet:
    """
    Set of instruments to be used in an experiment, including presets, knob and meter specs and alarm protocols
    """

    def __init__(self, specs=None, variables=None, alarms=None, presets=None, postsets=None):

        self.instruments = {}  # Will contain a list of instrument instances from the instrumentation submodule

        if specs:
            self.connect(specs)

        self.mapped_vars = {}
        if mapped_vars:
            self.map_variables(variables)

        if alarms:
            self.alarms = alarms
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

            self.instruments[name] = instrument

        self.apply(self.presets)

    def map_variables(self, variables):

        for name, mapping in variables.items():

            instrument, knob, meter = mapping['instrument'], mapping['knob'], mapping['meter']
            self.mapped_vars = self.mapped_vars + {
                name: MappedVariable(self.instruments[instrumnet], knob=knob, meter=meter)
            }

    def disconnect(self):
        """
        Disconnects communications with all instruments

        :return: None
        """

        self.apply(postsets)

        for instrument in self.instruments:
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
                self.mapped_vars[knob_name].set(value)
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

        if meters is None:
            return {name: var.measure() for name, var in self.mapped_vars if var.meter}


        readings = {}

        for meter in meters:

            if type(meter) is str:
                readings[meter] = self.mapped_vars[meter].measure()
            else:
                instrument_name, meter_name = meter
                instrument = self.instruments[instrument_name]
                readings[meter] = instrument.measure(meter_name)

        self.check_alarms(readings)

        return readings

    def check_alarms(self, readings):
        """
        Checks alarms, as specified by the alarms attribute.

        :param readings:
        :return: (dict) of alarms triggered (as keys) and protocols (as values)
        """

        triggered = {}

        for alarm, config in self.alarms.items():

            meter, condition, threshold, protocol = config

            value = readings.get(meter, None)

            if value is None:
                continue

            if instrumentation.alarm_map[condition](reading, threshold):
                triggered[alarm] = protocol

        return triggered


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
        self.clock.start_clock()

    def __iter__(self):
        return self


class Hold(Routine):
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

        try:
            value = self.values[0]
        except TypeError:
            value = self.values

        time = self.clock.total_time()

        if start <= time <= end:
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

        time = self.clock.total_time()

        if start <= time <= end:
            return start_value + (end_value - start_value)*(time - start) / (end - start)


class Transit(Routine):
    """
    Sequentially and immediately passes a value through the 'values' list argument, cutting it off at the single value of the 'times' argument.
    """

    def __next__(self):

        try:
            if len(end) == 1:
                end = times[0]
            else:
                raise IndexError("The times argument must be either a 1-element list, or a number!")
        except TypeError:
            end = times

        self.time = self.clock.total_time()

        if self.time <= end:
            return next(self.values_iter, None)


class Sweep(Routine):
    """
    Sequentially and cyclically sweeps a value through the 'values' list argument, starting at the first time in 'times' to the last.
    """

    def __next__(self):

        if len(self.times) == 1:
            start = self.times[0]
            end = np.inf
        elif len(self.times) == 2:
            start, end = self.times[:2]
        else:
            raise IndexError("The times argument must be either a 1- or 2-element list!")

        time = self.clock.total_time()

        if start <= time <= end:
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

        :param routines: (dict) dictionary of routine specifications.
        """

        self.clock = Clock()

        self.routines = {}
        if routines:
            self.add(routines)

    def add(self, routines):

        for name, spec in routines.items():
            kind, values = spec['routine'], spec['values']

            times = []
            for time in spec['times']:
                if isinstance(time, numbers.Number):
                    times.append(time)
                elif isinstance(time, str):
                    # times can be specified in the runcard with units, such as minutes, hours or days, e.g.  "6 hours"
                    value, unit = times.split(' ')
                    value = float(value)
                    times.append(values*{'minutes': 60, 'hours': 3600, 'days': 86400}[unit])

            routine = {
                'Hold': Hold,
                'Ramp': Ramp,
                'Sweep': Sweep,
                'Transit': Transit
            }[kind](times, values, self.clock)

            self.routines = self.routines + {name: routine}

    def start(self):
        self.clock.start_clock()

    def stop(self):
        self.clock.pause()

    def resume(self):
        self.clock.resume()

    def __iter__(self):
        return self

    def __next__(self):
        return {knob: next(routine) for knob, routine in self.routines.items()}


class Experiment:

    def __init__(self, runcard):

        self.clock = Clock()

        self.runcard = {}
        self.from_runcard(runcard)

        self.record = DataFrame()  # Will contain history of knob settings and meter readings for the experiment.

    def from_runcard(self, runcard):
        """
        Populates the experiment attributes from the given runcard.

        :param runcard: (file) runcard in the form of a binary file object.
        :return: None
        """
        runcard_dict = yaml.load(runcard)
        self.runcard = runcard_dict

        self.description = runcard_dict["Description"]

        self.instruments = InstrumentSet(
            runcard_dict['Instruments'],
            runcard_dict['Variables'],
            runcard_dict['Alarms'],
            runcard_dict['Presets'],
            runcard_dict['Postsets']
        )

        self.settings = runcard_dict['Experiment Settings']

        self.plotting = runcard_dict['Plotting']

        self.schedule = Schedule(runcard_dict['Schedule'])

    def save(self, name=None):

        if not name:
            name = get_timestamp()

        yaml.dump(self.runcard, 'runcard_'+name+'.yaml')

    def run(self, plot_interval=10):

        for configuration in self.schedule:

            self.instruments.apply(configuration)
            readings = self.instruments.read()

            record_time = {'TOTAL TIME': self.clock.total_time(), 'SCHEDULE TIME': self.schedule.clock.total_time()}
            self.record = self.record.append(record_time + configuration + readings, ignore_index=True)

        if self.settings['ending'] == 'repeat':
            self.schedule.clock.start_clock()  # reset of the schedule clock
            self.run(plot_interval=plot_interval)

    def end(self):

        self.instruments.disconnect()
