import re
from empyric.adapters import *
from empyric.collection.instrument import *

class BRAX3000(Instrument):
    """
    BRAX 3000 series pressure gauge controller and meter
    """

    name = "BRAX3000"

    supported_adapters = (
        (Serial, {'baud_rate': 19200, 'termination':b'\r', 'timeout': 1}),
        (VISASerial, {'baud_rate': 19200, 'timeout': 1})
    )

    knobs = (
        'ig state',
        'filament',
    )

    presets = {
        'filament': 1,
        'ig_state': 'ON'
    }

    meters = (
        'cg1 pressure',
        'cg2 pressure',
        'ig pressure',
    )

    @setter
    def set_ig_state(self, state):

        number = self.filament

        if state == 'ON':
            self.write(f'#IG{number} ON<CR>\r')
        if state == 'OFF':
            self.write(f'#IG{number} OFF<CR>\r')

        self.read()  # discard the response

    @getter
    def get_ig_state(self):
        return self.query('#IGS<CR>\r')

    @setter
    def set_filament(self, number):
        pass

    @measurer
    def measure_cg1_pressure(self):
        return float(self.query('#RDCG1<CR>\r').decode().strip()[4:-4])

    @measurer
    def measure_cg2_pressure(self):
        return float(self.query('#RDCG2<CR>\r').decode().strip()[4:-4])

    @measurer
    def measure_ig_pressure(self):

        def validator(response):
            match = re.search('\d\.\d+E-?\d\d', response.decode().strip())
            return bool(match)

        response = self.query('#RDIG<CR>\r', validator=validator).decode().strip()

        return float(re.findall('\d\.\d+E-?\d\d', response)[0])
