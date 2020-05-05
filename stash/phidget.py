import importlib
from tempyral_dev.stash.basics import *

class TCReader(Instrument, PhidgetDevice):

    name = 'TCReader1101'

    knobs = ('type',)

    meters = ('temperature',)

    def __init__(self, address, backend='phidget'):

        self.address = address

        self.connect()

        self.knob_values = {'type':'K'}

    def set_type(self, type):

        types = importlib.import_module('Phidget22.ThermocoupleType')

        type_dict = {
            'K': types.ThermocoupleType.THERMOCOUPLE_TYPE_K,
            'J': types.ThermocoupleType.THERMOCOUPLE_TYPE_J,
            'T': types.ThermocoupleType.THERMOCOUPLE_TYPE_T,
            'E': types.ThermocoupleType.THERMOCOUPLE_TYPE_E,
        }

        self.connection.setThermocoupleType(type_dict[type])

        self.knob_values['type'] = type

    def measure_temperature(self):

        return self.connection.getTemperature()







