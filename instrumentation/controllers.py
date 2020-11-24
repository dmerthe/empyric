from mercury.instruments.basics import *

class OmegaCN7500(Instrument):
    """
    Omega model CN7500 temperature controller

    """

    supported_backends = ['me-api']
    default_backend = 'me-api'

    baudrate = 38400

    name = 'CN7500'

    knobs = (
        'temperature setpoint',
    )

    meters = (
        'temperature',
        'power'
    )

    def __init__(self, address, **kwargs):
        self.knob_values = {knob: None for knob in OmegaCN7500.knobs}

        # Set up communication
        self.address = address
        self.backend = kwargs.get('backend', self.default_backend)
        self.delay = kwargs.get('delay', 0.05)
        self.connect()

        # Set up instrument

    def set_temperature_setpoint(self, setpoint):

        self.write(4097, int(round(setpoint * 10)))
        self.knob_values['temperature setpoint'] = setpoint

    def measure_temperature(self):

        return self.query(4096) * 0.1

    def measure_power(self):

        return self.query(0x1012) * 0.1
