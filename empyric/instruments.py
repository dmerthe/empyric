# This module pulls all supported instruments into the same namespace

from empyric.collection.instrument import *
from empyric.collection.sourcemeters import *
from empyric.collection.supplies import *
from empyric.collection.barometers import *
from empyric.collection.thermometers import *
from empyric.collection.multimeters import *
from empyric.collection.controllers import *
from empyric.collection.humans import *
from empyric.collection.spectrometers import *
from empyric.collection.virtual import *
from empyric.collection.generators import *
from empyric.collection.scopes import *
from empyric.collection.magnetometers import *
from empyric.collection.io import *

supported = {
    key: value
    for key, value in vars().items()
    if type(value) is type and issubclass(value, Instrument)
}
