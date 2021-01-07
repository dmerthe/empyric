import os
import re
import datetime
import numpy as np
import pandas as pd
import numbers

from empyric.adapters import *
from empyric.collection.instrument import Instrument

class Keithley2400(Instrument):
    """
    Keithley 2400 Sourcemeter, a 20 W power supply and picoammeter
    """

    name = 'Keithley2400'

    supported_adapters = (
        (VISAGPIB, {}),
        (LinuxGPIB, {}),
        (PrologixGPIB, {})
    )

    # Available knobs
    knobs = (
        'voltage',
        'fast voltages',
        'current',
        'voltage range',
        'current range',
        'nplc',
        'delay',
        'output',
        'source',
        'meter',
        'source delay'
    )

    presets = {
        'source': 'voltage',
        'meter': 'current',
        'voltage range': 200,
        'current range': 100e-3,
        'nplc': 1,
        'source_delay': 0,
        'output': 'ON'
    }

    postsets = {
        'voltage': 0,
        'output': 'OFF'
    }

    # Available meters
    meters = (
        'voltage',
        'current',
        'fast currents'
    )

    fast_voltages = None

    def set_source(self, variable):

        if variable not in ['voltage', 'current']:
            raise ValueError('Source must be either "current" or "voltage"')

        self.write(':SOUR:CLE:AUTO OFF')  # disable auto output-off

        self.set_output('OFF')

        if variable == 'voltage':

            self.write(':SOUR:FUNC VOLT')
            self.knob_values['source'] = 'voltage'

            self.set_voltage_range(self.knob_values.get('voltage range', None))

            self.knob_values['current'] = None

        if variable == 'current':

            self.write(':SOUR:FUNC CURR')
            self.knob_values['source'] = 'current'

            self.set_current_range(self.knob_values.get('current range', None))

            self.knob_values['voltage'] = None

    def set_meter(self, variable):

        if variable not in ['voltage', 'current']:
            raise ValueError('Source must be either "current" or "voltage"')

        if variable == 'voltage':
            self.write(':SENS:FUNC "VOLT"')
            self.write(':FORM:ELEM VOLT')

        if variable == 'current':
            self.write(':SENS:FUNC "CURR"')
            self.write(':FORM:ELEM CURR')

        self.knob_values['meter'] = variable

    def set_output(self, output):

        if output in [0, 'OFF', 'off']:
            self.write(':OUTP OFF')
            self.query(':OUTP?')  # for some reason, this is needed to ensure output off
            self.knob_values['output'] = 'OFF'
        elif output in [1, 'ON', 'on']:
            self.write(':OUTP ON')
            self.knob_values['output'] = 'ON'
        else:
            raise ValueError(f'Ouput setting {output} not recognized!')

    def measure_voltage(self):

        if self.knob_values['meter'] != 'voltage':
            self.set_meter('voltage')

        self.set_output('ON')

        def validator(response):
            match = re.match('.\d\.\d+E.\d\d', response)
            return bool(match)

        return float(self.query(':READ?', validator=validator))

    def measure_current(self):

        if self.knob_values['meter'] != 'current':
            self.set_meter('current')

        self.set_output('ON')

        def validator(response):
            match = re.match('.\d\.\d+E.\d\d', response)
            return bool(match)

        return float(self.query(':READ?', validator=validator))

    def set_voltage(self, voltage):

        if self.knob_values['source'] != 'voltage':
            Warning(f'Switching sourcing mode!')
            self.set_source('voltage')

        self.set_output('ON')

        self.write(':SOUR:VOLT:LEV %.2E' % voltage)

        self.knob_values['voltage'] = voltage

    def set_current(self, current):

        if self.knob_values['source'] != 'current':
            Warning(f'Switching sourcing mode!')
            self.set_source('current')

        self.set_output('ON')

        self.write(':SOUR:CURR:LEV %.2E' % current)

        self.knob_values['current'] = current

    def set_voltage_range(self, voltage_range):

        allowed_voltage_ranges = (0.2, 2, 20, 200) # allowable voltage ranges

        if voltage_range in allowed_voltage_ranges:

            if self.knob_values['source'] == 'voltage':
                self.write(':SOUR:VOLT:RANG %.2E' % voltage_range)
            else:
                self.write(':SENS:VOLT:PROT %.2E' % voltage_range)
                self.write(':SENS:VOLT:RANG %.2E' % voltage_range)

            self.knob_values['voltage range'] = voltage_range

        elif isinstance(voltage_range, numbers.Number):

            # Find nearest encapsulating voltage range
            try:
                nearest = np.argwhere( voltage_range <= np.array(allowed_voltage_ranges) ).flatten()[0]
            except IndexError:
                nearest = -1

            self.set_voltage_range(allowed_voltage_ranges[nearest])

        else:
            if self.knob_values['source'] == 'voltage':
                self.write(':SOUR:VOLT:RANG:AUTO 1')
            else:
                self.write(':SENS:VOLT:PROT MAX')
                self.write(':SENS:VOLT:RANG:AUTO 1')

            self.knob_values['voltage range'] = 'AUTO'

            Warning('given voltage range is not permitted; set to auto-range.')

    def set_current_range(self, current_range):

        allowed_current_ranges = (1e-6, 10e-6, 100e-6, 1e-3, 10e-3, 100e-3, 1)

        if current_range in allowed_current_ranges:

            if self.knob_values['source'] == 'current':
                self.write(':SOUR:CURR:RANG %.2E' % current_range)
            else:
                self.write(':SENS:CURR:PROT %.2E' % current_range)
                self.write(':SENS:CURR:RANG %.2E' % current_range)

            self.knob_values['current range'] = current_range

        elif isinstance(current_range, numbers.Number):

            # Find nearest encapsulating current range
            try:
                nearest = np.argwhere( current_range <= np.array(allowed_current_ranges) ).flatten()[0]
            except IndexError:
                nearest = -1

            Warning(f'Given current range not an option, setting to {allowed_current_ranges[nearest]} A instead')
            self.set_current_range(allowed_current_ranges[nearest])

        else:

            if self.knob_values['source'] == 'current':
                self.write(':SOUR:CURR:RANG:AUTO 1')
            else:
                self.write(':SENS:CURR:PROT MAX')
                self.write(':SENS:CURR:RANG:AUTO 1')

            Warning('given current range is not permitted; set to auto-range.')
            self.knob_values['current range'] = 'AUTO'

    def set_nplc(self, nplc):

        if self.knob_values['meter'] == 'current':
            self.write(':SENS:CURR:NPLC %.2E' % nplc)
        elif self.knob_values['meter'] == 'voltage':
            self.write(':SENS:VOLT:NPLC %.2E' % nplc)

        self.knob_values['nplc'] = nplc

    def set_delay(self, delay):

        self.delay = delay
        self.knob_values['delay'] = delay

    def set_fast_voltages(self, path):

        self.knob_values['fast voltages'] = path

        working_subdir = os.getcwd()
        os.chdir('..')

        fast_voltage_data = pd.read_csv(path)

        try:
            column_name = [col for col in fast_voltage_data if 'voltage' in col.lower()][0]
        except IndexError:
            raise IndexyError('unable to locate voltage data for fast IV sweep!')

        self.fast_voltages = fast_voltage_data[column_name].values

        os.chdir(working_subdir)

    def measure_fast_currents(self):

        if self.knob_values['source'] != 'voltage':
            self.set_source('voltage')

        self.set_output('ON')

        try:
            if len(self.fast_voltages) == 0:
                raise ValueError('Fast IV sweep voltages have not been set!')
        except AttributeError:
            raise ValueError('Fast IV sweep voltages have not been set!')

        self.write(':SOUR:VOLT:MODE LIST')

        list_length = len(fast_voltages)

        if list_length >= 100:
            sub_lists = [self.fast_voltages[i*100:(i+1)*100] for i in range(list_length // 100)]
        else:
            sub_lists = []

        if list_length % 100 > 0:
            sub_lists.append(self.fast_voltages[-(list_length % 100):])

        current_list = []

        normal_timeout = self.adapter.timeout
        self.adapter.timeout = None  # the response times can be long

        start = datetime.datetime.now()
        for voltage_list in sub_lists:

            voltage_str = ', '.join(['%.4E' % voltage for voltage in voltage_list])
            self.write(':SOUR:LIST:VOLT ' + voltage_str)
            self.write(':TRIG:COUN %d' % len(voltage_list))

            raw_response = self.query(':READ?').strip()
            current_list += [float(current_str) for current_str in raw_response.split(',')]

        self.adapter.timeout = normal_timeout  # put it back

        self.write(':SOUR:VOLT:MODE FIX')

        # Save current measurements to CSV file
        now = datetime.datetime.now()
        fast_iv_data = pd.DataFrame(
            {'fast voltages': self.fast_voltages, 'fast currents': current_list},
            index=pd.date_range(start=start, end=end, periods=len(current_list))
        )

        timestamp = now.strftime('%Y%m%d-%H%M%S')
        path = self.name + '-fast_currents_measurement-' + timestamp + '.csv'
        fast_iv_data.to_csv(path)

        return path

    def set_source_delay(self, delay):

        self.knob_values['source delay'] = delay
        self.write(':SOUR:DEL %.4E' % delay)


class Keithley2460(Instrument):
    """
    Keithley 2460 Sourcemeter, a 100 W power supply and picoammeter
    """

    name = 'Keithley2460'

    supported_adapters = (
        (VISAGPIB, {}),
        (LinuxGPIB, {}),
        (PrologixGPIB, {})
    )

    # Available knobs
    knobs = (
        'voltage',
        'fast voltages',
        'current',
        'voltage range',
        'current range',
        'nplc',
        'delay',
        'output',
        'source',
        'meter',
        'source delay'
    )

    presets = {
        'source': 'voltage',
        'meter': 'current',
        'voltage range': 100,
        'current range': 1,
        'nplc': 1,
        'source_delay': 0,
        'output': 'ON'
    }

    postsets = {
        'voltage': 0,
        'output': 'OFF'
    }

    # Available meters
    meters = (
        'voltage',
        'current',
        'fast currents'
    )

    fast_voltages = None

    def set_source(self, variable):

        if variable not in ['voltage', 'current']:
            raise ValueError('Source must be either "current" or "voltage"')

        self.set_output('OFF')

        if variable == 'voltage':

            self.write('SOUR:FUNC VOLT')
            self.knob_values['source'] = 'voltage'
            self.knob_values['current'] = None

        if variable == 'current':

            self.write('SOUR:FUNC CURR')
            self.knob_values['source'] = 'current'
            self.knob_values['voltage'] = None

    def set_meter(self, variable):

        if variable == 'voltage':
            self.write('SENS:FUNC "VOLT"')
            self.write('DISP:VOLT:DIG 5')
        elif variable == 'current':
            self.write('SENS:FUNC "CURR"')
            self.write('DISP:CURR:DIG 5')
        else:
            raise ValueError('Source must be either "current" or "voltage"')

        self.knob_values['meter'] = variable

    def set_output(self, output):

        if output in [0, 'OFF', 'off']:
            self.write(':OUTP OFF')
            self.knob_values['output'] = 'OFF'
        elif output in [1, 'ON', 'on']:
            self.write(':OUTP ON')
            self.knob_values['output'] = 'ON'
        else:
            raise ValueError(f'Output setting {output} not recognized!')

    def measure_voltage(self):

        if self.knob_values['meter'] != 'voltage':
            self.set_meter('voltage')

        if self.knob_values['output'] == 'ON':
            return float(self.query('READ?').strip())
        else:
            return np.nan

    def measure_current(self):

        if self.knob_values['meter'] != 'current':
            self.set_meter('current')

        if self.knob_values['output'] == 'ON':
            return float(self.query('READ?').strip())
        else:
            return 0

    def set_voltage(self, voltage):

        if self.knob_values['source'] != 'voltage':
            Warning(f'Switching sourcing mode to voltage!')
            self.set_source('voltage')
            self.set_output('ON')  # output if automatically shut off when the source mode is changed

        self.write('SOUR:VOLT:LEV %.4E' % voltage)

        self.knob_values['voltage'] = voltage

    def set_current(self, current):

        if self.knob_values['source'] != 'current':
            Warning(f'Switching sourcing mode to current!')
            self.set_source('current')
            self.set_output('ON')  # output if automatically shut off when the source mode is changed

        self.write('SOUR:CURR:LEV %.4E' % current)

        self.knob_values['current'] = current

    def set_voltage_range(self, voltage_range):

        allowed_voltage_ranges = (0.2, 2, 7, 10, 20, 100)

        if voltage_range in allowed_voltage_ranges:

            if self.knob_values['source'] == 'voltage':
                self.write('SOUR:VOLT:RANG %.2e' % voltage_range)
            else:
                self.write('SOUR:CURR:VLIM %.2e' % voltage_range)
                self.write('SENS:VOLT:RANG %.2e' % voltage_range)

            self.knob_values['voltage range'] = voltage_range

        elif isinstance(voltage_range, numbers.Number):

            # Find nearest encapsulating voltage range
            try:
                nearest = np.argwhere( voltage_range <= np.array(allowed_voltage_ranges) ).flatten()[0]
            except IndexError:
                nearest = -1

            self.set_voltage_range(allowed_voltage_ranges[nearest])

        elif voltage_range == 'AUTO':

            if self.knob_values['source'] == 'voltage':
                self.write(':SOUR:VOLT:RANG:AUTO ON')
            else:
                self.write(':SOUR:CURR:VLIM MAX')
                self.write(':SENS:VOLT:RANG:AUTO ON')

            self.knob_values['voltage range'] = 'AUTO'
        else:
            Warning('given voltage range is not permitted; voltage range unchanged')


    def set_current_range(self, current_range):

        allowed_current_ranges = (1e-6, 10e-6, 100e-6, 1e-3, 10e-3, 100e-3, 1, 4, 5, 7)

        if current_range in allowed_current_ranges:

            if self.knob_values['source'] == 'current':
                self.write('SOUR:CURR:RANG %.2E' % current_range)
            else:
                self.write('SOUR:VOLT:ILIM %.2e' % current_range)
                self.write('SENS:CURR:RANG %.2E' % current_range)

            self.knob_values['current range'] = current_range

        elif isinstance(current_range, numbers.Number):

            # Find nearest encapsulating current range
            try:
                nearest = np.argwhere(current_range <= np.array(allowed_current_ranges)).flatten()[0]
            except IndexError:
                nearest = -1

            self.set_current_range(allowed_current_ranges[nearest])

        elif current_range == 'AUTO':

            if self.knob_values['source'] == 'current':
                self.write('SOUR:CURR:RANG:AUTO 1')
            else:
                self.write('SOUR:VOLT:ILIM MAX')
                self.write('SENS:CURR:RANG:AUTO 1')

            self.knob_values['current range'] = 'AUTO'
        else:
            Warning('given current range is not permitted; current range unchanged')

    def set_nplc(self, nplc):

        if self.knob_values['meter'] == 'current':
            self.write('CURR:NPLC %.2E' % nplc)
        elif self.knob_values['meter'] == 'voltage':
            self.write('VOLT:NPLC %.2E' % nplc)

        self.knob_values['nplc'] = nplc

    def set_delay(self, delay):

        self.delay = delay
        self.knob_values['delay'] = delay

    def set_fast_voltages(self, path):

        if self.knob_values['source'] != 'voltage':
            self.set_source('voltage')

        self.knob_values['fast voltages'] = path

        working_subdir = os.getcwd()
        os.chdir('..')

        fast_voltage_data = pd.read_csv(path)

        try:
            column_name = [col for col in fast_voltage_data if 'voltage' in col.lower()][0]
        except IndexError:
            raise IndexyError('unable to locate voltage data for fast IV sweep!')

        self.fast_voltages = fast_voltage_data[column_name].values

        os.chdir(working_subdir)

    def measure_fast_currents(self):

        try:
            self.fast_voltages
        except AttributeError:
            raise ValueError('Fast IV sweep voltages have not been set!')

        if len(self.fast_voltages) == 0:
            raise ValueError('Fast IV sweep voltages have not been set!')

        path = self.name+'-fast_iv_measurement.csv'

        list_length = len(self.fast_voltages)

        if list_length >= 100:
            sub_lists = [self.fast_voltages[i*100:(i+1)*100] for i in range(list_length // 100)]
        else:
            sub_lists = []

        if list_length % 100 > 0:
            sub_lists.append(self.fast_voltages[-(list_length % 100):])

        current_list = []

        normal_timeout = self.adapter.timeout
        self.adapter.timeout = None  # the response times can be long

        start = datetime.datetime.now()
        for voltage_list in sub_lists:

            voltage_str = ', '.join(['%.4E' % voltage for voltage in voltage_list])
            self.write('SOUR:LIST:VOLT ' + voltage_str)
            self.write('SOUR:SWE:VOLT:LIST 1, %.2e' % self.knob_values['source delay'])
            self.write('INIT')
            self.write('*WAI')
            raw_response = self.query('TRAC:DATA? 1, %d, "defbuffer1", SOUR, READ' % len(voltage_list)).strip()
            current_list += [float(current_str) for current_str in raw_response.split(',')[1::2]]

        self.adapter.timeout = normal_timeout  # put it back
        end = datetime.datetime.now()

        # Save current measurements to CSV file
        now = datetime.datetime.now()
        fast_iv_data = pd.DataFrame(
            {'fast voltages': self.fast_voltages, 'fast currents': current_list},
            index=pd.date_range(start=start, end=end, periods=len(current_list))
        )

        timestamp = now.strftime('%Y%m%d-%H%M%S')
        path = self.name + '-fast_IV_sweep-' + timestamp + '.csv'
        fast_iv_data.to_csv(path)

        self.set_source(self.knob_values['source'])
        self.set_meter(self.knob_values['meter'])

        return path

    def set_source_delay(self, delay):

        self.knob_values['source delay'] = delay

        if self.knob_values['source'] == 'voltage':
            self.write('SOUR:VOLT:DEL %.4e' % delay)
        else:
            self.write('SOUR:CURR:DEL %.4e' % delay)


class Keithley2651A(Instrument):
    """
    Keithley 2651A High Power (200 W) Sourcemeter
    """

    name = 'Keithley2651A'

    supported_adapters = (
        (VISAGPIB, {}),
        (LinuxGPIB, {}),
        (PrologixGPIB, {})
    )

    # Available knobs
    knobs = (
        'voltage',
        'fast voltages',
        'current',
        'voltage range',
        'current range',
        'nplc',
        'output',
        'source',
        'meter',
        'source delay'
    )

    presets = {
        'voltage range': 40,
        'current range': 5,
        'nplc': 1,
        'source': 'voltage',
        'meter': 'current',
        'source_delay': 0,
        'output': 'ON'
    }

    postsets = {
        'voltage': 0,
        'output': 'OFF'
    }

    # Available meters
    meters = (
        'voltage',
        'current',
        'fast currents'
    )

    fast_voltages = None

    def set_source(self, variable):

        if variable in ['voltage','current']:
            self.knob_values['source'] = variable
        else:
            raise ValueError('source must be either "current" or "voltage"')

        if variable == 'voltage':

            self.write('smua.source.func =  smua.OUTPUT_DCVOLTS')
            self.set_voltage_range(self.knob_values['voltage range'])

            self.knob_values['current'] = None

        if variable == 'current':

            self.write('smua.source.func = smua.OUTPUT_DCAMPS')
            self.set_current_range(self.knob_values['current range'])

            self.knob_values['voltage'] = None

    def set_meter(self,variable):

        self.knob_values['meter'] = variable

        if variable == 'current':
            self.write('display.screen = display.SMUA')
            self.write('display.smua.measure.func = display.MEASURE_DCAMPS')

        if variable == 'voltage':
            self.write('display.screen = display.SMUA')
            self.write('display.smua.measure.func = display.MEASURE_DCVOLTS')

        # This sourcemeter does not require specifying the meter before taking a measurement

    def set_output(self, output):

        if output in [0, None, 'OFF', 'off']:
            self.write('smua.source.output = smua.OUTPUT_OFF')
            self.knob_values['output'] = 'OFF'
        elif output in [1, 'ON', 'on']:
            self.write('smua.source.output = smua.OUTPUT_ON')
            self.knob_values['output'] = 'ON'
        else:
            raise ValueError(f'Ouput setting {output} not recognized!')

    def measure_voltage(self):

        if self.knob_values['meter'] != 'voltage':
            self.set_meter('voltage')

        if self.knob_values['output'] == 'ON':
            return float(self.query('print(smua.measure.v())').strip())
        else:
            return np.nan

    def measure_current(self):

        if self.knob_values['meter'] != 'current':
            self.set_meter('current')

        if self.knob_values['output'] == 'ON':
            return float(self.query('print(smua.measure.i())').strip())
        else:
            return 0

    def set_voltage(self, voltage):

        if self.knob_values['source'] != 'voltage':
            Warning(f'Switching sourcing mode!')
            self.set_source('voltage')
            self.set_output('ON')  # output if automatically shut off when the source mode is changed

        self.write(f'smua.source.levelv = {voltage}')

        self.knob_values['voltage'] = voltage

    def set_current(self, current):

        if self.knob_values['source'] != 'current':
            Warning(f'Switching sourcing mode!')
            self.set_source('current')
            self.set_output('ON')  # output if automatically shut off when the source mode is changed

        self.write(f'smua.source.leveli = {current}')

        self.knob_values['current'] = current

    def set_voltage_range(self, voltage_range):

        if voltage_range == 'auto':
            self.write('smua.source.autorangev = smua.AUTORANGE_ON')
        else:
            self.write(f'smua.source.rangev = {voltage_range}')
            self.write(f'smua.source.limitv = {voltage_range}')

        self.knob_values['voltage range'] = voltage_range
        self.voltage_range = voltage_range

    def set_current_range(self, current_range):

        if current_range == 'auto':
            self.write('smua.source.autorangei = smua.AUTORANGE_ON')
        else:
            self.write(f'smua.source.rangei = {current_range}')
            self.write(f'smua.source.limiti = {current_range}')

        self.knob_values['current range'] = current_range
        self.current_range = current_range

    def set_nplc(self, nplc):

        self.write(f'smua.measure.nplc = {nplc}')

        self.knob_values['nplc'] = nplc
        self.nplc = nplc

    def set_fast_voltages(self, *args):

        if len(args) == 0:
            filedialog = importlib.import_module('tkinter.filedialog')
            path = filedialog.askopenfilename(title="Select CSV File with Fast IV Voltages")
        else:
            path = args[0]

        self.knob_values['fast voltages'] = path

        working_subdir = os.getcwd()
        os.chdir('..')  #  fast voltages should be in the parent working directory, along with the runcard

        fast_voltage_data = pd.read_csv(path)

        self.fast_voltages = np.round(fast_voltage_data['Voltage'].values, 2)

        os.chdir(working_subdir)  # return to the current working directory

    def measure_fast_currents(self):

        try:
            self.fast_voltages
        except AttributeError:
            raise ValueError('Fast IV sweep voltages have not been set!')

        if len(self.fast_voltages) == 0:
            raise ValueError('Fast IV sweep voltages have not been set!')

        path = self.name+'-fast_iv_measurement.csv'

        voltage_lists = []
        current_list = []

        list_length = 100  # maximum number of voltages to sweep at a time

        for i in range(len(self.fast_voltages) // list_length):
            voltage_lists.append(self.fast_voltages[i*list_length:(i+1)*list_length])

        remainder = len(self.fast_voltages) % list_length
        if remainder:
            voltage_lists.append(self.fast_voltages[-remainder:])

        # self.connection.timeout = float('inf')
        self.connection.timeout = 60 * 1000  # give it up to a minute to do sweep

        start = datetime.datetime.now()
        for voltage_list in voltage_lists:

            voltage_string = ', '.join([f'{voltage}' for voltage in voltage_list])

            self.write('vlist = {%s}' % voltage_string)
            self.write(f'SweepVListMeasureI(smua, vlist, 0.01, {len(voltage_list)})')
            raw_response = self.query(f'printbuffer(1, {len(voltage_list)}, smua.nvbuffer1)').strip()
            current_list += [float(current_str) for current_str in raw_response.split(',')]

            self.set_voltage(voltage_list[-1])  # hold last voltage until next sub-sweep

        self.connection.timeout = 1000  # put it back
        end = datetime.datetime.now()

        self.write('display.screen = display.SMUA')
        self.write('display.smua.measure.func = display.MEASURE_DCAMPS')

        # Save current measurements to CSV file
        now = datetime.datetime.now()
        fast_iv_data = pd.DataFrame(
            {'fast voltages': self.fast_voltages, 'fast currents': current_list},
            index=pd.date_range(start=start, end=end, periods=len(current_list))
        )

        timestamp = now.strftime('%Y%m%d-%H%M%S')
        path = self.name + '-fast_IV_sweep-' + timestamp + '.csv'
        fast_iv_data.to_csv(path)

        return path

    def set_source_delay(self,delay):

        self.knob_values['source delay'] = delay
        self.write(f'smua.source.delay = {delay}')