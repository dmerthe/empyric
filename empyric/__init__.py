import os
import sys
import argparse
import pytest

from empyric.experiment import Manager


def execute():  # Run an experiment with a runcard

    parser = argparse.ArgumentParser(
        description='Empyric Command Line Interface'
    )

    parser.add_argument('-r', '--runcard', type=str, required=False,
                        default=None)

    parser.add_argument('-d', '--directory', type=str, default=None)

    parser.add_argument('-t', '--test', action='store_true')

    args = parser.parse_args()

    if args.test:
        pytest.main(['--pyargs', os.path.join('empyric.tests')])
    else:
        manager = Manager(runcard=args.runcard)
        manager.run(directory=args.directory)
