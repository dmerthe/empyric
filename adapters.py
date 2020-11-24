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

        @functools.wraps(operation)
        def wrapping_function(self, *args, **kwargs):

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
                        return wrapping_function(self, *args, **kwargs)
                else:
                    self.disconnect()
                    time.sleep(self.delay)
                    self.connect()

                    self.repeats = 0
                    self.reconnects += 1
                    return wrapping_function(self, *args, **kwargs)
            else:
                raise ConnectionError(f'Unable to communicate with instrument at address f{self.address}!')

        return wrapping_function

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

    available_backends = ['serial']

    def connect(self):

        try:
            self.backend = Serial(self)
        except ImportError:
            raise ImportError('pyserial is required form using serial adapters!')


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
                raise ImportError('pyvisa with NI-VISA backend is required for using GPIB adapters on Windows or MacOS platforms!')
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
                raise ImportError('pyvisa with NI-VISA backend is required for using USB adapters on Windows or MacOS platforms!')
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

        self.address = adapter.address
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
    pass


class Linux(Backend):
    pass


class USBTMC(Backend):
    pass

# class USBAdapter(Adapter):
#     """
#     Adapter handling USB communcations (distinct from serial-usb adapters)
#     """
#
#     available_backends = ['visa', 'usbtmc']
#
#     def connect(self):
#         pass
#
#
# class GPIBAdapter(Adapter):
#     """
#     Representation of a GPIB adapter; implemented using either NI-VISA (Windows/MacOS) or the linux module (Linux)
#     """
#
#     available_backends = ['visa', 'linux-gpib']
#
#     def connect(self):
#
#         if sys.platform in ('win32', 'darwin'):
#             try:
#                 self.interface = VISAInterface(self)
#                 self.interface.connect()
#                 self.backend = 'visa'
#             except ImportError:
#                 raise ConnectionError('pyvisa with NI-VISA backend is required for using GPIB adapters with Windows or MacOS')
#         elif sys.platform is 'linux':
#             try:
#                 self.interface = LinuxGPIBInterface(self)
#                 self.interface.connect()
#                 self.backend = 'linux'
#             except ImportError:
#                 raise ConnectionError('linux module is required for using GPIB adapters with Linux')
#         else:
#             raise SystemError(f'{sys.platform} operating system type is not supported!')
#
#
#
#
#
# class SerialBackend(Backend):
#     pass
#
#
# class VISABackend(Backend):
#
#     def connect(self):
#
#         self.adapter.write = self.write
#         self.adapter.read = self.read
#         self.adapter.query = self.query
#
#         visa = importlib.import_module('visa')
#         manager = visa.ResourceManager()
#
#         if 'ASRL' in self.address:  # for serial connections
#             self.backend = manager.open_resource(self.address,
#                                                    open_timeout=self.timeout,
#                                                    baud_rate=self.baud_rate,
#                                                    delay=self.delay)
#         else:
#             self.backend = manager.open_resource(self.address,
#                                                    open_timeout=self.timeout,
#                                                    delay=self.delay)
#
#         self.backend.timeout = self.timeout
#
#         self.connected = True
#
#     @Adapter.chaperone
#     def write(self, message):
#         self.interface.write(message)
#
#     @Adapter.chaperone
#     def read(self, response_form=None):
#         response = self.interface.read()
#
#         if response is '':
#             return 'invalid'
#         else:
#             return response
#
#     def query(self, question, response_form=None):
#         self.write(question)
#         return self.read(response_form=response_form)
#
#     def disconnect(self):
#
#         self.interface.clear()
#         self.interface.close()
#         self.connected = False
#
#
#
# class VISAAdapter(Adapter):
#     """
#     Adapter handling communications with NI-VISA compatible instruments
#     """
#
#     backend = 'visa'
#
#     def connect(self):
#
#         visa = importlib.import_module('visa')
#         manager = visa.ResourceManager()
#
#         if 'ASRL' in self.address:  # for serial connections
#             self.interface = manager.open_resource(self.address,
#                                                    open_timeout=self.timeout,
#                                                    baud_rate=self.baud_rate,
#                                                    delay=self.delay)
#         else:
#             self.interface = manager.open_resource(self.address,
#                                                    open_timeout=self.timeout,
#                                                    delay=self.delay)
#
#         self.interface.timeout = self.timeout
#
#         self.connected = True
#
#     @Adapter.chaperone
#     def write(self, message):
#         self.interface.write(message)
#
#     @Adapter.chaperone
#     def read(self, response_form=None):
#         response = self.interface.read()
#
#
#
#         if response is '':
#             return 'invalid'
#         else:
#             return response
#
#     def query(self, question, response_form=None):
#         self.write(question)
#         return self.read(response_form=response_form)
#
#     def disconnect(self):
#
#         self.interface.clear()
#         self.interface.close()
#         self.connected = False
#
#
# class LinuxGPIBAdapter(Adapter):
#     """
#     Adapter handling communications with GPIB instruments using the Linux GPIB backend
#     """
#
#     def connect(self):
#         pass
#
