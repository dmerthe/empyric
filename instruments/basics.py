import os
import pandas
import numpy as np
import datetime
import time
import importlib
import warnings
from tkinter.filedialog import askopenfilename

from mercury.utilities.timetools import *
from ruamel.yaml import YAML

yaml = YAML()

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

    supported_backends = ['chaos']

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
    Generic base class for handling communication with GPIB instruments.

    """
    supported_backends = ['visa', 'linux-gpib']
    # Default GPIB communication settings
    delay = 0.1
    default_backend = 'visa'

    def connect(self):
        """
        Connect through the GPIB interface. Child class should have address and backend attributes upon calling this method.

        :return: None
        """

        try:
            address = self.address
        except(AttributeError):
            raise (ConnectionError('Device address has not been specified!'))

        if self.backend not in self.supported_backends:
            raise ConnectionError(f'Backend {self.backend} is not supported!')

        if self.backend == 'visa':
            visa = importlib.import_module('visa')
            resource_manager = visa.ResourceManager()
            self.connection = resource_manager.open_resource(address)
            self.name = self.name+f"-GPIB{address.split('::')[1]}"
        elif self.backend == 'linux-gpib':
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
    default_backend = 'visa'

    def connect(self):

        try:
            address = self.address
        except(AttributeError):
            raise (ConnectionError('Device address has not been specified!'))

        if self.backend not in self.supported_backends:
            raise ConnectionError(f'Backend {self.backend} is not supported!')

        if self.backend == 'visa':
            visa = importlib.import_module('visa')
            resource_manager = visa.ResourceManager()
            self.connection = resource_manager.open_resource(address, baud_rate=self.baudrate)
            self.name = self.name + f"-{address}"
        elif self.backend == 'serial':
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
    default_backend = 'phidget'

    def connect(self, kind=None):

        try:
            address = self.address
        except AttributeError:
            raise(ConnectionError('Device address has not been specified!'))

        if self.backend not in self.supported_backends:
            raise ConnectionError(f'Backend {self.backend} is not supported!')

        address_parts = address.split('-')

        serial_number = int(address_parts[0])
        port_numbers = [int(value) for value in address_parts[1:]]

        try:
            device_class = self.device_class
        except AttributeError:
            raise (ConnectionError('Phidget device class has not been specified!'))

        if len(port_numbers) == 1: # TC reader connected directly by USB to PC
            self.connection = device_class()
            self.connection.setDeviceSerialNumber(serial_number)
            self.connection.setChannel(port_numbers[0])
            self.connection.openWaitForAttachment(5000)
            self.name = self.name + f"-{address}"

        elif len(port_numbers) == 2: # TC reader connected to PC via VINT hub
            self.connection = device_class()
            self.connection.setDeviceSerialNumber(serial_number)
            self.connection.setHubPort(port_numbers[0])
            self.connection.setChannel(port_numbers[1])
            self.connection.openWaitForAttachment(5000)
            self.name = self.name + f"-{address}"

        else: # It's possible to daisy-chain hubs and other Phidget devices, but is not implemented here
            raise ConnectionError('Support for daisy-chained Phidget devices not supported!')

    def disconnect(self):

        self.connection.close()


class TwilioDevice():

    supported_backends = ['twilio']
    default_backend = 'twilio'

    def connect(self):

        try:
            phone_number = self.phone_number
        except AttributeError:
            raise(ConnectionError('Device address has not been specified!'))

        if backend != 'twilio':
            raise ConnectionError(f"Backend '{backend}' not  supported!")

        Client = importlib.import_module('twilio.rest').Client

        with open(askopenfilename(title='Select Twilio Credentials'),'rb') as credentials_file:
            credentials = yaml.load(credentials_file)
            account_sid = credentials['sid']
            auth_token = credentials['token']
            self.from_number = credentials['number']

        self.to_number = phone_number

        self.client = Client(account_sid, auth_token)

    def write(self, message):

        self.client.messages.create(
            to=self.to_number,
            from_=self.from_number,
            body=message
        )

    def read(self):
        incoming_messages = self.client.messages.list(from_=self.to_number, to=self.from_number, limit=1)

        if len(incoming_messages) > 0:
            return incoming_messages[-1].body, incoming_messages[-1].date_sent
        else:
            return '', datetime.datetime.fromtimestamp(0)

    def disconnect(self):
        return
