# This script is a placeholder for all the stuff in the stash, to make for simpler instrument importing

from tempyral_dev.stash.sourcemeters import *
from tempyral_dev.stash.supplies import *
from tempyral_dev.stash.multimeters import *
from tempyral_dev.stash.phidget import *
from tempyral_dev.stash.barometers import *

available_backends = ['serial', 'visa', 'linux', 'phidget', 'test']

alarm_map = {
    'IS': lambda val, thres: val == thres,
    'NOT': lambda val, thres : val != thres,
    'GREATER': lambda val, thres: val > thres,
    'GEQ': lambda val, thres: val > thres,
    'LESS': lambda val, thres: val < thres,
    'LEQ': lambda val, thres: val <= thres,
}