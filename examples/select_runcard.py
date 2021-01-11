import os
from empyric.experiment import Manager

manager = Manager()

os.chdir(os.path.join(os.environ["HOME"], "Desktop"))

manager.run()
