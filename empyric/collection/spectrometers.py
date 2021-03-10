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
        'filament',
        'mode',
        'mass'
    )

    presets = {
        'filament': 1
    }

    postsets = {
        'filament': 0
    }

    meters = {
        'spectrum',
        'total pressure',
        'helium pressure'
    }

    @setter
    def set_filament(self, current):
        # current is in mA

        if current >= 3.5:
            self.write('FL3.5')
        elif current <= 0:
            self.write('FL0')
        else:
            self.write('FL'+str(np.round(float(current), 2)))

    @getter
    def get_filament(self):
        return float(self.read('FL?'))

    @setter
    def set_mode(self, mode):
        pass

    @getter
    def get_mode(self):
        pass

    @setter
    def set_mass(self, mass):
        pass

    @getter
    def get_mass(self):
        pass

    @measurer
    def measure_spectrum(self):
        pass

    @measurer
    def measure_total_pressure(self):
        pass

    @measurer
    def measure_helium_pressure(self):
        pass
