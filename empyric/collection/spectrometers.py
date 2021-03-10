from empyric.adapters import *
from empyric.collection.instrument import *

class SRSRGA(Instrument):
    """
    SRS Residual Gas Analyzer, a quadrupole mass spectrometer with mass ranges from 100 to 300 amu
    """

    name = 'SRS-RGA'

    supported_adapters = (
        (Serial, {'baud_rate': 28800, 'stop_bits': 2})
    )

    knobs = (
        'filament current',
        'initial mass',
        'final mass',
        'steps per amu'
    )

    presets = {
        'filament': 1
    }

    postsets = {
        'filament': 0
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
            self.write('FL3.5')
        elif current <= 0:
            self.write('FL0')
        else:
            self.write('FL'+str(np.round(float(current), 2)))

        status_byte = self.read()  # not used; just to clear buffer

    @getter
    def get_filament_current(self):
        return float(self.read('FL?'))

    @setter
    def set_initial_mass(self, mass):
        self.write('MI'+f'{int(mass)}')

    @getter
    def get_initial_mass(self):
        return int(self.query('MI?'))

    @setter
    def set_final_mass(self, mass):
        self.write('MF'+f'{int(mass)}')

    @getter
    def get_final_mass(self):
        return int(self.query('MF?'))

    @setter
    def set_steps_per_amu(self, steps):
        self.write('SA'+f'{int(steps)}')

    @getter
    def get_steps_per_amu(self):
        return int(self.query('SA?'))

    @measurer
    def measure_spectrum(self):
        pass

    @measurer
    def measure_single_mass(self, mass):
        return float(self.query('MR'+f'{int(mass)}'))

    @measurer
    def measure_total_pressure(self):
        return float(self.query('TP?'))
