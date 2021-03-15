import os, sys
from empyric.experiment import Manager

manager = Manager()

if sys.platform == 'win32':
    directory = os.path.join(os.environ['USERPROFILE'], "Desktop")
else:
    directory = os.path.join(os.environ['HOME'], 'Desktop')

manager.run(directory=directory)
