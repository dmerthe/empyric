# This script is a placeholder for all the stuff in the stash, to make for simpler instrument importing

from mercury.instruments.sourcemeters import *
from mercury.instruments.supplies import *
from mercury.instruments.multimeters import *
from mercury.instruments.thermometers import *
from mercury.instruments.barometers import *

available_backends = ['serial', 'visa', 'linux', 'phidget', 'test', 'chaos']