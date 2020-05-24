import os
import pandas
import numpy as np
import time
import importlib
import warnings


class ConnectionError(BaseException):
    pass


class MeasurementError(BaseException):
    pass


class SetError(BaseException):
    pass


class Instrument(object):
    """
    Generic base class for any instrument that measures and/or controls some set of variables
    """

    def measure(self, meter, sample_number = 1):
        """

        :param variable: (string) name of the variable to be measured
        :return: (float) measured value of the variable
        """

        try:
            measurement_method = self.__getattribute__('measure_'+meter.replace(' ','_'))
        except AttributeError:
            raise MeasurementError(f"'{meter}' cannot be measured on {self.name}")

        if sample_number == 1:
            measurement = measurement_method()
        else:
            measurement = np.mean([measurement_method() for i in range(sample_number)])

        return measurement

    def set(self, knob, value, ramp_time = 0.0):
        """

        :param variable: (string) name of variable to be set
        :param value: (float/string) value of new variable setting
        :param ramp_time: (float) time in seconds to ramp from starting value to new value
        :return: None
        """

        try:
            set_method = self.__getattribute__('set_'+knob.replace(' ','_'))
        except AttributeError:
            raise SetError(f"'{knob}' cannot be set on {self.name}")

        if value is None:  # A None value passed into this function indicates that no change in setting is to be made
            return

        if ramp_time > 0.0:

            start_value = self.knob_values[knob]
            start_time = time.time()
            elapsed_time = 0.0

            while elapsed_time < ramp_time:

                set_method(start_value + (value - start_value)*elapsed_time/ramp_time)
                time.sleep(0.5)

                elapsed_time = time.time() - start_time

        set_method(value)


class HenonMachine(Instrument):
    """
    Simulation of an instrument based on the 'test.csv' file in the utopya directory.
    It has two knobs and two meters, useful for testing functionality of the utopya module
    in the absence of real instruments.
    """

    name = 'Henon Machine'

    knobs = ('a','b')

    meters = ('x', 'y', 'pseudostep')

    def __init__(self, adress=None, backend=None):
        # address and backend arguments are not used, but put them here to be consistent with all other instruments
        a = 1.4
        b = 0.3
        N = int(1e3)
        self.knob_values = {'a': a, 'b': b, 'N': N}

        x, y = 2*np.random.rand() - 1, 0.5*np.random.rand() - 0.25
        self.step = 0

        self.x_values = [x]
        self.y_values = [y]
        for i in range(N):
            x_new = 1 - a * x ** 2 + y
            y_new = b * x
            x = x_new
            y = y_new
            self.x_values.append(x)
            self.y_values.append(y)

    def disconnect(self):
        return

    def set_a(self, value):
        if self.knob_values['a'] == value:
            return

        a = value
        self.knob_values['a'] = a
        b  = self.knob_values['b']

        x, y = 2*np.random.rand() - 1, 0.5*np.random.rand() - 0.25
        self.step = 0

        self.x_values = [x]
        self.y_values = [y]
        N = int(1e3)
        for i in range(N):
            x_new = 1 - a * x ** 2 + y
            y_new = b * x
            x = x_new
            y = y_new
            self.x_values.append(x)
            self.y_values.append(y)

    def set_b(self, value):
        if self.knob_values['b'] == value:
            return

        a = self.knob_values['a']
        b = value
        self.knob_values['b'] = b

        x, y = 2 * np.random.rand() - 1, 0.5 * np.random.rand() - 0.25
        self.step = 0

        self.x_values = [x]
        self.y_values = [y]
        N = int(1e3)
        for i in range(N):
            x_new = 1 - a * x ** 2 + y
            y_new = b * x
            x = x_new
            y = y_new
            self.x_values.append(x)
            self.y_values.append(y)

    def measure_x(self):

        x = self.x_values[int(0.5*self.step)]

        self.step += 1

        return x

    def measure_y(self):

        y = self.y_values[int(0.5*self.step)]

        self.step += 1

        return y

    def measure_pseudostep(self):

        return int(0.5*self.step) % 10


class GPIBDevice():

    """
    Generic base class for handling communication with GPIB instruments
    """
    supported_backends = ['visa','linux-gpib']
    # Default GPIB communication settings
    delay = 0.1
    backend = 'visa'

    def connect(self, *args):

        if self.backend not in self.supported_backends:
            raise ConnectionError('Specified backend is not supported!')

        if len(args) > 0:
            address = args[0]
        else:
            try:
                address = self.address
            except(AttributeError):
                raise(ConnectionError('Device address has not been specified!'))

        if self.backend == 'visa':
            visa = importlib.import_module('visa')
            resource_manager = visa.ResourceManager()
            self.connection = resource_manager.open_resource(address)
            self.name = self.name+f"-GPIB{address.split('::')[1]}"
        if self.backend == 'linux-gpib':
            linux = importlib.import_module('linux')
            self.connection = linux.Gpib(name=0, pad=address)
            self.name = self.name + f"-GPIB{address.split('/')[-1]}"

    def disconnect(self):

        self.connection.close()

    def write(self, command):

        self.connection.write(command)

    def read(selfs):

        self.connection.read()

    def query(self, question, delay = None):

        if delay:
            return self.connection.query(question, delay=delay)
        else:
            return self.connection.query(question, delay=self.delay)


    def identify(self):

        return self.query('*IDN?')

    def reset(self):

        self.write('*RST')


class SerialDevice():

    """
    Generic base class for handling communication with instruments with the serial (pyserial) backend
    This includes devices that are connected by USB or Serial cable
    """

    # Default serial communication parameters
    supported_backends = ['serial','visa']
    baudrate = 9600
    timeout = 1.0
    delay = 0.1
    backend = 'visa'

    def connect(self, *args):

        if self.backend not in self.supported_backends:
            raise ConnectionError('Specified backend is not supported!')

        if len(args) > 0:
            address = args[0]
        else:
            try:
                address = self.address
            except(AttributeError):
                raise(ConnectionError('Device address has not been specified!'))

        if self.backend == 'visa':
            visa = importlib.import_module('visa')
            self.connection = visa.ResourceManager().open_resource(address)
            self.connection.baudrate = self.baudrate
            self.name = self.name + f"-{address}"
        if self.backend == 'serial':
            serial = importlib.import_module('serial')
            self.connection = serial.Serial(port=address, baudrate=self.baudrate, timeout=self.delay)
            self.name = self.name + f"-{address}"

    def disconnect(self):

        self.connection.close()

    def write(self, command):

        if self.backend == 'serial':
            padded_command = '\r%s\r\n' % command
            self.connection.write(padded_command.encode())
        if self.backend == 'visa':
            self.connection.write(command)

    def read(self):

        if self.backend == 'serial':
            return self.connection.read(100).decode().strip()
        if self.backend == 'visa':
            return self.connection.read()

    def query(self, question):

        self.write(question)
        time.sleep(self.delay)
        result = self.read()
        return result

    def identify(self):

        return self.query('*IDN?')

    def reset(self):

        self.write('*RST')


class PhidgetDevice():

    supported_backends = ['phidget']

    def connect(self, address=None, kind=None):

        if address is None:
            try:
                address = self.address
            except AttributeError:
                raise(ConnectionError('Device address has not been specified!'))

        address_parts = address.split('-')

        serial_number = int(address_parts[0])
        port_numbers = [int(value) for value in address_parts[1:]]

        if kind is None:
            try:
                device_class = self.device_class
            except AttributeError:
                raise (ConnectionError('Phidget device class has not been specified!'))

        if len(port_numbers) == 1: # TC reader connected directly by USB to PC
            self.connection = device_class()
            self.connection.setDeviceSerialNumber(serial_number)
            self.connection.setChannel(port_numbers[0])
            self.connection.open()
            self.name = self.name + f"-{address}"

        elif len(port_numbers) == 2: # TC reader connected to PC via VINT hub
            self.connection = device_class()
            self.connection.setDeviceSerialNumber(serial_number)
            self.connection.setHubPort(port_numbers[0])
            self.connection.setChannel(port_numbers[1])
            self.connection.open()
            self.name = self.name + f"-{address}"

        else: # It's possible to daisy-chain hubs and other Phidget devices, but is not implemented here
            raise ConnectionError('Support for daisy-chained Phidget devices not supported!')

    def disconnect(self):

        self.connection.close()

class ConsoleDevice():

    supported_backends = ['console']

    def connect(self, *args, **kwargs):
        pass

    def write(self, message):

        print(message)

    def query(self, message):

        return input(message)

    def read(self):

        return 'None'

class TwilioDevice():

    supported_backends = ['twilio']

    def connect(self, phone_number):

        Client = importlib.import_module('Client',package='twilio.rest')

        self.client = Client("AC2adbf0c1d8877fd83462fddb044b1ecd", "6c176312ec91dcb732fc96f4214ec499")
        self.phone_number = phone_number

    def write(self, message):

        client.messages.create(
            to=self.phone_number,
            from_="+12064017596",
            body=message
        )

    def read(self):

        return None


