import numbers, importlib
import numpy as np
from empyric.adapters import *
from empyric.collection.instrument import *


class Keithley2110(Instrument):
    """
    Keithley 2110 digital multimeter instrument
    """

    name = "Keithley2110"

    supported_adapters = (
        (USB, {}),
    )

    knobs = (
        'voltage range',
        'current range'
    )

    meters = (
        'voltage',
        'current',
        'temperature'
    )

    _mode = None

    @property
    def mode(self):
        return self._mode

    @mode.setter
    def mode(self, mode):
        if mode == 'voltage':
            self.write('FUNC "VOLT"')
            self._mode = 'voltage'
        if mode == 'current':
            self.write('FUNC "CURR"')
            self._mode = 'current'
        if mode == 'temperature':
            self.write('FUNC "TCO"')
            self._mode = 'temperature'

    @setter
    def set_voltage_range(self, voltage_range):

        allowed_voltage_ranges = (0.1, 1, 10, 100, 1000)

        if voltage_range in allowed_voltage_ranges:
            self.write('VOLT:RANG %.2e' % voltage_range)
        elif isinstance(voltage_range, numbers.Number):

            # Find nearest encapsulating voltage range
            try:
                nearest = np.argwhere(
                    voltage_range <= np.array(allowed_voltage_ranges)
                ).flatten()[0]
            except IndexError:
                nearest = -1

            self.set_voltage_range(allowed_voltage_ranges[nearest])

            Warning(
                'Given voltage range not an option, '
                f'setting to {allowed_voltage_ranges[nearest]} V instead'
            )

        elif voltage_range == 'AUTO':
            self.write('VOLT:RANG:AUTO')
        else:
            raise ValueError(
                f'voltage range choice {voltage_range} not permitted!'
            )

    @setter
    def set_current_range(self, current_range):

        allowed_current_ranges = (0.01, 0.1, 1, 3, 10)

        if current_range in allowed_current_ranges:
            self.write('CURR:RANG %.2e' % current_range)
        elif isinstance(current_range, numbers.Number):
            # Find nearest encapsulating current range
            try:
                nearest = np.argwhere(
                    current_range <= np.array(allowed_current_ranges)
                ).flatten()[0]
            except IndexError:
                nearest = -1

            self.set_current_range(allowed_current_ranges[nearest])

            Warning(
                'Given current range not an option, '
                f'setting to {allowed_current_ranges[nearest]} A instead'
            )

        elif current_range == 'AUTO':
            self.write('CURR:RANG:AUTO')
        else:
            raise ValueError(
                f'current range choice {current_range} not permitted!'
            )

    @measurer
    def measure_voltage(self):
        if self.mode != 'voltage':
            self.mode = 'voltage'
        return float(self.query('READ?'))

    @measurer
    def measure_current(self):
        if self.mode != 'current':
            self.mode = 'current'
        return float(self.query('READ?'))

    @measurer
    def measure_temperature(self):
        if self.mode != 'temperature':
            self.mode = 'temperature'
        return float(self.query('READ?'))


class Keithley6500(Instrument):
    """
    Multimeter with 6.5 digits and high speed scanning and digitizing
    capabilities.
    """

    name = 'Keithley6500'

    supported_adapters = (
        (Socket, {'write_termination': '\n'}),
    )

    knobs = (
        'meter',  # either 'voltage', 'current', 'fast voltages' or 'fast currents'
        'sample count',  # number of digitized measurements for fast voltages/currents
        'sample rate',  # sample rate for fast voltages/currents
        'nplc',  # number of power line cycles between measurements
        'range',  # measurement range for either voltage or current
    )

    meters = (
        'voltage',
        'current',
        'fast voltages',
        'fast currents'
    )

    @setter
    def set_meter(self, meter):

        if meter.lower() == 'voltage':
            self.write(f'dmm.measure.func = dmm.FUNC_DC_VOLTAGE')
        elif meter.lower() == 'current':
            self.write(f'dmm.measure.func = dmm.FUNC_DC_CURRENT')
        elif meter.lower() == 'fast voltages':
            self.write(f'dmm.digitize.func = dmm.FUNC_DIGITIZE_VOLTAGE')
        elif meter.lower() == 'fast currents':
            self.write(f'dmm.digitize.func = dmm.FUNC_DIGITIZE_CURRENT')
        else:
            raise ValueError(f'invalid meter "{meter}"')

        return meter.lower()

    @getter
    def get_meter(self):

        meter = self.query('print(dmm.measure.func)')

        if 'dmm.FUNC_NONE' in meter:
            meter = self.query('print(dmm.digitize.func)')

            if 'dmm.FUNC_NONE' in meter:
                raise ValueError(f'meter is undefined for {self.name}')

        meter_dict = {
            'dmm.FUNC_DC_CURRENT': 'current',
            'dmm.FUNC_DC_VOLTAGE': 'voltage',
            'dmm.FUNC_DIGITIZE_CURRENT': 'fast currents',
            'dmm.FUNC_DIGITIZE_VOLTAGE': 'fast voltages'
        }

        if meter in meter_dict:
            return meter_dict[meter]
        else:
            return None

    @setter
    def set_sample_count(self, count):

        if 'fast' in self.meter:
            self.write(f'dmm.digitize.count = {int(count)}')
        else:
            return np.nan

    @getter
    def get_sample_count(self):

        if 'fast' in self.meter:
            response = self.query('print(dmm.digitize.count)')

            if 'nil' in response:
                return np.nan
            else:
                return int(response)
        else:
            return np.nan

    @setter
    def set_sample_rate(self, rate):

        if 'fast' in self.meter:
            self.write(f'dmm.digitize.samplerate = {rate}')
        else:
            return np.nan

    @getter
    def get_sample_rate(self):

        if 'fast' in self.meter:

            response = self.query(f'print(dmm.digitize.samplerate)')

            if 'nil' in response:
                return np.nan
            else:
                return recast(response)
        else:
            return np.nan

    @setter
    def set_nplc(self, nplc):

        if 'fast' not in self.meter:
            self.write(f'dmm.measure.nplc = {nplc}')
        else:
            return np.nan

    @getter
    def get_nplc(self):

        if 'fast' not in self.meter:
            return recast(self.query('print(dmm.measure.nplc)'))
        else:
            return np.nan

    @setter
    def set_range(self, _range):

        if 'fast' not in self.meter:
            if _range.lower() == 'auto':
                self.write('dmm.measure.autorange = dmm.ON')
            else:
                self.write(f'dmm.measure.range = {_range}')
        else:
            return np.nan

    @getter
    def get_range(self):

        if 'fast' not in self.meter:
            if self.query('print(dmm.measure.autorange)') == 'dmm.ON':
                return 'auto'
            else:
                return recast(self.query('print(dmm.measure.range)'))
        else:
            return np.nan

    @measurer
    def measure_current(self):

        if self.meter != 'current':
            self.set_meter('current')

        return recast(self.query('print(dmm.measure.read())'))

    @measurer
    def measure_voltage(self):

        if self.meter != 'voltage':
            self.set_meter('voltage')

        return recast(self.query('print(dmm.measure.read())'))


class LabJackU6(Instrument):
    """
    LabJack U6 Multi-function DAQ
    """

    name = 'LabJackU6'

    supported_adapters = (
        # custom setup below until I can get serial or modbus comms to work
        (Adapter, {})
    )

    knobs = (
        'DAC0 ',
        'DAC1',
    )

    meters = (
        'AIN0',
        'AIN1',
        'AIN2',
        'AIN3',
        'internal temperature',
        'temperature 0',  # AIN0 / 41 uV / C
        'temperature 1',
        'temperature 2',
        'temperature 3',
    )

    def __init__(self, *args, **kwargs):
        u6 = importlib.import_module('u6')
        self.backend = u6.U6()

        if len(args) == 0 and 'address' not in kwargs:
            kwargs['address'] = str(self.backend.serialNumber)

        Instrument.__init__(self, *args, **kwargs)

    def write(self, register, value):
        self.backend.writeRegister(register, value)

    def read(self, register):
        return self.backend.readRegister(register)

    @setter
    def set_DAC0(self, value):
        self.write(5000, value)

    @setter
    def set_DAC1(self, value):
        self.write(5002, value)

    @getter
    def get_DAC0(self):
        self.read(5000)

    @getter
    def get_DAC1(self):
        self.read(5002)

    @measurer
    def measure_AIN0(self):
        return self.read(0)

    @measurer
    def measure_AIN1(self):
        return self.read(2)

    @measurer
    def measure_AIN2(self):
        return self.read(4)

    @measurer
    def measure_AIN3(self):
        return self.read(6)

    @measurer
    def measure_internal_temperature(self):
        return self.backend.getTemperature() - 273.15

    @measurer
    def measure_temperature_0(self):
        return self.read(0) / 37e-6 + self.measure_internal_temperature()

    @measurer
    def measure_temperature_1(self):
        return self.read(2) / 37e-6 + self.measure_internal_temperature()

    @measurer
    def measure_temperature_2(self):
        return self.read(4) / 37e-6 + self.measure_internal_temperature()

    @measurer
    def measure_temperature_3(self):
        return self.read(6) / 37e-6 + self.measure_internal_temperature()
