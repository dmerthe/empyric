import importlib
import time
import re


def chaperone(method):
    """
    Wraps all write, read and query methods of the adapters; monitors and handles communication issues

    :param method: (callable) method to be wrapped
    :return: (callable) wrapped method
    """

    def wrapped_method(self, *args, validator=None, **kwargs):

        if not self.connected:
            raise ConnectionError(f'Adapter is not connected for instrument at address {self.instrument.address}')

        while self.busy:  # wait for turn to talk to the instrument
            time.sleep(0.05)

        self.busy = True  # block other methods from talking to the instrument

        # Catch communication errors and either try to repeat communication or reset the connection
        attempts = 0
        reconnects = 0

        while reconnects <= self.max_reconnects:
            while attempts < self.max_attempts:

                try:

                    response = method(self, *args, **kwargs)

                    if validator:
                        valid_response = validator(response)
                    else:
                        valid_response = (response != '') * (response != float('nan')) * (response is not None)

                    if not valid_response:
                        raise ValueError(f'invalid response, {response}, from {method.__name__} method')
                    elif attempts > 0 or reconnects > 0:
                        print('Resolved')

                    self.busy = False
                    return response

                except BaseException as err:
                    print(f'Encountered {err} while trying to talk to {self.instrument.name}')
                    print('Trying again...')
                    attempts += 1

            # repeats have maxed out, so try reconnecting with the instrument
            print('Reconnecting...')
            self.disconnect()
            time.sleep(self.delay)
            self.connect()

            attempts = 0
            reconnects += 1

        # Getting here means that both repeats and reconnects have been maxed out
        raise ConnectionError(f'Unable to communicate with {self.instrument.name}!')

    wrapped_method.__doc__ = method.__doc__  # keep method doc string

    return wrapped_method


class Adapter:
    """
    Adapters connect instruments to the appropriate communication backends.
    """

    #: Maximum number of attempts to read from a port/channel, in the event of a communication error
    max_attempts = 3

    #: Maximum number of times to try to reset communications, in the event of a communication error
    max_reconnects = 1

    kwargs = ['baud_rate', 'timeout', 'delay', 'byte_size', 'parity', 'stop_bits', 'close_port_after_each_call',
              'slave_mode', 'byte_order']

    def __init__(self, instrument, **kwargs):

        # general parameters
        self.instrument = instrument
        self.backend = None
        self.connected = False
        self.repeats = 0
        self.reconnects = 0

        for key, value in kwargs.items():
            self.__setattr__(key, value)

        self.connect()

        self.busy = False  # indicator for multithreading

    def __del__(self):
        # Try to cleanly close communications when adapters are deleted
        if self.connected:
            try:
                self.disconnect()
            except BaseException as err:
                print(f'Error while disconnecting {self.instrument.name}:', err)
                pass

    # All methods below should be overwritten in child class definitions

    def __repr__(self):
        return 'Adapter'

    def connect(self):
        """
        Establishes communications with the instrument through the appropriate backend

        :return: None
        """
        self.connected = True

    @chaperone
    def write(self, *args, **kwargs):
        """
        Write a command.

        :param args: any arguments for the write method
        :param validator: (callable) function that returns True if its input looks right or False if it does not
        :param kwargs: any keyword arguments for the write method
        :return: (str/float/int/bool) instrument response, if valid
        """

        if hasattr(self, '_write'):
            return self._write(*args, **kwargs)
        else:
            raise AttributeError(self.__name__ + " adapter has no _write method")

    @chaperone
    def read(self, *args, **kwargs):
        """
        Read an awaiting message.

        :param args: any arguments for the read method
        :param validator: (callable) function that returns True if its input looks right or False if it does not
        :param kwargs: any keyword arguments for the read method
        :return: (str/float/int/bool) instrument response, if valid
        """

        if hasattr(self, '_read'):
            return self._read(*args, **kwargs)
        else:
            raise AttributeError(self.__name__ + " adapter has no _read method")

    @chaperone
    def query(self, *args, **kwargs):
        """
        Submit a query.

        :param args: any arguments for the query method
        :param validator: (callable) function that returns True if its input looks right or False if it does not
        :param kwargs: any keyword arguments for the query method
        :return: (str/float/int/bool) instrument response, if valid
        """

        if hasattr(self, '_query'):
            return self._query(*args, **kwargs)
        else:
            raise AttributeError(self.__name__ + " adapter has no _query method")

    def disconnect(self):
        """
        Close communication port/channel

        :return: None
        """
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
    input_termination = '\n'
    output_termination = '\r'

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

    def _write(self, message):

        self.backend.write((message + self.output_termination).encode())

        return "Success"

    def _read(self, until=None, num_bytes=None, decode=True):

        self.backend.timeout = self.timeout

        if num_bytes:
            response = self.backend.read(num_bytes)
        elif until:
            response = self.backend.read_until(until)
        else:
            response = self.backend.read_until(self.input_termination.encode())

        self.backend.reset_input_buffer()

        if decode:
            return response.decode().strip()
        else:
            return response

    def _query(self, question, until=None, num_bytes=None, decode=True):

        self._write(question)
        time.sleep(self.delay)
        return self._read(until=until, num_bytes=num_bytes, decode=decode)

    def disconnect(self):
        self.backend.reset_input_buffer()
        self.backend.reset_output_buffer()
        self.backend.close()

        self.connected = False

    @staticmethod
    def locate():
        """
        Determine the address of a serial instrument via the "unplug-it-then-plug-it-back-in" method.

        :return: None (address is printed to console)
        """
        list_ports = importlib.import_module('serial.tools.list_ports').comports

        input('Press enter when the instrument is disconnected')
        other_ports = list_ports()
        input('Press enter when the instrument is connected')
        all_ports = list_ports()

        try:
            instrument_address = [port.device for port in all_ports if port not in other_ports][0]
            print(f'Address: {instrument_address}')
            again = 'y' in input('Again? [y/n]').lower()
            if again:
                Serial.locate()
        except IndexError:
            raise ConnectionError('Instrument not found!')


class VISA:
    """
    Base class for VISA adapters; basic communination format is the same for all
    """

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

    def _write(self, message):
        self.backend.write(message)
        return "Success"

    def _read(self):
        self.backend.timeout = 1000 * self.timeout
        return self.backend.read()

    def _query(self, question):
        self._write(question)
        time.sleep(self.delay)
        return self._read()

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

    @staticmethod
    def locate():
        """
        Determine the address of a serial instrument via the "unplug-it-then-plug-it-back-in" method.

        :return: None (address is printed to console)
        """
        pyvisa = importlib.import_module('pyvisa')

        rm = pyvisa.ResourceManager()

        input('Press enter when the instrument is disconnected')
        other_ports = [resource for resource in rm.list_resources_info()
                       if resource.Interface_type == pyvisa.constants.InterfaceType.asrl]
        input('Press enter when the instrument is connected')
        all_ports = [resource for resource in rm.list_resources_info()
                     if resource.Interface_type == pyvisa.constants.InterfaceType.asrl]

        try:
            instrument_address = [port.Resource_name for port in all_ports if port not in other_ports][0]
            print(f'Address: {instrument_address}')
            again = 'y' in input('Again? [y/n]').lower()
            if again:
                Serial.locate()
        except IndexError:
            raise ConnectionError('Instrument not found!')


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
            if re.match('GPIB[0-9]::' + str(self.instrument.address) + '::INSTR', address):
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

    delay = 0.05
    _timeout = None

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

        self.descr = self.backend.dev(0, self.instrument.address, 0, 9, 1,
                                      0)  # integer corresponding to the device descriptor

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

    def _write(self, message):
        self.backend.write(self.descr, message)
        return "Success"

    def _read(self, read_length=512):
        self.set_timeout(self.timeout)
        return self.backend.read(self.descr, read_length).decode()

    def _query(self, question, read_length=512):
        self._write(question)
        time.sleep(self.delay)
        return self._read(read_length=read_length)

    def disconnect(self):
        self.backend.clear(self.descr)
        self.backend.close(self.descr)

        self.connected = False


class PrologixGPIBUSB:
    """
    Wraps serial communications with the Prologix GPIB-USB adapter; used by ``PrologixGPIB`` adapter
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
            if comport.manufacturer == 'Prologix':
                port = comport.device

        if port:
            self.serial_port = serial.Serial(port=port, timeout=1)
            # communications with this controller are a bit slow, so timeout should be set high
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

        return "Success"

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

    def _write(self, message):
        self.backend.write(message, address=self.instrument.address)
        return "Success"

    def _read(self):
        self.backend.timeout = self.timeout
        return self.backend.read(address=self.instrument.address)

    def _query(self, question):
        self._write(question)
        time.sleep(self.delay)
        return self._read()

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
        self.backend = usbtmc.Instrument('USB::' + self.instrument.address + '::INSTR')

        self.connected = True

    def _write(self, message):
        self.backend.write(message)
        return "Success"

    def _read(self):
        return self.backend.read()

    def _query(self, question):
        self._write(question)
        time.sleep(self.delay)
        return self._read()

    def disconnect(self):
        self.backend.close()
        self.connected = False

    @staticmethod
    def locate():
        """
        Determine the address of a serial instrument via the "unplug-it-then-plug-it-back-in" method.

        :return: None (address is printed to console)
        """
        list_addresses = importlib.import_module('usbtmc').list_resources

        input('Press enter when the instrument is disconnected')
        other_addresses = list_addresses()
        input('Press enter when the instrument is connected')
        all_addresses = list_addresses()

        try:
            instrument_address = [address for address in all_addresses if address not in other_addresses][0]
            print(f'Address: {instrument_address}')
            again = 'y' in input('Again? [y/n]').lower()
            if again:
                USBTMC.locate()
        except IndexError:
            raise ConnectionError('Instrument not found!')


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

    adapters = {}  # modbus adapters using the same serial port; for traffic control

    _busy = False

    @property
    def busy(self):
        return bool(sum([adapter._busy for adapter in Modbus.adapters.get(self.port, [])]))

    @busy.setter
    def busy(self, busy):
        self._busy = busy

    def __repr__(self):
        return 'Modbus'

    def connect(self):

        minimal_modbus = importlib.import_module('minimalmodbus')

        # Get port and channel
        self.port, self.channel = self.instrument.address.split('::')

        if self.port in Modbus.adapters:
            Modbus.adapters[self.port].append(self)
        else:
            Modbus.adapters[self.port] = [self]

        # Handshake with instrument
        self.backend = minimal_modbus.Instrument(self.port, int(self.channel), mode=self.slave_mode)
        self.backend.serial.baudrate = self.baud_rate
        self.backend.serial.timeout = self.timeout
        self.backend.serial.bytesize = self.byte_size
        self.backend.serial.parity = self.parity
        self.backend.serial.stopbits = self.stop_bits
        self.backend.close_port_after_each_call = True
        time.sleep(self.delay)

        self.connected = True

    def _write(self, register, message, dtype='uint16', byte_order=0):
        if dtype == 'uint16':
            self.backend.write_register(register, message)
        elif dtype == 'float':
            self.backend.write_float(register, message, byteorder=byte_order)
        time.sleep(self.delay)

        return "Success"

    def _read(self, register, dtype='uint16', byte_order=0):
        self.backend.serial.timeout = self.timeout

        if dtype == 'uint16':
            return self.backend.read_register(register)
        elif dtype == 'float':
            return self.backend.read_float(register, byteorder=byte_order)

    def disconnect(self):
        if not self.backend.close_port_after_each_call:
            self.backend.serial.close()
        self.connected = False

    @staticmethod
    def locate():
        return Serial.locate()


class Phidget(Adapter):
    """
    Handles communications with Phidget devices

    """

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

        self.backend.openWaitForAttachment(1000 * self.timeout)

        self.connected = True
        self.busy = False

    def _write(self, parameter, value):
        self.backend.__getattribute__('set' + parameter)(value)
        return "Success"

    def _query(self, parameter):
        return self.backend.__getattribute__('get' + parameter)()

    def disconnect(self):
        self.backend.close()
        self.connected = True
