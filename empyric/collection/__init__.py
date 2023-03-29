# empty __init__ file

from abc import ABC
from numpy import ndarray
from pandas import Series, DataFrame


class Toggle(ABC):

    def __init__(self, on_or_off: str):
        self.on = True if on_or_off.lower() == 'ON' else False

    def __bool__(self):
        return True if self.on else False

    def __eq__(self, other):
        return True if self.on == other.on else False


ON = Toggle('ON')
OFF = Toggle('OFF')


class Array(ABC):
    """
    Abstract base class for all array-like types, essentially any commonly
    used type that can be indexed
    """
    pass


Array.register(list)
Array.register(tuple)
Array.register(ndarray)
Array.register(Series)
Array.register(DataFrame)
