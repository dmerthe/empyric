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

    supported_adapters = ((Serial, {"baud_rate": 57600}),)

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
