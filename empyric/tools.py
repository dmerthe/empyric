import os
import time
import re
import select
import socket
import numbers
import numpy as np


# Tools for time-keeping
def convert_time(time_value):
    """
    If time_value is a string, converts a time of the form "[number] [units]"
    (e.g. "3.5 hours") to the time in seconds.
    If time_value is a number, just returns the same number
    If time_value is an array, iterates through the array doing either of the
    previous two operations on every element.

    :param time_value: (str/float) time value, possibly including units such as
    "hours"
    :return: (int) time in seconds
    """

    if np.size(time_value) > 1:
        return [convert_time(t) for t in time_value]

    if isinstance(time_value, numbers.Number):
        return time_value
    elif isinstance(time_value, str):
        # times can be specified in the runcard with units, such as minutes,
        # hours or days, e.g. "6 hours"
        time_parts = time_value.split(' ')

        if len(time_parts) == 1:
            return float(time_parts[0])
        elif len(time_parts) == 2:
            value, unit = time_parts
            value = float(value)
            return value * {
                'seconds': 1, 'second': 1,
                'minutes': 60, 'minute': 60,
                'hours': 3600, 'hour': 3600,
                'days': 86400, 'day': 86400
            }[unit]
        else:
            raise ValueError(f'Unrecognized time format for {time_value}!')


class Clock:
    """
    Clock for keeping time in an experiment; works like a standard stopwatch
    """

    def __init__(self):

        self.start_time = self.stop_time = time.time()  # initially stopped
        self.stoppage = 0  # total time during which the clock has been stopped

    def start(self):
        if self.stop_time:
            self.stoppage += time.time() - self.stop_time
            self.stop_time = False

    def stop(self):
        if not self.stop_time:
            self.stop_time = time.time()

    def reset(self):
        self.__init__()

    @property
    def time(self):
        if self.stop_time:
            elapsed_time = self.stop_time - self.start_time - self.stoppage
        else:
            elapsed_time = time.time() - self.start_time - self.stoppage

        return elapsed_time


# Utility functions that help interpret values
def is_on(value):
    on_values = [1, '1', 'ON', 'On', 'on']

    if value in on_values:
        return True
    else:
        return False


def is_off(value):
    off_values = [0, '0', 'OFF', 'Off', 'off']

    if value in off_values:
        return True
    else:
        return False


def to_number(value):
    if isinstance(value, numbers.Number):
        return value
    elif isinstance(str):
        return float(value)
    elif isinstance(np.ndarray) and np.ndim(value) == 0:
        return float(value)
    else:
        return np.nan


def find_nearest(allowed, value, overestimate=False, underestimate=False):
    """
    Find the closest in a list of allowed values to a given value.

    In some cases it might be beneficial to overestimate (choose nearest higher
    value) or underestimate (choose the nearest lower value)
    """

    if overestimate:
        diffs = np.array([abs(np.ceil(value - _value)) for _value in allowed])
        nearest = np.argwhere(diffs == np.min(diffs)).flatten()
    elif underestimate:
        diffs = np.array([abs(np.floor(value - _value)) for _value in allowed])
        nearest = np.argwhere(diffs == np.min(diffs)).flatten()
    else:
        diffs = np.array([abs(value - _value) for _value in allowed])
        nearest = np.argwhere(diffs == np.min(diffs)).flatten()

    if len(nearest) > 0:
        return allowed[nearest[0]]


def recast(value):
    """
    Convert a value into the appropriate type for the information it contains
    """

    if value is None:
        return None
    elif np.ndim(value) > 0:  # value is an array
        return np.array([recast(subval) for subval in value])
    elif isinstance(value, numbers.Number) or type(value) is bool:
        return value
    elif type(value) is str:

        if value.lower() == 'true':
            return True
        elif value.lower() == 'false':
            return False
        elif re.fullmatch('[0-9]*', value):  # integer
            return int(value)
        elif re.fullmatch('[-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?', value):
            # float
            return float(value)
        elif os.path.isfile(value):  # path in the current working directory
            return os.path.abspath(value)
        elif os.path.isfile(os.path.join('..', value)):  # ... up one level
            return os.path.abspath(os.path.join('..', value))
        else:
            return value
    else:
        return None


# Tools for handling sockets
def get_ip_address(remote_ip='8.8.8.8', remote_port=80):
    """Connect to Google's DNS Server to resolve IP address"""

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as tst_sock:
        tst_sock.connect((remote_ip, remote_port))
        return tst_sock.getsockname()[0]


def autobind_socket(_socket):
    """
    Automatically find the appropriate IP address and a free port to bind the
    socket to
    """

    bound = False

    ip_address = get_ip_address()

    for port in range(6174, 10000):
        try:
            _socket.bind((ip_address, port))
            bound = True
            break
        except OSError:
            pass

    if not bound:
        raise IOError(f'unable to bind socket at {ip_address} to any port!')

    return ip_address, port


def read_from_socket(_socket, nbytes=None, termination='\r', timeout=1):
    """
    Read from a socket, with care taken to get the whole message
    """

    # Block until the socket is readable or until timeout
    if timeout:
        readable = _socket in select.select([_socket], [], [], timeout)[0]
    else:
        readable = _socket in select.select([_socket], [], [])[0]

    if not readable:
        return None

    if nbytes is None:
        nbytes = np.inf

        if termination is None:
            raise ValueError(
                'nbytes must be a non-negative integer if termination is None'
            )

    null_responses = 0
    max_nulls = 3

    if type(termination) == str:
        termination = termination.encode()

    message = b''

    while len(message) < nbytes and null_responses < max_nulls:

        part = b''

        try:
            part = _socket.recv(1)
        except ConnectionResetError as err:
            print(f'Warning: {err}')
            break
        except socket.timeout:
            pass

        if len(part) > 0:

            message = message + part

            if termination is not None and termination in message:
                break

        else:
            null_responses += 1

    return message.decode().strip()


def write_to_socket(_socket, message, termination='\r', timeout=1):
    """
    Write a message to a socket, with care taken to get the whole message
    transmitted
    """

    # Block until the socket is writeable or until timeout
    if timeout:
        writeable = _socket in select.select([], [_socket], [], timeout)[1]
    else:
        writeable = _socket in select.select([], [_socket], [])[1]

    if not writeable:
        return 0

    bytes_message = (message + termination).encode()
    msg_len = len(bytes_message)

    failures = 0
    max_failures = 3

    total_sent = 0

    while total_sent < msg_len and failures < max_failures:

        sent = _socket.send(bytes_message[total_sent:])

        if sent == 0:
            failures += 1

        total_sent = total_sent + sent

    if total_sent < msg_len:
        raise IOError(
            f'Socket connection to {_socket.getsockname()} is broken!'
        )

    return total_sent
