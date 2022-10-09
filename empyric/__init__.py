import os
import sys
import argparse
import pytest

from empyric.experiment import Manager


def execute():

    parser = argparse.ArgumentParser(
        description='Empyric Command Line Interface'
    )

    parser.add_argument(
        '-r', '--runcard', type=str, required=False, default=None,
        help="path of experiment runcard to execute"
    )

    parser.add_argument(
        '-d', '--directory', type=str, default=None,
        help='directory to write data and plots to'
    )

    parser.add_argument(
        '-t', '--test', nargs='*',
        help='test empyric installation and components'
    )

    args = parser.parse_args()

    if args.test is not None:
        if len(args.test) == 0:
            pytest.main(['-r', 'A', '--pyargs', 'empyric.tests'])
    else:
        manager = Manager(runcard=args.runcard)
        manager.run(directory=args.directory)
