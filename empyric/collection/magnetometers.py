import numpy as np

from empyric.types import Float

from empyric.adapters import Serial
from empyric.instruments import Instrument, measurer


class AlphaLabMR3(Instrument):
    """
    AlphaLab Inc. Magnetoresistive 3 Axis Milligauss Meter

    Accuracy of +/-0.5% of reading; dynamic range of +/-1999.9 milligauss
    """

    name = 'AlphaLabMR3'

    supported_adapters = (
        (
            Serial, {'baud_rate': 115200, 'timeout': 1.0, 'delay': 1.0}
         ),
    )

    meters = (
        'field x',  # x component of magnetic field
        'field y',
        'field z',
        'field norm'  # magnitude of the magnetic field
    )

    def _measure_field(self) -> list:
        """Get """

        self.write('\x03\x00\x00\x00\x00\x00')

        response = self.read(bytes=4000, decode=False)

        fieldx, fieldy, fieldz = response[6:12], response[12:18], response[18:24]

        field_values = []

        for component in (fieldx, fieldy, fieldz):

            sgn_dec_bits = format(component[1], 'b')

            sgn_dec_bits = '0' * (8 - len(sgn_dec_bits)) + sgn_dec_bits

            sign = -1 if sgn_dec_bits[4] == '1' else 1

            decimal_places = sum(
                [int(bit) * 2 ** (2 - i) for i, bit in enumerate(sgn_dec_bits[-3:])]
            )

            int_value = int.from_bytes(component[-2:], byteorder='big')

            numerical_value = sign * int_value * 10 ** (-decimal_places)

            field_values.append(numerical_value)

        return field_values

    @measurer
    def measure_field_x(self) -> Float:
        return self._measure_field()[0]

    @measurer
    def measure_field_y(self) -> Float:
        return self._measure_field()[1]

    @measurer
    def measure_field_z(self) -> Float:
        return self._measure_field()[2]

    @measurer
    def measure_field_norm(self) -> Float:
        return np.linalg.norm(self._measure_field())
