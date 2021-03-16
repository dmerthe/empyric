import time
import numpy as np
import struct
from empyric.adapters import *
from empyric.collection.instrument import *

class SRSRGA(Instrument):
    """
    SRS Residual Gas Analyzer, a quadrupole mass spectrometer with mass ranges from 100 to 300 amu
    """

    name = 'SRS-RGA'

    supported_adapters = (
        (Serial, {'baud_rate': 28800, 'timeout': 300, 'input_termination': '\n\r'}),
    )

    knobs = (
        'filament current',
        'mass',
        'masses',
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
        'single',
        'spectrum',
        'total pressure'
    }

    @setter
    def set_filament_current(self, current):
        # current is in mA

        if current >= 3.5:
            self.query('FL3.5')
        elif current <= 0:
            self.query('FL0')
        else:
            self.query('FL'+f'{np.round(float(current), 2)}')

        time.sleep(5)

    @measurer
    def measure_filament_current(self):
        return float(self.query('FL?'))

    @setter
    def set_mass(self, mass):
        self.write('ML' + f'{int(mass)}')

    @setter
    def set_masses(self, masses):

        initial_mass, final_mass = masses[0], masses[-1]

        self.write('MI' + f'{int(initial_mass)}')
        self.write('MF' + f'{int(final_mass)}')

    @getter
    def get_masses(self):
        initial_mass = int(self.query('MI?'))
        final_mass = int(self.query('MF?'))

        return np.arange(initial_mass, final_mass + 1)

    @setter
    def set_ppsf(self, value):
        self.write(f'SP{value}')

    @getter
    def get_ppsf(self):
        return float(self.query('SP?'))

    @setter
    def set_tpsf(self, value):
        self.write(f'ST{value}')

    @getter
    def get_tpsf(self):
        return float(self.query('ST?'))

    @measurer
    def measure_spectrum(self):

        self.write('HS1')
        response = self.adapter.backend.read(4*len(self.masses))
        total_pressure = self.adapter.backend.read(4)  # automatically measured after every scan

        self.adapter.backend.reset_input_buffer()

        return np.array(struct.unpack('<'+'i'*len(self.masses), response)) * 1.0e-16 / self.ppsf * 1000

    @measurer
    def measure_single(self):

        self.write('MR'+f'{int(self.mass)}')
        response = self.adapter.backend.read(4)

        self.adapter.backend.reset_input_buffer()

        return struct.unpack('<i', response)[0] * 1.0e-16 / self.ppsf * 1000

    @measurer
    def measure_total_pressure(self):

        self.write('TP?')
        response = self.adapter.backend.read(4)

        self.adapter.backend.reset_input_buffer()

        return struct.unpack('<i', response)[0] * 1.0e-16 / self.tpsf * 1000
