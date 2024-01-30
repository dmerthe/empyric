import re

from empyric.collection.instrument import Instrument, setter, getter, measurer
from empyric.adapters import Socket, Modbus
from empyric.types import recast, Boolean, Toggle, Integer, Float, Array
from enum import Enum


class BrainboxesED560(Instrument):
    """
    Brainboxes 4 channel analog output (0-10 V / 0-20mA) gateway.

    For socket communication, the default port is 9500. If the IP address is
    unknown, you can use the Boost.IO Driver software to find it.

    ASCII Protocol must be used.
    """

    supported_adapters = ((Socket, {}),)

    knobs = (
        "analog_out0",
        "analog_out1",
        "analog_out2",
        "analog_out3",
    )

    @setter
    def set_analog_out0(self, value: Float):
        self.query("#010%f" % float(value), validator=self._set_validator)

    @getter
    def get_analog_out0(self) -> Float:
        response = self.query("$0160", validator=self._get_validator)
        return recast(response[3:])

    @setter
    def set_analog_out1(self, value: Float):
        self.query("#011%f" % float(value), validator=self._set_validator)

    @getter
    def get_analog_out1(self) -> Float:
        response = self.query("$0161", validator=self._get_validator)
        return recast(response[3:])

    @setter
    def set_analog_out2(self, value: Float):
        self.query("#012%f" % float(value), validator=self._set_validator)

    @getter
    def get_analog_out2(self) -> Float:
        response = self.query("$0162", validator=self._get_validator)
        return recast(response[3:])

    @setter
    def set_analog_out3(self, value: Float):
        self.query("#013%f" % float(value), validator=self._set_validator)

    @getter
    def get_analog_out3(self) -> Float:
        response = self.query("$0163", validator=self._get_validator)
        return recast(response[3:])

    @staticmethod
    def _get_validator(response):
        return re.match("!01\+\d\d\.\d\d\d", response)

    @staticmethod
    def _set_validator(response):
        return response.strip() == ">"


class BrainboxesED549(Instrument):
    """
    Brainboxes 4 channel analog input (0-10 V / 0-20mA) gateway.

    For socket communication, the default port is 9500. If the IP address is
    unknown, you can use the Boost.IO Driver software to find it.

    ASCII Protocol must be used.
    """

    supported_adapters = ((Socket, {}),)

    meters = (
        "analog_in0",
        "analog_in1",
        "analog_in2",
        "analog_in3",
    )

    @measurer
    def measure_analog_in0(self) -> Float:
        response = self.query("#010", validator=self._validator)
        return response[1:]

    @measurer
    def measure_analog_in1(self) -> Float:
        response = self.query("#011", validator=self._validator)
        return response[1:]

    @measurer
    def measure_analog_in2(self) -> Float:
        response = self.query("#012", validator=self._validator)
        return response[1:]

    @measurer
    def measure_analog_in3(self) -> Float:
        response = self.query("#013", validator=self._validator)
        return response[1:]

    @staticmethod
    def _validator(response):
        return re.match(">\+?\-?\d\d\.\d\d\d", response)


class ADAM6024(Instrument):
    """
    Advantech ADAM-6024 6 channel analog input (0-10 V / 0-20mA) / 2 channel
    analog output module.

    Using Modbus Protocol
    """

    supported_adapters = ((Modbus, {"byte_order": ">"}),)

    knobs = (
        "analog_out0",
        "analog_out1",
        "analog_in0_type",
        "analog_in1_type",
        "analog_in2_type",
        "analog_in3_type",
        "analog_in4_type",
        "analog_in5_type",
        "analog_out0_type",
        "analog_out1_type",
    )

    meters = (
        "analog_in0",
        "analog_in1",
        "analog_in2",
        "analog_in3",
        "analog_in4",
        "analog_in5",
    )

    presets = {
        "analog_in0_type": "+/-10V",
        "analog_in1_type": "+/-10V",
        "analog_in2_type": "+/-10V",
        "analog_in3_type": "+/-10V",
        "analog_in4_type": "+/-10V",
        "analog_in5_type": "+/-10V",
        "analog_out0_type": "0~10V",
        "analog_out1_type": "0~10V",
    }

    AIN_TYPES = {
        "4~20mA": 0x07,
        "+/-10V": 0x08,
        "0~20mA": 0x0D
    }

    AOUT_TYPES = {
        "0~20mA": 0x00,
        "4~20mA": 0x01,
        "0~10V": 0x02
    }

    def _measure_AIN(self, n) -> Float:
        raw = self.read(4, n, _type="16bit_uint")
        match self._get_AIN_type(n):
            case "4~20mA":
                return raw/65535.0 * 16 + 4
            case "+/-10V":
                return raw/65535.0 * 20 - 10
            case "0~20mA":
                return raw/65535.0 * 20
            case _:
                raise TypeError("Unrecognized Type")
                return None

    def _set_AOUT(self, n, value) -> Float:
        match self._get_AOUT_type(n):
            case "0~20mA":
                scaled_value = int((value)/20.0*((2**12)-1))
            case "4~20mA":
                scaled_value = int((value-4)/16.0*((2**12)-1))
            case "0~10V":
                scaled_value = int((value)/10.0*((2**12)-1))
            case _:
                scaled_value = None
                raise TypeError("Unrecognized Type")
        return self.write(6, 10 + n, scaled_value, _type="16bit_uint")

    def _get_AOUT(self, n) -> Float:
        raw = self.read(4, 10 + n, _type="16bit_uint")
        match self._get_AOUT_type(n):
            case "0~20mA":
                return raw/float(2**12-1) * 20
            case "4~20mA":
                return raw/float(2**12-1) * 16 + 4
            case "0~10V":
                return raw/float(2**12-1) * 10
            case _:
                raise TypeError("Unrecognized Type")
                return None

    def _set_AIN_type(self, n, str_value: str) -> Float:
        if str_value in self.AIN_TYPES.keys():
            value = self.AIN_TYPES[str_value]
            return self.write(6, 200 + n, value, _type="16bit_uint")
        else:
            raise TypeError(f"Value not in [{self.AIN_TYPES}]")

    def _get_AIN_type(self, n) -> str:
        ain_types_rev = {val: key for key, val in self.AIN_TYPES.items()}
        return ain_types_rev[self.read(4, 200 + n, _type="16bit_uint")]

    def _set_AOUT_type(self, n, str_value) -> Float:
        if str_value in self.AOUT_TYPES.keys():
            value = self.AOUT_TYPES[str_value]
            return self.write(6, 208 + n, value, _type="16bit_uint")
        else:
            raise TypeError(f"Value not in [{self.AOUT_TYPES}]")

    def _get_AOUT_type(self, n) -> str:
        aout_types_rev = {val: key for key, val in self.AOUT_TYPES.items()}
        return aout_types_rev[self.read(4, 208 + n, _type="16bit_uint")]

    @setter
    def set_analog_out0(self, value: Float):
        self._set_AOUT(0, value)

    @getter
    def get_analog_out0(self) -> Float:
        return self._get_AOUT(0)

    @setter
    def set_analog_out1(self, value: Float):
        self._set_AOUT(1, value)

    @getter
    def get_analog_out1(self) -> Float:
        return self._get_AOUT(1)

    @measurer
    def measure_analog_in0(self) -> Float:
        return self._measure_AIN(0)

    @measurer
    def measure_analog_in1(self) -> Float:
        return self._measure_AIN(1)

    @measurer
    def measure_analog_in2(self) -> Float:
        return self._measure_AIN(2)

    @measurer
    def measure_analog_in3(self) -> Float:
        return self._measure_AIN(3)

    @measurer
    def measure_analog_in4(self) -> Float:
        return self._measure_AIN(4)

    @measurer
    def measure_analog_in5(self) -> Float:
        return self._measure_AIN(5)

    @setter
    def set_analog_out0_type(self, value: str):
        self._set_AOUT_type(0, value)

    @getter
    def get_analog_out0_type(self) -> str:
        return self._get_AOUT_type(0)

    @setter
    def set_analog_out1_type(self, value: str):
        self._set_AOUT_type(1, value)

    @getter
    def get_analog_out1_type(self) -> str:
        return self._get_AOUT_type(1)

    @setter
    def set_analog_in0_type(self, value: str):
        self._set_AIN_type(0, value)

    @getter
    def get_analog_in0_type(self) -> str:
        return self._get_AIN_type(0)

    @setter
    def set_analog_in1_type(self, value: str):
        self._set_AIN_type(1, value)

    @getter
    def get_analog_in1_type(self) -> str:
        return self._get_AIN_type(1)

    @setter
    def set_analog_in2_type(self, value: str):
        self._set_AIN_type(2, value)

    @getter
    def get_analog_in2_type(self) -> str:
        return self._get_AIN_type(2)

    @setter
    def set_analog_in3_type(self, value: str):
        self._set_AIN_type(3, value)

    @getter
    def get_analog_in3_type(self) -> str:
        return self._get_AIN_type(3)

    @setter
    def set_analog_in4_type(self, value: str):
        self._set_AIN_type(4, value)

    @getter
    def get_analog_in4_type(self) -> str:
        return self._get_AIN_type(4)

    @setter
    def set_analog_in5_type(self, value: str):
        self._set_AIN_type(5, value)

    @getter
    def get_analog_in5_type(self) -> str:
        return self._get_AIN_type(5)