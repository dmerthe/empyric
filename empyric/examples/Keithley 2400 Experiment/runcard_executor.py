import os
from empyric.experiment import Manager

manager = Manager('keithley2400_runcard_example.yaml')

os.chdir(os.path.join(os.environ["HOME"], "Desktop"))

manager.run()
