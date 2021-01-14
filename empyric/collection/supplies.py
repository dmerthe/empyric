from empyric.adapters import *
from empyric.collection.instrument import *


class Keithley2260B(Instrument):
    """
    Keithley 2260B power supply, usually either 360 W or 720 W
    """

    name = 'Keithley2260B'

    supported_adapters = (
        (Serial, {}),
        (VISASerial, {})
    )

    knobs = (
        'max voltage',
        'max current',
        'output'
    )

    # no presets or postsets for this instrument

    meters = (
        'voltage',
        'current'
    )

    @measurer
    def measure_current(self):
        return [float(self.query('MEAS:CURR?')) for i in range(3)][-1] # sometimes the first measurement is lagged

    @measurer
    def measure_voltage(self):
        return [float(self.query('MEAS:VOLT?')) for i in range(3)][-1] # sometimes the first measurement is lagged

    @setter
    def set_max_voltage(self, voltage):
        if not self.max_current:
            self.get_max_current()

        self.write('APPL %.4f,%.4f' % (voltage, self.max_current))

    @setter
    def set_max_current(self, current):
        if not self.max_voltage:
            self.get_max_voltage()

        self.write('APPL %.4f,%.4f' % (self.max_voltage, current))

    @setter
    def set_output(self, output):

        if output == 'ON':
            self.write('OUTP:STAT:IMM ON')
        elif output == 'OFF':
            self.write('OUTP:STAT:IMM OFF')

    @getter
    def get_max_current(self):
        return float(self.query('CURR?'))

    @getter
    def get_max_voltage(self):
        return float(self.query('VOLT?'))


class BK9183B(Instrument):
    """
    B&K Precision Model 9183B (35V & 6A / 70V & 3A) power supply
    """

    name = 'BK9183B'

    supported_adapters = (
        (Serial, {'baud_rate': 57600}),
        (VISASerial, {'baud_rate': 57600})
    )
    
    knobs = (
        'max voltage',
        'max current',
        'output'
    )

    # no presets or postsets for this instrument

    meters = (
        'voltage',
        'current'
    )

    @setter
    def set_output(self, output):

        if output == 'ON':
            self.write('OUT ON')
        elif output == 'OFF':
            self.write('OUT OFF')

    @measurer
    def measure_current(self):
        return [float(self.query('MEAS:CURR?')) for i in range(3)][-1] # sometimes the first measurement is lagged

    @measurer
    def measure_voltage(self):
        return [float(self.query('MEAS:VOLT?')) for i in range(3)][-1] # sometimes the first measurement is lagged

    @setter
    def set_max_current(self, current):
        self.write('SOUR:CURR ' + str(current))

    @setter
    def set_max_voltage(self, voltage):
        self.write('SOUR:VOLT ' + str(voltage))

    @getter
    def get_max_current(self):
        return float(self.query('SOUR:CURR?'))

    @getter
    def get_max_voltage(self):
        return float(self.query('SOUR:VOLT?'))
