import importlib
import time
import numpy as np

from empyric.adapters import *
from empyric.collection.instrument import Instrument

class Phidget1101(Instrument):
    """
    Phidgets 4x TC reader
    Many instrumet methods (setX, getY, etc.) are mapped by the adapter from the Phidgets device class
    """

    name = 'Phidget1101'

    supported_adapters = (
        (Phidget, {}),
    )

    # Available knobs
    knobs = ('type',)

    # Available meters
    meters = ('temperature',)

    device_class = importlib.import_module('Phidget22.Devices.TemperatureSensor').TemperatureSensor

    def set_type(self, type_):

        types = importlib.import_module('Phidget22.ThermocoupleType')

        type_dict = {
            'K': types.ThermocoupleType.THERMOCOUPLE_TYPE_K,
            'J': types.ThermocoupleType.THERMOCOUPLE_TYPE_J,
            'T': types.ThermocoupleType.THERMOCOUPLE_TYPE_T,
            'E': types.ThermocoupleType.THERMOCOUPLE_TYPE_E,
        }

        self.adapter.set('ThermocoupleType', type_dict[type_])

        self.knob_values['type'] = type_

    def measure_temperature(self):

        return self.adapter.get('Temperature')
