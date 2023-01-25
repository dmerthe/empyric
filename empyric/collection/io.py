import re

from empyric.collection.instrument import Instrument, setter, getter, measurer
from empyric.adapters import Socket
from empyric.tools import recast

class BrainboxesED560(Instrument):
    """
    Brainboxes 4 channel analog output (0-10 V / 0-20mA) gateway.

    For socket communication, the default port is 9500. If the IP address is
    unknown, you can use the Boost.IO Driver software to find it.

    ASCII Protocol must be used.
    """

    supported_adapters = (
        (Socket, {}),
    )

    knobs = (
        'analog_out0',
        'analog_out1',
        'analog_out2',
        'analog_out3',
    )

    @setter
    def set_analog_out0(self, value):
        self.query('#010%f' % float(value), validator=self._set_validator)

    @getter
    def get_analog_out0(self):
        response = self.query('$0160', validator=self._get_validator)
        return recast(response[3:])

    @setter
    def set_analog_out1(self, value):
        self.query('#011%f' % float(value), validator=self._set_validator)

    @getter
    def get_analog_out1(self):
        response = self.query('$0161', validator=self._get_validator)
        return recast(response[3:])

    @setter
    def set_analog_out2(self, value):
        self.query('#012%f' % float(value), validator=self._set_validator)

    @getter
    def get_analog_out2(self):
        response = self.query('$0162', validator=self._get_validator)
        return recast(response[3:])

    @setter
    def set_analog_out3(self, value):
        self.query('#013%f' % float(value), validator=self._set_validator)

    @getter
    def get_analog_out3(self):
        response = self.query('$0163', validator=self._get_validator)
        return recast(response[3:])

    @staticmethod
    def _get_validator(response):
        return re.match('!01\+\d\d\.\d\d\d', response)

    @staticmethod
    def _set_validator(response):
        return response.strip() == '>'


class BrainboxesED549(Instrument):
    """
    Brainboxes 4 channel analog input (0-10 V / 0-20mA) gateway.

    For socket communication, the default port is 9500. If the IP address is
    unknown, you can use the Boost.IO Driver software to find it.

    ASCII Protocol must be used.
    """

    supported_adapters = (
        (Socket, {}),
    )

    meters = (
        'analog_in0',
        'analog_in1',
        'analog_in2',
        'analog_in3',
    )

    @measurer
    def measure_analog_in0(self):
        response = self.query('#010', validator=self._validator)
        return recast(response[1:])

    @measurer
    def measure_analog_in1(self):
        response = self.query('#011', validator=self._validator)
        return recast(response[1:])

    @measurer
    def measure_analog_in2(self):
        response = self.query('#012', validator=self._validator)
        return recast(response[1:])

    @measurer
    def measure_analog_in3(self):
        response = self.query('#013', validator=self._validator)
        return recast(response[1:])

    @staticmethod
    def _validator(response):
        print(response)
        return re.match('>\+?\-?\d\d\.\d\d\d', response)
