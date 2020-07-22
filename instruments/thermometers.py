import importlib
import numpy as np
from mercury.instruments.basics import *

class TCReader(Instrument):

    name = 'TCReader1101'

    knobs = ('type',)

    meters = ('temperature',)

    def __init__(self, address):

        ts = importlib.import_module('Phidget22.Devices.TemperatureSensor')
        self.PhidgetException = importlib.import_module("Phidget22.PhidgetException").PhidgetException

        self.device_class = ts.TemperatureSensor

        self.address = address
        self.backend = 'phidget'

        self.connect()

        self.knob_values = {'type': 'K'}

    def set_type(self, type_):

        types = importlib.import_module('Phidget22.ThermocoupleType')

        type_dict = {
            'K': types.ThermocoupleType.THERMOCOUPLE_TYPE_K,
            'J': types.ThermocoupleType.THERMOCOUPLE_TYPE_J,
            'T': types.ThermocoupleType.THERMOCOUPLE_TYPE_T,
            'E': types.ThermocoupleType.THERMOCOUPLE_TYPE_E,
        }

        self.connection.setThermocoupleType(type_dict[type_])

        self.knob_values['type'] = type_

    def measure_temperature(self):
        attempts = 5

        for i in range(attempts):
            try:
                return self.connection.getTemperature()
            except self.PhidgetException:
                tiempo.sleep(0.1)

        return -273.15  # if measurement fails








