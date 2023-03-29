# Standardization of data types
import os
import re
from abc import ABC
import pandas as pd
import numpy as np


class Boolean(ABC):
    """Abstract base class for all boolean types"""
    pass


Boolean.register(bool)
Boolean.register(np.bool_)


class Toggle:
    """
    Convenience class for handling toggle variables, which are either off or on.
    """

    on_values = [True, 1, '1', 'ON', 'On', 'on']
    off_values = [False, 0, '0', 'OFF', 'Off', 'off']

    def __init__(self, state: str):

        if state in self.on_values:
            self.on = True
        elif state in self.off_values:
            self.on = False
        else:
            raise ValueError(
                f'toggle was initialized with invalid state {state}'
            )

    def __bool__(self):
        return True if self.on else False

    def __eq__(self, other):
        return True if self.on == other.on else False


ON = Toggle('ON')
OFF = Toggle('OFF')


class Integer(ABC):
    """Abstract base class for all integer types"""
    pass


Integer.register(int)
Integer.register(np.integer)


class Float(ABC):
    """Abstract base class for all integer types"""
    pass


Float.register(float)
Float.register(np.floating)


class String(ABC):
    """Abstract base class for all string types"""
    pass


String.register(str)
String.register(np.str_)


class Array(ABC):
    """
    Abstract base class for all array-like types, essentially any commonly
    used type that can be indexed
    """
    pass


Array.register(list)
Array.register(tuple)
Array.register(np.ndarray)
Array.register(pd.Series)
Array.register(pd.DataFrame)


def recast(value):
    """
    Convert a value into the appropriate type for the information it contains.

    Booleans are converted into numpy booleans; integers are converted into
    64-bit numpy integers; floats are converted into 64-bit numpy floats.

    Array-like values are converted into the analogous numpy array.

    Strings are inspected to determine if they represent boolean or numerical
    values and, if so, recasts values to the appropriate types. If a string
    is a path in either the working directory or the parent directory thereof,
    it is converted into the full absolute path. If a string does not
    represent boolean or numerical values and is not a path, then this function
    just returns the same string.

    If the value argument does not fit into one of the above categories, a
    `TypeError` is thrown.
    """

    if value is None or value == '':
        return None
    elif isinstance(value, Array):  # value is an array
        np_array = np.array(value)
        rep_elem = np_array.flatten()[0]
        return np_array.astype(type(recast(rep_elem)))
    elif isinstance(value, Boolean):
        return np.bool_(value)
    elif isinstance(value, Integer):
        return np.int64(value)
    elif isinstance(value, Float):
        return np.float64(value)
    elif isinstance(value, String):

        if value.lower() == 'true':
            return np.bool_(True)
        elif value.lower() == 'false':
            return np.bool_(False)
        elif re.fullmatch('[0-9]+', value):  # integer
            return np.int64(value)
        elif re.fullmatch('[-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?', value):
            # float
            return float(value)
        elif os.path.isfile(value):  # path in the current working directory
            return os.path.abspath(value)
        elif os.path.isfile(os.path.join('..', value)):  # ... up one level
            return os.path.abspath(os.path.join('..', value))
        else:
            return value  # must be an actual string
    else:
        raise TypeError(f'unable to recast value {value} of type {type(value)}')
