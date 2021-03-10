from empyric.adapters import *
from empyric.collection.instrument import *

class SRSRGA(Instrument):
    """
    SRS Residual Gas Analyzer, a quadrupole mass spectrometer with mass ranges from 100 to 300 amu
    """

    name = 'SRS-RGA'

    supported_adapters = (
        (Serial, {'baud_rate': 28800, 'stop_bits': 2, 'timeout': None}),
    )

    knobs = (
        'filament current',
        'initial mass',
        'final mass',
        'steps per amu'
    )

    presets = {
        'filament current': 1
    }

    postsets = {
        'filament current': 0
    }

    meters = {
        'spectrum',
        'single mass',
        'total pressure'
    }

    @setter
    def set_filament_current(self, current):
        # current is in mA

        if current >= 3.5:
            self.write('FL3.5\r\n')
        elif current <= 0:
            self.write('FL0\r\n')
        else:
            self.write('FL'+f'{np.round(float(current), 2)}\r\n')

        self.read()  # status byte; not used

    @getter
    def get_filament_current(self):
        return float(self.query('FL?\r\n'))

    @setter
    def set_initial_mass(self, mass):
        self.write('MI'+f'{int(mass)}\r\n')

    @getter
    def get_initial_mass(self):
        return int(self.query('MI?\r\n'))

    @setter
    def set_final_mass(self, mass):
        self.write('MF'+f'{int(mass)}\r\n')

    @getter
    def get_final_mass(self):
        return int(self.query('MF?\r\n'))

    @setter
    def set_steps_per_amu(self, steps):
        self.write('SA'+f'{int(steps)}\r\n')

    @getter
    def get_steps_per_amu(self):
        return int(self.query('SA?\r\n'))

    @measurer
    def measure_spectrum(self):
        return 0

    @measurer
    def measure_single_mass(self, mass):
        return float(self.query('MR'+f'{int(mass)}\r\n'))

    @measurer
    def measure_total_pressure(self):
        return float(self.query('TP?\r\n'))
