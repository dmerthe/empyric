import re
import struct
import socket
import numpy as np

from empyric.tools import logger
from empyric.types import Toggle, Float, ON, OFF
from empyric.adapters import Serial, Socket, GPIB
from empyric.collection.instrument import Instrument, setter, getter, measurer


class Keithley2260B(Instrument):
    """
    Keithley 2260B power supply, usually either 360 W or 720 W
    """

    name = "Keithley2260B"

    supported_adapters = (
        (Serial, {"baud_rate": 115200, "write_termination": "\r\n"}),
        (Socket, {"read_termination": "\n", "write_termination": "\n"}),
    )

    knobs = ("max voltage", "max current", "output")

    # no presets or postsets for this instrument

    meters = ("voltage", "current")

    @measurer
    def measure_current(self) -> Float:
        def validator(response):
            return bool(re.match("[\+\-]\d+\.\d\d\d", response))

        return float(self.query("MEAS:CURR?", validator=validator))

    @measurer
    def measure_voltage(self) -> Float:
        def validator(response):
            return bool(re.match("[\+\-]\d+\.\d\d\d", response))

        return float(self.query("MEAS:VOLT?", validator=validator))

    @setter
    def set_max_voltage(self, voltage: Float):
        self.write("VOLT %.4f" % voltage)

    @setter
    def set_max_current(self, current: Float):
        self.write("CURR %.4f" % current)

    @setter
    def set_output(self, output: Toggle):
        if output == ON:
            self.write("OUTP:STAT:IMM ON")
        elif output == OFF:
            self.write("OUTP:STAT:IMM OFF")

    @getter
    def get_output(self) -> Toggle:
        response = self.query("OUTP?")

        if response == "0":
            return OFF
        elif response == "1":
            return ON

    @getter
    def get_max_current(self) -> Float:
        def validator(response):
            return bool(re.match("[\+\-]\d+\.\d\d\d", response))

        return float(self.query("CURR?", validator=validator))

    @getter
    def get_max_voltage(self) -> Float:
        def validator(response):
            return bool(re.match("[\+\-]\d+\.\d\d\d", response))

        return float(self.query("VOLT?", validator=validator))


class BK9183B(Instrument):
    """
    B&K Precision Model 9183B (35V & 6A / 70V & 3A) power supply
    """

    name = "BK9183B"

    supported_adapters = (
        (Serial, {"baud_rate": 57600}),
        (Socket, {"read_termination": "\n", "write_termination": "\n"}),
    )

    knobs = ("max voltage", "max current", "output")

    # no presets or postsets for this instrument

    meters = ("voltage", "current")

    @setter
    def set_output(self, output: Toggle):
        if output == ON:
            self.write("OUT ON")
        elif output == OFF:
            self.write("OUT OFF")

    @measurer
    def measure_current(self):
        # sometimes the first measurement is lagged
        return [float(self.query("MEAS:CURR?")) for i in range(3)][-1]

    @measurer
    def measure_voltage(self):
        # sometimes the first measurement is lagged
        return [float(self.query("MEAS:VOLT?")) for i in range(3)][-1]

    @setter
    def set_max_current(self, current):
        self.write("SOUR:CURR " + str(current))

    @setter
    def set_max_voltage(self, voltage):
        self.write("SOUR:VOLT " + str(voltage))

    @getter
    def get_max_current(self):
        return float(self.query("SOUR:CURR?"))

    @getter
    def get_max_voltage(self):
        return float(self.query("SOUR:VOLT?"))


class UltraflexInductionHeater(Instrument):
    """UltraFlex Ultraheat S2 (or similar) 2 kW induction heater"""

    name = "UltraflexInductionHeater"

    supported_adapters = (Serial, {})

    knobs = ("power", "output", "mode")

    meters = (
        "voltage",
        "current",
        "frequency",
    )

    @measurer
    def measure_current(self):
        return 0.1 * float(self.query("S3i11K")[3:-3], 16)

    @measurer
    def measure_voltage(self):
        return float(self.query("S3v04K")[3:-3], 16)

    @measurer
    def measure_frequency(self):
        return 1e3 * float(self.query("S3f14K")[3:-3], 16)

    @setter
    def set_power(self, percent_of_max):
        if percent_of_max < 0 or percent_of_max > 100:
            raise ValueError(
                "power setting must be a percentage value between 0 and 100"
            )

        ascii_command = "S34"
        ascii_command += hex(int(round(percent_of_max)))[-2:].upper()
        ascii_command += hex(512 - sum(ascii_command.encode()))[-2:].upper()
        self.query(ascii_command + "K")

    @getter
    def get_power(self):
        return float(self.query("S3B38K")[3:5], 16)

    @setter
    def set_output(self, output):
        if Toggle(output):
            self.query("S3200E8K")
        else:
            self.query("S3347K")

    @setter
    def set_mode(self, mode):
        if mode.lower() == "manual":
            self.query("S3L01CDK")
        elif mode.lower() == "remote":
            self.query("S3L00CEK")
        else:
            raise ValueError(
                f"{self.name}: Unsupported control mode {mode}. "
                'Allowed values are "manual" and "remote".'
            )


class SRSPS300(Instrument):
    """
    Stanford Rsearch Systems PS-300 series high voltage power supply.
    """

    name = "SRSPS350"

    supported_adapters = ((GPIB, {}),)

    knobs = (
        "output",
        "voltage",
        "max voltage",
        "max current",
        "trip current",
        "clear trip",
    )

    presets = {"output": "OFF", "voltage": 0, "max current": 5e-3}

    postsets = {"output": "OFF", "voltage": 0, "max current": 5e-3}

    meters = ("voltage", "current")

    @setter
    def set_output(self, output: Toggle):
        if output == ON:
            self.write("HVON")
        else:
            self.write("HVOF")

    @getter
    def get_output(self) -> Toggle:
        # last bit of status byte is the output state

        def validator(response):
            return re.match("\d{1}", response)

        status_bit_7 = int(self.query("*STB? 7", validator=validator))

        if status_bit_7 == 1:
            return ON
        else:
            return OFF

    @setter
    def set_voltage(self, voltage: Float):
        self.write("VSET%f" % float(voltage))

    @getter
    def get_voltage(self) -> Float:
        return float(self.query("VSET?"))

    @setter
    def set_max_voltage(self, voltage: Float):
        self.write("VLIM%f" % float(voltage))

    @getter
    def get_max_voltage(self) -> Float:
        return float(self.query("VLIM?"))

    @setter
    def set_max_current(self, current: Float):
        self.write("ILIM%f" % float(current))

    @getter
    def get_max_current(self) -> Float:
        return float(self.query("ILIM?"))

    @setter
    def set_trip_current(self, current: Float):
        self.write("ITRP%f" % float(current))

    @getter
    def get_trip_current(self) -> Float:
        return float(self.query("ITRP?"))

    @setter
    def set_clear_trip(self, state: Toggle) -> Toggle:
        if state == ON:
            self.write("TCLR")

        return self.get_clear_trip()

    @getter
    def get_clear_trip(self):
        try:
            status_byte_1 = int(self.query("*STB? 1"))
            status_byte_2 = int(self.query("*STB? 2"))

            ovp_tripped = status_byte_1 == 1
            ocp_tripped = status_byte_2 == 1

        except ValueError:
            return None

        if ovp_tripped or ocp_tripped:
            return OFF
        else:
            return ON

    @measurer
    def measure_voltage(self) -> Float:
        return float(self.query("VOUT?"))

    @measurer
    def measure_current(self) -> Float:
        return float(self.query("IOUT?"))


class KoradKWR100(Instrument):
    """
    Korad KWR100 series power supply

    When using LAN communications (via Socket adapter) use the KWR100 Assistant
    executable to configure IP address and port number. Also, send the command
    ":SYST:UPDMODE 0" in order to be able to use an arbitrary local port.
    """

    name = "KWR100"

    supported_adapters = (
        (
            Socket,
            {
                "type": socket.SOCK_DGRAM,  # UDP
                "write_termination": "\n",
                "read_termination": "\n",
                "timeout": 1,
            },
        ),
    )

    knobs = ("output", "max voltage", "max current")

    meters = ("voltage", "current")

    @setter
    def set_output(self, state: Toggle):
        if state == ON:
            self.write("OUT:1")
        elif state == OFF:
            self.write("OUT:0")

    @getter
    def get_output(self) -> Toggle:
        response = self.query("OUT?")

        if response == "0":
            return OFF
        elif response == "1":
            return ON

    @setter
    def set_max_voltage(self, voltage: Float):
        self.write("VSET:%.2f" % voltage)

    @getter
    def get_max_voltage(self) -> Float:
        return float(self.query("VSET?"))

    @setter
    def set_max_current(self, current: Float):
        self.write("ISET:%.2f" % current)

    @getter
    def get_max_current(self) -> Float:
        return float(self.query("ISET?"))

    @measurer
    def measure_voltage(self) -> Float:
        return float(self.query("VOUT?"))

    @measurer
    def measure_current(self) -> Float:
        return float(self.query("IOUT?"))


class MagnaPowerSL1000(Instrument):
    """Magna-Power SL series 1.5 kW (1 kV / 1.5 A) power supply"""

    supported_adapters = (
        (
            Serial,
            {
                "baud_rate": 19200,
                "read_termination": "\r\n",
                "write_termination": "\r\n",
                "timeout": 10.0,
            },
        ),
    )

    name = "MagnaPowerSL1000"

    knobs = (
        "output",
        "output protection clear",
        "over voltage protection",
        "over current protection",
        "max voltage",
        "max current",
    )

    meters = ("voltage", "current")

    @setter
    def set_output(self, state: Toggle):
        if state == ON:
            self.write("OUTP:START")
        elif state == OFF:
            self.write("OUTP:STOP")

    @getter
    def get_output(self) -> Toggle:
        response = self.query("OUTP?").strip()

        if response == b"1":
            return ON
        elif response == b"0":
            return OFF
        else:
            return None

    @setter
    def set_output_protection_clear(self, state: Toggle):
        if state == ON:
            self.write("OUTP:PROT:CLE")

        return self.get_over_current_protection()

    @getter
    def get_output_protection_clear(self) -> Toggle:
        # Read the "questionable" register

        response = self.query("STAT:QUES:COND?")

        try:
            register = int(response)
        except ValueError:
            return None

        # Questionable Register bits as described in the manual
        ov_bit, register = register // 1024, register % 1024
        oc_bit, register = register // 512, register % 512
        pb_bit, register = register // 256, register % 256
        pgm_bit, register = register // 128, register % 128
        ot_bit, register = register // 64, register % 64
        fuse_bit, register = register // 32, register % 32
        alm_bit, register = register // 16, register % 16

        if any([ov_bit, oc_bit, pb_bit, pgm_bit, ot_bit, fuse_bit, alm_bit]):
            return OFF
        else:
            return ON

    @setter
    def set_over_voltage_protection(self, voltage: Float):
        self.write("VOLT:PROT %.1f" % voltage)

    @getter
    def get_over_voltage_protection(self) -> Float:
        response = self.query("VOLT:PROT?")

        try:
            return float(response)
        except ValueError:
            return np.nan

    @setter
    def set_over_current_protection(self, voltage: Float):
        self.write("CURR:PROT %.1f" % voltage)

    @getter
    def get_over_current_protection(self) -> Float:
        response = self.query("CURR:PROT?")

        try:
            return float(response)
        except ValueError:
            return np.nan

    @setter
    def set_max_voltage(self, voltage: Float):
        self.write("VOLT %.1f" % voltage)

    @getter
    def get_max_voltage(self) -> Float:
        response = self.query("VOLT?")

        try:
            return float(response)
        except ValueError:
            return np.nan

    @setter
    def set_max_current(self, current: Float):
        self.write("CURR %.1f" % current)

    @getter
    def get_max_current(self) -> Float:
        response = self.query("CURR?")

        try:
            return float(response)
        except ValueError:
            return np.nan

    @measurer
    def measure_voltage(self) -> Float:
        response = self.query("MEAS:VOLT?").strip()

        try:
            return float(response)
        except ValueError:
            return np.nan

    @measurer
    def measure_current(self) -> Float:
        response = self.query("MEAS:CURR?").strip()

        try:
            return float(response)
        except ValueError:
            return np.nan


class SorensenXG10250(Instrument):
    """
    Sorensen XG 10-250 series high current power supply.

    The analog control mode option allows the power supply to operate in a
    voltage-controlled current mode via its non-isolated input pin.

    By default, the RS-485 multicast address is assumed to be 1.
    """

    name = "SorensenXG10250"

    supported_adapters = (
        (Serial, {"baud_rate": 9600, "read_termination": "\r", "lib": "pyserial"}),
    )

    knobs = ("max voltage", "max current", "output", "analog control mode")

    meters = ("voltage", "current", "analog input voltage", "analog input current")

    def __init__(
        self, address=None, adapter=None, presets=None, postsets=None, **kwargs
    ):
        self.address = address

        self.knobs = ("connected",) + self.knobs

        self.analog_mode_state = None

        adapter_connected = False
        if adapter:
            self.adapter = adapter(self, **kwargs)
        else:
            errors = []
            for _adapter, settings in self.supported_adapters:
                settings.update(kwargs)
                try:
                    self.adapter = _adapter(self, **settings)
                    adapter_connected = True
                    break
                except BaseException as error:
                    msg = (
                        f"in trying {_adapter.__name__} adapter, "
                        f"got {type(error).__name__}: {error}"
                    )
                    errors.append(msg)

            if not adapter_connected:
                message = (
                    f"unable to connect an adapter to "
                    f"instrument {self.name} at address {address}:\n"
                )
                for error in errors:
                    message = message + f"{error}\n"
                raise ConnectionError(message)

        if self.address:
            self.name = self.name + "@" + str(self.address)

        self.write("*ADR 1")  # Set multicast address to 1 by default

        # Get existing knob settings, if possible
        for knob in self.knobs:
            if hasattr(self, "get_" + knob.replace(" ", "_")):
                # retrieves the knob value from the instrument
                self.__getattribute__("get_" + knob.replace(" ", "_"))()
            else:
                # knob value is unknown until it is set
                self.__setattr__(knob.replace(" ", "_"), None)

        # Apply presets
        if presets:
            self.presets = {**self.presets, **presets}

        for knob, value in self.presets.items():
            self.set(knob, value)

        # Get postsets
        if postsets:
            self.postsets = {**self.postsets, **postsets}

        self.kwargs = kwargs

    def float_validator(self, response):
        return bool(re.match("\d+\.\d+", response))

    @measurer
    def measure_current(self):
        return self.query("MEAS:CURR?", validator=self.float_validator)

    @measurer
    def measure_voltage(self):
        return self.query("MEAS:VOLT?", validator=self.float_validator)

    @measurer
    def measure_analog_input_voltage(self):
        return self.query("MEAS:APR?", validator=self.float_validator)

    @measurer
    def measure_analog_input_current(self):
        return self.query("MEAS:APR:CURR?", validator=self.float_validator)

    @setter
    def set_output(self, output: Toggle):
        if output == ON:
            self.write("OUTP ON")
        elif output == OFF:
            self.write("OUTP OFF")

    @setter
    def set_analog_control_mode(self, analog_control_mode: Toggle):
        if analog_control_mode == ON:
            self.write("SYST:REM:SOUR:CURR AVOL")
        if analog_control_mode == OFF:
            self.write("SYST:REM:SOUR:CURR LOC")

        # Verify mode was sent
        def str_validator(response):
            return bool(re.match("Current mode: .*", response))

        response = self.query(
            "SYST:REM:SOUR:CURR?", validator=str_validator, until="\r"
        )
        if "Analog " in response:
            self.analog_mode_state = ON
        elif "LOCAL" in response:
            self.analog_mode_state = OFF

    @setter
    def set_max_current(self, current):
        self.write("SOUR:CURR " + str(current))

    @setter
    def set_max_voltage(self, voltage):
        self.write("SOUR:VOLT " + str(voltage))

    @getter
    def get_max_current(self):
        return self.query("SOUR:CURR?")

    @getter
    def get_max_voltage(self):
        return self.query("SOUR:VOLT?")

    @getter
    def get_output(self) -> Toggle:
        response = self.query("OUTP?")
        if response.startswith("0"):
            return OFF
        elif response.startswith("1"):
            return ON

    @getter
    def get_analog_control_mode(self) -> Toggle:
        if self.analog_mode_state is None:

            def str_validator(response):
                return bool(re.match("Current mode: .*", response))

            response = self.query(
                "SYST:REM:SOUR:CURR?", validator=str_validator, until="\r"  # :CURR?",
            )
            if "Analog " in response:
                self.analog_mode_state = ON
            elif "LOCAL" in response:
                self.analog_mode_state = OFF

        return self.analog_mode_state


class BK9140(Instrument):
    """
    B&K Precision Model 9140 (35V & 6A / 70V & 3A) power supply
    """

    name = "BK9140"

    supported_adapters = (
        (Serial, {"baud_rate": 57600}),
        (Socket, {"read_termination": "\n", "write_termination": "\n"}),
    )

    knobs = (
        "max voltage 1",
        "max current 1",
        "output 1",
        "max voltage 2",
        "max current 2",
        "output 2",
        "max voltage 3",
        "max current 3",
        "output 3",
    )

    # no presets or postsets for this instrument

    meters = (
        "voltage 1",
        "current 1",
        "voltage 2",
        "current 2",
        "voltage 3",
        "current 3",
    )

    @setter
    def set_output_1(self, output: Toggle):
        self.write(":INST:SEL 1")
        if output == ON:
            self.write("OUT ON")
        elif output == OFF:
            self.write("OUT OFF")

    @setter
    def set_output_2(self, output: Toggle):
        self.write(":INST:SEL 2")
        if output == ON:
            self.write("OUT ON")
        elif output == OFF:
            self.write("OUT OFF")

    @setter
    def set_output_3(self, output: Toggle):
        self.write(":INST:SEL 3")
        if output == ON:
            self.write("OUT ON")
        elif output == OFF:
            self.write("OUT OFF")

    @measurer
    def measure_current_1(self):
        # sometimes the first measurement is lagged
        self.write(":INST:SEL 1")
        return [float(self.query("MEAS:CURR?")) for i in range(3)][-1]

    @measurer
    def measure_voltage_1(self):
        # sometimes the first measurement is lagged
        self.write(":INST:SEL 1")
        return [float(self.query("MEAS:VOLT?")) for i in range(3)][-1]

    @setter
    def set_max_current_1(self, current):
        self.write(":INST:SEL 1")
        self.write("SOUR:CURR " + str(current))

    @setter
    def set_max_voltage_1(self, voltage):
        self.write(":INST:SEL 1")
        self.write("SOUR:VOLT " + str(voltage))

    @getter
    def get_max_current_1(self):
        self.write(":INST:SEL 1")
        return float(self.query("SOUR:CURR?"))

    @getter
    def get_max_voltage_1(self):
        self.write(":INST:SEL 1")
        return float(self.query("SOUR:VOLT?"))

    @measurer
    def measure_current_2(self):
        # sometimes the first measurement is lagged
        self.write(":INST:SEL 2")
        return [float(self.query("MEAS:CURR?")) for i in range(3)][-1]

    @measurer
    def measure_voltage_2(self):
        # sometimes the first measurement is lagged
        self.write(":INST:SEL 2")
        return [float(self.query("MEAS:VOLT?")) for i in range(3)][-1]

    @setter
    def set_max_current_2(self, current):
        self.write(":INST:SEL 2")
        self.write("SOUR:CURR " + str(current))

    @setter
    def set_max_voltage_2(self, voltage):
        self.write(":INST:SEL 2")
        self.write("SOUR:VOLT " + str(voltage))

    @getter
    def get_max_current_2(self):
        self.write(":INST:SEL 2")
        return float(self.query("SOUR:CURR?"))

    @getter
    def get_max_voltage_2(self):
        self.write(":INST:SEL 2")
        return float(self.query("SOUR:VOLT?"))

    @measurer
    def measure_current_3(self):
        # sometimes the first measurement is lagged
        self.write(":INST:SEL 3")
        return [float(self.query("MEAS:CURR?")) for i in range(3)][-1]

    @measurer
    def measure_voltage_3(self):
        # sometimes the first measurement is lagged
        self.write(":INST:SEL 3")
        return [float(self.query("MEAS:VOLT?")) for i in range(3)][-1]

    @setter
    def set_max_current_3(self, current):
        self.write(":INST:SEL 3")
        self.write("SOUR:CURR " + str(current))

    @setter
    def set_max_voltage_3(self, voltage):
        self.write(":INST:SEL 3")
        self.write("SOUR:VOLT " + str(voltage))

    @getter
    def get_max_current_3(self):
        self.write(":INST:SEL 3")
        return float(self.query("SOUR:CURR?"))

    @getter
    def get_max_voltage_3(self):
        self.write(":INST:SEL 3")
        return float(self.query("SOUR:VOLT?"))


class GlassmanOQ500(Instrument):
    """
    Glassman OQ series high voltage power supply (500 kV / 10 mA).


    """

    name = "GlassmanOQ"

    supported_adapters = (
        (
            Serial,
            {
                "baud_rate": 9600,
                "write_termination": "\r",
                "read_termination": "\r",
                "lib": "pyserial",
            },
        ),
    )

    knobs = ("max voltage", "max current", "output enable", "reset")

    meters = ("voltage", "current", "fault state")

    SOH: bytes = b"\x01"
    EOM: bytes = b"\x0D"

    max_output_voltage_volts = 500000.0  # 500kV
    max_output_current_mA = 20  # 20 mA

    vi_setpoints = [None, None]

    def _compute_checksum(self, message_segment: bytes) -> bytes:
        crc = (
            sum(struct.unpack(">" + "B" * len(message_segment), message_segment)) % 256
        )
        return bytes(format(crc, "X"), "utf-8")

    def _test_checksum(self, message: bytes) -> bool:
        calculated_crc = self._compute_checksum(message[1:-2])
        return message[-2:] == calculated_crc

    def _wrap_message(self, message_content) -> str:
        if type(message_content) != bytes:
            message_content = message_content.encode("utf-8")
        message = self.SOH
        message += message_content
        calculated_crc = self._compute_checksum(message_content)
        message += calculated_crc
        # message += self.EOM
        return message.decode()

    def _construct_set_message(
        self,
        normalized_voltage_cmd: float | None = None,
        normalized_current_cmd: float | None = None,
        hv_on_cmd: bool | None = None,
        hv_off_cmd: bool | None = None,
        reset_cmd: bool | None = None,
    ) -> str:
        # process inputs
        if normalized_voltage_cmd is not None:
            self.normalized_voltage_cmd = normalized_voltage_cmd
        if normalized_current_cmd is not None:
            self.normalized_current_cmd = normalized_current_cmd
        if hv_on_cmd is None:
            self.hv_on_cmd = False
        else:
            self.hv_on_cmd = hv_on_cmd
        if hv_off_cmd is None:
            self.hv_off_cmd = False
        else:
            self.hv_off_cmd = hv_off_cmd
        if reset_cmd is None:
            self.reset_cmd = False
        else:
            self.reset_cmd = reset_cmd

        # construct message
        message: bytes = b"S"  # command identifier
        message += bytes(
            format(int(0xFFF * self.normalized_voltage_cmd), "X").zfill(3), "utf-8"
        )
        message += bytes(
            format(int(0xFFF * self.normalized_current_cmd), "X").zfill(3), "utf-8"
        )
        message += b"000000"  # bytes 9-14
        message += bytes(
            format(
                int((self.reset_cmd << 2) ^ (self.hv_on_cmd << 1) ^ self.hv_off_cmd),
                "X",
            ),
            "utf-8",
        )
        return self._wrap_message(message)

    def _check_response_message(self, message) -> bool | None:
        if message == "":
            return None
        if self._test_checksum(message.encode("utf-8")):
            if message[0] == "R":
                # Check for fault state on byte 11, bit 1
                ps_fault = message[10:13][1:2]
                if ps_fault == "1":
                    logger.warning(
                        "GlassmanOQ500: Power supply is in a fault state. "
                        "A PS reset command must be sent "
                        "(via 'reset' knob) to clear fault "
                        "before setting new values!"
                    )
                return message
            else:
                raise KeyError(
                    f"GlassmanOQ500: Incorrect Message Type [{message[0]}]"
                    f" in decode_response_message()"
                )
        else:
            print(f"Checksum failed: {message}")
            raise ValueError(
                "GlassmanOQ500: Checksum error in " "decode_response_message()"
            )

    def _acknowledge_validator(self, message) -> bool | None:
        if message == "":
            return None
        if message == "A":
            return True
        elif message[0] == "E":
            logger.warning(
                f"GlassmanOQ500: Error message received "
                f"during set command: {message}. "
                f"See manual for further details."
            )
        else:
            return False

    @setter
    def set_max_voltage(self, voltage_Volts: Float):
        self.vi_setpoints[0] = voltage_Volts
        if self.vi_setpoints[1] is None:
            logger.warning(
                f"GlassmanOQ500: Waiting for current setpoint "
                f"to set voltage to {voltage_Volts} V."
            )
        else:
            normalized_voltage_cmd = voltage_Volts / self.max_output_voltage_volts
            normalized_current_cmd = self.vi_setpoints[1] / self.max_output_current_mA
            message: str = self._construct_set_message(
                normalized_voltage_cmd=normalized_voltage_cmd,
                normalized_current_cmd=normalized_current_cmd,
            )
            self.query(message, validator=self._acknowledge_validator)

    @setter
    def set_max_current(self, current_mA: Float):
        self.vi_setpoints[1] = current_mA
        if self.vi_setpoints[0] is None:
            logger.warning(
                f"GlassmanOQ500: Waiting for voltage setpoint "
                f"to set current to {current_mA} mA."
            )
        else:
            normalized_voltage_cmd = (
                self.vi_setpoints[0] / self.max_output_voltage_volts
            )
            normalized_current_cmd = current_mA / self.max_output_current_mA
            message: str = self._construct_set_message(
                normalized_voltage_cmd=normalized_voltage_cmd,
                normalized_current_cmd=normalized_current_cmd,
            )
            self.query(message, validator=self._acknowledge_validator)

    @getter
    def get_output_enable(self) -> Toggle:
        query = self._wrap_message("Q")
        response: str = self.query(query)
        response = self._check_response_message(response)[10:13][0:1]
        bytestr = bin(int(response))[2:].zfill(4)
        bit = bytestr[1:2]
        if bit == "1":
            return ON
        else:
            return OFF

    @setter
    def set_output_enable(self, output: Toggle):
        if output == ON:
            if self.vi_setpoints[0] is None or self.vi_setpoints[1] is None:
                logger.warning(
                    "GlassmanOQ500: Waiting for voltage and current "
                    "setpoints to be set in order to set output ON."
                )
            else:
                normalized_voltage_cmd = (
                    self.vi_setpoints[0] / self.max_output_voltage_volts
                )
                normalized_current_cmd = (
                    self.vi_setpoints[1] / self.max_output_current_mA
                )
                message: str = self._construct_set_message(
                    hv_on_cmd=True,
                    hv_off_cmd=False,
                    normalized_voltage_cmd=normalized_voltage_cmd,
                    normalized_current_cmd=normalized_current_cmd,
                )
                self.query(message, validator=self._acknowledge_validator)
        else:
            message: str = self._construct_set_message(
                hv_off_cmd=True,
                hv_on_cmd=False,
                normalized_voltage_cmd=0.0,
                normalized_current_cmd=0.0,
            )

            self.query(message, validator=self._acknowledge_validator)

    @setter
    def set_reset(self, reset: Toggle):
        if reset == ON:
            message: str = self._construct_set_message(
                reset_cmd=True, normalized_current_cmd=0.0, normalized_voltage_cmd=0.0
            )
            self.query(message, validator=self._acknowledge_validator)
            message: str = self._construct_set_message(
                reset_cmd=False, normalized_current_cmd=0.0, normalized_voltage_cmd=0.0
            )
            self.query(message, validator=self._acknowledge_validator)
            return OFF

    @measurer
    def measure_voltage(self) -> Float:
        response = self.query(self._wrap_message("Q"))
        voltage = self._check_response_message(response)[1:4]
        voltage_normalized = int(voltage, 16) / 0x3FF
        voltage_outp = voltage_normalized * self.max_output_voltage_volts
        return voltage_outp

    @measurer
    def measure_current(self) -> Float:
        response = self.query(self._wrap_message("Q"))
        current = self._check_response_message(response)[4:7]
        current_normalized = int(current, 16) / 0x3FF
        current_outp = current_normalized * self.max_output_current_mA
        return current_outp

    @measurer
    def measure_fault_state(self) -> Toggle:
        response = self.query(self._wrap_message("Q"))
        response = self._check_response_message(response)[10:13][1:2]
        bytestr = bin(int(response))[2:].zfill(4)
        bit = bytestr[2:3]
        if bit == "1":
            logger.warning(
                "GlassmanOQ500: Power supply is in a fault state. A PS reset "
                "command must be sent (via 'reset' knob) to clear "
                "fault before setting new values!"
            )
            return ON  # fault detected
        elif bit == "0":
            return OFF  # no fault


class PWX1500L(Instrument):
    name = "PWX1500L"

    supported_adapters = (
        (Socket, {"read_termination": "\r\n", "write_termination": "\r\n"}),
    )

    knobs = ("max voltage", "max current", "output")

    meters = ("voltage", "current")

    @measurer
    def measure_current(self) -> Float:
        def validator(response):
            return bool(re.match("[\+\-]\d+\.\d\d\d", response))

        return float(self.query("MEAS:CURR?", validator=validator))

    @measurer
    def measure_voltage(self) -> Float:
        def validator(response):
            return bool(re.match("[\+\-]\d+\.\d\d\d", response))

        return float(self.query("MEAS:VOLT?", validator=validator))

    @setter
    def set_max_voltage(self, voltage: Float):
        self.write("VOLT %.2f" % voltage)

    @setter
    def set_max_current(self, current: Float):
        self.write("CURR %.2f" % current)

    @setter
    def set_output(self, output: Toggle):
        if output == ON:
            self.write("OUTP ON")
        elif output == OFF:
            self.write("OUTP OFF")

    @getter
    def get_output(self) -> Toggle:
        response = self.query("OUTP?")

        if response == "0":
            return OFF
        elif response == "1":
            return ON

    @getter
    def get_max_current(self) -> Float:
        def validator(response):
            return bool(re.match("[\+\-]\d+\.\d\d\d", response))

        return float(self.query("CURR?", validator=validator))

    @getter
    def get_max_voltage(self) -> Float:
        def validator(response):
            return bool(re.match("[\+\-]\d+\.\d\d\d", response))

        return float(self.query("VOLT?", validator=validator))
