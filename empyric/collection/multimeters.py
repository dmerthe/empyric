import numbers
from empyric.adapters import *
from empyric.collection.instrument import Instrument

class Keithley2110(Instrument):
    """
    Keithley 2110 digital multimeter instrument
    """

    name = "Keithley2110"

    supported_adapters = (
        (VISAUSB, {}),
        (USBTMC, {})
    )

    knobs = (
        'meter'
        'voltage range',
        'current range',
        'temperature mode'
    )

    meters = (
        'voltage',
        'current',
        'temperature'
    )

    def set_voltage_range(self, voltage_range):

        allowed_voltage_ranges = (0.1, 1, 10, 100, 1000)

        if voltage_range in allowed_voltage_ranges:
            self.write('VOLT:RANG %.2e' % voltage_range)
        elif isinstance(voltage_range, numbers.Number):

            # Find nearest encapsulating voltage range
            try:
                nearest = np.argwhere( voltage_range <= np.array(allowed_voltage_ranges) ).flatten()[0]
            except IndexError:
                nearest = -1

            self.set_voltage_range(allowed_voltage_ranges[nearest])

            Warning(f'Given voltage range not an option, setting to {allowed_voltage_ranges[nearest]} V instead')

        elif voltage_range == 'AUTO':
            self.write('VOLT:RANG:AUTO')
        else:
            raise ValueError(f'voltage range choice {voltage_range} not permitted!')

    def set_current_range(self, current_range):

        allowed_current_ranges = (0.01, 0.1, 1, 3, 10)

        if current_range in allowed_current_ranges:
            self.write('CURR:RANG %.2e' % current_range)
        elif isinstance(current_range, numbers.Number):
            # Find nearest encapsulating current range
            try:
                nearest = np.argwhere(current_range <= np.array(allowed_current_ranges)).flatten()[0]
            except IndexError:
                nearest = -1

            self.set_current_range(allowed_current_ranges[nearest])

            Warning(f'Given current range not an option, setting to {allowed_current_ranges[nearest]} A instead')

        elif current_range == 'AUTO':
            self.write('CURR:RANG:AUTO')
        else:
            raise ValueError(f'current range choice {current_range} not permitted!')

    def measure_voltage(self):

        if self.meter != 'voltage':
            self.set_meter('voltage')

        return float(self.query('READ?'))

    def measure_current(self):

        if self.meter != 'current':
            self.set_meter('current')

        return float(self.query('READ?'))

    def measure_temperature(self):

        if self.meter != 'temperature':
            self.set_meter('temperature')

        return float(self.query('READ?'))

    def set_meter(self, meter):

        if meter == 'voltage':
            self.write('FUNC "VOLT"')
        if meter == 'current':
            self.write('FUNC "CURR"')
        if meter == 'temperature':
            self.write('FUNC "TCO"')

