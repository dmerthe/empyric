from empyric.collection.instrument import Instrument, setter, getter, measurer
from empyric.adapters import Socket


class BrainboxesED560(Instrument):
    """
    Brainboxes 4 channel analog output (0-10 V / 0-20mA) gateway
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
        self.write('#010%f' % float(value))

    @getter
    def get_analog_out0(self):
        response = self.query('$0160')
        return float(response[3:])

    @setter
    def set_analog_out1(self, value):
        self.write('#011%f' % float(value))

    @getter
    def get_analog_out1(self):
        response = self.query('$0161')
        return float(response[3:])

    @setter
    def set_analog_out2(self, value):
        self.write('#012%f' % float(value))

    @getter
    def get_analog_out2(self):
        response = self.query('$0162')
        return float(response[3:])

    @setter
    def set_analog_out3(self, value):
        self.write('#013%f' % float(value))

    @getter
    def get_analog_out3(self):
        response = self.query('$0163')
        return float(response[3:])


class BrainboxesED549(Instrument):
    """
    Brainboxes 4 channel analog input (0-10 V / 0-20mA) gateway
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
        response = self.query('#010')
        return float(response[1:])

    @measurer
    def measure_analog_in1(self):
        response = self.query('#011')
        return float(response[1:])

    @measurer
    def measure_analog_in2(self):
        response = self.query('#012')
        return float(response[1:])

    @measurer
    def measure_analog_in3(self):
        response = self.query('#013')
        return float(response[1:])
