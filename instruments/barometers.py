from mercury.instruments.basics import *


class BRAX3XXX(Instrument):
    """
    Keithley 2110 multimeter instrument
    """

    supported_backends = ['serial', 'me-api']
    default_backend = 'serial'

    baudrate = 9600

    name = "BRAX3XXX"

    knobs = (
        'ig state',
        'filament',
    )

    meters = (
        'cg1 pressure',
        'cg2 pressure',
        'ig pressure',
        'ig state'
    )

    def __init__(self, address, **kwargs):

        self.knob_values = {knob: None for knob in BRAX3XXX.knobs}

        # Set up communication
        self.address = address
        self.backend = kwargs.get('backend', self.default_backend)
        self.connect()

        # Set up instrument
        self.set_filament(kwargs.get('filament', 1))
        self.set_ig_state(kwargs.get('ig_state', 1))

    def set_ig_state(self, state):

        number = self.knob_values['filament']

        if state == 'ON':
            self.write(f'#IG{number} ON<CR>')
        if state == 'OFF':
            self.write(f'#IG{number} OFF<CR>')

        self.read()  # discard the response

    def set_filament(self, number):

        self.knob_values['filament'] = number

    def measure_ig_state(self):

        response = self.query('#IGS<CR>')

        if 'ON' in response:
            return 1
        else:
            return 0

    def measure_cg1_pressure(self):

        for i in range(3):
            try:
                return float(self.query('#RDCG1<CR>')[4:-4])
            except ValueError:
                pass

    def measure_cg2_pressure(self):

        for i in range(3):
            try:
                return float(self.query('#RDCG2<CR>')[4:-4])
            except ValueError:
                pass

    def measure_ig_pressure(self):

        for i in range(3):
            try:
                return float(self.query('#RDIG<CR>')[4:])
            except ValueError:
                pass
