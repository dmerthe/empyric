import importlib
import functools
import time
import warnings
import sys
import re


def chaperone(method):
    """
    Utility function that wraps the read methods of adapters to monitor and handle communication issues

    :param method: (callable) write, read or query method to be wrapped
    :return: (callable) wrapped method
    """

    def wrapped_method(self, *args, **kwargs):

        if not self.connected:
            raise ConnectionError(f'Adapter is not connected for instrument at address {self.instrument.address}')

        # Catch communication errors and either try to repeat communication or reset the connection
        if self.reconnects < self.max_reconnects:
            if self.repeats < self.max_repeats:
                try:
                    result = method(self, *args, **kwargs)

                    if result != 'invalid':
                        self.repeats = 0
                        self.reconnects = 0
                        return result
                except BaseException as err:
                    warnings.warn(f'Encountered {err} during communication with {self} at address {self.instrument.address}')
                    self.repeats += 1
                    return wrapped_method(self, *args, **kwargs)
            else:
                self.disconnect()
                time.sleep(self.delay)
                self.connect()

                self.repeats = 0
                self.reconnects += 1
                return wrapped_method(self, *args, **kwargs)
        else:
            raise ConnectionError(f'Unable to communicate with instrument at address {self.instrument.address}!')

    return wrapped_method


class Adapter:
    """
    Adapters connect instruments defined in an experiment to the appropriate communication backends.
    """

    max_repeats = 3
    max_reconnects = 1

    def __init__(self, instrument, **kwargs):

        # general parameters
        self.instrument = instrument

        for key, value in kwargs:
            self.__setattr__(key, value)

        self.connected = False
        self.repeats = 0
        self.reconnects = 0

        self.connect()

    # All methods below should be overwritten in child class definitions
    def connect(self):
        self.connected = True

    def write(self, message):
        pass

    @chaperone
    def read(self, response_form=None):
        pass

    def query(self, question, response_form=None):
        pass

    def disconnect(self):
        self.connected = False


class Serial(Adapter):
    """
    Handles communications with serial instruments through the PySerial module
    """

    baud_rate = 9600
    timeout = 0.1
    delay = 0.1

    def connect(self):

        serial = importlib.import_module('serial')
        self.backend = serial.Serial(port='COM' + self.instrument.address,
                                     baudrate=self.baud_rate,
                                     timeout=self.timeout)

        self.connected = True

    def write(self, message):
        self.backend.write(message)

    @chaperone
    def read(self, response_form=None):
        response = self.backend.read()

        if response_form:
            if not re.match(response_form, response):
                return 'invalid'

        if response == '':
            return 'invalid'
        else:
            return response

    def query(self, question, response_form=None):
        self.write(question)
        time.sleep(self.delay)
        return self.read(response_form=response_form)

    def disconnect(self):

        self.backend.flushInput()
        self.backend.flushOutput()
        self.backend.close()

        self.connected = False


class VISASerial(Adapter):
    """
    Handles communications with serial instruments through the PyVISA module and NI-VISA
    """

    baud_rate = 9600
    timeout = 0.1

    def connect(self):

        visa = importlib.import_module('pyvisa')
        manager = visa.ResourceManager()

        self.backend = manager.open_resource(f"ASRL{self.instrument.address}::INSTR",
                                             open_timeout=self.timeout,
                                             baud_rate=self.baud_rate)

        self.connected = True

    def write(self, message):
        self.backend.write(message)

    @chaperone
    def read(self, response_form=None):
        response = self.backend.read()

        if response_form:
            if not re.match(response_form, response):
                return 'invalid'

        if response == '':
            return 'invalid'
        else:
            return response

    def query(self, question, response_form=None):
        self.write(question)
        time.sleep(self.delay)
        return self.read(response_form=response_form)

    def disconnect(self):
        self.backend.clear()
        self.backend.close()

        self.connected = False


class VISAGPIB(Adapter):
    """
    Handles communications with GPIB instruments through the PyVISA module and NI-VISA
    """

    timeout = 0.1

    def connect(self):

        visa = importlib.import_module('pyvisa')
        manager = visa.ResourceManager()

        full_address = None
        for address in manager.list_resources():
            if re.match('GPIB[0-9]::'+str(self.instrument.address)+'::INSTR', address):
                full_address = address

        if full_address:
            self.backend = manager.open_resource(full_address, open_timeout=self.timeout)
        else:
            ConnectionError(f'GPIB device at address {self.instrument.address} not found!')

        self.connected = True

    def write(self, message):
        self.backend.write(message)

    @chaperone
    def read(self, response_form=None):
        response = self.backend.read()

        if response_form:
            if not re.match(response_form, response):
                return 'invalid'

        if response == '':
            return 'invalid'
        else:
            return response

    def query(self, question, response_form=None):
        self.write(question)
        time.sleep(self.delay)
        return self.read(response_form=response_form)

    def disconnect(self):
        self.backend.clear()
        self.backend.close()

        self.connected = False


class VISAUSB(Adapter):
    """
    Handles communications with pure USB instruments through the PyVISA module and NI-VISA
    """

    def connect(self):

        visa = importlib.import_module('pyvisa')
        manager = visa.ResourceManager()

        serial_number = str(self.instrument.address)

        for address in manager.list_resources():
            if serial_number in address:
                self.backend = manager.open_resource(address,
                                                     open_timeout=self.timeout)
                self.backend.timeout = self.timeout

        self.connected = True

    def write(self, message):
        self.backend.write(message)

    @chaperone
    def read(self, response_form=None):
        response = self.backend.read()

        if response_form:
            if not re.match(response_form, response):
                return 'invalid'

        if response == '':
            return 'invalid'
        else:
            return response

    def query(self, question, response_form=None):
        self.write(question)
        time.sleep(self.delay)
        return self.read(response_form=response_form)

    def disconnect(self):
        self.backend.clear()
        self.backend.close()

        self.connected = False


class LinuxGPIB(Adapter):
    """
    Handles communications with GPIB instruments through the Linux-GPIB interface
    """

    # Timeout values (in seconds) allowed by the Linux-GPIB backend; I don't know why
    timeouts = {
        0: None,
        1: 10e-6,
        2: 30e-6,
        3: 100e-6,
        4: 300e-6,
        5: 1e-3,
        6: 3e-3,
        7: 10e-3,
        8: 30e-3,
        9: 100e-3,
        10: 300e-3,
        11: 1,
        12: 3,
        13: 10,
        14: 30,
        15: 100,
        16: 300,
        17: 1000
    }

    def connect(self):

        # Match specified timeout to an allowable timeout of at least as long
        for index, timeout in self.timeouts.items():
            if self.timeout is None:
                self.timeout_index = 0
                break
            elif timeout is None:
                continue
            elif timeout >= self.timeout:
                self.timeout_index = index
                break

        self.backend = importlib.import_module('gpib')

        self.descr = self.backend.dev(0, self.instrument.address, 0, self.timeout_index, 1, 0)  # integer corresponding to the device descriptor

        self.connected = True

    def write(self, message):
        self.backend.write(self.descr, message)

    def read(self, response_form=None, read_length=512):
        response = self.backend.read(self.descr, read_length).decode()

        if response_form:
            if not re.match(response_form, response):
                return 'invalid'

        if response == '':
            return 'invalid'
        else:
            return response

    def query(self, question, response_form=None):
        self.write(question)
        time.sleep(self.delay)
        return self.read(response_form=response_form)

    def disconnect(self):
        self.backend.clear(self.descr)
        self.backend.close(self.descr)

        self.connected = False


class PrologixGPIBController:
    """
    Wraps serial communications with the Prologix GPIB-USB adapter
    """

    timeout = 0.1
    delay = 0.1

    def __init__(self, delay=None):

        if delay:
            self.delay = delay

        self.devices = []

        serial = importlib.import_module('serial')
        list_ports = importlib.import_module('serial.tools.list_ports')

        port = None
        for comport in list_ports.comports():
            if comport.interface == 'Prologix GPIB-USB Controller':
                port = comport.device

        if port:
            self.backend = serial.Serial(port=port, timeout=self.timeout)
        else:
            raise ConnectionError(f'Prologix GPIB-USB adapter not found!')

        self.write('rst', to_controller=True)
        print('Resetting Prologix GPIB-USB controller...')
        time.sleep(6)  # controller
        self.write('mode 1', to_controller=True)
        self.write('auto 0', to_controller=True)

    def write(self, message, to_controller=False, address=None):

        if address:
            if address in self.devices:
                self.write(f'addr {address}', to_controller=True)
            else:
                raise AttributeError(f"GPIB device at address {address} is not connected!")

        proper_message = message.encode() + b'\r'

        if to_controller:
            proper_message = b'++' + proper_message

        self.backend.write(proper_message)
        time.sleep(self.delay)

    def read(self, address=None):

        if address:
            if address in self.devices:
                self.write(f'addr {address}', to_controller=True)
            else:
                raise AttributeError(f"GPIB device at address {address} is not connected!")

        self.write('read eoi', to_controller=True)
        return self.backend.read_until().decode().strip()

    def close(self):
        self.backend.close()


class PrologixGPIB(Adapter):
    """
    Handles communications with GPIB instruments using the Prologix GPIB-USB adapter
    """

    delay = 0.1

    # A single Prologix GPIB-USB adapter can address several GPIB instruments,
    # but only one reference to the controller's serial port can exist
    controller = None

    def connect(self):

        if not PrologixGPIB.controller:
            PrologixGPIB.controller = PrologixGPIBController(delay=self.delay)

        PrologixGPIB.controller.devices.append(self.instrument.address)

        self.backend = PrologixGPIB.controller

        self.connected = True

    def write(self, message):
        self.backend.write(message, address=self.instrument.address)

    @chaperone
    def read(self, response_form=None):
        response = self.backend.read(address=self.instrument.address)

        if response_form:
            if not re.match(response_form, response):
                return 'invalid'

        if response == '':
            return 'invalid'
        else:
            return response

    def query(self, question, response_form=None):
        self.write(question)
        return self.read(response_form=response_form)

    def disconnect(self):
        self.backend.write('clr', to_controller=True, address=self.instrument.address)  # clear the instrument buffers
        self.backend.write('loc', to_controller=True)  # return instrument to local control

        self.backend.devices.remove(self.instrument.address)

        if len(self.backend.devices) == 0:
            self.backend.close()
            PrologixGPIB.controller = None

        self.connected = False


class USBTMC(Adapter):
    """
    Handles communications with pure USB instruments through the USBTMC interface
    """

    def connect(self):
        usbtmc = importlib.import_module('usbtmc')
        self.backend = usbtmc.Instrument('USB::'+self.instrument.address+'::INSTR')

        self.connected = True

    def write(self, message):
        self.backend.write(message)

    @chaperone
    def read(self, response_form=None):
        response = self.backend.read()

        if response_form:
            if not re.match(response_form, response):
                return 'invalid'

        if response == '':
            return 'invalid'
        else:
            return response

    def query(self, question, response_form=None):
        self.write(question)
        time.sleep(self.delay)
        return self.read(response_form=response_form)

    def disconnect(self):
        self.backend.close()
        self.connected = False


class Modbus(Adapter):
    """
    Handles communications with modbus serial instruments through the Minimal Modbus package
    """

    def connect(self):

        # Save parameters
        port, channel = self.instrument.address.split('-')

        if not hasattr(self, 'baud_rate'):
            self.baud_rate = 9600

        if not hasattr(self, 'delay'):
            self.delay = 0.05

        # Handshake with instrument
        minimal_modbus = importlib.import_module('minimalmodbus')
        minimal_modbus.CLOSE_PORT_AFTER_EACH_CALL = True

        self.backend = minimal_modbus.Instrument(port, channel)
        self.backend.serial.baudrate = self.baud_rate
        time.sleep(self.delay)

        self.connected = True

    def write(self, register, message):
        self.backend.write_register(register, message)
        time.sleep(self.delay)

    @chaperone
    def read(self, register, response_form=None):

        response = self.backend.read_register(register)

        if response_form:
            if not re.match(response_form, response):
                return 'invalid'

        if response == '':
            return 'invalid'
        else:
            return response

    def query(self, register, question, response_form=None):
        self.write(register, question)
        time.sleep(self.delay)
        return self.read(register, response_form=response_form)

    def disconnect(self):
        self.backend.close()
        self.connected = False


class Phidget(Adapter):

    def connect(self):

        address_parts = self.instrument.address.split('-')

        serial_number = int(address_parts[0])

        self.PhidgetException = importlib.import_module("Phidget22.PhidgetException").PhidgetException

        self.backend = self.instrument.device_class()
        self.backend.setDeviceSerialNumber(serial_number)

        if hasattr(self, 'channel'):
            self.connection.setChannel(self.channel)

        if hasattr(self, 'port'):
            self.connection.setHubPort(self.port)

        self.backend.openWaitForAttachment(5000)

        # map instrument methods based on device class
        for name, method in self.instrument.device_class.__dict__:
            if '_' not in attr:
                if 'get' in attr:
                    self.instrument.__setattr__(name, chaperone(method))
                else:
                    self.instrument.__setattr__(name, method)
