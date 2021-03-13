import importlib
import functools
import time
import warnings
import sys
import re


def chaperone(method):
    """
    Wraps all read and query methods of adapters; monitors and handles communication issues

    :param method: (callable) method to be wrapped
    :return: (callable) wrapped method
    """

    def wrapped_method(self, *args, validator=None, **kwargs):
        """

        :param self: (Adapter) the adapter object whose method is being wrapped
        :param args: any arguments to the method to be wrapped
        :param validator: (callable) function that returns True if its input looks right or False if it does not
        :param kwargs: any keyword arguments for the method to be wrapped
        :return: (str/float/int/bool) instrument response, if valid
        """

        if not self.connected:
            raise ConnectionError(f'Adapter is not connected for instrument at address {self.instrument.address}')

        # Catch communication errors and either try to repeat communication or reset the connection
        if self.reconnects < self.max_reconnects:
            if self.repeats < self.max_repeats:
                try:
                    response = method(self, *args, **kwargs)

                    if validator:
                        valid_response = validator(response)
                    else:
                        valid_response = (response != '') * (response != b'') * (response != float('nan'))

                    if valid_response:
                        self.repeats = 0  # reset repeat counter upon valid communcation
                        self.reconnects = 0  # reset reconnection counter
                        return response
                    else:
                        raise ValueError(f'invalid response, {response}, from {method.__name__} method')

                except BaseException as err:
                    warnings.warn(f'Encountered {err} while trying to read from {self.instrument}')
                    self.repeats += 1
                    return wrapped_method(self, *args, validator=validator, **kwargs)
            else:
                self.disconnect()
                time.sleep(self.delay)
                self.connect()

                self.repeats = 0
                self.reconnects += 1
                return wrapped_method(self, *args, validator=validator, **kwargs)
        else:
            raise ConnectionError(f'Unable to communicate with instrument at address {self.instrument.address}!')

    return wrapped_method


class Adapter:
    """
    Adapters connect instruments defined in an experiment to the appropriate communication backends.
    """

    max_repeats = 3
    max_reconnects = 1

    kwargs = ['baud_rate', 'timeout', 'delay', 'byte_size', 'parity', 'stop_bits', 'close_port_after_each_call',
              'slave_mode', 'byte_order']

    def __init__(self, instrument, **kwargs):

        # general parameters
        self.instrument = instrument

        self.connected = False
        self.repeats = 0
        self.reconnects = 0

        for key, value in kwargs.items():
                self.__setattr__(key, value)

        self.connect()

    def __del__(self):
        # Try to cleanly close communications when adapters are deleted
        if self.connected:
            try:
                self.disconnect()
            except BaseException:
                pass

    # All methods below should be overwritten in child class definitions

    def __repr__(self):
        return 'Adapter'

    def connect(self):
        self.connected = True

    def write(self, message):
        pass

    @chaperone
    def read(self):
        pass

    @chaperone
    def query(self, question):
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
    parity = 'N'
    stop_bits = 1
    termination = b'\n'

    def __repr__(self):
        return 'Serial'

    def connect(self):

        serial = importlib.import_module('serial')
        self.backend = serial.Serial(port=self.instrument.address,
                                     baudrate=self.baud_rate,
                                     stopbits=self.stop_bits,
                                     parity=self.parity,
                                     timeout=self.timeout)

        self.backend.reset_input_buffer()
        self.backend.reset_output_buffer()

        self.connected = True

    def write(self, message):

        if type(message) == bytes:
            self.backend.write(message)
        else:
            self.backend.write(message.encode())

    @chaperone
    def read(self, until=None, bytes=None):

        self.backend.timeout = self.timeout

        if bytes:
            response = self.backend.read(bytes)
        elif until:
            response = self.backend.read_until(until)
        else:
            response = self.backend.read_until(self.termination)

        self.backend.reset_input_buffer()

        return response

    @chaperone
    def query(self, question, until=None, bytes=None):

        self.write(question)
        time.sleep(self.delay)
        self.backend.timeout = self.timeout

        if bytes:
            response = self.backend.read(bytes)
        elif until:
            response = self.backend.read_until(until)
        else:
            response = self.backend.read_until(self.termination)

        self.backend.reset_input_buffer()

        return response

    def disconnect(self):
        self.backend.reset_input_buffer()
        self.backend.reset_output_buffer()
        self.backend.close()

        self.connected = False


class VISA:

    @property
    def timeout(self):
        if self.connected:
            return self.backend.timeout
        else:
            return None

    @timeout.setter
    def timeout(self, timeout):
        if self.connected:
            self.backend.timeout = timeout

    def write(self, message):
        self.backend.write(message)

    @chaperone
    def read(self):
        self.backend.timeout = 1000 * self.timeout
        return self.backend.read()

    @chaperone
    def query(self, question):
        self.backend.write(question)
        time.sleep(self.delay)
        return self.backend.read()

    def disconnect(self):
        self.backend.clear()
        self.backend.close()

        self.connected = False


class VISASerial(VISA, Adapter):
    """
    Handles communications with serial instruments through the PyVISA module and NI-VISA
    """

    baud_rate = 9600
    timeout = 0.1

    def __repr__(self):
        return 'VISASerial'

    def connect(self):

        visa = importlib.import_module('pyvisa')
        manager = visa.ResourceManager()

        self.backend = manager.open_resource(f"ASRL{self.instrument.address}::INSTR",
                                             open_timeout=self.timeout,
                                             baud_rate=self.baud_rate)

        self.connected = True


class VISAGPIB(VISA, Adapter):
    """
    Handles communications with GPIB instruments through the PyVISA module and NI-VISA
    """

    def __repr__(self):
        return 'VISAGPIB'

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


class VISAUSB(VISA, Adapter):
    """
    Handles communications with pure USB instruments through the PyVISA module and NI-VISA
    """

    def __repr__(self):
        return 'VISAUSB'

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

    @property
    def timeout(self):
        return self._timeout

    @timeout.setter
    def timeout(self, timeout):

        if self.connected:
            self.set_timeout(timeout)
            self._timeout = timeout
        else:
            self._timeout = None


    def __repr__(self):
        return 'LinuxGPIB'

    def connect(self):

        self.backend = importlib.import_module('gpib')

        self.descr = self.backend.dev(0, self.instrument.address, 0, 9, 1, 0)  # integer corresponding to the device descriptor

        self.connected = True

    def set_timeout(self, new_timeout):

        if new_timeout is None:
            self.backend.timeout(self.descr, 0)
        else:
            for index, timeout in self.timeouts.items()[1:]:
                if timeout >= new_timeout:
                    self.backend.timeout(self.descr, index)
                    break

        self._timeout = new_timeout

    def write(self, message):
        self.backend.write(self.descr, message)

    @chaperone
    def read(self, read_length=512):
        self.set_timeout(self.timeout)
        return self.backend.read(self.descr, read_length).decode()

    @chaperone
    def query(self, question):
        self.backend.write(question)
        time.sleep(self.delay)
        return self.backend.read()

    def disconnect(self):
        self.backend.clear(self.descr)
        self.backend.close(self.descr)

        self.connected = False


class PrologixGPIBUSB:
    """
    Wraps serial communications with the Prologix GPIB-USB adapter
    """

    @property
    def timeout(self):
        return self.serial_port.timeout

    @timeout.setter
    def timeout(self, timeout):
        self.serial_port.timeout = timeout

    def __init__(self):

        self.devices = []

        serial = importlib.import_module('serial')
        list_ports = importlib.import_module('serial.tools.list_ports')

        port = None
        for comport in list_ports.comports():
            if comport.interface == 'Prologix GPIB-USB Controller':
                port = comport.device

        if port:
            self.serial_port = serial.Serial(port=port, timeout=1)
            # communcations with this controller are a bit slow, so timeout should be set high
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

        self.serial_port.write(proper_message)

    def read(self, address=None):

        if address:
            if address in self.devices:
                self.write(f'addr {address}', to_controller=True)
            else:
                raise AttributeError(f"GPIB device at address {address} is not connected!")

        self.write('read eoi', to_controller=True)

        return self.serial_port.read_until().decode().strip()

    def close(self):
        self.serial_port.close()


class PrologixGPIB(Adapter):
    """
    Handles communications with GPIB instruments using the Prologix GPIB-USB adapter
    """

    delay = 0.2

    # A single Prologix GPIB-USB adapter can address several GPIB instruments,
    # but only one reference to the controller's serial port can exist
    controller = None

    def __repr__(self):
        return 'PrologixGPIB'

    @property
    def timeout(self):
        if self.connected:
            return self.backend.timeout
        else:
            return None

    @timeout.setter
    def timeout(self, timeout):
        if self.connected:
            self.backend.timeout = timeout

    def connect(self):

        if not PrologixGPIB.controller:
            PrologixGPIB.controller = PrologixGPIBUSB()

        PrologixGPIB.controller.devices.append(self.instrument.address)

        self.backend = PrologixGPIB.controller

        self.connected = True

    def write(self, message):
        self.backend.write(message, address=self.instrument.address)

    @chaperone
    def read(self):
        self.backend.timeout = self.timeout
        return self.backend.read(address=self.instrument.address)

    @chaperone
    def query(self, question):
        self.backend.write(question, address=self.instrument.address)
        time.sleep(self.delay)
        return self.backend.read(address=self.instrument.address)

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

    def __repr__(self):
        return 'USBTMC'

    def connect(self):
        usbtmc = importlib.import_module('usbtmc')
        self.backend = usbtmc.Instrument('USB::'+self.instrument.address+'::INSTR')

        self.connected = True

    def write(self, message):
        self.backend.write(message)

    @chaperone
    def read(self):
        return self.backend.read()

    @chaperone
    def query(self, question):
        self.backend.write(question)
        time.sleep(self.delay)
        return self.backend.read()

    def disconnect(self):
        self.backend.close()
        self.connected = False


class Modbus(Adapter):
    """
    Handles communications with modbus serial instruments through the Minimal Modbus package
    """

    # Common defaults
    slave_mode = 'rtu'
    baud_rate = 38400
    timeout = 0.05
    byte_size = 8
    stop_bits = 1
    parity = 'N'
    delay = 0.05

    def __repr__(self):
        return 'Modbus'

    def connect(self):

        minimal_modbus = importlib.import_module('minimalmodbus')
        serial = importlib.import_module('serial')

        # Get port and channel
        port, channel = self.instrument.address.split('::')

        # Handshake with instrument
        self.backend = minimal_modbus.Instrument(port, int(channel), mode=self.slave_mode)
        self.backend.serial.baudrate = self.baud_rate
        self.backend.serial.timeout = self.timeout
        self.backend.serial.bytesize = self.byte_size
        self.backend.serial.parity = self.parity
        self.backend.serial.stopbits = self.stop_bits
        self.backend.close_port_after_each_call = True
        time.sleep(self.delay)

        self.connected = True

    def write(self, register, message, type='uint16', byte_order=0):
        if type == 'uint16':
            self.backend.write_register(register, message)
        elif type == 'float':
            self.backend.write_float(register, message, byteorder=byte_order)
        time.sleep(self.delay)

    @chaperone
    def read(self, register, type='uint16', byte_order=0):
        self.backend.serial.timeout = self.timeout

        if type == 'uint16':
            return self.backend.read_register(register)
        elif type == 'float':
            return self.backend.read_float(register, byteorder=byte_order)

    def disconnect(self):
        if not self.backend.close_port_after_each_call:
            self.backend.serial.close()
        self.connected = False


class Phidget(Adapter):

    delay = 0.2
    timeout = 5

    def __repr__(self):
        return 'Phidget'

    def connect(self):

        address_parts = self.instrument.address.split('::')
        address_parts = [int(part) for part in address_parts]

        serial_number = address_parts[0]

        self.PhidgetException = importlib.import_module("Phidget22.PhidgetException").PhidgetException

        self.backend = self.instrument.device_class()

        self.backend.setDeviceSerialNumber(serial_number)

        if len(address_parts) == 2:
            self.backend.setChannel(address_parts[1])
        if len(address_parts) == 3:
            self.backend.setHubPort(address_parts[1])
            self.backend.setChannel(address_parts[2])



        self.backend.openWaitForAttachment(1000*self.timeout)

        self.connected = True

    @chaperone
    def get(self, parameter):

        try:
            return self.backend.__getattribute__('get'+parameter)()
        except Phidget.Exception:
            return float('nan')

    def set(self, parameter, value):
        set_method = self.backend.__getattribute__('set'+parameter)(value)

    def disconnect(self):
        self.backend.close()
        self.connected = True
