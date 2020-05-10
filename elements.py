import time
import numbers
import yaml
import numpy as np
from pandas import DataFrame
import instrumentation

def get_timestamp(path=None):
    """
    Generates a timestamp in the YYYYMMDD-HHmmss format

    :param path: (string) path to get timestamp from; if None, a new timestamp will be generated and returned
    :return: (string) the formatted timestamp
    """

    if path:
        timestamp_format = re.compile(r'\d\d\d\d\d\d\d\d-\d\d\d\d\d\d')
        timestamp_matches = timestamp_format.findall(path)
        if len(timestamp_matches) > 0:
            return timestamp_matches[-1]
    else:
        return time.strftime("%Y%m%d-%H%M%S", time.localtime())

def timestamp_path(path, timestamp=None):
    """

    :param path: (str) path to which the timestamp will be appended or updated
    :param timestamp: (string) if provided, this timestamp will be appended. If not provided, a new timestamp will be generated.
    :return: (str) timestamped path
    """

    already_timestamped = False

    if not timestamp:
        timestamp = get_timestamp()

    # separate extension
    full_name = '.'.join(path.split('.')[:-1])
    extension = '.' + path.split('.')[-1]

    # If there is already a timestamp, replace it
    # If there is not already a timestamp, append it

    timestamp_format = re.compile(r'\d\d\d\d\d\d\d\d-\d\d\d\d\d\d')
    timestamp_matches = timestamp_format.findall(path)

    if len(timestamp_matches) > 0:
        already_timestamped = True

    if already_timestamped:
        return '-'.join(full_name.split('-')[:-2]) + '-' + timestamp + extension
    else:
        return full_name + '-' + timestamp + extension


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

        self.mapped_variables = {}
        if variables:
            self.map_variables(variables)

        if alarms:
            self.alarms = {alarm + {'triggered': False} for alarm in alarms}
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
            self.mapped_variables = self.mapped_variables + {
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

        if meters is None:
            return {name: var.measure() for name, var in self.mapped_variables.items() if var.meter}

        readings = {}

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

            alarm_triggered = instrumentation.alarm_map[condition](value, threshold)
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

        now = self.clock.total_time()

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

        now = self.clock.total_time()

        if start <= now <= end:
            return start_value + (end_value - start_value)*(now - start) / (end - start)


class Transit(Routine):
    """
    Sequentially and immediately passes a value through the 'values' list argument, cutting it off at the single value of the 'times' argument.
    """

    def __next__(self):

        try:
            if len(self.times) == 1:
                end = self.times[0]
            else:
                raise IndexError("The times argument must be either a 1-element list, or a number!")
        except TypeError:
            end = self.times

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

        now = self.clock.total_time()

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
            for time_value in spec['times']:
                if isinstance(time_value, numbers.Number):
                    times.append(time_value)
                elif isinstance(time_value, str):
                    # times can be specified in the runcard with units, such as minutes, hours or days, e.g.  "6 hours"
                    value, unit = time_value.split(' ')
                    value = float(value)
                    times.append(value*{'minutes': 60, 'hours': 3600, 'days': 86400}[unit])

            routine = {
                'Hold': Hold,
                'Ramp': Ramp,
                'Sweep': Sweep,
                'Transit': Transit
            }[kind](times, values, self.clock)

            self.routines.update({name:routine})

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
        """

        :param runcard: (file) runcard file
        """

        self.clock = Clock()

        self.from_runcard(runcard)

        self.record = DataFrame()  # Will contain history of knob settings and meter readings for the experiment.

        self.terminate = False  # flag for terminating the experiment

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

    def save(self):

        self.record.to_csv(timestamp_path('data.csv'))

    def run(self, first=True):

        if first:  # save the runcard for the experiment upon execution for record keeping
            with open(timestamp_path('runcard.yaml'), 'w') as runcard_file:
                yaml.dump(self.runcard, runcard_file)

        for configuration in self.schedule:

            state = configuration

            if self.terminate:
                self.save()
                break

            self.instruments.apply(configuration)
            readings = self.instruments.read()
            state.update(readings)

            times = {'TOTAL TIME': self.clock.total_time(), 'SCHEDULE TIME': self.schedule.clock.total_time()}
            state.update(times)

            self.record = self.record.append(line, ignore_index=True)

        ending_option = self.settings['ending']
        if ending_option == 'repeat':
            self.schedule.clock.start_clock()  # reset the schedule clock
            self.run(first=False)
        elif ending_option == 'end':
            self.end()
        elif ending_option == 'hold':
            while not self.terminate:
                self.instruments.apply(configuration)  # reuse last configuration from loop above
                readings = self.instruments.read()
                state.update(readings)

                times = {'TOTAL TIME': self.clock.total_time(), 'SCHEDULE TIME': self.schedule.clock.total_time()}
                state.update(times)
                self.record = self.record.append(state, ignore_index=True)
        elif 'yaml' in ending_option:
            # Ending option can be another experiment runcard,
            # e.g. for a specific shutdown sequence or follow-up experiment
            with open(ending_option, 'r') as runcard:
                self.end(followup=runcard)

    def end(self, followup=None):

        if followup:
            self.__init__(followup)
            self.run()
        else:
            self.instruments.disconnect()
