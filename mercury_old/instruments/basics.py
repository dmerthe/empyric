import numpy as np
import datetime
import os
import importlib
from tkinter.filedialog import askopenfilename

from mercury.utilities import tiempo
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

    supported_backends = ['serial', 'visa', 'usb', 'linux-gpib', 'me-api', 'phidget', 'twilio']

    def measure(self, meter, sample_number=1):
        """
        Measure the value of a variable associated with this instrument

        :param meter: (string) name of the variable to be measured
        :return: (float/string) measured value of the variable
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

    def set(self, knob, value, ramp_time=0.0):
        """
        Set the value of a variable associated with this instrument

        :param knob: (string) name of variable to be set
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
            start_time = tiempo.time()
            elapsed_time = 0.0

            while elapsed_time < ramp_time:

                current_value = start_value + (value - start_value)*elapsed_time/ramp_time
                set_method(current_value)
                tiempo.sleep(0.5)

                elapsed_time = tiempo.time() - start_time

        set_method(value)

    def connect(self):

        if self.backend == 'serial':
            serial = importlib.import_module('serial')
            self.connection = serial.Serial(port=self.address, baudrate=self.baudrate, timeout=self.delay)
            self.name = self.name + f"-{self.address}"

        elif self.backend == 'visa':
            visa = importlib.import_module('visa')
            resource_manager = visa.ResourceManager()
            self.connection = resource_manager.open_resource(self.address)
            self.name = self.name + f"-GPIB{self.address.split('::')[1]}"

        elif self.backend == 'usb':
            usb = importlib.import_module('usbtmc')
            self.connection = usb.Instrument(self.address)

        elif self.backend == 'linux-gpib':
            linux = importlib.import_module('linux')
            self.connection = linux.Gpib(name=0, pad=self.address)
            self.name = self.name + f"-GPIB{self.address.split('/')[-1]}"

        elif self.backend == 'me-api':

            # get list of ME APIs
            instr_mod_path = importlib.import_module('instruments').__file__
            instr_apis = [path.split('.')[0] for path in os.listdir(os.path.dirname(instr_mod_path)) if '.py' in path]

            supported = False

            for api in instr_apis:

                try:
                    api_module = importlib.import_module(api)
                except BaseException:  # if anything goes wrong, skip it
                    continue

                if self.name in api_module.__dict__:

                    supported = True

                    instr_class = api_module.__dict__[self.name]

                    backend_supported = False
                    for backend in instr_class.supported_backends:
                        try:
                            self.connection = instr_class(self.address, backend=backend)
                            backend_supported = True
                            break
                        except BaseException as error:
                            print(f'Tried connecting with {backend} backend, but got error: {error}')

                    if not backend_supported:
                        raise ConnectionError(f"Unable to find suitable backend for {self.name} at {self.address}!")

                    # # Override measure and set methods with with those from the ME API
                    # method_list = [meth for meth in dir(self.connection) if callable(getattr(self.connection, meth))]
                    #
                    # for method in method_list:
                    #     if 'measure_' in method or 'set_' in method:
                    #         self.__setattr__(method, self.connection.__getattribute__(method))

            if not supported:
                raise ConnectionError(f"{self.name} is not supported by the ME APIs")

        elif self.backend == 'phidget':

            try:
                address = self.address
            except AttributeError:
                raise (ConnectionError('Device address has not been specified!'))

            if self.backend not in self.supported_backends:
                raise ConnectionError(f'Backend {self.backend} is not supported!')

            address_parts = address.split('-')

            serial_number = int(address_parts[0])
            port_numbers = [int(value) for value in address_parts[1:]]

            try:
                device_class = self.device_class
            except AttributeError:
                raise (ConnectionError('Phidget device class has not been specified!'))

            if len(port_numbers) == 1:  # TC reader connected directly by USB to PC
                self.connection = device_class()
                self.connection.setDeviceSerialNumber(serial_number)
                self.connection.setChannel(port_numbers[0])
                self.connection.openWaitForAttachment(5000)
                self.name = self.name + f"-{address}"

            elif len(port_numbers) == 2:  # TC reader connected to PC via VINT hub
                self.connection = device_class()
                self.connection.setDeviceSerialNumber(serial_number)
                self.connection.setHubPort(port_numbers[0])
                self.connection.setChannel(port_numbers[1])
                self.connection.openWaitForAttachment(5000)
                self.name = self.name + f"-{address}"

            else:  # It's possible to daisy-chain hubs and other Phidget devices, but is not implemented here
                raise ConnectionError('Support for daisy-chained Phidget devices not supported!')

        elif self.backend == 'twilio':

            try:
                phone_number = self.phone_number
            except AttributeError:
                raise (ConnectionError('Device address has not been specified!'))

            Client = importlib.import_module('twilio.rest').Client

            with open(askopenfilename(title='Select Twilio Credentials'), 'rb') as credentials_file:
                credentials = yaml.load(credentials_file)
                account_sid = credentials['sid']
                auth_token = credentials['token']
                self.from_number = credentials['number']

            self.to_number = phone_number

            self.client = Client(account_sid, auth_token)

        else:
            raise ConnectionError(f"Backend {self.backend} not supported!")

    def disconnect(self):

        try:
            self.connection.close()
        except AttributeError:
            self.connection.disconnect()

    def write(self, message):

        if self.backend == 'serial':
            padded_message = '\r%s\r\n' % message
            self.connection.write(padded_message.encode())

        if self.backend in ['visa', 'usb', 'linux-gpib', 'me-api']:
            self.connection.write(message)

        if self.backend == 'twilio':
            self.client.messages.create(
                to=self.to_number,
                from_=self.from_number,
                body=message
            )

    def read(self):

        if self.backend == 'serial':
            return self.connection.read(100).decode().strip()

        if self.backend in ['visa', 'usb', 'linux-gpib', 'me-api']:
            return self.connection.read()

        if self.backend == 'twillio':
            incoming_messages = self.client.messages.list(from_=self.to_number, to=self.from_number, limit=1)

            if len(incoming_messages) > 0:
                return incoming_messages[-1].body, incoming_messages[-1].date_sent
            else:
                return '', datetime.datetime.fromtimestamp(0)

    def query(self, question, delay=None):

        if self.backend == 'me-api':
            return self.connection.query(question)

        self.write(question)

        if delay:
            tiempo.sleep(delay)
        if 'delay' in self.__dict__:
            tiempo.sleep(self.delay)

        return self.read()


class HenonMachine(Instrument):
    """
    Simulation of an instrument based on the 'test.csv' file in the utopya directory.
    It has two knobs and two meters, useful for testing functionality of the utopya module
    in the absence of real instruments.
    """

    supported_backends = ['chaos']
    default_backend = 'chaos'

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


class NoiseGenerator(Instrument):
    """
    Artificial instrument for testing; contains 2 meters (X in, Y in) and 4 knobs (X out, Y out, sigma X, sigma Y)
    Meter X (X = 1 or 2) return the value of knob X with gaussian noise of standard deviation sigma X
    """

    supported_backends = ['noise']
    default_backend = 'noise'

    name = 'Noise Generator'

    knobs = ('X in', 'Y in', 'sigma X', 'sigma Y')

    meters = ('X out', 'Y out')

    def __init__(self, address=None, backend=None):

        self.knob_values = {'X in': 0, 'Y in': 0, 'sigma X': 0.1, 'sigma Y': 0.1}

    def set_X_in(self, X):
        self.knob_values['X in'] = X

    def set_Y_in(self, Y):
        self.knob_values['Y in'] = Y

    def set_sigma_X(self, sigma):
        self.knob_values['sigma X'] = sigma

    def set_sigma_Y(self, sigma):
        self.knob_values['sigma Y'] = sigma

    def measure_X_out(self):
        return self.knob_values['X in'] + self.knob_values['sigma X']*np.random.randn()

    def measure_Y_out(self):
        return self.knob_values['Y in'] + self.knob_values['sigma Y']*np.random.randn()

    def disconnect(self):
        return