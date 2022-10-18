import importlib
import time
import re


def chaperone(method):
    """
    Wraps all write, read and query methods of the adapters; monitors and
    handles communication issues.

    :param method: (callable) method to be wrapped
    :return: (callable) wrapped method
    """

    def wrapped_method(self, *args, validator=None, **kwargs):

        if not self.connected:
            raise AdapterError(
                'Adapter is not connected for instrument '
                f'at address {self.instrument.address}'
            )

        while self.busy:  # wait for turn to talk to the instrument
            time.sleep(0.05)

        self.busy = True  # block other methods from talking to the instrument

        # Catch communication errors and either try to repeat communication
        # or reset the connection
        attempts = 0
        reconnects = 0

        while reconnects <= self.max_reconnects:
            while attempts < self.max_attempts:

                try:

                    response = method(self, *args, **kwargs)

                    if validator and not validator(response):

                        raise ValueError(
                            f'invalid response, {response}, '
                            f'from {method.__name__} method'
                        )

                    elif attempts > 0 or reconnects > 0:
                        print('Resolved')

                    self.busy = False
                    return response

                except BaseException as err:
                    print(
                        f'Encountered {err} while trying '
                        f'to talk to {self.instrument.name}'
                        '\nRetrying...'
                    )
                    attempts += 1

            # repeats have maxed out, so try reconnecting with the instrument
            print('Reconnecting...')
            self.disconnect()
            time.sleep(self.delay)
            self.connect()

            attempts = 0
            reconnects += 1

        # Getting here means that both repeats
        # and reconnects have been maxed out
        raise AdapterError(
            f'Unable to communicate with {self.instrument.name}!'
        )

    wrapped_method.__doc__ = method.__doc__  # keep method doc string

    return wrapped_method


class AdapterError(BaseException):
    pass


class Adapter:
    """
    Base class for all adapters
    """

    #: Maximum number of attempts to read from a port/channel,
    # in the event of a communication error
    max_attempts = 3

    #: Maximum number of times to try to reset communications,
    # in the event of a communication error
    max_reconnects = 1

    kwargs = [
        'baud_rate', 'timeout', 'delay', 'byte_size', 'parity', 'stop_bits',
        'close_port_after_each_call', 'slave_mode', 'byte_order'
    ]

    # Library used by adapter; overwritten in children classes.
    lib = 'python'

    # If upon instantiation no valid library is found for adapter, raise
    # AdapterError with the following message; overwritten in children classes.
    no_lib_msg = 'no valid library found for adapter; ' \
                 'check library installation'

    def __init__(self, instrument, **kwargs):

        if self.lib is None:
            # determined by class attribute `implementation`
            raise AdapterError(self.no_lib_msg)

        # general parameters
        self.instrument = instrument
        self.backend = None
        self.connected = False
        self.repeats = 0
        self.reconnects = 0

        for key, value in kwargs.items():
            self.__setattr__(key, value)

        self.connect()

        self.instrument.adapter = self

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
        Establishes communications with the instrument through the appropriate
        backend.

        :return: None
        """
        self.connected = True

    @chaperone
    def write(self, *args, **kwargs):
        """
        Write a command.

        :param args: any arguments for the write method
        :param validator: (callable) function that returns True if its input
        looks right or False if it does not
        :param kwargs: any keyword arguments for the write method
        :return: (str/float/int/bool) instrument response, if valid
        """

        if hasattr(self, '_write'):
            return self._write(*args, **kwargs)
        else:
            raise AttributeError(
                self.__name__ + " adapter has no _write method")

    @chaperone
    def read(self, *args, **kwargs):
        """
        Read an awaiting message.

        :param args: any arguments for the read method
        :param validator: (callable) function that returns True if its input
        looks right or False if it does not
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
        :param validator: (callable) function that returns True if its input
        looks right or False if it does not
        :param kwargs: any keyword arguments for the query method
        :return: (str/float/int/bool) instrument response, if valid
        """

        if hasattr(self, '_query'):
            return self._query(*args, **kwargs)
        else:
            raise AttributeError(
                self.__name__ + " adapter has no _query method"
            )

    def disconnect(self):
        """
        Close communication port/channel

        :return: None
        """
        self.connected = False


class Serial(Adapter):
    """
    Handles communications with serial instruments through either PyVISA or
    PySerial. If both are installed, it defaults to PyVISA.
    """

    baud_rate = 9600
    timeout = 0.1
    delay = 0.1
    parity = 'N'
    stop_bits = 1
    read_termination = '\n'
    write_termination = '\r'

    # Get serial library
    if importlib.util.find_spec('pyvisa'):
        lib = 'pyvisa'
    elif importlib.util.find_spec('serial'):
        lib = 'pyserial'
    else:
        lib = None

    no_lib_msg = 'No serial library was found! '\
                 'Please install either PySerial or PyVISA.'

    def connect(self):

        # List of errors that gets reported in unable to connect
        errors = []

        # First try connecting with PyVISA
        if self.lib == 'pyvisa':

            pyvisa = importlib.import_module('pyvisa')

            self.backend = pyvisa.open_resource(
                self.instrument.address,
                baud_rate=self.baud_rate,
                stop_bits=self.stop_bits,
                parity=self.parity,
                timeout=self.timeout,
                write_termination=self.write_termination,
                read_terimation=self.read_termination
            )

        # Then try connecting with PySerial
        elif self.lib == 'pyserial':

            serial = importlib.import_module('serial')

            self.backend = serial.Serial(
                port=self.instrument.address,
                baudrate=self.baud_rate,
                stopbits=self.stop_bits,
                parity=self.parity,
                timeout=self.timeout
            )

        if not self.backend:
            raise AdapterError(
                'Unable to initialize a suitable serial adapter backend for'
                f'{self.instrument} at {self.instrument.address};'
                'check you serial configuration.'
            )

        self.connected = True

    def _write(self, message):

        if self.lib == 'pyvisa':
            self.backend.write(message)
        elif self.lib == 'pyserial':
            self.backend.write((message + self.write_termination).encode())

        return "Success"

    def _read(self, bytes=None, until=None, decode=True):

        if self.lib == 'pyvisa':
            if bytes:
                response = self.backend.read_bytes(bytes)
            elif until:
                response = b''
                while until.encode() not in response:
                    response = response + self.backend.read_raw(1)
            else:
                return self.backend.read(decode=False)  # decoded below

        elif self.lib == 'pyserial':
            if bytes:
                response = self.backend.read(bytes)
            elif until:
                response = self.backend.read_until(until)
            else:
                response = self.backend.read_until(
                    self.read_termination.encode()
                )

        else:
            response = b''

        if decode:
            response = response.decode().strip()

        return response

    def _query(self, question, bytes=None, until=None, decode=True):

        self._write(question)
        time.sleep(self.delay)
        return self._read(bytes=bytes, until=until, decode=decode)

    def disconnect(self):

        if self.lib == 'pyvisa':
            self.backend.clear()

        elif self.lib == 'pyserial':
            self.backend.reset_input_buffer()
            self.backend.reset_output_buffer()

        self.backend.close()

        self.connected = False

    def __repr__(self):
        return 'Serial'

    @classmethod
    def list(cls, verbose=True):
        """
        List all connected serial devices

        :param verbose: (bool) if True, list of devices will be printed
        (defaults to True).

        :return: (list of str) List of connected serial devices
        """

        if cls.lib == 'pyvisa':

            pyvisa = importlib.import_module('serial')
            resource_manager = pyvisa.ResourceManager()

            devices = resource_manager.list_resources()

            if verbose:
                print('Connected serial devices (via PyVISA)')
                print('\n'.join(devices))

        elif cls.lib == 'pyserial':

            list_ports = importlib.import_module(
                'serial.tools.list_ports'
            ).comports

            devices = [port.device for port in list_ports()]

            if verbose:
                print('Connected serial devices (via PySerial)')
                print('\n'.join(devices))

        else:
            raise AdapterError(cls.no_lib_msg)

        return devices

    @classmethod
    def locate(cls):
        """
        Determine the address of a serial instrument via the
        "unplug-it-then-plug-it-back-in" method.

        :return: None (address is printed to console)
        """

        input('Press enter when the instrument is disconnected')

        other_devices = Serial.list(verbose=False)

        input('Press enter when the instrument is connected')

        all_devices = Serial.list(verbose=False)

        try:

            instrument_address = [
                device for device in all_devices if device not in other_devices
            ][0]

            print(f'Address: {instrument_address}\n')

        except IndexError:
            print('Instrument not found!\n')

        again = 'y' in input('Try again? [y/n]').lower()
        if again:
            Serial.locate()


class GPIB(Adapter):
    """
    Handles communications with GPIB instruments through either PyVISA, LinuxGPIB (if OS is Linux) for most GPIB-USB
    controllers (defaults to PyVISA, if installed). For Prologix GPIB-USB adapter units, this adapter uses PySerial
    to facilitate communcations.
    """

    # Timeout values (in seconds) allowed by the Linux-GPIB backend; I don't know why
    linux_gpib_timeouts = {
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

    prologix_controller = None

    delay = 0.05
    _timeout = None

    @property
    def timeout(self):
        return self._timeout

    @timeout.setter
    def timeout(self, timeout):

        if self.connected:
            if self.lib == 'pyvisa':
                # pyvisa records timeouts in milliseconds
                self.backend.timeout = timeout * 1000
                self._timeout = timeout
            elif self.lib == 'linux-gpib':
                self._timeout = self._linux_gpib_set_timeout(timeout)
        else:
            self._timeout = None

    def connect(self):

        errors = []

        try:
            visa = importlib.import_module('pyvisa')

            self.lib = 'pyvisa'

            manager = visa.ResourceManager()

            full_address = None
            for address in manager.list_resources():

                instrument_address = str(self.instrument.address)

                address_format = 'GPIB[0-9]::' + instrument_address + '::INSTR'

                address_match = re.match(
                    address_format,
                    address
                )

                if address_match:
                    full_address = address

            if full_address:
                self.backend = manager.open_resource(
                    full_address,
                    open_timeout=self.timeout
                )
            else:
                AdapterError(
                    'GPIB device at address '
                    f'{self.instrument.address} not found!'
                )

        except BaseException as error:
            errors.append(error)
            pass

        try:
            self.backend = importlib.import_module('gpib')

            self.lib = 'linux-gpib'

            self.descr = self.backend.dev(
                0, self.instrument.address, 0, 9, 1, 0
            )

        except BaseException as error:
            errors.append(error)
            pass

        try:

            if not GPIB.prologix_controller:
                GPIB.prologix_controller = PrologixGPIBUSB()

            self.lib = 'prologix-gpib'

            GPIB.prologix_controller.devices.append(self.instrument.address)

            self.backend = GPIB.prologix_controller

        except BaseException as error:
            errors.append(error)
            pass

        if not self.lib:
            raise AdapterError(
                'No GPIB library was found! '
                'For Windows or Mac, please install PyVISA.\n'
                'For Linux please install either PyVISA or LinuxGPIB.\n'
                'Prologix GPIB-USB adapters are also supported '
                'and require either PyVISA or PySerial.'
            )

        if not self.backend:
            raise AdapterError(
                'Unable to initialize GPIB adapter for '
                f'{self.instrument} at address {self.instrument.address}; '
                'the following errors were encountered:\n'
                '\n'.join([str(error) for error in errors])
            )

        self.connected = True

    def _write(self, message):

        if self.lib == 'pyvisa':
            self.backend.write(message)
        elif self.lib == 'linux-gpib':
            self.backend.write(self.descr, message)
        elif self.lib == 'prologix-gpib':
            self.backend.write(message, address=self.instrument.address)

        return "Success"

    def _read(self, bytes=1024):

        if self.lib == 'pyvisa':
            return self.backend.read()
        elif self.lib == 'linux-gpib':
            return self.backend.read(self.descr, bytes).decode()
        elif self.lib == 'prologix-gpib':
            return self.backend.read(address=self.instrument.address)

    def _query(self, question):
        self._write(question)
        time.sleep(self.delay)
        return self._read()

    def _linux_gpib_set_timeout(self, timeout):

        if timeout is None:
            self.backend.timeout(self.descr, 0)
            return None
        else:
            for index, allowed_timeout in self.linux_gpib_timeouts.items()[1:]:
                if allowed_timeout >= timeout:
                    self.backend.timeout(self.descr, index)
                    break

            return allowed_timeout

    def disconnect(self):

        if self.lib == 'pyvisa':
            self.backend.clear()
            self.backend.close()
        elif self.lib == 'linux-gpib':
            self.backend.clear(self.descr)
            self.backend.close(self.descr)
        elif self.lib == 'prologix-gpib':

            # clear the instrument buffers
            self.backend.write('clr', to_controller=True,
                               address=self.instrument.address)

            # return instrument to local control
            self.backend.write('loc', to_controller=True)

            self.backend.devices.remove(self.instrument.address)

            if len(self.backend.devices) == 0:
                self.backend.close()
                GPIB.prologix_controller = None

        self.connected = False

    def __repr__(self):
        return 'GPIB'


class PrologixGPIBUSB:
    """
    Wraps serial communications with the Prologix GPIB-USB adapter unit.
    """

    @property
    def timeout(self):
        return self.serial_port.timeout

    @timeout.setter
    def timeout(self, timeout):
        self.serial_port.timeout = timeout

    def __init__(self):

        self.devices = []

        try:
            serial = importlib.import_module('serial')

        except ImportError:
            raise AdapterError(
                'Please install the PySerial library '
                'to connect a Prologix GPIB-USB adapter.'
            )

        list_ports = importlib.import_module('serial.tools.list_ports')

        port = None
        for comport in list_ports.comports():
            if comport.manufacturer == 'Prologix':
                port = comport.device

        if port:
            self.serial_port = serial.Serial(port=port, timeout=1)
            # communications with this controller are a bit slow
        else:
            raise AdapterError(f'Prologix GPIB-USB adapter not found!')

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
                raise AttributeError(
                    f"GPIB device at address {address} is not connected!"
                )

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
                raise AttributeError(
                    f"GPIB device at address {address} is not connected!"
                )

        self.write('read eoi', to_controller=True)

        return self.serial_port.read_until().decode().strip()

    def close(self):
        self.serial_port.close()


class USB(Adapter):
    """
    Handles communications with pure USB instruments through PyVISA or USBTMC.
    """

    timeout = 0.5

    def connect(self):

        errors = []

        serial_number = str(self.instrument.address)

        try:
            visa = importlib.import_module('pyvisa')

            self.lib = 'pyvisa'

            manager = visa.ResourceManager()

            for address in manager.list_resources():
                if serial_number in address:
                    self.backend = manager.open_resource(
                        address,
                        open_timeout=self.timeout
                    )
                    self.backend.timeout = self.timeout

        except BaseException as error:
            errors.append(error)
            pass

        try:
            usbtmc = importlib.import_module('usbtmc')

            self.lib = 'usbtmc'

            self.backend = usbtmc.Instrument(
                'USB::' + serial_number + '::INSTR'
            )

        except BaseException as error:
            errors.append(error)
            pass

        if not self.lib:
            raise AdapterError(
                'No USB library was found! '
                'Please install either the PyVISA or USBTMC libraries.'
            )

        if not self.backend:
            raise AdapterError(
                'Unable to initialize USB adapter for '
                f'{self.instrument} @ {self.instrument.address}; '
                'the following errors were encountered:\n'
                '\n'.join([str(error) for error in errors])
            )

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

    def __repr__(self):
        return 'USB'


class Modbus(Adapter):
    """
    Handles communications with modbus serial instruments through the
    Minimal Modbus package
    """

    # Common defaults
    slave_mode = 'rtu'
    baud_rate = 38400
    timeout = 0.05
    byte_size = 8
    stop_bits = 1
    parity = 'N'
    delay = 0.05

    # For traffic control of modbus adapters using the same serial ports
    adapters = {}

    _busy = False

    @property
    def busy(self):
        return bool(sum([
            adapter._busy for adapter in Modbus.adapters.get(self.port, [])
        ]))

    @busy.setter
    def busy(self, busy):
        self._busy = busy

    def __repr__(self):
        return 'Modbus'

    def connect(self):

        try:

            minimal_modbus = importlib.import_module('minimalmodbus')

            self.lib = 'minimalmodbus'

        except ImportError:

            raise AdapterError(
                'Modbus adapters require the minimalmodbus library'
            )

        # Get port and channel
        self.port, self.channel = self.instrument.address.split('::')

        if self.port in Modbus.adapters:
            Modbus.adapters[self.port].append(self)
        else:
            Modbus.adapters[self.port] = [self]

        # Handshake with instrument
        self.backend = minimal_modbus.Instrument(
            self.port,
            int(self.channel),
            mode=self.slave_mode
        )

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

        try:
            self.PhidgetException = importlib.import_module(
                "Phidget22.PhidgetException"
            ).PhidgetException
        except ImportError:
            raise AdapterError(
                'Phidget instruments require the Phidget22 library'
            )

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


supported = {key: value for key, value in vars().items()
             if type(value) is type and issubclass(value, Adapter)}
