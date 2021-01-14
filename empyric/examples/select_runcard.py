import os
from empyric.experiment import Manager

manager = Manager()

manager.run(directory=os.path.join(os.environ["HOME"], "Desktop"))
