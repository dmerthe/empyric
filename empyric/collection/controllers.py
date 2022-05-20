from empyric.adapters import *
from empyric.tools import is_on, is_off
from empyric.collection.instrument import *


class OmegaCN7500(Instrument):
    """
    Omega model CN7500 PID temperature controller
    """

    name = 'OmegaCN7500'

    supported_adapters = (
        (Modbus, {'slave_mode': 'rtu',
                  'baud_rate': 38400,
                  'parity': 'N',
                  'delay': 0.2}),
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

    @setter
    def set_output(self, state):
        if state == 'ON':
            self.backend.write_bit(0x814, 1)  # turn on output & start PID control
        elif state == 'OFF':
            self.backend.write_bit(0x814, 0)  # turn off output & stop PID control

    @setter
    def set_setpoint(self, setpoint):
        self.write(0x1001, 10*setpoint)

    @getter
    def get_setpoint(self):
        return self.read(0x1001) / 10

    @setter
    def set_proportional_band(self, P):
        self.write(0x1009, int(P))

    @getter
    def get_proportional_band(self):
        return self.read(0x1009)

    @setter
    def set_integration_time(self, Ti):
        self.write(0x100c, int(Ti))

    @getter
    def get_integration_time(self):
        return self.read(0x100c)

    @setter
    def set_derivative_time(self, Td):
        self.write(0x100b, int(Td))

    @getter
    def get_derivative_time(self):
        return self.read(0x100b)

    @measurer
    def measure_temperature(self):
        return self.read(0x1000) / 10

    @measurer
    def measure_power(self):
        return self.read(0x1000) / 10


class OmegaPlatinum(Instrument):
    """
    Omega Platinum series PID controller
    """

    name = "OmegaPlatinum"

    supported_adapters = (
        (Modbus, {
            'baud_rate': 19200,
            'parity': 'O'
        }),
    )

    knobs = (
        'setpoint',
        'autotune',
        'output',
        'tc type',
    )

    meters = (
        'temperature',
        'power'
    )

    TC_map = {
        'K': 1,
        'J': 0,
        'T': 2,
        'E': 3,
        'N': 4,
        'R': 6,
        'S': 7,
        'B': 8,
        'C': 9,
    }

    inverse_TC_map = {v: k for k, v in TC_map.items()}

    @measurer
    def measure_temperature(self):
        return self.read(0x0280, dtype='float')

    @measurer
    def measure_power(self):
        return self.read(0x022A, dtype='float')

    @setter
    def set_setpoint(self, setpoint):
        self.write(0x02E2, setpoint, dtype='float')

    @getter
    def get_setpoint(self):
        return self.read(0x02E2, dtype='float')

    @setter
    def set_autotune(self, state):
        if is_on(state):
            self.write(0x0243, 1)
        elif is_off(state):
            self.write(0x0243, 0)

    @setter
    def set_output(self, state):
        if is_on(state):
            self.write(0x0240, 6)
        elif is_off(state):
            self.write(0x0240, 8)

    @getter
    def get_output(self):
        state = self.read(0x0240)
        if state == 6 or state == 4:
            return 'ON'
        elif state == 8:
            return 'OFF'
        elif state == 1:
            return 'IDLE'
        elif state == 10:
            return 'ALARM'
        else:
            return float('nan')

    @setter
    def set_tc_type(self, _type):
        try:
            self.write(0x0283, OmegaPlatinum.TC_map[_type.upper()])
        except (KeyError, AttributeError):
            raise ValueError(f'{self.name}: Invalid thermocouple type {_type}')

    @getter
    def get_tc_type(self):
        try:
            return self.inverse_TC_map[self.read(0x0283)]
        except KeyError:
            return None


class RedLionPXU(Instrument):
    """
    Red Lion PXU temperature PID controller
    """

    name = 'RedLionPXU'

    supported_adapters = (
        (Modbus, {'buad_rate': 38400}),
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

    @setter
    def set_output(self, state):
        if state == 'ON':
            self.backend.write_bit(0x11, 1)  # turn on output & start PID control
        elif state == 'OFF':
            self.backend.write_bit(0x11, 0)  # turn off output & stop PID control

    @setter
    def set_setpoint(self, setpoint):
        self.write(0x1, int(setpoint))

    @measurer
    def measure_temperature(self):
        return self.read(0x0)

    @measurer
    def measure_power(self):
        return self.read(0x8) / 10

    @setter
    def set_autotune(self, state):
        if state == 'ON':
            self.write(0xf, 1)
        elif state == 'OFF':
            self.write(0xf, 0)


class WatlowEZZone(Instrument):
    """
    Watlow EZ-Zone PID process controller
    """

    name = 'WatlowEZZone'

    supported_adapters = (
        (Modbus, {'baud_rate': 9600}),
    )

    knobs = (
        'setpoint',
    )

    meters = (
        'temperature',
    )

    @measurer
    def measure_temperature(self):
        return self.read(360, dtype='float', byte_order=3)  # swapped little-endian byte order (= 3 in minimalmodbus)

    @getter
    def get_setpoint(self):
        return self.read(2160, dtype='float', byte_order=3)

    @setter
    def set_setpoint(self, setpoint):
        return self.write(2160, setpoint, dtype='float', byte_order=3)

    @getter
    def get_proportional_band(self):
        return self.read(1890, dtype='float', byte_order=3)

    @setter
    def set_proportional_band(self, band):
        return self.write(1890, band, dtype='float', byte_order=3)

    @getter
    def get_time_integral(self):
        return self.read(1894, dtype='float', byte_order=3)

    @setter
    def set_time_integral(self, integral):
        return self.write(1894, integral, dtype='float', byte_order=3)

    @getter
    def get_time_derivative(self):
        return self.read(1896, dtype='float', byte_order=3)

    @setter
    def set_time_derivative(self, derivative):
        return self.write(1896, derivative, dtype='float', byte_order=3)
