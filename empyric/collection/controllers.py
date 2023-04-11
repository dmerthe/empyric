from empyric.adapters import *
from empyric.types import Toggle, ON, OFF, Float, Integer, String
from empyric.collection.instrument import *


class OmegaCN7500(Instrument):
    """
    Omega model CN7500 PID temperature controller
    """

    name = 'OmegaCN7500'

    supported_adapters = (
        (ModbusSerial, {'slave_mode': 'rtu',
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
    def set_output(self, state: Toggle):
        if state == ON:
            # turn on output & start PID control
            self.backend.write_bit(0x814, 1)
        elif state == OFF:
            # turn off output & stop PID control
            self.backend.write_bit(0x814, 0)

    @setter
    def set_setpoint(self, setpoint: Float):
        self.write(0x1001, int(10*setpoint))

    @getter
    def get_setpoint(self) -> Float:
        return self.read(0x1001) / 10

    @setter
    def set_proportional_band(self, P: Integer):
        self.write(0x1009, P)

    @getter
    def get_proportional_band(self) -> Integer:
        return self.read(0x1009)

    @setter
    def set_integration_time(self, Ti: Integer):
        self.write(0x100c, Ti)

    @getter
    def get_integration_time(self) -> Integer:
        return self.read(0x100c)

    @setter
    def set_derivative_time(self, Td: Integer):
        self.write(0x100b, Td)

    @getter
    def get_derivative_time(self) -> Integer:
        return self.read(0x100b)

    @measurer
    def measure_temperature(self) -> Float:
        return self.read(0x1000) / 10

    @measurer
    def measure_power(self) -> Float:
        return self.read(0x1000) / 10


class OmegaPlatinum(Instrument):
    """
    Omega Platinum series PID controller
    """

    name = "OmegaPlatinum"

    supported_adapters = (
        (ModbusSerial, {
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
    def measure_temperature(self) -> Float:
        return self.read(0x0280, dtype='float')

    @measurer
    def measure_power(self) -> Float:
        return self.read(0x022A, dtype='float')

    @setter
    def set_setpoint(self, setpoint: Float):
        self.write(0x02E2, setpoint, dtype='float')

    @getter
    def get_setpoint(self) -> Float:
        return self.read(0x02E2, dtype='float')

    @setter
    def set_autotune(self, state: Toggle):
        if state == ON:
            self.write(0x0243, 1)
        else:
            self.write(0x0243, 0)

    @setter
    def set_output(self, state: Toggle):
        if state == ON:
            self.write(0x0240, 6)
        else:
            self.write(0x0240, 8)

    @getter
    def get_output(self) -> Toggle:
        state = self.read(0x0240)
        if state == 6 or state == 4:
            return ON
        else:
            return OFF

    @setter
    def set_tc_type(self, _type: String):
        try:
            self.write(0x0283, OmegaPlatinum.TC_map[_type.upper()])
        except (KeyError, AttributeError):
            raise ValueError(f'{self.name}: Invalid thermocouple type {_type}')

    @getter
    def get_tc_type(self) -> String:
        try:
            return self.inverse_TC_map[self.read(0x0283)]
        except KeyError:
            return 'None'


class RedLionPXU(Instrument):
    """
    Red Lion PXU temperature PID controller
    """

    name = 'RedLionPXU'

    supported_adapters = (
        (ModbusSerial, {'buad_rate': 38400}),
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
    def set_output(self, state: Toggle):
        if state == ON:
            # turn on output & start PID control
            self.backend.write_bit(0x11, 1)
        elif state == OFF:
            # turn off output & stop PID control
            self.backend.write_bit(0x11, 0)

    @setter
    def set_setpoint(self, setpoint: Integer):
        self.write(0x1, int(setpoint))

    @measurer
    def measure_temperature(self) -> Integer:
        return self.read(0x0)

    @measurer
    def measure_power(self) -> Float:
        return self.read(0x8) / 10

    @setter
    def set_autotune(self, state: Toggle):
        if state == ON:
            self.write(0xf, 1)
        elif state == OFF:
            self.write(0xf, 0)


class WatlowEZZone(Instrument):
    """
    Watlow EZ-Zone PID process controller
    """

    name = 'WatlowEZZone'

    supported_adapters = (
        (ModbusSerial, {'baud_rate': 9600}),
    )

    knobs = (
        'setpoint',
    )

    meters = (
        'temperature',
    )

    @measurer
    def measure_temperature(self) -> Float:
        # swapped little-endian byte order (= 3 in minimalmodbus)
        return self.read(360, dtype='float', byte_order=3)

    @getter
    def get_setpoint(self) -> Float:
        return self.read(2160, dtype='float', byte_order=3)

    @setter
    def set_setpoint(self, setpoint: Float):
        return self.write(2160, setpoint, dtype='float', byte_order=3)

    @getter
    def get_proportional_band(self) -> Float:
        return self.read(1890, dtype='float', byte_order=3)

    @setter
    def set_proportional_band(self, band: Float):
        return self.write(1890, band, dtype='float', byte_order=3)

    @getter
    def get_time_integral(self) -> Float:
        return self.read(1894, dtype='float', byte_order=3)

    @setter
    def set_time_integral(self, integral: Float):
        return self.write(1894, integral, dtype='float', byte_order=3)

    @getter
    def get_time_derivative(self) -> Float:
        return self.read(1896, dtype='float', byte_order=3)

    @setter
    def set_time_derivative(self, derivative: Float):
        return self.write(1896, derivative, dtype='float', byte_order=3)


class MKSGSeries(Instrument):
    """MKS G series mass flow controller"""

    name = 'MKSGSeries'

    supported_adapters = ((Modbus, {}),)

    knobs = (
        'setpoint',  # flow rate setpoint in SCCM
        'ramp time'  # ramp time in milliseconds
    )

    meters = (
        'flow rate',  # actual flow rate in SCCM
        'valve position',  # valve position in percent
        'temperature'  # temperature in degrees C
    )

    @setter
    def set_setpoint(self, setpoint: Float):
        self.write(16, 0xA000, setpoint, dtype='32bit_float')

    @getter
    def get_setpoint(self) -> Float:
        return self.read(3, 0xA000, count=2, dtype='32bit_float')

    @setter
    def set_ramp_time(self, ramp_time: Float):
        self.write(16, 0xA002, int(ramp_time), dtype='32bit_uint')

    @getter
    def get_ramp_time(self) -> Float:
        return self.read(3, 0xA002, count=2, dtype='32bit_uint')

    @measurer
    def measure_flow_rate(self) -> Float:
        return self.read(4, 0x4000, count=2, dtype='32bit_float')

    @measurer
    def measure_valve_position(self) -> Float:
        return self.read(4, 0x4004, count=2, dtype='32bit_float')

    @measurer
    def measure_temperature(self) -> Float:
        return self.read(4, 0x4002, count=2, dtype='32bit_float')


class AlicatMFC(Instrument):
    """Alicat mass flow controller"""

    name = 'AlicatMFC'

    supported_adapters = (
        (Modbus, {}),
    )

    knobs = (
        'setpoint',  # flow rate setpoint in SCCM
    )

    meters = (
        'flow rate',  # actual flow rate in SCCM
        'temperature',  # temperature in degrees C
        'pressure'  
        # pressure in PSI (absolute, gauge or differential,
        # depending on device configuration)
    )

    @setter
    def set_setpoint(self, setpoint: Float):
        self.write(16, 1009, setpoint, dtype='32bit_float')

    @getter
    def get_setpoint(self) -> Float:
        return self.read(3, 1009, count=2, dtype='32bit_float')

    @measurer
    def measure_flow_rate(self) -> Float:
        return self.read(4, 1208, count=2, dtype='32bit_float')

    @measurer
    def measure_temperature(self) -> Float:
        return self.read(4, 1204, count=2, dtype='32bit_float')

    @measurer
    def measure_pressure(self) -> Float:
        return self.read(4, 1202, count=2, dtype='32bit_float')
