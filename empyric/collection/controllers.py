from empyric.adapters import *
from empyric.collection.instrument import Instrument


class OmegaCN7500(Instrument):
    """
    Omega model CN7500 temperature PID controller
    """

    name = 'OmegaCN7500'

    supported_adapters = (
        (Modbus, {'buad_rate': 38400}),
    )

    knobs = (
        'output',
        'setpoint',
        'proportional band',
        'integration time',
        'derivative time'
    )

    meters = (
        'temperature',
        'power'
    )

    def set_output(self, state):
        if state == 'ON':
            self.backend.write_bit(2068, 1)  # turn on output & start PID control
        elif state == 'OFF':
            self.backend.write_bit(2068, 0)  # turn off output & stop PID control

    def set_setpoint(self, setpoint):
        self.write(4097, setpoint, number_of_decimals=1)

    def set_proportional_band(self, P):
        self.write(4105, int(P))
        self.knob_values['proportional band'] = P

    def get_proportional_band(self):
        P = self.read(4105)
        self.knob_values['proportional band'] = P
        return P

    def set_integration_time(self, Ti):
        self.write(4108, int(Ti))

    def get_integration_time(self):
        return self.read(4108)

    def set_derivative_time(self, Td):
        self.write(4107, int(Td))
        self.knob_values['integration time'] = setpoint

    def get_derivative_time(self):
        return self.read(4107)

    def measure_temperature(self):
        return self.read(4096, number_of_decimals=1)

    def measure_power(self):
        return self.read(4114, number_of_decimals=1)


class RedLionPXU(Instrument):
    """
    Red Lion's PXU temperature PID controller
    """

    name = 'RedLionPXU'

    supported_adapters = (
        (Modbus, {'buad_rate': 38400})
    )

    knobs = (
        'output',
        'setpoint',
        'autotune'
    )

    meters = (
        'temperature',
        'power'
    )

    def set_output(self, state):
        if state == 'ON':
            self.backend.write_bit(17, 1)  # turn on output & start PID control
        elif state == 'OFF':
            self.backend.write_bit(17, 0)  # turn off output & stop PID control

    def set_setpoint(self, setpoint):
        self.write(1, int(setpoint))
        self.knob_values['setpoint'] = setpoint

    def measure_temperature(self):
        return self.read(0)

    def measure_power(self):
        return self.read(8, number_of_decimals=1)

    def set_autotune(self, state):
        if state == 'ON':
            self.write(15, 1)
        elif state == 'OFF':
            self.write(15, 0)
