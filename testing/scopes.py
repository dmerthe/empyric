import os
import datetime
import pandas as pd

from mercury.instruments.basics import *
from mercury.utilities import *

class Tek2000Series(Instrument):
    """
    Common Tektronix TDS 2000 series oscilloscope used to measure waveforms
    """

    supported_backends = ['visa', 'me-api']
    default_backend = ['visa']

    name = 'Tek2000Series'

    # Available knobs
    knobs = (
        'channel 1',
        'channel 2',
        'channel 3',
        'channel 4',
        'horizontal scale',
        'scale 1',
        'scale 2'
        'scale 3',
        'scale 4',
        'horizontal position',
        'position 1',
        'position 2',
        'position 3',
        'position 4',
        'multiplier 1',
        'multiplier 2',
        'multiplier 3',
        'multiplier 4'
    )

    # Available meters
    meters = (
        'waveforms',
    )

    def __init__(self, address, **kwargs):

        self.knob_values = {knob: None for knob in Tek2000Series.knobs}

        # Set up communication
        self.address = address
        self.backend = kwargs.get('backend', self.default_backend)
        self.delay = kwargs.get('delay', 1)
        self.connect()



