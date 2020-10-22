import importlib
import functools
import time
import warnings
import sys

supported_adapters = ['serial','gpib', 'usb']

class Adapter:

    max_failures = 3
    max_reconnects = 2

    def __init__(self, address, **kwargs):

        # general parameters
        self.address = address
        self.delay = kwargs.get('delay', 0.1)
        self.timeout = kwargs.get('timeout', 0.1)

        # for serial comms
        self.baud_rate = kwargs.get('baud_rate', 9600)

        self.connected = False
        self.failures = 0
        self.reconnects = 0

    @staticmethod
    def chaperone(operation):  # wraps all communication methods, deals with communication issues

        @functools.wraps(operation)
        def wrapping_function(self, *args, **kwargs):

            if not self.connected:
                raise ConnectionError(f'Adapter is not connected for instrument at address {self.address}')

            # Catch communication errors and either try to repeat communication or reset the connection
            if self.reconnects < self.max_reconnects:
                if self.failures < self.max_failures:
                    try:
                        result = operation(self, *args, **kwargs)
                        self.failures = 0

                        if result is not 'invalid':
                            return result
                    except BaseException as err:
                        warnings.warn('Encountered '
                                      + err.__name__
                                      + f' during communication with {self.type} instrument at address {self.address}')
                        self.failures += 1
                        return wrapping_function(self, *args, **kwargs)
                else:
                    self.disconnect()
                    time.sleep(self.delay)
                    self.connect()

                    self.failures = 0
                    return wrapping_function(self, *args, **kwargs)
            else:
                raise ConnectionError(f'Unable to communicate with instrument at address f{self.address}!')

        return wrapping_function

    def query(self, message):
        self.write(message)
        return self.read()

    # Some dummy methods below for testing; should be overwritten by children classes
    def connect(self):
        self.connected = True

    def disconnect(self):
        self.connected = False

    @Adapter.chaperone
    def write(self, message):
        self.buffer = 'message'

    @Adapter.chaperone
    def read(self):
        try:
            return self.buffer
        except AttributeError:
            return ''


class SerialAdapter(Adapter):
    """
    Adapter handling communications with serial instruments
    """

    backend = 'serial'

    def connect(self):

        serial = importlib.import_module('serial')
        self.interface = serial.Serial(port=self.address, baudrate=self.baud_rate, timeout=self.timeout)

    @Adapter.chaperone
    def write(self, message):
        self.interface.write(message)

    @Adapter.chaperone
    def read(self, response_form=None):
        response = self.interface.read()

        if response is '':
            return 'invalid'
        else:
            return response

    def query(self, question, response_form=None):
        self.write(question)
        time.sleep(self.delay)
        return self.read(response_form=response_form)

    def disconnect(self):

        self.interface.flushInput()
        self.interface.flushOutput()
        self.interface.close()
        self.connected = False


class GPIBAdapter(Adapter):
    """
    Representation of a GPIB adapter; implemented using either NI-VISA (Windows/Mac) or the linux module (Linux)
    """

    def connect(self):

        if sys.platform in ('win32', 'darwin'):
            try:
                self.interface = VISAInterface(self)
                self.interface.connect()
                self.backend = 'visa'
            except ImportError:
                raise ConnectionError('pyvisa with NI-VISA backend is required for using GPIB adapters with Windows')
        elif sys.platform is 'linux':
            try:
                self.interface = LinuxGPIBInterface(self)
                self.interface.connect()
                self.backend = 'linux'
            except ImportError:
                raise ConnectionError('linux module is required for using GPIB adapters with Linux')
        else:
            raise SystemError(f'{sys.platform} operating system type is not supported!')


class Interface:

    def __init__(self, adapter):

        adapter.write = self.write
        adapter.read = self.read

class VISAAdapter(Adapter):
    """
    Adapter handling communications with NI-VISA compatible instruments
    """

    backend = 'visa'

    def connect(self):

        visa = importlib.import_module('visa')
        manager = visa.ResourceManager()

        if 'ASRL' in self.address:  # for serial connections
            self.interface = manager.open_resource(self.address,
                                                   open_timeout=self.timeout,
                                                   baud_rate=self.baud_rate,
                                                   delay=self.delay)
        else:
            self.interface = manager.open_resource(self.address,
                                                   open_timeout=self.timeout,
                                                   delay=self.delay)

        self.interface.timeout = self.timeout

        self.connected = True

    @Adapter.chaperone
    def write(self, message):
        self.interface.write(message)

    @Adapter.chaperone
    def read(self, response_form=None):
        response = self.interface.read()

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
        self.connected = False




class LinuxGPIBAdapter(Adapter):
    """
    Adapter handling communications with GPIB instruments using the Linux GPIB backend
    """

    def connect(self):
        pass

