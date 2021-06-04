import numbers, importlib
from empyric.adapters import *
from empyric.collection.instrument import *

class Keithley2110(Instrument):
    """
    Keithley 2110 digital multimeter instrument
    """

    name = "Keithley2110"

    supported_adapters = (
        (USBTMC, {}),
        (VISAUSB, {})
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
                nearest = np.argwhere( voltage_range <= np.array(allowed_voltage_ranges) ).flatten()[0]
            except IndexError:
                nearest = -1

            self.set_voltage_range(allowed_voltage_ranges[nearest])

            Warning(f'Given voltage range not an option, setting to {allowed_voltage_ranges[nearest]} V instead')

        elif voltage_range == 'AUTO':
            self.write('VOLT:RANG:AUTO')
        else:
            raise ValueError(f'voltage range choice {voltage_range} not permitted!')

    @setter
    def set_current_range(self, current_range):

        allowed_current_ranges = (0.01, 0.1, 1, 3, 10)

        if current_range in allowed_current_ranges:
            self.write('CURR:RANG %.2e' % current_range)
        elif isinstance(current_range, numbers.Number):
            # Find nearest encapsulating current range
            try:
                nearest = np.argwhere(current_range <= np.array(allowed_current_ranges)).flatten()[0]
            except IndexError:
                nearest = -1

            self.set_current_range(allowed_current_ranges[nearest])

            Warning(f'Given current range not an option, setting to {allowed_current_ranges[nearest]} A instead')

        elif current_range == 'AUTO':
            self.write('CURR:RANG:AUTO')
        else:
            raise ValueError(f'current range choice {current_range} not permitted!')

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


class LabJackU6(Instrument):
    """
    LabJack U6 Multi-function DAQ
    """

    name = 'LabJackU6'

    supported_adapters = (
        (Adapter, {})  # custom setup below until I can get serial or modbus comms to work
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

        if address not in kwargs:
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
