import time
import numpy as np
import struct
from empyric.adapters import *
from empyric.collection.instrument import *
from empyric.types import Float, Integer, Array


class SRSRGA(Instrument):
    """
    SRS Residual Gas Analyzer, a quadrupole mass spectrometer with mass ranges
    from 100 to 300 amu
    """

    name = 'SRS-RGA'

    supported_adapters = (
        (
            Serial,
            {'baud_rate': 28800, 'timeout': 300, 'read_termination': '\n\r'}
        ),
    )

    knobs = (
        'initialize'
        'filament current',
        'mass',
        'masses',
        'mass range',
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

    def __init__(self, *args, **kwargs):

        Instrument.__init__(self, *args, **kwargs)

    @setter
    def set_filament_current(self, current: Float):
        # current is in mA

        if current >= 3.5:
            self.query('FL3.5')
        elif current <= 0:
            self.query('FL0')
        else:
            self.query('FL'+f'{np.round(current, 2)}')

        time.sleep(5)

    @measurer
    def measure_filament_current(self) -> Float:
        return float(self.query('FL?'))

    @setter
    def set_mass(self, mass: Integer):
        self.write('ML' + f'{mass}')

    @getter
    def get_mass(self) -> Integer:
        return int(self.query('ML?'))

    @setter
    def set_masses(self, masses: Array):
        initial_mass, final_mass = masses[0], masses[-1]

        self.write('MI' + f'{int(initial_mass)}')
        self.write('MF' + f'{int(final_mass)}')

        self.mass_range = [initial_mass, final_mass]

    @getter
    def get_masses(self) -> Array:

        initial_mass = int(self.query('MI?'))
        final_mass = int(self.query('MF?'))

        self.mass_range = [initial_mass, final_mass]

        return np.arange(initial_mass, final_mass + 1, dtype=np.int64)

    @setter
    def set_mass_range(self, mass_range: Array):

        initial_mass, final_mass = mass_range

        self.write('MI' + f'{int(initial_mass)}')
        self.write('MF' + f'{int(final_mass)}')

        self.masses = np.arange(initial_mass, final_mass + 1)

    @getter
    def get_mass_range(self) -> Array:
        initial_mass = int(self.query('MI?'))
        final_mass = int(self.query('MF?'))

        self.masses = np.arange(initial_mass, final_mass + 1)

        return [initial_mass, final_mass]


    @setter
    def set_ppsf(self, value: Float):
        self.write(f'SP{value}')

    @getter
    def get_ppsf(self) -> Float:
        return float(self.query('SP?'))

    @setter
    def set_tpsf(self, value: Float):
        self.write(f'ST{value}')

    @getter
    def get_tpsf(self) -> Float:
        return float(self.query('ST?'))

    @measurer
    def measure_spectrum(self) -> Array:
        response = self.query(
            'HS1', num_bytes=4*(len(self.masses)+1), decode=False
        )
        return np.array(
            struct.unpack('<'+'i'*(len(self.masses)+1), response)
        )[:-1] * 1.0e-16 / self.ppsf * 1000

    @measurer
    def measure_single(self) -> Float:
        response = self.query(
            'MR'+f'{int(self.mass)}', num_bytes=4, decode=False
        )
        return struct.unpack('<i', response)[0] * 1.0e-16 / self.ppsf * 1000

    @measurer
    def measure_total_pressure(self) -> Float:
        response = self.query('TP?', num_bytes=4, decode=False)
        return struct.unpack('<i', response)[0] * 1.0e-16 / self.tpsf * 1000
