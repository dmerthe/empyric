import importlib
import functools
import time

supported_adapters = ['dummy', 'serial', 'visa', 'phidget', 'linux']

class Adapter:

    failures = 0
    reconects = 0

    max_failures = 5
    max_reconnects = 5

    @staticmethod
    def chaperone(operation):

        @functools.wraps(operation)
        def wrapping_function(self, *args, **kwargs):

            if self.reconnects < self.max_reconnects:
                if self.failures < self.max_failures:
                    try:
                        result = operation(self, *args, **kwargs)
                        self.failures = 0

                        if result is not 'invalid':
                            return result
                    except:
                        self.failures += 1
                        return wrapping_function(self, *args, **kwargs)
                else:
                    self.reconnect()
                    self.failures = 0
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
        if not self.connected:
            raise ConnectionError('Adapter is not connected!')
        self.buffer.append(message)

    @Adapter.chaperone
    def read(self):
        if not self.connected:
            raise ConnectionError('Adapter is not connected!')
        return self.buffer.pop(0)

    def query(self, message):
        self.write(message)
        return self.read()

class VISAAdapter:
    """
    Adapter handling communications with NI-VISA compatible resources
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
    def read(self):
        response = self.interface.read()

        if response is '':
            return 'invalid'
        else:
            return response

    def query(self, question):
        self.write(question)
        time.sleep(self.delay)

        return self.read()

    def disconnect(self):

        self.interface.close()
        self.connected = False
