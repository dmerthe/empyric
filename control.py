from mercury.experiment import *
from mercury.instruments import *
from mercury.routines import *
from mercury.adapters import *


class Controller:
    """
    Runs experiments
    """
    def __init__(self, runcard, gui=None):

        if isinstance(runcard, str):  # runcard argument can be a path string
            with open(path, 'rb') as runcard_file:
                self.runcard = yaml.load(runcard_file) # load runcard in dictionary form
        elif isinstance(runcard, dict):
            self.runcard = runcard
        else:
            raise ValueError('runcard not recognized!')

        self.gui = gui

        self.description = runcard['Description']
        self.settings = runcard['Settings']

        self.instruments = {}
        for name, specs in runcard['Instruments']:



            self.instruments[name] = Instrument()

class GUI:
    pass