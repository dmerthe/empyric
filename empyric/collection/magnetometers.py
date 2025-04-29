import time
import numpy as np

from empyric.types import Float
from empyric.adapters import Serial
from empyric.instruments import Instrument, measurer


class AlphaLabMR3(Instrument):
    """
    AlphaLab Inc. Magnetoresistive 3 Axis Milligauss Meter

    Accuracy of +/-0.5% of reading; dynamic range of +/-1999.9 milligauss
    """

    name = "AlphaLabMR3"

    supported_adapters = (
        (Serial, {"baud_rate": 115200, "timeout": 1.0, "delay": 1.0}),
    )

    meters = (
        "x component",  # x component of magnetic field
        "y component",
        "z component",
        "magnitude",  # magnitude of the magnetic field
    )

    def _measure_field(self) -> list:
        """Get the magnetic field vector"""

        # clear buffer
        while self.adapter.in_waiting:
            self.adapter.read(bytes=self.adapter.in_waiting, decode=False)
            time.sleep(0.1)

        response = self.query("\x03\x00\x00\x00\x00\x00", bytes=31, decode=False)

        _time = response[:6]
        vector = response[6:12], response[12:18], response[18:24]
        magnitude = response[24:30]
        end_byte = response[30]

        B_values = []

        for component in vector:

            sgn_dec_bits = format(component[1], "b")

            sgn_dec_bits = "0" * (8 - len(sgn_dec_bits)) + sgn_dec_bits

            sign = -1 if sgn_dec_bits[4] == "1" else 1

            decimal_places = sum(
                [int(bit) * 2 ** (2 - i) for i, bit in enumerate(sgn_dec_bits[-3:])]
            )

            int_value = int.from_bytes(component[-2:], byteorder="big")

            numerical_value = sign * int_value * 10 ** (-decimal_places)

            B_values.append(numerical_value)

        return B_values

    @measurer
    def measure_x_component(self) -> Float:
        """Measure the x component of the magnetic field"""
        return self._measure_field()[0]

    @measurer
    def measure_y_component(self) -> Float:
        """Measure the y component of the magnetic field"""
        return self._measure_field()[1]

    @measurer
    def measure_z_component(self) -> Float:
        """Measure the z component of the magnetic field"""
        return self._measure_field()[2]

    @measurer
    def measure_magnitude(self) -> Float:
        """Measure the magnetic field vector and compute the magnitude"""
        return np.linalg.norm(self._measure_field())
