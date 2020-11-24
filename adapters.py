import importlib
import functools
import time
import warnings
import sys
import re

supported_adapters = ['serial', 'gpib', 'usb']


class Adapter:
    """
    Adapters connect instruments defined in an experiment to the appropriate communication backends.
    """

    max_repeats = 3
    max_reconnects = 1

    def __init__(self, address, delay=0.1, timeout=0.1, baud_rate=9600, **kwargs):

        # general parameters
        self.address = address
        self.delay = delay
        self.timeout = timeout

        # for serial communications
        self.baud_rate = baud_rate

        self.connected = False
        self.repeats = 0
        self.reconnects = 0

    @staticmethod
    def chaperone(operation):  # wraps write, read and query methods and deals with communication issues

        def wrapped_operation(self, *args, **kwargs):

            if not self.connected:
                raise ConnectionError(f'Adapter is not connected for instrument at address {self.address}')

            # Catch communication errors and either try to repeat communication or reset the connection
            if self.reconnects < self.max_reconnects:
                if self.repeats < self.max_repeats:
                    try:
                        result = operation(self, *args, **kwargs)

                        if result is not 'invalid':
                            self.repeats = 0
                            self.reconnects = 0
                            return result
                    except BaseException as err:
                        warnings.warn('Encountered '
                                      + err.__name__
                                      + f' during communication with {self.type} instrument at address {self.address}')
                        self.repeats += 1
                        return wrapped_operation(self, *args, **kwargs)
                else:
                    self.disconnect()
                    time.sleep(self.delay)
                    self.connect()

                    self.repeats = 0
                    self.reconnects += 1
                    return wrapped_operation(self, *args, **kwargs)
            else:
                raise ConnectionError(f'Unable to communicate with instrument at address f{self.address}!')

        return wrapped_operation

    @chaperone
    def write(self, message):
        return self.backend.write(message)

    @chaperone
    def read(self, response_form=None):
        return self.backend.read(response_form=response_form)

    @chaperone
    def query(self, message, response_form=None):
        return self.backend.query(message, response_form=response_form)

    @chaperone
    def disconnect(self):
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
        elif sys.platform is 'linux':
            try:
                self.backend = Linux(self)
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
        elif sys.platform is 'linux':
            try:
                self.backend = USBTMC(self)
            except ImportError:
                raise ImportError('the usbtmc module is required for using USB adapters on Linux platforms!')
        else:
            raise SystemError(f'{sys.platform} operating system type is not supported!')


class Backend:
    """
    Backends, through combinations of drivers and APIs, facilitate communication between the computer and instruments.
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

    def write(self, message):
        self.backend.write(message)

    def read(self, response_form=None):
        response = self.backend.read()

        if response_form:
            if not re.match(response_form, response):
                return 'invalid'

        if response is '':
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

        if isinstance(adapter, GPIBAdapter):
            self.address = f"GPIB::{adapter.address}::INSTR"
            self.backend = manager.open_resource(self.address,
                                                 open_timeout=self.timeout,
                                                 delay=self.delay)

        if isinstance(adapter, USBAdapter):
            serial_no = adapter.address

            for address in manager.list_resources():
                if serial_no in address:
                    self.address = address
                    self.backend = manager.open_resource(self.address,
                                                         open_timeout=self.timeout,
                                                         delay=self.delay)
                    return

            raise ConnectionError(f'device with serial number {serial_no} is not connected!')

    def write(self, message):
        self.backend.write(message)

    def read(self, response_form=None):
        response = self.backend.read()

        if response_form:
            if not re.match(response_form, response):
                return 'invalid'

        if response is '':
            return 'invalid'
        else:
            return response

    def query(self, question, response_form=None):
        self.write(question)
        return self.read(response_form=response_form)

    def disconnect(self):
        self.interface.clear()
        self.interface.close()


class Linux(Backend):
    pass


class USBTMC(Backend):
    pass
