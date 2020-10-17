import importlib
import functools
import time
import warnings

supported_adapters = ['dummy', 'serial', 'visa', 'phidget', 'linux']

class Adapter:

    failures = 0
    reconnects = 0

    max_failures = 5
    max_reconnects = 2

    def __init__(self, address, **kwargs):

        self.address = address

        for key, value in kwargs.items:
            setattr(self, key, value)

        self.connected = False

    @staticmethod
    def chaperone(operation):

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
                        warnings.warn(err)
                        self.failures += 1
                        return wrapping_function(self, *args, **kwargs)
                else:
                    self.reconnect()
                    self.failures = 0
                    return wrapping_function(self, *args, **kwargs)
            else:
                raise ConnectionError(f'Unable to communicate with instrument at address f{self.address}!')

        return wrapping_function

    def reconnect(self):
        self.disconnect()
        time.sleep(self.delay)
        self.connect()

class DummyAdapter(Adapter):
    """
    Dummy adapter for testing purposes
    """

    backend = None

    def __init__(self, address, **kwargs):

        Adapter.__init__()

        self.address = address
        self.interface = None
        self.buffer = []

        self.connected = False

    def connect(self):
        self.connected = True

    def disconnect(self):
        self.connected = False

    @Adapter.chaperone
    def write(self, message):
        self.buffer.append(message)

    @Adapter.chaperone
    def read(self):
        return self.buffer.pop(0)

    def query(self, message):
        self.write(message)
        return self.read()

class VISAAdapter:
    """
    Adapter handling communications with NI-VISA compatible instruments
    """

    backend = 'visa'

    def __init__(self, address, **kwargs):

        self.address = address
        self.timeout = kwargs.get('timeout', 0.1)
        self.delay = kwargs.get('delay', 0)

        if 'ASRL' in address:
            self.type = 'serial'
            self.baud_rate = kwargs.get('baud_rate', 9600)

        if 'GPIB' in address:
            self.type = 'gpib'

        if 'USB' in address:
            self.type = 'usb'

        self.connected = False

    def connect(self):

        visa = importlib.import_module('visa')
        manager = visa.ResourceManager()

        if self.type is 'serial':
            self.interface = manager.open_resource(self.address, open_timeout=self.timeout, baud_rate=self.baud_rate)
        else:
            self.interface = manager.open_resource(self.address, open_timeout=self.timeout)

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
        time.sleep(self.delay)
        return self.read(response_form=response_form)

    def disconnect(self):

        self.interface.clear()
        self.interface.close()
        self.connected = False


class SerialAdapter(Adapter):
    """
    Adapter handling communications with serial instruments
    """

    backend = 'visa'

    def __init__(self, address, **kwargs):

        self.address = address
        self.timeout = kwargs.get('timeout', 0.1)
        self.delay = kwargs.get('delay', 0)
        self.baudrate = kwargs.get('baudrate', 9600)

        self.connected = False

    def connect(self):

        serial = importlib.import_module('serial')
        self.interface = serial.Serial(port=self.address, baudrate=self.baudrate, timeout=self.timeout)

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


class USBAdapter(Adapter):

    def __init__(self):
        pass
