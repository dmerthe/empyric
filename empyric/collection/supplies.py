from empyric.adapters import *
from empyric.collection.instrument import Instrument


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

    def measure_current(self):
        return [float(self.query('MEAS:CURR?')) for i in range(3)][-1] # sometimes the first measurement is lagged

    def measure_voltage(self):
        return [float(self.query('MEAS:VOLT?')) for i in range(3)][-1] # sometimes the first measurement is lagged

    def set_max_voltage(self, voltage):
        self.write('APPL %.4f,%.4f' % (voltage, self.knob_values['max current']))
        self.knob_values['max voltage'] = voltage

    def set_max_current(self, current):
        self.write('APPL %.4f,%.4f' % (self.knob_values['max voltage'], current))
        self.knob_values['max current'] = current

    def set_output(self, output):

        if output == 'ON':
            self.write('OUTP:STAT:IMM ON')
            self.knob_values['output'] = 'ON'
        elif output == 'OFF':
            self.write('OUTP:STAT:IMM OFF')
            self.knob_values['output'] = 'OFF'

    def get_max_current(self):
        return float(self.query('CURR?'))

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

    def set_output(self, output):

        if output == 'ON':
            self.write('OUT ON')
            self.knob_values['output'] = 'ON'
        elif output == 'OFF':
            self.write('OUT OFF')
            self.knob_values['output'] = 'OFF'

    def measure_current(self):
        return [float(self.query('MEAS:CURR?')) for i in range(3)][-1] # sometimes the first measurement is lagged

    def measure_voltage(self):
        return [float(self.query('MEAS:VOLT?')) for i in range(3)][-1] # sometimes the first measurement is lagged

    def set_max_current(self, current):
        self.write('SOUR:CURR ' + str(current))
        self.knob_values['max current'] = current

    def set_max_voltage(self, voltage):
        self.write('SOUR:VOLT ' + str(voltage))
        self.knob_values['max voltage'] = voltage

    def get_max_current(self):
        return float(self.query('SOUR:CURR?'))

    def get_max_voltage(self):
        return float(self.query('SOUR:VOLT?'))
