from mercury.stash.basics import *

class BRAX3XXX(Instrument, SerialDevice):
    """
    Keithley 2110 multimeter instrument
    """

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

    def __init__(self, address, backend='serial'):

        self.address = address
        self.backend = backend

        self.knob_values = {knob: None for knob in BRAX3XXX.knobs}

        self.connect(address)

        self.knob_values['filament'] = 1
        self.knob_values['ig state'] = 'OFF'

        self.read()

    def set_ig_state(self, state):

        number = self.knob_values['filament']

        if state == 'ON':
            self.write(f'#IG{number} ON<CR>')
        if state == 'OFF':
            self.write(f'#IG{number} OFF<CR>')

    def set_filament(self, number):

        self.knob_values['filament'] = number

    def measure_ig_state(self):

        response = self.query('#IGS<CR>')

        if 'ON' in response:
            return 1
        else:
            return 0

    def measure_cg1_pressure(self):

        try:
            return float(self.query('#RDCG1<CR>')[4:-4])
        except ValueError:
            return float(self.query('#RDCG1<CR>')[4:-4])

    def measure_cg2_pressure(self):

        try:
            return float(self.query('#RDCG2<CR>')[4:-4])
        except ValueError:
            return float(self.query('#RDCG2<CR>')[4:-4])

    def measure_ig_pressure(self):

        try:
            return float(self.query('#RDIG<CR>')[4:])
        except ValueError:
            return float(self.query('#RDIG<CR>')[4:])