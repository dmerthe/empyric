import os, sys
from empyric.experiment import Manager


def run_experiment():  # Run an experiment with a runcard

    args = sys.argv[1:]

    runcard = None
    if len(args) > 0:
        runcard = args[0]

    directory = None
    if len(args) > 1:
        directory = args[1]

    manager = Manager(runcard=runcard)
    manager.run(directory=directory)
