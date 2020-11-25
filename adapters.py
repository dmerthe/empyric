import importlib
import functools
import time
import warnings
import sys
import re

from mercury.elements import Adapter

supported_adapters = ['serial', 'gpib', 'usb']


## Adapters ##
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


class GPIBAdapter(Adapter):
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


class USBAdapter(Adapter):
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
                                                 baud_rate=self.baud_rate,
                                                 delay=self.delay)

        elif isinstance(adapter, GPIBAdapter):
            self.address = f"GPIB::{adapter.address}::INSTR"
            self.backend = manager.open_resource(self.address,
                                                 open_timeout=self.timeout,
                                                 delay=self.delay)

        elif isinstance(adapter, USBAdapter):
            serial_no = adapter.address

            for address in manager.list_resources():
                if serial_no in address:
                    self.address = address
                    self.backend = manager.open_resource(self.address,
                                                         open_timeout=self.timeout,
                                                         delay=self.delay)
                    return

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
