import os
from empyric.experiment import Manager

manager = Manager('Phidget_1101_runcard_example.yaml')

os.chdir(os.path.join(os.environ["HOME"], "Desktop"))

manager.run()
