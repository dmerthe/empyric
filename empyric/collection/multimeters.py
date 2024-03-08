import numbers, importlib
import numpy as np
from empyric.adapters import *
from empyric.collection.instrument import *
from empyric.types import Float, String, Integer, Array


class Keithley2110(Instrument):
    """
    Keithley 2110 digital multimeter instrument
    """

    name = "Keithley2110"

    supported_adapters = ((USB, {}),)

    knobs = ("voltage range", "current range")

    meters = ("voltage", "current", "temperature")

    _mode = None

    @property
    def mode(self):
        return self._mode

    @mode.setter
    def mode(self, mode):
        if mode == "voltage":
            self.write('FUNC "VOLT"')
            self._mode = "voltage"
        if mode == "current":
            self.write('FUNC "CURR"')
            self._mode = "current"
        if mode == "temperature":
            self.write('FUNC "TCO"')
            self._mode = "temperature"

    @setter
    def set_voltage_range(self, voltage_range: Float):
        allowed_voltage_ranges = (0, 0.1, 1.0, 10.0, 100.0, 1000.0)

        if voltage_range in allowed_voltage_ranges[1:]:
            self.write("VOLT:RANG %.2e" % voltage_range)
        elif isinstance(voltage_range, numbers.Number):
            # Find nearest encapsulating voltage range
            try:
                nearest = np.argwhere(
                    voltage_range <= np.array(allowed_voltage_ranges)
                ).flatten()[0]
            except IndexError:
                nearest = -1

            self.set_voltage_range(allowed_voltage_ranges[nearest])

            Warning(
                "Given voltage range not an option, "
                f"setting to {allowed_voltage_ranges[nearest]} V instead"
            )

        elif voltage_range == 0.0:
            self.write("VOLT:RANG:AUTO")
        else:
            raise ValueError(f"voltage range choice {voltage_range} not permitted!")

    @setter
    def set_current_range(self, current_range: Float):
        allowed_current_ranges = (0.0, 0.01, 0.1, 1.0, 3.0, 10.0)

        if current_range in allowed_current_ranges:
            self.write("CURR:RANG %.2e" % current_range)
        elif isinstance(current_range, numbers.Number):
            # Find nearest encapsulating current range
            try:
                nearest = np.argwhere(
                    current_range <= np.array(allowed_current_ranges)
                ).flatten()[0]
            except IndexError:
                nearest = -1

            self.set_current_range(allowed_current_ranges[nearest])

            Warning(
                "Given current range not an option, "
                f"setting to {allowed_current_ranges[nearest]} A instead"
            )

        elif current_range == 0.0:
            self.write("CURR:RANG:AUTO")
        else:
            raise ValueError(f"current range choice {current_range} not permitted!")

    @measurer
    def measure_voltage(self) -> Float:
        if self.mode != "voltage":
            self.mode = "voltage"
        return float(self.query("READ?"))

    @measurer
    def measure_current(self) -> Float:
        if self.mode != "current":
            self.mode = "current"
        return float(self.query("READ?"))

    @measurer
    def measure_temperature(self) -> Float:
        if self.mode != "temperature":
            self.mode = "temperature"
        return float(self.query("READ?"))


class Keithley6500(Instrument):
    """
    Multimeter with 6.5 digits and high speed scanning and digitizing
    capabilities.

    For socket communication default port is 5025. If IP address is unknown,
    you can find or set it on the unit's Communication --> LAN menu.

    Uses TSP communication protocol.

    The `range` knob has separate values for the basic measurements (meter =
    'voltage' or 'current') and the digitized measurements (meter = 'fast
    voltages' or 'fast currents'). Be sure to set the desired range after
    switching meter types.
    """

    name = "Keithley6500"

    supported_adapters = (
        (Socket, {"write_termination": "\n", "read_termination": "\n", "timeout": 0.5}),
    )

    knobs = ("meter", "nplc", "range", "sample count", "sample rate", "trigger_source")

    meters = ("voltage", "current", "fast voltages", "fast currents")

    _trig_src = "trigger.EVENT_DISPLAY"
    meter = None

    @setter
    def set_meter(self, meter: String):
        if meter.lower() == "voltage":
            self.write(f"dmm.measure.func = dmm.FUNC_DC_VOLTAGE")
        elif meter.lower() == "current":
            self.write(f"dmm.measure.func = dmm.FUNC_DC_CURRENT")
        elif meter.lower() == "fast voltages":
            self.write(f"dmm.digitize.func = dmm.FUNC_DIGITIZE_VOLTAGE")
        elif meter.lower() == "fast currents":
            self.write(f"dmm.digitize.func = dmm.FUNC_DIGITIZE_CURRENT")
        else:
            raise print(f"Warning: invalid meter {meter} for Keithley6500")
            return self.get_meter()

        return meter.lower()

    @getter
    def get_meter(self) -> String:
        def validator(response):
            return re.match("dmm.FUNC", response)

        meter = self.query("print(dmm.measure.func)", validator=validator)

        if "dmm.FUNC_NONE" in meter:
            meter = self.query("print(dmm.digitize.func)")

            if "dmm.FUNC_NONE" in meter:
                raise ValueError(f"meter is undefined for {self.name}")

        meter_dict = {
            "dmm.FUNC_DC_CURRENT": "current",
            "dmm.FUNC_DC_VOLTAGE": "voltage",
            "dmm.FUNC_DIGITIZE_CURRENT": "fast currents",
            "dmm.FUNC_DIGITIZE_VOLTAGE": "fast voltages",
        }

        if meter in meter_dict:
            return meter_dict[meter]
        else:
            return ""

    @setter
    def set_sample_count(self, count: Integer):
        if "fast" in self.meter:  # pylint: disable=unsupported-membership-test
            self.write(f"dmm.digitize.count = {count}")
        else:
            return 1

    @getter
    def get_sample_count(self) -> Integer:
        if "fast" in self.meter:  # pylint: disable=unsupported-membership-test
            response = self.query("print(dmm.digitize.count)")

            if "nil" in response:
                return 0
            else:
                return int(response)
        else:
            return 1

    @setter
    def set_sample_rate(self, rate: Integer):
        if "fast" in self.meter:  # pylint: disable=unsupported-membership-test
            self.write(f"dmm.digitize.samplerate = {rate}")
        else:
            return 0

    @getter
    def get_sample_rate(self) -> Integer:
        if "fast" in self.meter:  # pylint: disable=unsupported-membership-test
            response = self.query("print(dmm.digitize.samplerate)")

            if "nil" in response:
                return 0
            else:
                return int(response)
        else:
            return 0

    @setter
    def set_nplc(self, nplc: Integer):
        if self.meter in ["voltage", "current"]:
            self.write(f"dmm.measure.nplc = {nplc}")
        else:
            return 0

    @getter
    def get_nplc(self) -> Integer:
        if self.meter in ["voltage", "current"]:
            return int(self.query("print(dmm.measure.nplc)"))
        else:
            return 0

    @setter
    def set_range(self, _range: Float):
        meter = self.get_meter()

        if meter in ["voltage", "current"]:
            if _range == 0.0:
                self.write("dmm.measure.autorange = dmm.ON")
            else:
                self.write(f"dmm.measure.range = {_range}")
        elif meter in ["fast voltages", "fast currents"]:
            self.write("dmm.digitize.range = %.3e" % _range)
        else:
            return self.get_range()

    @getter
    def get_range(self) -> Float:
        meter = self.get_meter()

        if meter in ["voltage", "current"]:
            if self.query("print(dmm.measure.autorange)") == "dmm.ON":
                return 0.0
            else:
                return float(self.query("print(dmm.measure.range)"))

        elif meter in ["fast voltages", "fast currents"]:
            return float(self.query("print(dmm.digitize.range)"))

    @setter
    def set_trigger_source(self, trigger_source: String):
        valid_sources = {
            "front panel": "trigger.EVENT_DISPLAY",
            "front": "trigger.EVENT_DISPLAY",
            "external in": "trigger.EVENT_EXTERNAL",
            "ext": "trigger.EVENT_EXTERNAL",
        }

        if trigger_source.lower() in valid_sources:
            self._trig_src = valid_sources[trigger_source.lower()]
        else:
            raise ValueError(f"invalid trigger source for {self.name}")

    @getter
    def get_trigger_source(self) -> String:
        trigger_sources = {
            "trigger.EVENT_DISPLAY": "front panel",
            "trigger.EVENT_EXTERNAL": "external in",
        }

        return trigger_sources[self._trig_src]

    @measurer
    def measure_current(self) -> Float:
        if self.meter != "current":
            self.set_meter("current")

        return recast(self.query("print(dmm.measure.read())"))

    @measurer
    def measure_voltage(self) -> Float:
        if self.meter != "voltage":
            self.set_meter("voltage")

        return recast(self.query("print(dmm.measure.read())"))

    def _execute_fast_measurements(self):
        if "fast" not in self.meter:  # pylint: disable=unsupported-membership-test
            return

        trigger_src = {
            "front panel": "trigger.EVENT_DISPLAY",
            "external in": "trigger.EVENT_EXTERNAL",
        }[self.get_trigger_source()]

        self.write(
            "trigger.model.setblock(1, trigger.BLOCK_BUFFER_CLEAR, "
            "defbuffer1)\n"
            "trigger.model.setblock(2, trigger.BLOCK_WAIT, "
            f"{trigger_src})\n"
            "trigger.model.setblock(3, trigger.BLOCK_DELAY_CONSTANT, 0)\n"
            "trigger.model.setblock(4, trigger.BLOCK_MEASURE_DIGITIZE, "
            "defbuffer1, dmm.digitize.count)\n"
            "trigger.model.initiate()\n"
        )

        running = True

        running_states = [
            "trigger.STATE_BUILDING",
            "trigger.STATE_RUNNING",
            "trigger.STATE_PAUSED",
            "trigger.STATE_WAITING",
        ]

        failed_states = [
            "trigger.STATE_ABORTING",
            "trigger.STATE_ABORTED",
            "trigger.STATE_FAILED",
        ]

        state = ""

        while running:
            self.write("state, state, block_num = trigger.model.state()")

            state = self.query("print(state)")

            running = state in running_states

            time.sleep(0.25)

        if state in failed_states:
            raise RuntimeError(f'fast measurement failed; trigger state is "{state}"')

        readings = self.query(
            "printbuffer(1, defbuffer1.n, defbuffer1.readings)", nbytes=np.inf
        )

        return np.array([np.float64(reading) for reading in readings.split(", ")])

    @measurer
    def measure_fast_voltages(self) -> Array:
        if self.meter != "fast voltages":
            self.set_meter("fast voltages")

        fast_voltages = self._execute_fast_measurements()

        return fast_voltages

    @measurer
    def measure_fast_currents(self) -> Array:
        if self.meter != "fast currents":
            self.set_meter("fast currents")

        fast_currents = self._execute_fast_measurements()

        return fast_currents


class LabJackU6(Instrument):
    """
    LabJack U6 Multi-function DAQ
    """

    name = "LabJackU6"

    supported_adapters = (
        # custom setup below until I can get serial or modbus comms to work
        (Adapter, {}),
    )

    knobs = (
        "DAC0 ",
        "DAC1",
    )

    meters = (
        "AIN0",
        "AIN1",
        "AIN2",
        "AIN3",
        "device temperature",
        "temperature 0",
        "temperature 1",
        "temperature 2",
        "temperature 3",
    )

    def __init__(self, *args, **kwargs):
        u6 = importlib.import_module("u6")
        self.backend = u6.U6()

        if len(args) == 0 and "address" not in kwargs:
            kwargs["address"] = str(self.backend.serialNumber)

        Instrument.__init__(self, *args, **kwargs)

    def write(self, register, value):
        self.backend.writeRegister(register, value)

    def read(self, register):
        return self.backend.readRegister(register)

    @setter
    def set_DAC0(self, value: Float):
        self.write(5000, value)

    @setter
    def set_DAC1(self, value: Float):
        self.write(5002, value)

    @getter
    def get_DAC0(self) -> Float:
        self.read(5000)

    @getter
    def get_DAC1(self) -> Float:
        self.read(5002)

    @measurer
    def measure_AIN0(self) -> Float:
        return self.read(0)

    @measurer
    def measure_AIN1(self) -> Float:
        return self.read(2)

    @measurer
    def measure_AIN2(self) -> Float:
        return self.read(4)

    @measurer
    def measure_AIN3(self) -> Float:
        return self.read(6)

    @measurer
    def measure_device_temperature(self) -> Float:
        return self.backend.getTemperature() - 273.15

    @measurer
    def measure_temperature_0(self) -> Float:
        return self.read(0) / 37e-6 + self.measure_device_temperature()

    @measurer
    def measure_temperature_1(self) -> Float:
        return self.read(2) / 37e-6 + self.measure_device_temperature()

    @measurer
    def measure_temperature_2(self) -> Float:
        return self.read(4) / 37e-6 + self.measure_device_temperature()

    @measurer
    def measure_temperature_3(self) -> Float:
        return self.read(6) / 37e-6 + self.measure_device_temperature()


class LabJackT7(Instrument):
    """
    LabJack T7/T7-Pro DAQ

    Only reading the default 14 inputs as voltages is currently supported, but
    this may eventually be expanded.
    """

    name = "LabJackT7"

    supported_adapters = ((Modbus, {}),)

    knobs = ("DIO0", "DIO1", "DIO2", "DIO3", "DIO4", "DIO5", "DIO6", "DIO7")

    meters = (
        "AIN0",
        "AIN1",
        "AIN2",
        "AIN3",
        "AIN4",
        "AIN5",
        "AIN6",
        "AIN7",
        "AIN8",
        "AIN9",
        "AIN10",
        "AIN11",
        "AIN12",
        "AIN13",
        "AIN all",
        "device temperature",
        "AIN0TC",
        "AIN1TC",
        "AIN2TC",
        "AIN3TC",
        "AIN4TC",
        "AIN5TC",
        "AIN6TC",
        "AIN7TC",
        "AIN8TC",
        "AIN9TC",
        "AIN10TC",
        "AIN11TC",
        "AIN12TC",
        "AIN13TC",
    )

    def _set_DION(self, n, value: Integer):
        self.write(16, 2000 + n, value, _type="16bit_uint")

    def _get_DION(self, n) -> Integer:
        return self.read(3, 2000 + n, count=1, _type="16bit_uint")

    def _measure_AIN(self, n) -> Float:
        return self.read(3, 2 * n, count=2, _type="32bit_float")
    
    def _measure_AIN_EF_READ_A(self, n) -> Float:
        return self.read(3, 2 * n + 7000, count=2, _type="32bit_float")
<<<<<<< HEAD
=======

    def _measure_AIN_EF_READ_A(self, n) -> Float:
        return self.read(3, 2 * n + 7000, count=2, _type="32bit_float")
>>>>>>> cfd1d3be5d3834c284f5839fb28b6db4d19e3bc0

    @setter
    def set_DIO0(self, value: Integer):
        self._set_DION(0, value)

    @getter
    def get_DIO0(self) -> Integer:
        return self._get_DION(0)

    @setter
    def set_DIO1(self, value: Integer):
        self._set_DION(1, value)

    @getter
    def get_DIO1(self) -> Integer:
        return self._get_DION(1)

    @setter
    def set_DIO2(self, value: Integer):
        self._set_DION(2, value)

    @getter
    def get_DIO2(self) -> Integer:
        return self._get_DION(2)

    @setter
    def set_DIO3(self, value: Integer):
        self._set_DION(3, value)

    @getter
    def get_DIO3(self) -> Integer:
        return self._get_DION(3)

    @setter
    def set_DIO4(self, value: Integer):
        self._set_DION(4, value)

    @getter
    def get_DIO4(self) -> Integer:
        return self._get_DION(4)

    @setter
    def set_DIO5(self, value: Integer):
        self._set_DION(5, value)

    @getter
    def get_DIO5(self) -> Integer:
        return self._get_DION(5)

    @setter
    def set_DIO6(self, value: Integer):
        self._set_DION(6, value)

    @getter
    def get_DIO6(self) -> Integer:
        return self._get_DION(6)

    @setter
    def set_DIO7(self, value: Integer):
        self._set_DION(7, value)

    @getter
    def get_DIO7(self) -> Integer:
        return self._get_DION(7)

    @measurer
    def measure_AIN0(self) -> Float:
        return self._measure_AIN(0)

    @measurer
    def measure_AIN1(self) -> Float:
        return self._measure_AIN(1)

    @measurer
    def measure_AIN2(self) -> Float:
        return self._measure_AIN(2)

    @measurer
    def measure_AIN3(self) -> Float:
        return self._measure_AIN(3)

    @measurer
    def measure_AIN4(self) -> Float:
        return self._measure_AIN(4)

    @measurer
    def measure_AIN5(self) -> Float:
        return self._measure_AIN(5)

    @measurer
    def measure_AIN6(self) -> Float:
        return self._measure_AIN(6)

    @measurer
    def measure_AIN7(self) -> Float:
        return self._measure_AIN(7)

    @measurer
    def measure_AIN8(self) -> Float:
        return self._measure_AIN(8)

    @measurer
    def measure_AIN9(self) -> Float:
        return self._measure_AIN(9)

    @measurer
    def measure_AIN10(self) -> Float:
        return self._measure_AIN(10)

    @measurer
    def measure_AIN11(self) -> Float:
        return self._measure_AIN(11)

    @measurer
    def measure_AIN12(self) -> Float:
        return self._measure_AIN(12)

    @measurer
    def measure_AIN13(self) -> Float:
        return self._measure_AIN(13)

    @measurer
    def measure_AIN_all(self) -> Array:
        """Reads all 14 analog inputs in a single call"""
        return self.read(4, 0, count=2 * 14, _type="32bit_float")

    @measurer
    def measure_device_temperature(self) -> Float:
        """Device temperature in C"""
        return self.read(4, 60052, count=2, _type="32bit_float") - 273.15

    @measurer
    def measure_AIN0TC(self) -> Float:
        return self._measure_AIN_EF_READ_A(0)

    @measurer
    def measure_AIN1TC(self) -> Float:
        return self._measure_AIN_EF_READ_A(1)

    @measurer
    def measure_AIN2TC(self) -> Float:
        return self._measure_AIN_EF_READ_A(2)

    @measurer
    def measure_AIN3TC(self) -> Float:
        return self._measure_AIN_EF_READ_A(3)

    @measurer
    def measure_AIN4TC(self) -> Float:
        return self._measure_AIN_EF_READ_A(4)

    @measurer
    def measure_AIN5TC(self) -> Float:
        return self._measure_AIN_EF_READ_A(5)

    @measurer
    def measure_AIN6TC(self) -> Float:
        return self._measure_AIN_EF_READ_A(6)

    @measurer
    def measure_AIN7TC(self) -> Float:
        return self._measure_AIN_EF_READ_A(7)

    @measurer
    def measure_AIN8TC(self) -> Float:
        return self._measure_AIN_EF_READ_A(8)

    @measurer
    def measure_AIN9TC(self) -> Float:
        return self._measure_AIN_EF_READ_A(9)

    @measurer
    def measure_AIN10TC(self) -> Float:
        return self._measure_AIN_EF_READ_A(10)

    @measurer
    def measure_AIN11TC(self) -> Float:
        return self._measure_AIN_EF_READ_A(11)

    @measurer
    def measure_AIN12TC(self) -> Float:
        return self._measure_AIN_EF_READ_A(12)

    @measurer
    def measure_AIN13TC(self) -> Float:
        return self._measure_AIN_EF_READ_A(13)
