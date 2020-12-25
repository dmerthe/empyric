from mercury.instruments.basics import *


class Keithley2260B(Instrument):

    supported_backends = ['visa', 'serial', 'me-api']
    default_backend = 'visa'

    """
    Keithley 2260B Power supply, usually either 360 W or 720 W
    """
    name = 'Keithley2260B'

    knobs = (
        'max voltage',
        'max current',
        'output state'
    )

    meters = (
        'voltage',
        'current'
    )

    def __init__(self, address, **kwargs):

        self.knob_values = {knob: None for knob in Keithley2260B.knobs}

        # Set up communication
        self.address = address
        self.backend = kwargs.get('backend', self.default_backend)
        self.delay = kwargs.get('delay', 0.05)
        self.connect()

        # Set up instrument
        if kwargs.get('reset', False):
            self.reset()
        else:
            # Record initial values of voltage & current knobs for consistent operation between reconnects, if no reset is requested)
            voltage = self.measure_voltage()
            current = self.measure_current()

            self.knob_values['max voltage'] = float(self.connection.query('SOUR:VOLT:LEV:IMM:AMPL? MAX'))
            self.knob_values['max current'] = float(self.connection.query('SOUR:CURR:LEV:IMM:AMPL? MAX'))

            self.set_max_current(np.min([current, self.knob_values['max current']]))
            self.set_max_voltage(np.min([voltage, self.knob_values['max voltage']]))

            # Turn output on
            self.output_on()

    def output_on(self):
        self.write('OUTP:STAT:IMM ON')

    def output_off(self):
        self.write('OUTP:STAT:IMM OFF')

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

    def set_output_state(self, state):

        if state == 'ON':
            self.output_on()
            self.knob_values['output state'] = 'ON'
        elif state == 'OFF':
            self.output_off()
            self.knob_values['output state'] = 'OFF'


class BK9183B(Instrument):

    supported_backends = ['serial', 'me-api']
    default_backend = 'serial'

    name = 'BK9183B'

    baudrate = 57600
    
    knobs = (
        'max voltage',
        'max current',
        'output state'
    )

    meters = (
        'voltage',
        'current'
    )

    def __init__(self, address, delay=0.05, reset=False, **kwargs):

        self.knob_values = {knob: None for knob in BK9183B.knobs}

        # Set up communication
        self.address = address
        self.backend = kwargs.get('backend', self.default_backend)
        self.delay = kwargs.get('delay', 0.05)
        self.connect()

        if reset:
            self.reset()
        else:
            self.knob_values['max voltage'] = self.write('SOUR:VOLT?')
            self.knob_values['max current'] = self.write('SOUR:CURR?')

            self.set_output_state('ON')

    def output_on(self):
        self.write('OUT ON')

    def output_off(self):
        self.write('OUT OFF')

    def set_output_state(self, state):

        if state == 'ON':
            self.output_on()
            self.knob_values['output state'] = 'ON'
        elif state == 'OFF':
            self.output_off()
            self.knob_values['output state'] = 'OFF'

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
