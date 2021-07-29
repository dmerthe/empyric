import os
from empyric.experiment import Manager

run_directory = os.path.expanduser('~/Desktop')

manager = Manager()
manager.run(directory=run_directory)
