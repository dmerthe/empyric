import importlib
import functools
import time
import warnings
import sys
import re


def chaperone(method):
    """
    Utility function that wraps the read methods of adapters to monitor and handle communication issues

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

    def __init__(self, address, **kwargs):

        # general parameters
        self.address = address

        for key, value in kwargs:
            self.__setattr__(key, value)

        self.connected = False
        self.repeats = 0
        self.reconnects = 0

        self.connect()

    # All methods below should be overwritten in children class definitions
    def connect(self):
        self.connected = True

    def write(self, message):
        pass

    @chaperone
    def read(self, response_form=None):
        pass

    def query(self, message, response_form=None):
        pass

    def disconnect(self):
        self.connected = False

class Serial(Adapter):
    """
    Handles communications with serial instruments through the PySerial module
    """

    def connect(self):

        serial = importlib.import_module('serial')
        self.backend = serial.Serial(port='COM' + self.address, baudrate=self.baud_rate, timeout=self.timeout)

    def write(self, message):
        self.backend.write(message)

    @chaperone
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


class VISASerial(Adapter):
    """
    Handles communications with serial instruments through the PyVISA module
    """

    def connect(self):

        visa = importlib.import_module('pyvisa')
        manager = visa.ResourceManager()

        self.backend = manager.open_resource(f"ASRL{self.address}::INSTR",
                                             open_timeout=self.timeout,
                                             baud_rate=self.baud_rate)

    def write(self, message):
        self.backend.write(message)

    @chaperone
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
        self.backend.clear()
        self.backend.close()


class VISAGPIB(Adapter):

    def connect(self):

        visa = importlib.import_module('pyvisa')
        manager = visa.ResourceManager()
        self.backend = manager.open_resource(f"GPIB0::{self.address}::INSTR",
                                             open_timeout=self.timeout)

    def write(self, message):
        self.backend.write(message)

    @chaperone
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
        self.backend.clear()
        self.backend.close()


class VISAUSB(Adapter):


    def connect(self):

        visa = importlib.import_module('pyvisa')
        manager = visa.ResourceManager()

        serial_number = self.address

        for address in manager.list_resources():
            if serial_number in address:
                self.address = address
                self.backend = manager.open_resource(self.address,
                                                     open_timeout=self.timeout)
                self.backend.timeout = self.timeout

    def write(self, message):
        self.backend.write(message)

    @chaperone
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
        self.backend.clear()
        self.backend.close()


class LinuxGPIB(Adapter):

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

    def connect(self):

        # Match specified timeout to an allowable timeout of at least as long
        for index, timeout in self.timeouts.items():
            if self.timeout is None:
                self.timeout_index = 0
                break
            elif timeout is None:
                continue
            elif timeout >= self.timeout:
                self.timeout_index = index
                break

        self.backend = importlib.import_module('gpib')

        self.descr = self.backend.dev(0, self.address, 0, self.timeout_index, 1, 0)  # integer corresponding to the device descriptor

        self.connected = True

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

class USBTMC(Adapter):
    pass

class Modbus(Adapter):
    pass
