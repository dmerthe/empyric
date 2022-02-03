import os
import re
import datetime
import numpy as np
import pandas as pd
import numbers

from empyric.adapters import *
from empyric.collection.instrument import *

class Keithley2400(Instrument):
    """
    Keithley 2400 Sourcemeter, a 20 W power supply and picoammeter
    """

    name = 'Keithley2400'

    supported_adapters = (
        (LinuxGPIB, {}),
        (PrologixGPIB, {}),
        (VISAGPIB, {})
    )

    # Available knobs
    knobs = (
        'voltage',
        'fast voltages',
        'current',
        'voltage range',
        'voltage limit',
        'current range',
        'current limit',
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
        'voltage':0,
        'output': 'ON',
        'voltage range': 200,
        'current range': 100e-3,
        'nplc': 1,
        'source_delay': 0,
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

    current_ranges = (1e-6, 10e-6, 100e-6, 1e-3, 10e-3, 100e-3, 1, 'AUTO')  # allowed current range settings
    voltage_ranges = (0.2, 2, 20, 200, 'AUTO')  # allowed voltage range settings
    ovp_levels = (20, 40, 60, 80, 100, 120, 140, 160, 210)  # over-voltage protection level settings

    @setter
    def set_source(self, variable):

        if variable not in ['voltage', 'current']:
            raise ValueError('Source must be either "current" or "voltage"')

        self.write(':SOUR:CLE:AUTO OFF')  # disable auto output-off

        self.set_output('OFF')

        if variable == 'voltage':

            self.write(':SOUR:FUNC VOLT')
            self.current = None

        if variable == 'current':

            self.write(':SOUR:FUNC CURR')
            self.voltage = None

    @setter
    def set_meter(self, variable):

        if variable not in ['voltage', 'current']:
            raise ValueError('Source must be either "current" or "voltage"')

        if variable == 'voltage':
            self.write(':SENS:FUNC "VOLT"')
            self.write(':FORM:ELEM VOLT')

        if variable == 'current':
            self.write(':SENS:FUNC "CURR"')
            self.write(':FORM:ELEM CURR')

    @setter
    def set_output(self, output):

        if output in [0, 'OFF', 'off']:
            self.write(':OUTP OFF')
            self.query(':OUTP?')  # for some reason, this is needed to ensure output off
        elif output in [1, 'ON', 'on']:
            self.write(':OUTP ON')
        else:
            raise ValueError(f'Ouput setting {output} not recognized!')

    @measurer
    def measure_voltage(self):

        if self.meter != 'voltage':
            self.set_meter('voltage')

        self.set_output('ON')

        def validator(response):
            match = re.match('.\d\.\d+E.\d\d', response)
            return bool(match)

        return float(self.query(':READ?', validator=validator))

    @measurer
    def measure_current(self):

        if self.meter != 'current':
            self.set_meter('current')

        self.set_output('ON')

        self.write(':TRIG:COUN 1')

        def validator(response):
            match = re.match('.\d\.\d+E.\d\d', response)
            return bool(match)

        return float(self.query(':READ?', validator=validator))

    @setter
    def set_voltage(self, voltage):

        if self.source != 'voltage':
            Warning(f'Switching source mode to voltage!')
            self.set_source('voltage')

        self.set_output('ON')

        self.write(':SOUR:VOLT:LEV %.2E' % voltage)

    @setter
    def set_current(self, current):

        if self.source != 'current':
            Warning(f'Switching source mode to current!')
            self.set_source('current')

        self.set_output('ON')

        self.write(':SOUR:CURR:LEV %.2E' % current)

    @setter
    def set_voltage_range(self, voltage_range):

        if voltage_range in self.voltage_ranges:
            if self.source == 'voltage':
                self.write(':SOUR:VOLT:RANGE %.2E' % voltage_range)
            else:
                if voltage_range == 'AUTO':
                    self.write(':SENS:VOLT:RANGE AUTO')
                else:
                    self.write(':SENS:VOLT:RANGE %.2E' % voltage_range)
        else:
            first_line = f'Given voltage range {voltage_range} is not a valid value for {self.name}\n'
            second_line = f'Valid values are {self.voltage_ranges}'
            raise ValueError(first_line + second_line)

    @setter
    def set_voltage_limit(self, voltage_limit):

        if self.source == 'voltage':
            if int(voltage_limit) in self.ovp_levels:
                self.write(':SOUR:VOLT:PROT %d' % int(voltage_limit))
            else:
                first_line = f'{self.name} is sourcing voltage, but given voltage limit {voltage_limit} is not a valid value\n'
                second_line = f'Valid values are {self.ovp_levels}'
                raise ValueError(first_line + second_line)
        else:
            self.write(':SENS:VOLT:PROT %.2E' % voltage_limit)

    @setter
    def set_current_range(self, current_range):

        if current_range in self.current_ranges:
            if self.source == 'current':
                self.write(':SOUR:CURR:RANGE %.2E' % current_range)
            else:
                if current_range == 'AUTO':
                    self.write(':SENS:CURR:RANGE AUTO')
                else:
                    self.write(':SENS:CURR:RANGE %.2E' % current_range)
        else:
            first_line = f'Given current range {current_range} is not a valid value for {self.name}\n'
            second_line = f'Valid values are {self.current_ranges}'
            raise ValueError(first_line + second_line)

    @setter
    def set_current_limit(self, current_limit):
        self.write(':SENS:CURR:PROT %.2E' %  current_limit)

    @setter
    def set_nplc(self, nplc):

        if self.meter == 'current':
            self.write(':SENS:CURR:NPLC %.2E' % nplc)
        elif self.meter == 'voltage':
            self.write(':SENS:VOLT:NPLC %.2E' % nplc)

    @setter
    def set_delay(self, delay):
        self.adapter.delay = delay

    @setter
    def set_fast_voltages(self, voltages):
        self.fast_voltages = voltages

        # import fast voltages, if specified as a path
        if type(self.fast_voltages) == str:  # can be specified as a path
            try:
                fast_voltage_data = pd.read_csv(self.fast_voltages)
            except FileNotFoundError:
                # probably in an experiment data directory; try going up a level
                working_subdir = os.getcwd()
                os.chdir('..')
                fast_voltage_data = pd.read_csv(self.fast_voltages)
                os.chdir(working_subdir)

            columns = fast_voltage_data.columns
            self.fast_voltages = fast_voltage_data[columns[0]].astype(float).values

    @measurer
    def measure_fast_currents(self):

        if self.source != 'voltage':
            self.set_source('voltage')

        self.set_output('ON')

        try:
            if len(self.fast_voltages) == 0:
                raise ValueError('Fast IV sweep voltages have not been set!')
        except AttributeError:
            raise ValueError('Fast IV sweep voltages have not been set!')

        self.write(':SOUR:VOLT:MODE LIST')

        list_length = len(self.fast_voltages)

        if list_length >= 100:  # can only take 100 voltages at a time
            sub_lists = [self.fast_voltages[i*100:(i+1)*100] for i in range(list_length // 100)]
        else:
            sub_lists = []

        if list_length % 100 > 0:
            sub_lists.append(self.fast_voltages[-(list_length % 100):])

        current_list = []

        normal_timeout = self.adapter.timeout
        self.adapter.timeout = None  # the response times can be long

        for voltage_list in sub_lists:
            voltage_str = ', '.join(['%.4E' % voltage for voltage in voltage_list])
            self.write(':SOUR:LIST:VOLT ' + voltage_str)
            self.write(':TRIG:COUN %d' % len(voltage_list))

            raw_response = self.query(':READ?').strip()
            current_list += [float(current_str) for current_str in raw_response.split(',')]

        self.adapter.timeout = normal_timeout  # put it back

        self.write(':SOUR:VOLT:MODE FIX')
        self.write(':TRIG:COUN 1')

        return np.array(current_list)

    @setter
    def set_source_delay(self, delay):
        self.write(':SOUR:DEL %.4E' % delay)


class Keithley2460(Instrument):
    """
    Keithley 2460 Sourcemeter, a 100 W power supply and picoammeter
    """

    name = 'Keithley2460'

    supported_adapters = (
        (LinuxGPIB, {}),
        (PrologixGPIB, {}),
        (VISAGPIB, {})
    )

    # Available knobs
    knobs = (
        'voltage',
        'fast voltages',
        'current',
        'voltage range',
        'voltage limit',
        'current range',
        'current limit',
        'nplc',
        'delay',
        'output',
        'source',
        'meter',
        'remote sense',
        'source delay'
    )

    presets = {
        'source': 'voltage',
        'meter': 'current',
        'voltage':0,
        'output': 'ON',
        'nplc': 1,
        'source delay': 0,
        'remote sense': 'OFF'
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

    current_ranges = (1e-6, 10e-6, 100e-6, 1e-3, 10e-3, 100e-3, 1, 4, 5, 7)
    voltage_ranges = (0.2, 2, 7, 10, 20, 100)
    ovp_levels = (2, 5, 10, 20, 40, 60, 80, 100, 120, 140, 160, 180)

    @setter
    def set_source(self, variable):

        if variable not in ['voltage', 'current']:
            raise ValueError('Source must be either "current" or "voltage"')

        self.set_output('OFF')

        if variable == 'voltage':

            self.write('SOUR:FUNC VOLT')
            self.current = None

        if variable == 'current':

            self.write('SOUR:FUNC CURR')
            self.voltage = None

    @setter
    def set_meter(self, variable):

        if variable == 'voltage':
            self.write('SENS:FUNC "VOLT"')
            self.write('DISP:VOLT:DIG 5')
        elif variable == 'current':
            self.write('SENS:FUNC "CURR"')
            self.write('DISP:CURR:DIG 5')
        else:
            raise ValueError('Source must be either "current" or "voltage"')

    @setter
    def set_output(self, output):

        if output in [0, 'OFF', 'off']:
            self.write(':OUTP OFF')
        elif output in [1, 'ON', 'on']:
            self.write(':OUTP ON')
        else:
            raise ValueError(f'Output setting {output} not recognized!')

    @measurer
    def measure_voltage(self):

        if self.meter != 'voltage':
            self.set_meter('voltage')

        if self.output == 'ON':
            return float(self.query('READ?').strip())
        else:
            return np.nan

    @measurer
    def measure_current(self):

        if self.meter != 'current':
            self.set_meter('current')

        if self.output == 'ON':
            return float(self.query('READ?').strip())
        else:
            return 0

    @setter
    def set_voltage(self, voltage):

        if self.source != 'voltage':
            Warning(f'Switching sourcing mode to voltage!')
            self.set_source('voltage')
            self.set_output('ON')  # output if automatically shut off when the source mode is changed

        self.write('SOUR:VOLT:LEV %.4E' % voltage)

    @setter
    def set_current(self, current):

        if self.source != 'current':
            Warning(f'Switching sourcing mode to current!')
            self.set_source('current')
            self.set_output('ON')  # output if automatically shut off when the source mode is changed

        self.write('SOUR:CURR:LEV %.4E' % current)

    @setter
    def set_voltage_range(self, voltage_range):

        if voltage_range in self.voltage_ranges:
            if self.source == 'voltage':
                self.write(':SOUR:VOLT:RANGE %.2E' % voltage_range)
            else:
                if voltage_range == 'AUTO':
                    self.write(':SENS:VOLT:RANGE:AUTO ON')
                else:
                    self.write(':SENS:VOLT:RANGE %.2E' % voltage_range)
        else:
            first_line = f'Given voltage range {voltage_range} is not a valid value for {self.name}\n'
            second_line = f'Valid values are {self.voltage_ranges}'
            raise ValueError(first_line + second_line)

    @setter
    def set_voltage_limit(self, voltage_limit):

        if self.source == 'voltage':
            if int(voltage_limit) in self.ovp_levels:
                self.write(':SOUR:VOLT:PROT PROT%d' % int(voltage_limit))
            else:
                first_line = f'{self.name} is sourcing voltage, but given voltage limit {voltage_limit} is not a valid value\n'
                second_line = f'Valid values are {self.ovp_levels}'
                raise ValueError(first_line + second_line)
        else:
            self.write(':SOUR:CURR:VLIM %.2E' % voltage_limit)

    @setter
    def set_current_range(self, current_range):

        if current_range in self.current_ranges:
            if self.source == 'current':
                self.write(':SOUR:CURR:RANGE %.2E' % current_range)
            else:
                if current_range == 'AUTO':
                    self.write(':SENS:CURR:RANGE:AUTO ON')
                else:
                    self.write(':SENS:CURR:RANGE %.2E' % current_range)
        else:
            first_line = f'Given current range {current_range} is not a valid value for {self.name}\n'
            second_line = f'Valid values are {self.current_ranges}'
            raise ValueError(first_line + second_line)

    @setter
    def set_current_limit(self, current_limit):
        self.write(':SOUR:VOLT:ILIM %.2E' % current_limit)

    @setter
    def set_nplc(self, nplc):

        if self.meter == 'current':
            self.write('CURR:NPLC %.2E' % nplc)
        elif self.meter == 'voltage':
            self.write('VOLT:NPLC %.2E' % nplc)

    @setter
    def set_delay(self, delay):
        self.adapter.delay = delay

    @setter
    def set_fast_voltages(self, voltages):
        self.fast_voltages = voltages

        # import fast voltages, if specified as a path
        if type(self.fast_voltages) == str:  # can be specified as a path
            try:
                fast_voltage_data = pd.read_csv(self.fast_voltages)
            except FileNotFoundError:
                # probably in an experiment data directory; try going up a level
                working_subdir = os.getcwd()
                os.chdir('..')
                fast_voltage_data = pd.read_csv(self.fast_voltages)
                os.chdir(working_subdir)

            columns = fast_voltage_data.columns
            self.fast_voltages = fast_voltage_data[columns[0]].astype(float).values

    @measurer
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
            self.write('SOUR:SWE:VOLT:LIST 1, %.2e' % self.source_delay)
            self.write('INIT')
            self.write('*WAI')
            raw_response = self.query('TRAC:DATA? 1, %d, "defbuffer1", SOUR, READ' % len(voltage_list)).strip()
            current_list += [float(current_str) for current_str in raw_response.split(',')[1::2]]

        self.adapter.timeout = normal_timeout  # put it back
        end = datetime.datetime.now()

        return np.array(current_list)

    @setter
    def set_source_delay(self, delay):

        if self.source == 'voltage':
            self.write('SOUR:VOLT:DEL %.4e' % delay)
        else:
            self.write('SOUR:CURR:DEL %.4e' % delay)

    @setter
    def set_remote_sense(self, state):
        if bool(state) or state in ['ON', '1']:
            self.write('VOLT:RSEN ON')
        else:
            self.write('VOLT:RSEN OFF')

        self.set_output('ON')

    @getter
    def get_remote_sense(self):
        if int(self.query('VOLT:RSEN?').strip()):
            return 'ON'
        else:
            return 'OFF'


class Keithley2651A(Instrument):
    """
    Keithley 2651A High Power (200 W) Sourcemeter
    """

    name = 'Keithley2651A'

    supported_adapters = (
        (LinuxGPIB, {}),
        (PrologixGPIB, {}),
        (VISAGPIB, {})
    )

    # Available knobs
    knobs = (
        'voltage',
        'fast voltages',
        'current',
        'voltage range',
        'voltage limit',
        'current range',
        'current limit',
        'nplc',
        'output',
        'source',
        'meter',
        'source delay'
    )

    presets = {
        'voltage range': 40,
        'current range': 5,
        'voltage':0,
        'output': 'ON',
        'nplc': 1,
        'source': 'voltage',
        'meter': 'current',
        'source_delay': 0
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

    @setter
    def set_source(self, variable):

        if variable == 'voltage':
            self.write('smua.source.func =  smua.OUTPUT_DCVOLTS')
        elif variable == 'current':
            self.write('smua.source.func = smua.OUTPUT_DCAMPS')
        else:
            raise ValueError('source must be either "current" or "voltage"')

    @setter
    def set_meter(self,variable):

        self.write('display.screen = display.SMUA')

        if variable == 'current':
            self.write('display.smua.measure.func = display.MEASURE_DCAMPS')

        if variable == 'voltage':
            self.write('display.smua.measure.func = display.MEASURE_DCVOLTS')

        # This sourcemeter does not require specifying the meter before taking a measurement

    @setter
    def set_output(self, output):

        if output in [0, 'OFF', 'off']:
            self.write('smua.source.output = smua.OUTPUT_OFF')
        elif output in [1, 'ON', 'on']:
            self.write('smua.source.output = smua.OUTPUT_ON')
        else:
            raise ValueError(f'Ouput setting {output} not recognized!')

    @measurer
    def measure_voltage(self):

        if self.meter != 'voltage':
            self.set_meter('voltage')

        if self.output == 'ON':
            return float(self.query('print(smua.measure.v())').strip())
        else:
            return np.nan

    @measurer
    def measure_current(self):

        if self.meter != 'current':
            self.set_meter('current')

        if self.output == 'ON':
            return float(self.query('print(smua.measure.i())').strip())
        else:
            return 0

    @measurer
    def set_voltage(self, voltage):

        if self.source != 'voltage':
            Warning(f'Switching sourcing mode!')
            self.set_source('voltage')
            self.set_output('ON')  # output if automatically shut off when the source mode is changed

        self.write(f'smua.source.levelv = {voltage}')

    @setter
    def set_current(self, current):

        if self.source != 'current':
            Warning(f'Switching sourcing mode!')
            self.set_source('current')
            self.set_output('ON')  # output if automatically shut off when the source mode is changed

        self.write(f'smua.source.leveli = {current}')

    @setter
    def set_voltage_range(self, voltage_range):

        if voltage_range == 'auto':
            self.write('smua.source.autorangev = smua.AUTORANGE_ON')
        else:
            self.write(f'smua.source.rangev = {voltage_range}')

    @setter
    def set_voltage_limit(self, voltage_limit):
        self.write(f'smua.source.limitv = {voltage_limit}')

    @setter
    def set_current_range(self, current_range):

        if current_range == 'auto':
            self.write('smua.source.autorangei = smua.AUTORANGE_ON')
        else:
            self.write(f'smua.source.rangei = {current_range}')

    @setter
    def set_current_limt(self, current_limit):
        self.write(f'smua.source.limiti = {current_limit}')

    @setter
    def set_nplc(self, nplc):
        self.write(f'smua.measure.nplc = {nplc}')

    @setter
    def set_fast_voltages(self, voltages):
        self.fast_voltages = voltages

        # import fast voltages, if specified as a path
        if type(self.fast_voltages) == str:  # can be specified as a path
            try:
                fast_voltage_data = pd.read_csv(self.fast_voltages)
            except FileNotFoundError:
                # probably in an experiment data directory; try going up a level
                working_subdir = os.getcwd()
                os.chdir('..')
                fast_voltage_data = pd.read_csv(self.fast_voltages)
                os.chdir(working_subdir)

            columns = fast_voltage_data.columns
            self.fast_voltages = fast_voltage_data[columns[0]].astype(float).values

    @measurer
    def measure_fast_currents(self):

        try:
            if len(self.fast_voltages) == 0:
                raise ValueError('Fast IV sweep voltages have not been set!')
        except AttributeError:
            raise ValueError('Fast IV sweep voltages have not been set!')

        voltage_lists = []
        current_list = []

        list_length = 100  # maximum number of voltages to sweep at a time

        for i in range(len(self.fast_voltages) // list_length):
            voltage_lists.append(self.fast_voltages[i*list_length:(i+1)*list_length])

        remainder = len(self.fast_voltages) % list_length
        if remainder:
            voltage_lists.append(self.fast_voltages[-remainder:])

        normal_timeout = self.backend.timeout
        self.backend.timeout = 60  # give it up to a minute to do sweep

        start = datetime.datetime.now()
        for voltage_list in voltage_lists:

            voltage_string = ', '.join([f'{voltage}' for voltage in voltage_list])

            self.write('vlist = {%s}' % voltage_string)
            self.write(f'SweepVListMeasureI(smua, vlist, 0.01, {len(voltage_list)})')
            raw_response = self.query(f'printbuffer(1, {len(voltage_list)}, smua.nvbuffer1)').strip()
            current_list += [float(current_str) for current_str in raw_response.split(',')]

            self.set_voltage(voltage_list[-1])  # hold last voltage until next sub-sweep

        end = datetime.datetime.now()

        self.connection.timeout = normal_timeout  # put it back

        self.write('display.screen = display.SMUA')
        self.write('display.smua.measure.func = display.MEASURE_DCAMPS')

        return np.array(current_list)

    @setter
    def set_source_delay(self,delay):
        self.write(f'smua.source.delay = {delay}')
