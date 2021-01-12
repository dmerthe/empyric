from empyric.adapters import *
from empyric.collection.instrument import Instrument


class TekScope(Instrument):
    """
    Tektronix oscillscope of the TDS200, TDS1000/2000, TDS1000B/2000B, TPS2000 series

    """

    name = 'TekScope'

    supported_adapters = (
        (VISAUSB, {'timeout': 10}),  # acquisitions can take a long time
        (USBTMC, {'timeout': 10})
    )

    knobs = (
        'horz scale',
        'horz position',
        'ch1 scale',
        'ch1 position',
        'ch2 scale',
        'ch2 position',
        'ch3 scale',
        'ch3 position',
        'ch4 scale',
        'ch4 position',
        'trigger level',
    )

    meters = (
        'channel 1',
        'channel 2',
        'channel 3',
        'channel 4',
    )

    def set_horz_scale(self, scale):
        self.write('HOR:SCA %.3e' % scale)

    def set_horz_position(self, position):
        self.write('HOR:POS %.3e' % scale)

    def set_ch1_scale(self, scale):
        self.write('CH1:SCA %.3e' % scale)

    def set_ch2_scale(self, scale):
        self.write('CH1:SCA %.3e' % scale)

    def set_ch3_scale(self, scale):
        self.write('CH1:SCA %.3e' % scale)

    def set_ch4_scale(self, scale):
        self.write('CH1:SCA %.3e' % scale)

    def set_ch1_position(self, position):
        self.write('CH1:POS %.3e' % position)

    def set_ch2_position(self, position):
        self.write('CH1:POS %.3e' % position)

    def set_ch3_position(self, position):
        self.write('CH1:POS %.3e' % position)

    def set_ch4_position(self, position):
        self.write('CH1:POS %.3e' % position)

    def set_trigger_level(self, level):
        self.write('TRIG:MAI:LEV %.3e' % level)
