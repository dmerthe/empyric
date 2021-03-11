import time
from empyric.adapters import *
from empyric.collection.instrument import *

class SRSRGA(Instrument):
    """
    SRS Residual Gas Analyzer, a quadrupole mass spectrometer with mass ranges from 100 to 300 amu
    """

    name = 'SRS-RGA'

    supported_adapters = (
        (Serial, {'baud_rate': 28800, 'stop_bits': 2, 'timeout': None, 'termination':'\n\r'}),
    )

    knobs = (
        'filament current',
        'initial mass',
        'final mass',
        'steps per amu',
        'ppsf',  # partial pressure sensitivity factor
        'tpsf'  # total pressure sensitivity factor
    )

    presets = {
        'filament current': 1
    }

    postsets = {
        'filament current': 0
    }

    meters = {
        'filament current',
        'spectrum',
        'single mass',
        'total pressure'
    }

    ppsf = 0.119
    tpsf = 0.0023

    @setter
    def set_filament_current(self, current):
        # current is in mA

        if current >= 3.5:
            self.query('FL3.5\r\n')
        elif current <= 0:
            self.query('FL0\r\n')
        else:
            self.query('FL'+f'{np.round(float(current), 2)}\r\n')

        time.sleep(5)

    @measurer
    def measure_filament_current(self):
        return float(self.query('FL?\r\n').decode().strip())

    @setter
    def set_initial_mass(self, mass):
        self.write('MI'+f'{int(mass)}\r\n')

    @getter
    def get_initial_mass(self):
        return int(self.query('MI?\r\n').decode().strip())

    @setter
    def set_final_mass(self, mass):
        self.write('MF'+f'{int(mass)}\r\n')

    @getter
    def get_final_mass(self):
        return int(self.query('MF?\r\n').decode().strip())

    @setter
    def set_steps_per_amu(self, steps):
        self.write('SA'+f'{int(steps)}\r\n')

    @getter
    def get_steps_per_amu(self):
        return int(self.query('SA?\r\n').decode().strip())

    @setter
    def set_ppsf(self, value):
        self.write(f'SP{value}\r\n')

    @getter
    def get_ppsf(self):
        return float(self.query('SP?\r\n').decode().strip())

    @setter
    def set_tpsf(self, value):
        self.write(f'ST{value}\r\n')

    @getter
    def get_tpsf(self):
        return float(self.query('ST?\r\n').decode().strip())

    @measurer
    def measure_spectrum(self):
        return 0

    @measurer
    def measure_single_mass(self, mass):
        import struct

        self.write('MR'+f'{int(mass)}\r\n')

        while not self.adapter.backend.in_waiting:
            time.sleep(0.1)

        response = self.adapter.read().split(b'\n\r')[0]

        return struct.unpack('<i', response)[0] * 1.0e-16 / self.ppsf

    @measurer
    def measure_total_pressure(self):
        import struct

        self.write('TP?\r\n')

        while not self.adapter.backend.in_waiting:
            time.sleep(0.1)

        response = self.adapter.read().split(b'\n\r')[0]

        return struct.unpack('<i', response)[0] * 1.0e-16 / self.tpsf
