import time
import numbers
import numpy as np


# Tools for time-keeping
def convert_time(time_value):
    """
    If time_value is a string, converts a time of the form "[number] [units]" (e.g. "3.5 hours") to the time in seconds.
    If time_value is a number, just returns the same number
    If time_value is an array, iterates through the array doing either of the previous two operations on every element.

    :param time_value: (str/float) time value, possibly including units such as "hours"
    :return: (int) time in seconds
    """

    if np.size(time_value) > 1:
        return [convert_time(t) for t in time_value]

    if isinstance(time_value, numbers.Number):
        return time_value
    elif isinstance(time_value, str):
        # times can be specified in the runcard with units, such as minutes, hours or days, e.g. "6 hours"
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

        self.start_time = self.stop_time = time.time()  # clock is initially stopped
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

    In some cases it might be beneficial to overestimate (choose nearest higher value)
    or underestimate (choose the nearest lower value)
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
