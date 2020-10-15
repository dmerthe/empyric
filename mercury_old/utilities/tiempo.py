# Various time-related definitions and utility functions; contains all contents of the standard Python time module.

from time import *
import re
import numbers


class Clock:
    """
    Clock object for tracking elapsed time.
    """

    def __init__(self):
        self.start()

    def start(self):
        self.start_time = time()

        self.stop_time = None  # if paused, the time when the clock was paused
        self.total_stoppage = 0  # amount of stoppage time, or total time while paused

    def stop(self):
        if not self.stop_time:
            self.stop_time = time()

    def resume(self):
        if self.stop_time:
            self.total_stoppage += time() - self.stop_time
            self.stop_time = None

    def time(self):
        if not self.stop_time:
            return time() - self.start_time - self.total_stoppage
        else:
            return self.stop_time - self.start_time - self.total_stoppage




def convert_time(time_value):
    """
    Converts a time of the form "number units" (e.g. "3.5 hours") to the time in seconds.

    :param time_value: (str/float) time value, possibly including units such as 'hours'
    :return: (int) time in seconds
    """
    if isinstance(time_value, numbers.Number):
        return time_value
    elif isinstance(time_value, str):
        # times can be specified in the runcard with units, such as minutes, hours or days, e.g.  "6 hours"
        time_parts = time_value.split(' ')

        if len(time_parts) == 1:
            return float(time_parts[0])
        elif len(time_parts) == 2:
            value, unit = time_parts
            value = float(value)
            return value * {
                'seconds': 1, 'second':1,
                'minutes': 60, 'minute': 60,
                'hours': 3600, 'hour': 3600,
                'days': 86400, 'day':86400
            }[unit]
        else:
            raise ValueError(f'Unrecognized time format for {time_value}!')


def get_timestamp(path=None):
    """
    Generates a timestamp in the YYYYMMDD-HHmmss format.

    :param path: (string) path to get timestamp from; if None, a new timestamp will be generated and returned
    :return: (string) the formatted timestamp
    """

    if path:
        timestamp_format = re.compile(r'\d\d\d\d\d\d\d\d-\d\d\d\d\d\d')
        timestamp_matches = timestamp_format.findall(path)
        if len(timestamp_matches) > 0:
            return timestamp_matches[-1]
    else:
        return strftime("%Y%m%d-%H%M%S", localtime())


def timestamp_path(path, timestamp=None):
    """
    Appends a timestamp to a path string.

    :param path: (str) path to which the timestamp will be appended or updated
    :param timestamp: (string) if provided, this timestamp will be appended. If not provided, a new timestamp will be generated.
    :return: (str) timestamped path
    """

    already_timestamped = False

    if not timestamp:
        timestamp = get_timestamp()

    # separate extension
    full_name = '.'.join(path.split('.')[:-1])
    extension = '.' + path.split('.')[-1]

    # If there is already a timestamp, replace it
    # If there is not already a timestamp, append it

    timestamp_format = re.compile(r'\d\d\d\d\d\d\d\d-\d\d\d\d\d\d')
    timestamp_matches = timestamp_format.findall(path)

    if len(timestamp_matches) > 0:
        already_timestamped = True

    if already_timestamped:
        return '-'.join(full_name.split('-')[:-2]) + '-' + timestamp + extension
    else:
        return full_name + '-' + timestamp + extension
