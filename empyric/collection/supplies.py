from empyric.adapters import *
from empyric.collection.instrument import *
from empyric.types import Toggle, Float, ON, OFF


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

    # supported_adapters = ((Serial, {"baud_rate": 57600}),)
    # Example of how to do this:
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

class SorensenXG(Instrument):
    """
    Sorensen XG 10-250 series high current power supply.
    """

    name = "SorensenXG10250"

    supported_adapters = ((Serial, {"baud_rate": 9600}))

    knobs = ("max voltage", "max current", "output")

    presets = {"output": "OFF", "voltage": 0, "max current": 5e-3}

    postsets = {"output": "OFF", "voltage": 0, "max current": 5e-3}

    meters = ("voltage", "current")


    @measurer
    def measure_current(self):
        return float(self.query("MEAS:CURR?"))

    @measurer
    def measure_voltage(self):
        return float(self.query("MEAS:VOLT?"))
    
    @setter
    def set_output(self, output: Toggle):
        if output == ON:
            self.write("OUTP: ON")
        elif output == OFF:
            self.write("OUTP: OFF")

    @setter
    def set_max_current(self, current):
        self.write("SOUR:CURR:PROT " + str(current))

    @setter
    def set_max_voltage(self, voltage):
        self.write("SOUR:VOLT:PROT " + str(voltage))

    @getter
    def get_max_current(self):
        return float(self.query("SOUR:CURR?"))

    @getter
    def get_max_voltage(self):
        return float(self.query("SOUR:VOLT?"))
    
    @getter
    def get_output(self) -> Toggle:
        response = self.query("OUTP?")
        if response == "OFF":
            return OFF
        elif response == "ON":
            return ON
        