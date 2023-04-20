# Standardization of data types
import abc
import os
import re
from abc import ABC
import pandas as pd
import numpy as np
from typing import Any


class Type(ABC):
    """Abstract base class for all supported data types"""
    pass


class Boolean(Type):
    """Abstract base class for all boolean types; `bool` and `np.bool_` are
    subclasses"""
    pass


Boolean.register(bool)
Boolean.register(np.bool_)


class Toggle(Type):
    """
    Convenience class for handling toggle variables, which are either off or on.
    """

    on_values = [True, 1, '1', 'ON', 'On', 'on']
    off_values = [False, 0, '0', 'OFF', 'Off', 'off']

    def __init__(self, state: [str, bool, int, type]):

        if hasattr(state, 'on'):
            self.on = state.on
        elif state in self.on_values:
            self.on = True
        elif state in self.off_values:
            self.on = False
        else:
            raise ValueError(
                f'toggle was initialized with invalid state {state}'
            )

    def __bool__(self):
        return True if self.on else False

    def __int__(self):
        return 1 if self.on else 0

    def __str__(self):
        return 'ON' if self.on else 'OFF'

    def __eq__(self, other):

        if hasattr(other, 'on'):
            return self.on == other.on
        else:
            if self.on and other in self.on_values:
                return True
            elif not self.on and other in self.off_values:
                return True
            else:
                return False


ON = Toggle('ON')
OFF = Toggle('OFF')


class Integer(Type):
    """Abstract base class for all integer types; `int` and `np.integer` are
    subclasses"""
    pass


Integer.register(int)
Integer.register(np.integer)


class Float(Type):
    """Abstract base class for all float types; `float` and `np.floating` are
    subclasses"""
    pass


Float.register(float)
Float.register(np.floating)


class String(Type):
    """Abstract base class for all string types; `str` and `np.str_` are
    subclasses"""
    pass


String.register(str)
String.register(np.str_)


class Array(Type):
    """
    Abstract base class for all array-like types, essentially any commonly
    used type that can be indexed; `list`, `tuple`, `numpy.ndarray`,
    `pandas.Series` and `pandas.Dataframe` are subclasses
    """
    pass


Array.register(list)
Array.register(tuple)
Array.register(np.ndarray)
Array.register(pd.Series)
Array.register(pd.DataFrame)


supported = {key: value for key, value in vars().items()
             if type(value) is abc.ABCMeta and issubclass(value, Type)}


def recast(value: Any, to: type = Type) -> [Type, None]:
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
    warning will be printed and None will be returned.

    :param value: (Any) the value whose type needs converting
    :param to: (Type) optional keyword argument indicating which type to
                       convert to; default value is `Type` which indicates
                       that the type should be inferred based on the value.
    """

    if to != Type:

        if value is None:
            return None

        for dtype in np.array([to], dtype=object).flatten():
            try:
                # recast to desired
                if issubclass(dtype, Boolean):
                    return np.bool_(value)
                elif issubclass(dtype, Toggle):
                    return Toggle(value)
                elif issubclass(dtype, Integer):
                    return np.int64(value)
                elif issubclass(dtype, Float):
                    return np.float64(value)
                elif issubclass(dtype, String):
                    return np.str_(value)
                elif issubclass(dtype, Array) and np.ndim(value) > 0:
                    return np.array(value)
            except ValueError:
                pass

        print(
            f'Warning: unable to recast value {value} to type {to}'
        )

        return None

    else:
        # infer type
        if isinstance(value, Boolean):
            return np.bool_(value)
        elif isinstance(value, Toggle):
            return value
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
            elif value in (Toggle.on_values + Toggle.off_values):
                return Toggle(value)
            elif os.path.isfile(value):  # path in the current working directory
                return os.path.abspath(value)
            elif os.path.isfile(os.path.join('..', value)):  # ... up one level
                return os.path.abspath(os.path.join('..', value))
            else:
                return value  # must be an actual string
        if isinstance(value, Array):  # value is an array
            np_array = np.array(value)  # convert to numpy array
            rep_elem = np_array.flatten()[0]  # representative element
            return np_array.astype(type(recast(rep_elem)))
        else:

            print(
                f'Warning: unable to recast value {value} of type {type(value)}'
            )

            return None
