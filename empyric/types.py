# Standardization of data types

import os
import re
from typing import Any
import numpy as np

Boolean = (bool, np.bool_)

Integer = (int, np.integer)

Float = (float, np.floating)

String = (str, np.str_)

Scalar = (Boolean, Integer, Float, String)

Array = (list, tuple, np.ndarray)


class Toggle:
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


def recast(value: Any, to: type = None) -> (Any, None):
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

    if to is not None:

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
