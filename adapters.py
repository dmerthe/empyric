import importlib
import functools
import time
import warnings
import sys
import re

supported_adapters = ['serial', 'gpib', 'usb']


def chaperone(method):
    """
    Utility function that wraps the write, read and query methods of adapters and deals with communication issues

    :param method: (callable) write, read or query method to be wrapped
    :return: (callable) wrapped method
    """

    def wrapped_method(self, *args, **kwargs):

        if not self.connected:
            raise ConnectionError(f'Adapter is not connected for instrument at address {self.address}')

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
                    warnings.warn(f'Encountered {err} during communication with {self} at address {self.address}')
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
            raise ConnectionError(f'Unable to communicate with instrument at address f{self.address}!')

    return wrapped_method


## Adapters ##

class Adapter:
    """
    Adapters connect instruments defined in an experiment to the appropriate communication backends.
    """

    max_repeats = 3
    max_reconnects = 1

    def __init__(self, address, delay=0.1, timeout=0.2, baud_rate=9600):
        # general parameters
        self.address = address
        self.delay = delay
        self.timeout = timeout

        # for serial communications
        self.baud_rate = baud_rate

        self.connected = False
        self.repeats = 0
        self.reconnects = 0

        self.connect()

    def connect(self):  # should be overwritten in children class definitions
        self.backend = Backend(self)
        self.connected = True

    @chaperone
    def write(self, message):
        return self.backend.write(message)

    @chaperone
    def read(self, response_form=None):
        return self.backend.read(response_form=response_form)

    @chaperone
    def query(self, message, response_form=None):
        return self.backend.query(message, response_form=response_form)

    def disconnect(self):
        self.connected = False
        return self.backend.disconnect()

class SerialAdapter(Adapter):
    """
    Adapter handling communications with serial instruments
    """

    available_backends = ['serial', 'visa']

    def connect(self):

        try:
            self.backend = Serial(self)
            return
        except ImportError:
            pass

        try:
            self.backend = VISA(self)
        except ImportError:
            raise ImportError('either pyserial or pyvisa is required for using serial adapters!')


class GPIB(Adapter):
    """
    Adapter handling communications with GPIB instruments
    """

    available_backends = ['visa', 'linux']

    def connect(self):

        if sys.platform in ('win32', 'darwin'):
            try:
                self.backend = VISA(self)
            except ImportError:
                raise ImportError(
                    'the pyvisa module is required for using GPIB adapters on Windows or MacOS platforms!')
        elif sys.platform == 'linux':
            try:
                self.backend = LinuxGPIB(self)
            except ImportError:
                raise ImportError('the linux module is required for using GPIB adapters on Linux platforms!')
        else:
            raise SystemError(f'{sys.platform} operating system type is not supported!')


class USB(Adapter):
    """
    Adapter handling communications with USB (distinct from serial-to-usb) instruments
    """

    def connect(self):

        if sys.platform in ('win32', 'darwin'):
            try:
                self.backend = VISA(self)
            except ImportError:
                raise ImportError(
                    'pyvisa with NI-VISA backend is required for using USB adapters on Windows or MacOS platforms!')
        elif sys.platform == 'linux':
            try:
                self.backend = USBTMC(self)
            except ImportError:
                raise ImportError('the usbtmc module is required for using USB adapters on Linux platforms!')
        else:
            raise SystemError(f'{sys.platform} operating system type is not supported!')


## Backends ##
class Backend:
    """
    Backends facilitate communication between the computer and instruments, through combinations of drivers and APIs.
    """

    def __init__(self, adapter):
        self.adapter = adapter

    # The 4 methods below should be overwritten in Backend child class definitions
    def write(self, message):
        pass

    def read(self):
        pass

    def query(self, question, response_form=None):
        pass

    def disconnect(self):
        pass


class Serial(Backend):

    def __init__(self, adapter):

        self.address = 'COM' + adapter.address
        self.baud_rate = adapter.baud_rate
        self.timeout = adapter.timeout
        self.delay = adapter.delay

        serial = importlib.import_module('serial')
        self.backend = serial.Serial(port=self.address, baudrate=self.baud_rate, timeout=self.timeout)
        adapter.connected = True

    def write(self, message):
        self.backend.write(message)

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


class VISA(Backend):

    def __init__(self, adapter):

        self.timeout = adapter.timeout
        self.delay = adapter.delay

        visa = importlib.import_module('pyvisa')
        manager = visa.ResourceManager()

        if isinstance(adapter, SerialAdapter):
            self.address = f"ASRL{adapter.address}::INSTR"
            self.backend = manager.open_resource(self.address,
                                                 open_timeout=self.timeout,
                                                 baud_rate=self.baud_rate)
            self.backend.timeout = self.timeout

        elif isinstance(adapter, GPIB):
            self.address = f"GPIB::{adapter.address}::INSTR"
            self.backend = manager.open_resource(self.address,
                                                 open_timeout=self.timeout)
            self.backend.timeout = self.timeout

        elif isinstance(adapter, USB):
            serial_no = adapter.address

            for address in manager.list_resources():
                if serial_no in address:
                    self.address = address
                    self.backend = manager.open_resource(self.address,
                                                         open_timeout=self.timeout)
                    self.backend.timeout = self.timeout

            raise ConnectionError(f'device with serial number {serial_no} is not connected!')
        else:
            raise ConnectionError(f'unsupported adapter {adapter} for VISA backend!')

        adapter.connected = True

    def write(self, message):
        self.backend.write(message)

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
        self.interface.clear()
        self.interface.close()


class LinuxGPIB(Backend):

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

    def __init__(self, adapter):

        self.address = adapter.address
        self.delay = adapter.delay

        # Match specified timeout to an allowable timeout of at least as long
        for key, timeout in self.timeouts.items():
            if adapter.timeout is None:
                self.timeout = 0
                break
            elif timeout is None:
                continue
            elif timeout >= adapter.timeout:
                self.timeout = key
                break

        self.backend = importlib.import_module('gpib')

        self.descr = self.backend.dev(0, self.address, 0, self.timeout, 1, 0)  # integer corresponding to the device descriptor

        adapter.connected = True


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

class USBTMC(Backend):
    pass
