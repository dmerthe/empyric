import copy
import datetime
import importlib
import numpy as np
import pandas as pd

from mercury import instrumentation
from mercury.utilities import tiempo
from mercury.utilities import alarms

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


class DerivedVariable:
    """
    A variable that is calculated from other variables
    """

    def __init__(self, expression, parents):
        """

        :param expression: (str) expression of the derived variable in terms of the parent variables
        :param parents: (dict) dictionary of parent variables of the form, 'name': mapped_variable
        """

        self.expression = expression
        self.parents = parents

    def measure(self):

        expression = copy.copy(self.expression)

        for name, variable in self.parents.items():
            expression.replace(name, str(variable.measure()))

        return eval(expression)


class InstrumentSet:
    """
    Set of instruments to be used in an experiment, including presets, knob and meter specs and alarm protocols
    """

    def __init__(self, specs=None, variables=None, alarms=None, presets=None, postsets=None):

        self.instruments = {}  # Will contain a list of instrument instances from the instrumentation submodule

        if specs:  # instrument specifications
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

            kind, backend, address = spec['kind'], spec.get('backend', 'auto'), spec['address']

            if backend == 'auto':
                backend = instrumentation.__dict__[kind].default_backend

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

            if 'instrument' in mapping:  # for mapped variables
                instrument, knob, meter = mapping['instrument'], mapping.get('knob', 'none'), mapping.get('meter', 'none')
                self.mapped_variables.update({name: MappedVariable(self.instruments[instrument], knob=knob, meter=meter)})
                if knob:
                    self.instruments[instrument].mapped_variables[knob] = name
                if meter:
                    self.instruments[instrument].mapped_variables[meter] = name
            elif 'expression' in mapping:  # for derived variables
                expression = mapping.pop('expression')
                parents = {short_name: self.mapped_variables[full_name] for short_name, full_name in mapping.items()}
                self.mapped_variables[name] = DerivedVariable(expression, parents)


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

        if meters:
            readings = {}
            for meter in meters:

                if type(meter) is str:  # if meter is a mapped variable
                    readings[meter] = self.mapped_variables[meter].measure()
                else:  # otherwise, the meter can be specified by the corresponding (instrument, meter) tuple
                    instrument_name, meter_name = meter
                    instrument = self.instruments[instrument_name]
                    readings[meter] = instrument.measure(meter_name)
        else:
            readings = {name: var.measure() for name, var in self.mapped_variables.items() if var.meter}

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

            alarm_triggered = alarms.alarm_map[condition](value, threshold)
            if alarm_triggered:
                self.alarms[alarm]['triggered'] = True


class Routine:
    """
    Base class for the routines.
    """

    def __init__(self, **kwargs):

        self.times = np.array([kwargs['times']]).flatten()

        self.start_time = -np.inf
        self.stop_time = np.inf
        self.interval = 0

        self.last_call = -np.inf  # last time the __next__ method has been called

        if len(self.times) >= 1:
            self.start_time = tiempo.convert_time(self.times[0])

        if len(self.times) >= 2:
            self.stop_time = tiempo.convert_time(self.times[1])

        if len(self.times) >= 3:
            self.interval = tiempo.convert_time(self.times[2])

        self.values = np.array([kwargs['values']]).flatten()

        if 'clock' in kwargs:
            self.clock = kwargs['clock']
        else:
            self.clock = tiempo.Clock()

    def __iter__(self):
        return self


class Repeat(Routine):
    """
    Repeats a value, given by the 'values' argument (1-element list or number), from the first time in 'times' to the second.

    """

    def __next__(self):

        now = self.clock.time()
        if self.start_time <= now < self.stop_time and now >= self.last_call + self.interval:
            self.last_call = now
            return self.values[0]


class Ramp(Routine):
    """
    Linearly ramps a value from the first value in 'values' to the second, from the first time in 'times' to the second.
    """

    def __next__(self):

        start_value, end_value = self.values[0], self.values[1]
        start_time, end_time = self.start_time, self.stop_time

        now = self.clock.time()
        if start_time <= now <= end_time and now >= self.last_call + self.interval:
            self.last_call = now
            return start_value + (end_value - start_value)*(now - start_time) / (end_time - start_time)
        elif end_time < now <= end_time + self.interval:  # Make sure it sets the end value
            return end_value


class Transit(Routine):
    """
    Sequentially and immediately passes a value once through the 'values' list argument, cutting it off at the single value of the 'times' argument.
    This routine can be thought of as a generalization of the Ramp routine.
    """

    def __init__(self):
        Routine.__init__(self, **kwargs)

        self.values_iter = iter(self.values)

    def __next__(self):

        now = self.clock.time()
        if now < self.stop_time:
            self.last_call = now
            return next(self.values_iter, None)


class Sweep(Routine):
    """
    Sequentially and cyclically sweeps a value through the 'values' list argument, starting at the first time in 'times' and ending at the last.
    """

    def __init__(self, **kwargs):

        Routine.__init__(self, **kwargs)

        self.values_iter = iter(self.values)

    def __next__(self):

        now = self.clock.time()
        if self.start_time <= now < self.stop_time and now >= self.last_call + self.interval:
            self.last_call = now

            try:
                return next(self.values_iter)
            except StopIteration:
                self.values_iter = iter(self.values)  # restart the sweep
                return next(self.values_iter)


class PIDControl(Routine):
    """
    Provides basic a PID feedback loop, with the input attribute giving the error signal
    """

    def __init__(self, **kwargs):

        Routine.__init__(self, **kwargs)

        if 'input' not in kwargs:
            raise AttributeError('PIDControl routine requires an input (meter)!')

        self.input = kwargs['input']

        simple_pid = importlib.import_module('simple_pid')
        self.controller = simple_pid.PID(setpoint=self.values[0])

        if 'Kp' not in kwargs:
            raise AttributeError('PIDControl routine requires at least a proportional gain!')

        self.controller.tunings = (
            kwargs['Kp'], 0, 0
        )

        if 'Ki' in kwargs:  # use given integral gain
            self.controller.Ki = kwargs['Ki']
        elif 'Ti' in kwargs:  # or use integral time constant
            self.controller.Ki = kwargs['Kp'] / kwargs['Ti']

        if 'Kd' in kwargs:  # use given derivative gain
            self.controller.Kd = kwargs['Kd']
        elif 'Td' in kwargs:  # or use given derivative time constant
            self.controller.Kd = kwargs['Kp'] / kwargs['Td']

        if self.interval > 0:  # Ideally, the PID controller is operated at a fixed time interval
            self.controller.sample_time = self.interval

        self.model = kwargs.get('model', None)

    def __next__(self):

        now = self.clock.time()
        if self.start_time <= now < self.stop_time and now >= self.last_call + self.interval:
            self.last_call = now

            # Get input and determine output
            input_ = self.input.measure()
            output = self.controller(input_)

            return output

class Minimize(Routine):
    # under construction
    """
    Minimize a variable (meter) by simulated annealing
    """

    cool_modes = ['immediate', 'linear']

    def __init__(self, **kwargs):

        Routine.__init__(self, **kwargs)

        if 'input' not in kwargs:
            raise AttributeError('PIDControl routine requires an input (meter)!')

        self.input = kwargs['input']

        self.cool_mode = kwargs.get('cooling_mode', 'linear')
        if self.cool_mode not in self.cool_modes:
            raise AttributeError("Cooling mode not recognized! Must be 'immediate', 'linear' or 'exponential'")

        self.T0 = kwargs.get('initial_temperature', 1)
        self.T = kwargs.get('initial_temperature', 1)

        self.prior_setting = self.values[0]
        self.setting = self.values[0]
        self.scale = self.values[1]
        self.reading = self.input.measure()

    def __next__(self):

        now = self.clock.time()
        if self.start_time <= now < self.stop_time and now >= self.last_call + self.interval:
            self.cool()

            new_reading = self.input.measure()  # response to last knob setting
            is_better = self.is_better(new_reading)
            self.reading = new_reading

            if is_better:
                # record better setting and move on to next setting
                self.prior_setting = self.setting
                self.setting = self.setting + self.scale*(2*np.random.rand() - 1)
            else:
                # return to previous setting
                self.setting = self.prior_setting

            return self.setting


    def is_better(self, value):

        if value < self.reading:
            return True
        else:
            return np.exp(-(value - self.reading) / self.T) > np.random.rand()

    def cool(self):

        mode = self.cool_mode
        now = self.clock.time()

        start_time = self.start_time
        end_time = self.stop_time

        if self.cool_mode == 'linear':
            self.T = self.T0*(1 - (now - start_time) / (end_time - start_time))
        if self.cool_mode == 'immediate':
            self.T = 0


class Maximize(Routine):
    # under construction
    """
    Minimize a variable (meter) by simulated annealing
    """

    cool_modes = ['immediate', 'linear']

    def __init__(self, **kwargs):

        Routine.__init__(self, **kwargs)

        if 'input' not in kwargs:
            raise AttributeError('PIDControl routine requires an input (meter)!')

        self.input = kwargs['input']

        self.cool_mode = kwargs.get('cooling_mode', 'linear')
        if self.cool_mode not in self.cool_modes:
            raise AttributeError("Cooling mode not recognized! Must be 'immediate', 'linear' or 'exponential'")

        self.T0 = kwargs.get('initial_temperature', 1)
        self.T = kwargs.get('initial_temperature', 1)

        self.prior_setting = self.values[0]
        self.setting = self.values[0]
        self.scale = self.values[1]
        self.reading = self.input.measure()

    def __next__(self):

        now = self.clock.time()
        if self.start_time <= now < self.stop_time and now >= self.last_call + self.interval:

            self.cool()

            new_reading = self.input.measure()  # response to last knob setting
            is_better = self.is_better(new_reading)
            self.reading = new_reading

            if is_better:
                # record better setting and move on to next setting
                self.prior_setting = self.setting
                self.setting = self.setting + self.scale * (2 * np.random.rand() - 1)
            else:
                # return to previous setting
                self.setting = self.prior_setting

            return self.setting

    def is_better(self, value):

        if value > self.reading:
            return True
        else:
            return np.exp((value - self.reading) / self.T) > np.random.rand()

    def cool(self):

        mode = self.cool_mode
        now = self.clock.time()

        start_time = self.start_time
        end_time = self.stop_time

        if self.cool_mode == 'linear':
            self.T = self.T0 * (1 - (now - start_time) / (end_time - start_time))
        if self.cool_mode == 'immediate':
            self.T = 0


available_routines = {
    'Repeat': Repeat,
    'Ramp': Ramp,
    'Sweep': Sweep,
    'Transit': Transit,
    'PIDControl': PIDControl,
    'Minimize': Minimize,
    'Maximize': Maximize
}


class Schedule:
    """
    Schedule of settings to be applied to knobs, implemented as an iterable to allow for flexibility in combining different kinds of routines
    """

    def __init__(self, instrument_set=None, routines=None):
        """

        :param routines: (dict) dictionary of routine specifications (following the runcard yaml format).
        """

        self.clock = tiempo.Clock()

        self.stop_time = 0

        if instrument_set:
            self.instrument_set = instrument_set

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
            kind, variable = spec.pop('routine'), spec.pop('variable')

            if 'input' in spec:  # some routines require an input
                input = self.instrument_set.mapped_variables[spec['input']]
                routine = available_routines[kind](clock=self.clock, input=input, **spec)
            else:
                routine = available_routines[kind](clock=self.clock, **spec)

            routine = available_routines[kind](clock=self.clock, **spec)

            if routine.stop_time > self.stop_time:
                self.stop_time = routine.stop_time

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

        if self.clock.time() >= self.stop_time:
            raise StopIteration

        return output


class Experiment:

    default_settings = {
        'duration': np.inf,
        'follow-up': None,
        'step interval': 0,
        'plot interval': 10,
        'save interval': 60
    }

    def __init__(self, runcard):
        """

        :param runcard: (dict) runcard in dictionary form (built from a yaml file)
        """

        self.clock = tiempo.Clock()  # used for save timing

        self.last_step = -np.inf  # time of last step taken
        self.last_save = -np.inf  # time of last save

        self.runcard = runcard
        self.description = runcard["Description"]  # Required

        self.instruments = InstrumentSet(
            specs=runcard['Instruments'],  # Required
            variables=runcard['Variables'],  # Required
            alarms=runcard.get('Alarms', None),  # Optional
            presets=runcard.get('Presets', None),  # Optional
            postsets=runcard.get('Postsets', None)  # Optional
        )

        self.settings = runcard.get('Settings', self.default_settings)  # Optional; if not given, use default settings above
        self.plotting = runcard.get('Plotting', None)  # Optional
        self.schedule = Schedule(instrument_set=self.instruments, routines=runcard['Schedule'])  # Required

        # Prepare for data collection
        self.data = pd.DataFrame(
            columns=['Total Time', 'Schedule Time'] + list(self.instruments.mapped_variables)
        )  # Will contain history of knob settings and meter readings for the experiment.

        self.status = 'Starting...'
        self.followup = self.settings.get('follow-up', [])  # list of followup experiments or actions

        if isinstance(self.followup, str):  # In the runcard, a followup can be indicated by a single string
            # convert to list
            if self.followup.lower() == 'none':
                self.followup = []
            else:
                self.followup = [self.followup]

    def __iter__(self):
        return self

    def __next__(self):

        if 'Starting' in self.status:
            self.initialize()

        if 'Finished' in self.status:
            self.finalize()
            raise StopIteration

        self.next_step()
        self.check_time()
        self.check_alarms()
        self.update_status()

        return self.state

    def initialize(self):
        """
        Called on first step of experiment. Starts the clocks, updates status and gets a timestamp.

        :return: None
        """
        self.clock.start()  # start the experiment clock (real time)
        self.schedule.start()  # start the schedule clock (excludes pauses)
        self.status = 'Running'
        self.timestamp = tiempo.get_timestamp()

    def update_status(self):
        """
        Updates the experiment status for control and monitoring purposes.

        :return: None
        """
        remaining_time = self.schedule.stop_time - self.schedule.clock.time()

        if 'Paused' in self.status:  # When paused, status does not change
            return
        elif remaining_time == np.inf:
            self.status = f"Running indefinitely"
        else:
            # Show a countdown
            units = 'seconds'
            if remaining_time > 60:
                remaining_time = remaining_time / 60
                units = 'minutes'
                if remaining_time > 60:
                    remaining_time = remaining_time / 60
                    units = 'hours'

            self.status = f"Running: {np.round(remaining_time, 2)} {units} remaining"

    def next_step(self):
        """
        Progresses the experiment according to its schedule.

        :return: None
        """

        if self.clock.time() < self.last_step + tiempo.convert_time(self.settings['step interval']):
            return self.state  # Only apply settings at frequency limited by 'step interval' experiment setting

        self.last_step = self.clock.time()

        state = {'Total Time': self.clock.time(), 'Schedule Time': self.schedule.clock.time()}

        configuration = next(self.schedule)  # Get the next step from the schedule

        # Get previously set knob values if no corresponding routines are running for any knobs
        for name, variable in self.instruments.mapped_variables.items():
            if variable.knob and name not in configuration:
                configuration[name] = variable.get()

        state.update(configuration)

        self.instruments.apply(configuration)  # apply settings to instrument knobs
        readings = self.instruments.read()  # checking meter readings
        state.update(readings)  # now contains time values + knob values + meter readings

        self.state = pd.Series(state, name=datetime.datetime.now())
        self.data.loc[self.state.name] = self.state

        self.save()

    def check_time(self):
        """
        If experiment time has exceeded duration setting or schedule time has exceeded the scheduled stop time,
        end the experiment.

        :return: None
        """
        duration = tiempo.convert_time(self.settings['duration'])
        if self.schedule.clock.time() > self.schedule.stop_time:
            self.status = 'Finished: Schedule completed'

        if self.clock.time() > duration:
            self.status = 'Finished: Experiment duration exceeded'

    def check_alarms(self):
        """
        Check alarms in the instrument set, and follow-up with corresponding protocols if triggered

        :return: None
        """
        alarm_followups = []  # list of alarm protocols (runcards) to be executed upon terminating this experiment
        
        for name, alarm in self.instruments.alarms.items():
            if alarm['triggered']:

                protocol = alarm['protocol']
                if protocol.lower() == 'pause':
                    #  Pause until alarm is no longer triggered
                    self.schedule.clock.stop()
                    self.status = f"Schedule Paused: {name} alarm triggered!"
                elif 'yaml' in protocol:
                    # End this experiment and execute the specified runcard
                    alarm_followups.append(protocol)
                    self.status = f"Finished: {name} alarm triggered! Executing {protocol}..."
                elif 'check' in protocol.lower():
                    # Check an indicator (meter, typically of the human variety) to decide what to do
                    decider_name = protocol.split(' ')[1:]
                    decider = self.instruments.mapped_variables[decider_name]
                    self.status = f"Paused: {name} alarm triggered! Checking with {decider_name}..."

                    instrument = decider.instrument

                    if 'prompt' in instrument.knobs:  # true for ConsoleUser and SMSUser
                        # Give context to human
                        prompt = f"Alarm {name} triggered while running {self.description[name]}! DISABLE, PAUSE or END?"
                        instrument.set('prompt', prompt)

                    decision = decider.measure()

                    if decision.upper() == 'DISABLE':
                        self.instruments.alarms.pop(name)  # permanently removes alarm from experiment instrument set
                    elif decision.upper() == 'PAUSE':
                        #  Pause until alarm is no longer triggered
                        self.instruments.alarms[name]['protocol'] == 'pause'
                        self.schedule.clock.stop()
                        self.status = f"Schedule Paused: {name} alarm triggered!"
                    elif decision.upper() == 'END':
                        # End experiment immediately
                        self.instruments.alarms[name]['protocol'] == 'end'
                        self.status = f"Finished: {name} alarm triggered! Ending immediately"

                else:
                    # End experiment immediately
                    self.status = f"Finished: {name} alarm triggered! Ending immediately"

            else:
                # Unpause, if alarm protocol was to pause (PAUSE condition above) and alarm no longer triggered
                if self.status == f"Schedule Paused: {name} alarm triggered!":
                    self.schedule.clock.resume()
                    self.status = f"Running: {name} alarm is no longer triggered"

        if len(alarm_followups) > 0:
            self.followup = alarm_followups  # Cancel any scheduled follow-ups and just execute alarm protocols

    def save(self, save_now=False):
        """
        Save data, but at a maximum frequency set by the given save interval, unless overridden by the save_now keyword.

        :param save_now: (bool/str) If False, saves will only occur at a maximum frequency defined by the 'save interval' experimt setting. Otherwise, experiment data is saved immediately.
        :return: None
        """

        now = self.clock.time()
        save_interval = tiempo.convert_time(self.settings.get('save interval', 60))

        if now >= self.last_save + save_interval or save_now:
            self.data.to_csv(tiempo.timestamp_path('data.csv', timestamp=self.timestamp))
            self.last_save = self.clock.time()

    def finalize(self):
        """
        Called whenever status indicates that experiment has finished. Saves data and disconnects from instruments.

        :return: None
        """
        self.save('now')
        self.instruments.disconnect()
