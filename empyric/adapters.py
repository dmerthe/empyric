import importlib
import socket
import time
import re
from threading import Lock

import numpy as np

from empyric.tools import read_from_socket, write_to_socket


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
                "Adapter is not connected for instrument "
                f"at address {self.instrument.address}"
            )

        self.lock.acquire()

        # Catch communication errors and either try to repeat communication
        # or reset the connection

        reconnects = 0

        while reconnects < self.max_reconnects:

            if not self.connected:
                print("Reconnecting...")
                time.sleep(self.delay)
                self.connect()
                reconnects += 1

            attempts = 0

            while attempts < self.max_attempts:
                try:
                    response = method(self, *args, **kwargs)

                    if validator and not validator(response):
                        if hasattr(response, "__len__") and len(response) > 100:
                            response = str(response[:50]) + "..." + str(response[-50:])

                        raise ValueError(
                            f"invalid response, {response}, "
                            f"from {method.__name__} method"
                        )

                    elif attempts > 0 or reconnects > 0:
                        print("Resolved")

                    self.lock.release()
                    return response

                except BaseException as err:
                    print(
                        f"Encountered {err} while trying "
                        f"to talk to {self.instrument.name}"
                        "\nRetrying..."
                    )
                    attempts += 1

            # getting here means attempts have maxed out;
            # disconnect adapter and potentially reconnect on next iteration
            self.disconnect()

        # Getting here means that both attempts and reconnects have been maxed out
        self.lock.release()
        raise AdapterError(f"Unable to communicate with {self.instrument.name}!")

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

    kwargs = []

    # Library used by adapter; overwritten in children classes.
    lib = "python"

    # If upon instantiation no valid library is found for adapter, raise
    # AdapterError with the following message; overwritten in children classes.
    no_lib_msg = "no valid library found for adapter; " "check library installation"

    delay = 0.1  # delay between successive communication attempts

    def __init__(self, instrument, **kwargs):
        if self.lib is None:
            # determined by class attribute `lib`
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

        # This lock is used by the chaperone wrapper function to prevent
        # cross-talk from different threads. Each time an adapter's write, read
        # or query methods is called, the lock is acquired and then released
        # when the transaction is complete.
        self.lock = Lock()

    def __del__(self):
        # Try to cleanly close communications when adapters are deleted
        if hasattr(self, "connected") and self.connected:
            try:
                self.disconnect()
            except BaseException as err:
                print(f"Error while disconnecting {self.instrument.name}:", err)
                pass

    # All methods below should be overwritten in child class definitions

    def __repr__(self):
        return "Adapter"

    def connect(self):
        """
        Establishes communications with the instrument through the appropriate
        backend.
        """
        self.connected = True

    @chaperone
    def write(self, *args, validator=None, **kwargs):
        """
        Write a command.

        :param args: any arguments for the write method
        :param validator: (callable) function that returns True if its input
                          looks right or False if it does not
        :param kwargs: any keyword arguments for the write method

        :return: (str) literal 'Success' if write operation is successful
        """

        if hasattr(self, "_write"):
            return self._write(*args, **kwargs)
        else:
            raise AttributeError(self.__name__ + " adapter has no _write method")

    @chaperone
    def read(self, *args, validator=None, **kwargs):
        """
        Read an awaiting message.

        :param args: any arguments for the read method
        :param validator: (callable) function that returns True if its input
                          looks right or False if it does not
        :param kwargs: any keyword arguments for the read method

        :return: instrument response
        """

        if hasattr(self, "_read"):
            return self._read(*args, **kwargs)
        else:
            raise AttributeError(self.__name__ + " adapter has no _read method")

    @chaperone
    def query(self, *args, validator=None, **kwargs):
        """
        Submit a query.

        :param args: any arguments for the query method
        :param validator: (callable) function that returns True if its input
                          looks right or False if it does not
        :param kwargs: any keyword arguments for the query method

        :return: instrument response
        """

        if hasattr(self, "_query"):
            return self._query(*args, **kwargs)
        else:
            raise AttributeError(self.__name__ + " adapter has no _query method")

    def disconnect(self):
        """
        Close communication port/channel.

        Every ``disconnect`` method should set the ``connected`` attribute to
        ``False`` in order for the ``chaperone`` wrapper to work correctly.
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
    parity = "N"
    stop_bits = 1
    read_termination = "\n"
    write_termination = "\r"

    kwargs = [
        "baud_rate",
        "timeout",
        "delay",
        "byte_size",
        "parity",
        "stop_bits",
    ]

    # Get serial library
    if importlib.util.find_spec("pyvisa"):
        lib = "pyvisa"
    elif importlib.util.find_spec("serial"):
        lib = "pyserial"
    else:
        lib = None

    no_lib_msg = (
        "No serial library was found! " "Please install either PySerial or PyVISA."
    )

    def connect(self):
        # First try connecting with PyVISA
        if self.lib == "pyvisa":

            if "COM" in self.instrument.address:

                com_port = int(re.search("\d+", self.instrument.address)[0])

                print(
                    "PyVISA is the serial communications backend; reformatting "
                    f"PySerial style address '{self.instrument.address}' to "
                    f"'ASRL{com_port}::INSTR'"
                )

                self.instrument.address = f"ASRL{com_port}::INSTR"

            pyvisa = importlib.import_module("pyvisa")

            self.backend = pyvisa.ResourceManager().open_resource(
                self.instrument.address,
                baud_rate=self.baud_rate,
                stop_bits=pyvisa.constants.StopBits(int(self.stop_bits * 10)),
                parity={
                    "N": pyvisa.constants.Parity(0),  # none
                    "O": pyvisa.constants.Parity(1),  # odd
                    "E": pyvisa.constants.Parity(2),  # even
                    "M": pyvisa.constants.Parity(3),  # mark
                    "S": pyvisa.constants.Parity(4),  # space
                }[self.parity],
                timeout=self.timeout,
                write_termination=self.write_termination,
                read_termination=self.read_termination,
            )

        # Then try connecting with PySerial
        elif self.lib == "pyserial":
            if "ASRL" in self.instrument.address:

                com_port = int(re.search("\d+", self.instrument.address)[0])

                print(
                    f"PySerial is the serial communications backend; reformatting "
                    f"PyVISA style address '{self.instrument.address}' to "
                    f"'COM{com_port}'"
                )

                self.instrument.address = f"COM{com_port}"

            serial = importlib.import_module("serial")

            self.backend = serial.Serial(
                port=self.instrument.address,
                baudrate=self.baud_rate,
                stopbits=self.stop_bits,
                parity=self.parity,
                timeout=self.timeout,
            )

        else:
            raise AdapterError(f"invalid library specification, {self.lib}")

        self.connected = True

    def _write(self, message):
        if self.lib == "pyvisa":
            self.backend.write(message)
        elif self.lib == "pyserial":
            self.backend.write((message + self.write_termination).encode())

        return "Success"

    def _read(self, bytes=None, until=None, decode=True):
        if self.lib == "pyvisa":
            if bytes:
                response = self.backend.read_bytes(bytes)
            else:
                return self.backend.read_raw()  # decoded below

        elif self.lib == "pyserial":
            if bytes:
                response = self.backend.read(bytes)
            elif until:
                response = self.backend.read_until(until)
            else:
                response = self.backend.read_until(self.read_termination.encode())

        else:
            response = b""

        if decode:
            response = response.decode().strip()

        return response

    def _query(self, question, bytes=None, until=None, decode=True):
        self._write(question)
        time.sleep(self.delay)
        return self._read(bytes=bytes, until=until, decode=decode)

    def disconnect(self):
        if self.lib == "pyvisa":
            IOerror = importlib.import_module("pyvisa").errors.VisaIOError

            try:
                self.backend.clear()
            except IOerror:
                pass

        elif self.lib == "pyserial":
            self.backend.reset_input_buffer()
            self.backend.reset_output_buffer()

        self.backend.close()

        self.connected = False

    def __repr__(self):
        return "Serial"

    @classmethod
    def list(cls):
        """
        List all connected serial devices

        :param verbose: (bool) if True, list of devices will be printed
                        (defaults to True).

        :return: (list of str) List of connected serial devices
        """

        if cls.lib == "pyvisa":
            pyvisa = importlib.import_module("pyvisa")
            resource_manager = pyvisa.ResourceManager()

            devices = resource_manager.list_resources()

        elif cls.lib == "pyserial":
            list_ports = importlib.import_module("serial.tools.list_ports").comports

            devices = [port.device for port in list_ports()]

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

        input("Press enter when the instrument is disconnected")

        other_devices = Serial.list()

        input("Press enter when the instrument is connected")

        all_devices = Serial.list()

        try:
            instrument_address = [
                device for device in all_devices if device not in other_devices
            ][0]

            print(f"Address: {instrument_address}\n")

        except IndexError:
            print("Instrument not found!\n")

        again = "y" in input("Try again? [y/n]").lower()
        if again:
            Serial.locate()


class GPIB(Adapter):
    """
    Handles communications with GPIB instruments through either PyVISA,
    LinuxGPIB (if OS is Linux) for most GPIB-USB controllers (defaults to
    PyVISA, if installed). For Prologix GPIB-USB adapter units, this adapter
    uses PySerial to facilitate communications.
    """

    # Enumerated timeout values (in seconds) allowed by the Linux-GPIB backend
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
        17: 1000,
    }

    kwargs = ["prologix_address"]

    prologix_address = None
    prologix_controllers = {}

    delay = 0.05
    _timeout = None

    # Get GPIB library
    if importlib.util.find_spec("pyvisa"):
        lib = "pyvisa"
    elif importlib.util.find_spec("gpib_ctypes"):
        lib = "linux-gpib"
    else:
        if importlib.util.find_spec("serial"):
            lib = "prologix-gpib"

    no_lib_msg = (
        "No valid library found for GPIB adapters!"
        "Please install PyVISA (with GPIB drivers), Linux-GPIB, or"
        "use a Prologix GPIB-USB or GPIB-ETHERNET adapter "
        "(requires PySerial)"
    )

    def __init__(self, instrument, **kwargs):
        super().__init__(instrument, **kwargs)
        self._descr = None

    @property
    def timeout(self):
        return self._timeout

    @timeout.setter
    def timeout(self, timeout):
        if self.connected:
            if self.lib == "pyvisa" or self.lib == "prologix-gpib":
                # pyvisa records timeouts in milliseconds
                if timeout is None:
                    self.backend.timeout = None
                else:
                    self.backend.timeout = timeout * 1000
                self._timeout = timeout
            elif self.lib == "linux-gpib":
                self._timeout = self._linux_gpib_set_timeout(timeout)
        else:
            self._timeout = None

    def connect(self):
        if self.prologix_address is not None:
            self.lib = "prologix-gpib"

        if self.lib == "pyvisa":
            visa = importlib.import_module("pyvisa")

            manager = visa.ResourceManager()

            full_address = None
            for address in manager.list_resources():
                instrument_address = str(self.instrument.address)

                address_format = "GPIB[0-9]::" + instrument_address + "::INSTR"

                address_match = re.match(address_format, address)

                if address_match:
                    full_address = address

            if full_address:
                self.backend = manager.open_resource(full_address)
            else:
                AdapterError(
                    "GPIB device at address " f"{self.instrument.address} not found!"
                )

        elif self.lib == "linux-gpib":
            self.backend = importlib.import_module("gpib")

            self._descr = self.backend.dev(0, self.instrument.address, 0, 9, 1, 0)

        elif self.lib == "prologix-gpib":
            if self.prologix_address is None:
                raise AdapterError(
                    "trying to connect to Prologix GPIB adapter but no address "
                    "was provided (prologix_address argument was not set); "
                    "must be either an IP address (for Prologix GPIB-LAN) or "
                    "serial port (for Prologix GPIB-USB)"
                )

            if self.prologix_address in GPIB.prologix_controllers:
                self.backend = GPIB.prologix_controllers[self.prologix_address]
            else:
                if re.match("\d+\.\d+\.\d+\.\d+", self.prologix_address):
                    self.backend = PrologixGPIBLAN(self.prologix_address)
                else:
                    self.backend = PrologixGPIBUSB(self.prologix_address)

                GPIB.prologix_controllers[self.prologix_address] = self.backend

            if self.instrument.address not in self.backend.devices:
                self.backend.devices.append(self.instrument.address)

        else:
            raise AdapterError(
                f"invalid library specification; options are 'pyvisa', "
                f"'linux-gpib' or 'prologix-gpib'. If using a Prologix GPIB "
                "adapter, its 'prologix address' argument must be specified"
            )

        self.connected = True

    def _write(self, message):
        if self.lib == "pyvisa":
            self.backend.write(message)
        elif self.lib == "linux-gpib":
            self.backend.write(self._descr, message)
        elif self.lib == "prologix-gpib":
            self.backend.write(message, address=self.instrument.address)

        return "Success"

    def _read(self, bytes=1024):
        if self.lib == "pyvisa":
            return self.backend.read()
        elif self.lib == "linux-gpib":
            return self.backend.read(self._descr, bytes).decode()
        elif self.lib == "prologix-gpib":
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
        if self.lib == "pyvisa":
            self.backend.clear()
            self.backend.close()
        elif self.lib == "linux-gpib":
            self.backend.clear(self._descr)
            self.backend.close(self._descr)
        elif self.lib == "prologix-gpib":
            # clear the instrument buffers
            self.backend.write(
                "clr", to_controller=True, address=self.instrument.address
            )

            # return instrument to local control
            self.backend.write("loc", to_controller=True)

            # unlink device from controller
            self.backend.devices.remove(self.instrument.address)

            # if no more devices are connected to the controller, close it
            if len(self.backend.devices) == 0:
                self.backend.close()
                GPIB.prologix_controllers.pop(self.prologix_address)

        self.connected = False

    def __repr__(self):
        return "GPIB"


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

    def __init__(self, port):
        try:
            serial = importlib.import_module("serial")
        except ImportError:
            raise AdapterError(
                "Please install the PySerial library "
                "to connect a Prologix GPIB-USB adapter."
            )

        self.serial_port = serial.Serial(port=port, timeout=1)

        # set adapter to "controller" mode
        self.write("mode 1", to_controller=True)

        # instruments talk only when requested to
        self.write("auto 0", to_controller=True)

        # set timeout to 0.5 seconds
        self.write("read_tmo_ms 500", to_controller=True)

        # Do not append CR or LF to messages
        self.write("eos 3", to_controller=True)

        # Assert EOI with last byte to indicate end of data
        self.write("eoi 1", to_controller=True)

        # Append CR to responses from instruments to indicate message
        # termination
        self.write("eot_char 13", to_controller=True)
        self.write("eot_enable 1", to_controller=True)

        self.address = None
        self.devices = []

    def write(self, message, to_controller=False, address=None):
        if address and address != self.address:
            self.write(f"addr {address}", to_controller=True)
            self.address = address

            if address not in self.devices:
                self.devices.append(address)

        proper_message = message.encode() + b"\r"

        if to_controller:
            proper_message = b"++" + proper_message

        self.serial_port.write(proper_message)

        return "Success"

    def read(self, from_controller=False, address=None):
        if address and address != self.address:
            self.write(f"addr {address}", to_controller=True)
            self.address = address

            if address not in self.devices:
                self.devices.append(address)

        if not from_controller:
            self.write(f"read eoi", to_controller=True)

        response = self.serial_port.read_until(b"\r").decode().strip()

        return response

    def close(self):
        self.serial_port.close()


class PrologixGPIBLAN:
    """
    Wraps serial communications with the Prologix GPIB-ETHERNET adapter unit.

    The IP address of the adapter unit can be found with Prologix's Netfinder
    utility and GPIB configuration can be modified with Prologix's GPIB
    Configurator.
    """

    @property
    def timeout(self):
        return self.socket.gettimeout()

    @timeout.setter
    def timeout(self, timeout):
        self.socket.settimeout(timeout)

    def __init__(self, ip_address):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self.socket.connect((ip_address, 1234))

        self.socket.settimeout(1)

        # set adapter to "controller" mode
        self.write("mode 1", to_controller=True)

        # instruments talk only when requested to
        self.write("auto 0", to_controller=True)

        # set timeout to 0.5 seconds
        self.write("read_tmo_ms 500", to_controller=True)

        # Do not append CR or LF to messages
        self.write("eos 3", to_controller=True)

        # Assert EOI with last byte to indicate end of data
        self.write("eoi 1", to_controller=True)

        # Append CR to responses from instruments to indicate message
        # termination
        self.write("eot_char 13", to_controller=True)
        self.write("eot_enable 1", to_controller=True)

        self.devices = []
        self.address = None

    def write(self, message, to_controller=False, address=None):
        if address and address != self.address:
            self.write(f"addr {address}", to_controller=True)
            self.address = address

            if address not in self.devices:
                self.devices.append(address)

        if to_controller:
            message = "++" + message

        write_to_socket(self.socket, message)

        return "Success"

    def read(self, from_controller=False, address=None):
        if address and address != self.address:
            self.write(f"addr {address}", to_controller=True)
            self.address = address

            if address not in self.devices:
                self.devices.append(address)

        if not from_controller:
            self.write(f"read eoi", to_controller=True)

        return read_from_socket(self.socket)

    def close(self):
        self.socket.shutdown(socket.SHUT_RDWR)
        self.socket.close()


class USB(Adapter):
    """
    Handles communications with pure USB instruments through PyVISA or USBTMC.
    """

    # Get USB library
    if importlib.util.find_spec("pyvisa"):
        lib = "pyvisa"
    elif importlib.util.find_spec("usbtmc"):
        lib = "usbtmc"
    else:
        lib = None

    no_lib_msg = "No USB library was found! " "Please install either PyVISA or USBTMC."

    _timeout = 0.5

    @property
    def timeout(self):
        return self._timeout

    @timeout.setter
    def timeout(self, timeout):
        if self.backend is not None:
            if self.lib == "usbtmc":
                self.backend.timeout = timeout
            elif self.lib == "pyvisa":
                self.backend.timeout = 1000 * timeout

        self._timeout = timeout

    def connect(self):
        serial_number = str(self.instrument.address)

        if self.lib == "pyvisa":
            visa = importlib.import_module("pyvisa")

            manager = visa.ResourceManager()

            for address in manager.list_resources():
                if serial_number in address:
                    self.backend = manager.open_resource(
                        address, open_timeout=1000 * self.timeout
                    )

                    # PyVISA timeout is in milliseconds
                    self.backend.timeout = 1000 * self.timeout

        elif self.lib == "usbtmc":
            usbtmc = importlib.import_module("usbtmc")

            self.backend = usbtmc.Instrument("USB::" + serial_number + "::INSTR")

            self.backend.timeout = self.timeout

        else:
            raise AdapterError(f"invalid library specification, {self.lib}")

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
        return "USB"


class Socket(Adapter):
    """
    Handles communications between sockets using Python's built-in socket module
    """

    family = socket.AF_INET
    type = socket.SOCK_STREAM

    ip_address = None
    port = None

    read_termination = "\r"
    write_termination = "\r"
    timeout = 1

    kwargs = ["read_termination", "write_termination", "timeout"]

    def connect(self):
        if self.connected:
            self.disconnect()

        self.backend = socket.socket(self.family, self.type)

        self.backend.settimeout(self.timeout)

        address = self.instrument.address
        remote_ip_address, remote_port = address.split("::")

        self.backend.connect((remote_ip_address, int(remote_port)))

        self.connected = True

    def _write(self, message):
        write_to_socket(
            self.backend,
            message,
            termination=self.write_termination,
            timeout=self.timeout,
        )

        return "Success"

    def _read(self, **kwargs):
        termination = kwargs.pop("termination", self.read_termination)
        timeout = kwargs.pop("timeout", self.timeout)

        return read_from_socket(
            self.backend, termination=termination, timeout=timeout, **kwargs
        )

    def _query(self, question, **kwargs):
        self._write(question)
        return self._read(**kwargs)

    def disconnect(self):
        # Clear out any unread messages

        try:
            unread = self._read(decode=False, nbytes=np.inf, timeout=1)
            while unread:
                unread = self._read(decode=False, nbytes=np.inf, timeout=1)
        except ConnectionError:
            pass

        self.backend.shutdown(socket.SHUT_RDWR)
        self.backend.close()

        self.connected = False

    def __repr__(self):
        return "Socket"


class ModbusSerial(Adapter):
    """
    (TO BE REMOVED)

    Handles communications with modbus serial instruments through the
    Minimal ModbusSerial package
    """

    # Common defaults
    slave_mode = "rtu"
    baud_rate = 38400
    timeout = 0.05
    byte_size = 8
    stop_bits = 1
    parity = "N"
    delay = 0.05

    kwargs = ["close_port_after_each_call", "slave_mode", "byte_order"]

    # For traffic control of modbus adapters using the same serial ports
    adapters = {}

    _busy = False

    # Get Minimal Modbus library
    if importlib.util.find_spec("minimalmodbus"):
        lib = "minimalmodbus"
    else:
        lib = None

    no_lib_msg = (
        "No ModbusSerial library was found! " "Please install the minimalmodbus library"
    )

    @property
    def busy(self):
        return bool(
            sum([adapter._busy for adapter in ModbusSerial.adapters.get(self.port, [])])
        )

    @busy.setter
    def busy(self, busy):
        self._busy = busy

    def __repr__(self):
        return "ModbusSerial"

    def connect(self):
        minimal_modbus = importlib.import_module("minimalmodbus")

        # Get port and channel
        self.port, self.channel = self.instrument.address.split("::")

        if self.port in ModbusSerial.adapters:
            ModbusSerial.adapters[self.port].append(self)
        else:
            ModbusSerial.adapters[self.port] = [self]

        # Handshake with instrument
        self.backend = minimal_modbus.Instrument(
            self.port, int(self.channel), mode=self.slave_mode
        )

        self.backend.serial.baudrate = self.baud_rate
        self.backend.serial.timeout = self.timeout
        self.backend.serial.bytesize = self.byte_size
        self.backend.serial.parity = self.parity
        self.backend.serial.stopbits = self.stop_bits
        self.backend.close_port_after_each_call = True
        time.sleep(self.delay)

        self.connected = True

    def _write(self, register, message, dtype="uint16", byte_order=0):
        if dtype == "uint16":
            self.backend.write_register(register, message)
        elif dtype == "float":
            self.backend.write_float(register, message, byteorder=byte_order)
        time.sleep(self.delay)

        return "Success"

    def _read(self, register, dtype="uint16", byte_order=0):
        self.backend.serial.timeout = self.timeout

        if dtype == "uint16":
            return self.backend.read_register(register)
        elif dtype == "float":
            return self.backend.read_float(register, byteorder=byte_order)

    def disconnect(self):
        if not self.backend.close_port_after_each_call:
            self.backend.serial.close()

        self.connected = False

    @staticmethod
    def locate():
        return Serial.locate()


class Modbus(Adapter):
    """
    Handles communication with instruments via the Modbus communication
    protocol, over either TCP, UDP, or serial ports, using PyModbus.
    """

    kwargs = (
        "slave id",
        "byte order",
        "word order",
        "baud rate",
        "timeout",
        "byte size",
        "stop bits",
        "parity",
        "delay",
        "protocol",
    )

    slave_id = 0
    # Byte and word order is either little-endian (<) or big-endian (>)
    byte_order = ">"
    word_order = ">"

    types = [
        "8bit_uint",
        "16bit_uint",
        "32bit_uint",
        "64bit_uint",
        "8bit_int",
        "16bit_int",
        "32bit_int",
        "64bit_int",
        "16bit_float",
        "32bit_float",
        "64bit_float",
    ]

    baud_rate = 19200
    timeout = 0.05
    byte_size = 8
    stop_bits = 1
    parity = "N"
    delay = 0.05

    protocol = None

    # This dict contains all active Modbus serial adapters. When a new adapter
    # is initialized with the same com port as an existing one, it uses the
    # same Modbus client object as its backend (they are differentiated by
    # their slave IDs).
    _serial_adapters = {}

    # Locate PyModbus library
    if importlib.util.find_spec("pymodbus"):
        lib = "pymodbus"
    else:
        lib = None

    @property
    def busy(self):
        if self.protocol == "Serial":
            return bool(
                sum(
                    [
                        adapter._busy
                        for adapter in Modbus._serial_adapters.get(self.port, [])
                    ]
                )
            )
        else:
            return self._busy

    @busy.setter
    def busy(self, busy):
        self._busy = busy

    def connect(self):
        client = importlib.import_module(".client", package="pymodbus")

        # Get port (Serial) or address & port (TCP)
        address = self.instrument.address.split("::")

        if re.match("\d+\.\d+\.\d+\.\d+", address[0]):
            if str(self.protocol).upper() == "UDP":
                # Modbus UDP
                self.protocol = "UDP"

                if len(address) == 1:
                    address.append(502)  # standard Modbus UDP port (fascinating that it's the same as TCP)
                self.backend = client.ModbusUdpClient(host=address[0], port=int(address[1]))

                self.backend.connect()
            else:
                # Modbus TCP
                self.protocol = "TCP"

                if len(address) == 1:
                    address.append(502)  # standard Modbus TCP port

                self.backend = client.ModbusTcpClient(host=address[0], port=int(address[1]))

                self.backend.connect()
        else:
            # Modbus Serial
            self.protocol = "Serial"

            if len(address) == 1:
                # assume slave id is zero if not specified
                port, slave_id = address[0], 0

            else:
                port, slave_id = address

            if port in Modbus._serial_adapters:
                Modbus._serial_adapters[port].append(self)

                # use existing backend
                self.backend = Modbus._serial_adapters[port].backend

            else:
                Modbus._serial_adapters[port] = [self]

                self.backend = client.ModbusSerialClient(
                    address=port,
                    baudrate=self.baud_rate,
                    bytesize=self.byte_size,
                    parity=self.parity,
                    stopbits=self.stop_bits,
                )

                self.backend.connect()

            self.slave_id = slave_id

        # Get data reading/writing utility classes
        payload_module = importlib.import_module(".payload", package="pymodbus")

        # Utility for encoding data
        self._builder_cls = payload_module.BinaryPayloadBuilder

        # Utility for decoding data
        self._decoder_cls = payload_module.BinaryPayloadDecoder

        self.connected = True

    def _write(self, func_code, address, values, _type=None):
        """
        Write values to coils (func_code = 5 [single] or 15 [multiple]) or
        holding registers (func_code = 6 [single] or 16 [multiple]).

        The Modbus data type for decoding registers is specified by the `_type`
        argument. Valid values for `_type` are listed in the `_types` attribute.
        """

        values = np.array([values]).flatten()

        if func_code not in [5, 15, 6, 16]:
            raise ValueError(f"invalid Modbus function code {func_code}")

        if _type and _type not in self.types:
            raise TypeError(
                "invalid _type argument; must be one of:\n" + ", ".join(self.types)
            )

        if "5" in str(func_code):
            # Write coils

            bool_values = [bool(value) for value in values]

            response = self.backend.write_coils(
                address, bool_values, slave=self.slave_id
            )

            if response.function_code == 15:
                return "Success"
            else:
                raise AdapterError(
                    f"error writing to coil(s) on {self.instrument.name}"
                )

        else:
            # Write registers

            if _type is None:
                _type = "16bit_uint"

            builder = self._builder_cls(
                byteorder=self.byte_order, wordorder=self.word_order
            )

            for value in values:
                builder.__getattribute__("add_" + _type)(value)

            register_values = builder.to_registers()

            response = self.backend.write_registers(
                address, register_values, slave=self.slave_id
            )

            if response.function_code == 16:
                return "Success"
            else:
                raise AdapterError(
                    f"error writing to register(s) on {self.instrument.name} "
                    "for writing coils/registers"
                )

    def _read(self, func_code, address, count=1, _type=None):
        """
        Read from coils (func_code = 1), discrete inputs (func_code = 2),
        holding registers (func_code = 3), or input registers (func_code = 4).

        A single data unit is read by specifying the function code
        (`func_code`) and address; the data can be converted to the desired
        data type (`_type` = `int` or `float`). Multiple sequential addresses
        are read by specifying the count.
        """

        if _type and _type not in self.types:
            raise TypeError(
                "invalid _type argument; must be one of:\n" ", ".join(self.types)
            )

        # Enumerate modbus read functions
        read_functions = {
            1: self.backend.read_coils,
            2: self.backend.read_discrete_inputs,
            3: self.backend.read_holding_registers,
            4: self.backend.read_input_registers,
        }

        if func_code in [1, 2]:
            # Read coils or discrete inputs

            response = read_functions[func_code](
                address, count=count, slave=self.slave_id
            ).bits

            bits = [bool(bit) for bit in response][:count]

            if len(bits) == 1:
                return bits[0]
            else:
                return bits

        elif func_code in [3, 4]:
            # Read holding registers or input registers

            registers = read_functions[func_code](
                address, count=count, slave=self.slave_id
            ).registers

            decoder = self._decoder_cls.fromRegisters(
                registers, byteorder=self.byte_order, wordorder=self.word_order
            )

            n_values = int(16 * count / (int(_type.split("bit")[0])))

            values = [
                decoder.__getattribute__("decode_" + _type)() for _ in range(n_values)
            ]

            if len(values) == 1:
                return values[0]
            else:
                return values

        else:
            # Invalid function code
            raise ValueError(
                f"invalid Modbus function code {func_code} for "
                "reading coils/registers"
            )

    def _query(self, *args, **kwargs):
        """Alias of `_read` method"""
        return self._read(*args, **kwargs)

    def disconnect(self):
        self.backend.close()

        self.connected = False


class Phidget(Adapter):
    """
    Handles communications with Phidget devices
    """

    delay = 0.2
    timeout = 5

    if importlib.util.find_spec("Phidget22"):
        lib = "phidget"
    else:
        lib = None

    no_lib_msg = (
        "Phidget library was not found! " "Please install (pip[3] install Phidget22)."
    )

    def __repr__(self):
        return "Phidget"

    def connect(self):
        address_parts = self.instrument.address.split("::")
        address_parts = [int(part) for part in address_parts]

        serial_number = address_parts[0]

        self.PhidgetException = importlib.import_module(
            "Phidget22.PhidgetException"
        ).PhidgetException

        self.backend = self.instrument.device_class()

        self.backend.setDeviceSerialNumber(serial_number)

        if len(address_parts) == 2:
            self.backend.setChannel(address_parts[1])
        if len(address_parts) == 3:
            self.backend.setHubPort(address_parts[1])
            self.backend.setChannel(address_parts[2])

        self.backend.openWaitForAttachment(1000 * self.timeout)

        self.connected = True

    def _write(self, parameter, value):
        self.backend.__getattribute__("set" + parameter)(value)
        return "Success"

    def _query(self, parameter):
        return self.backend.__getattribute__("get" + parameter)()

    def disconnect(self):
        self.backend.close()
        self.connected = False


supported = {
    key: value
    for key, value in vars().items()
    if type(value) is type and issubclass(value, Adapter)
}

kwargs = []
for cls in supported.values():
    for kwarg in cls.kwargs:
        kwargs.append(kwarg)
