import struct
from empyric.tools import find_nearest
from empyric.adapters import *
from empyric.collection.instrument import *


class TekScope(Instrument):
    """
    Tektronix oscillscope of the TDS200, TDS1000/2000, TDS1000B/2000B,
    TPS2000 series

    """

    name = 'TekScope'

    supported_adapters = (
        (USB, {'timeout': 10}),  # acquisitions can take a long time
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

    @setter
    def set_horz_scale(self, scale):
        self.write('HOR:SCA %.3e' % scale)

    @setter
    def set_horz_position(self, position):
        self.write('HOR:POS %.3e' % position)

    @setter
    def set_ch1_scale(self, scale):
        self.write('CH1:SCA %.3e' % scale)

    @setter
    def set_ch2_scale(self, scale):
        self.write('CH1:SCA %.3e' % scale)

    @setter
    def set_ch3_scale(self, scale):
        self.write('CH1:SCA %.3e' % scale)

    @setter
    def set_ch4_scale(self, scale):
        self.write('CH1:SCA %.3e' % scale)

    @setter
    def set_ch1_position(self, position):
        self.write('CH1:POS %.3e' % position)

    @setter
    def set_ch2_position(self, position):
        self.write('CH1:POS %.3e' % position)

    @setter
    def set_ch3_position(self, position):
        self.write('CH1:POS %.3e' % position)

    @setter
    def set_ch4_position(self, position):
        self.write('CH1:POS %.3e' % position)

    @setter
    def set_trigger_level(self, level):
        self.write('TRIG:MAI:LEV %.3e' % level)

    def _measure_channel(self, channel):

        self.write('DAT:ENC ASCI') # ensure ASCII encoding of data
        self.write('DAT:SOU CH%d' % channel)  # switch to channel 1

        scale_factor = float(self.query('WFMPRE:YMULT?'))
        zero = float(self.query('WFMPRE:YZERO?'))
        offset = float(self.query('WFMPRE:YOFF?'))

        self.write('ACQ:STATE RUN') # acquire the waveform

        while int(self.query('BUSY?')):
            time.sleep(1)  # wait for acquisition to complete

        str_data = self.query('CURVE?').split(' ')[1].split(',')
        return np.array([
            (float(datum) - offset)*scale_factor + zero for datum in str_data
        ])

    @measurer
    def measure_channel_1(self):
        return self._measure_channel(1)

    @measurer
    def measure_channel_2(self):
        return self._measure_channel(2)

    @measurer
    def measure_channel_3(self):
        return self._measure_channel(3)

    @measurer
    def measure_channel_4(self):
        return self._measure_channel(4)
