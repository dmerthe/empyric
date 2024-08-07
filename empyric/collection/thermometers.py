import importlib

from empyric.types import recast, String, Float
from empyric.adapters import Phidget, Serial
from empyric.instruments import Instrument, setter, measurer


class Phidget1101(Instrument):
    """
    Phidgets 4x TC reader
    Many instrument methods (setX, getY, etc.) are mapped by the adapter from
    the Phidgets device class
    """

    name = "Phidget1101"

    supported_adapters = ((Phidget, {}),)

    # Available knobs
    knobs = ("type",)

    # Available meters
    meters = ("temperature",)

    def __init__(self, *args, **kwargs):
        self.device_class = importlib.import_module(
            "Phidget22.Devices.TemperatureSensor"
        ).TemperatureSensor

        Instrument.__init__(self, *args, **kwargs)

    @setter
    def set_type(self, type_: String):
        types = importlib.import_module("Phidget22.ThermocoupleType")

        type_dict = {
            "K": types.ThermocoupleType.THERMOCOUPLE_TYPE_K,
            "J": types.ThermocoupleType.THERMOCOUPLE_TYPE_J,
            "T": types.ThermocoupleType.THERMOCOUPLE_TYPE_T,
            "E": types.ThermocoupleType.THERMOCOUPLE_TYPE_E,
        }

        self.write("ThermocoupleType", type_dict[type_])

    @measurer
    def measure_temperature(self) -> Float:
        return self.query("Temperature")


class WilliamsonPyrometer(Instrument):
    """
    Williamson Pro Series 2-color pyrometer.
    """

    supported_adapters = (
        (
            Serial,
            {
                "read_termination": b"\n\r",
                "write_termination": b"\r\n",
                "baud_rate": 38400,
            },
        ),
    )

    meters = (
        "temperature",
        "unfiltered temperature",
        "signal strength",
    )

    @measurer
    def measure_temperature(self) -> Float:
        # temp returned in F, convert to C
        return (recast(self.query("FT")) - 32) / 1.8

    @measurer
    def measure_unfiltered_temperature(self) -> Float:
        # temp returned in F, convert to C
        return (recast(self.query("UT")) - 32) / 1.8

    @measurer
    def measure_signal_strength(self) -> Float:
        return recast(self.query("SS"))
