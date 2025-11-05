import re

from empyric.types import Toggle, ON, OFF, Integer, Float
from empyric.adapters import Serial
from empyric.collection.instrument import Instrument, setter, getter, measurer


class BRAX3000(Instrument):
    """
    BRAX 3000 series pressure gauge controller and meter
    """

    name = "BRAX3000"

    supported_adapters = (
        (Serial, {"baud_rate": 19200, "read_termination": "\r", "timeout": 1}),
    )

    knobs = (
        "ig state",
        "filament",
    )

    presets = {"filament": 1, "ig_state": "ON"}

    meters = (
        "cg1 pressure",
        "cg2 pressure",
        "ig pressure",
    )

    @setter
    def set_ig_state(self, state: Toggle):
        number = self.filament

        if state == ON:
            self.write(f"#IG{number} ON<CR>")
        if state == OFF:
            self.write(f"#IG{number} OFF<CR>")

        self.read()  # discard the response

    @getter
    def get_ig_state(self) -> Toggle:
        response = self.query("#IGS<CR>")

        if "ON" in response:
            return ON
        elif "OFF" in response:
            return OFF

    @setter
    def set_filament(self, number: Integer):
        pass

    @measurer
    def measure_cg1_pressure(self) -> Float:
        return float(self.query("#RDCG1<CR>")[4:-4])

    @measurer
    def measure_cg2_pressure(self) -> Float:
        return float(self.query("#RDCG2<CR>")[4:-4])

    @measurer
    def measure_ig_pressure(self) -> Float:
        def validator(response):
            match = re.search(r"\d\.\d+E-?\d\d", response)
            return bool(match)

        response = self.query("#RDIG<CR>", validator=validator)

        return float(re.findall(r"\d\.\d+E-?\d\d", response)[0])


class KJLSPARC(Instrument):
    """
    Kurt J Lesker cold cathode gauge controller
    """

    name = "KJLSPARC"

    supported_adapters = (
        (Serial, {"baud_rate": 115200, "read_termination": "\r", "timeout": 1.0}),
    )

    meters = ("pressure",)

    @measurer
    def measure_pressure(self) -> Float:

        response = self.query("vac?")

        if response[4:] == "ERROR":
            return np.nan
        else:
            return float(response[4:])
