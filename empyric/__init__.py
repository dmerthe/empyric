import os
import sys
import argparse
import pytest

from empyric.experiment import Manager


# List of testable features.
# Tests are invoked at the command line with `empyric --test <feature>`
testable_features = [
    'experiment',  # tests Variable, Experiment and Manager classes (default)
    'serial',  # tests configuration of serial backend
]


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
        if len(args.test) == 0:  # test main classes in experiment.py
            pytest.main(
                [
                    '-r', 'A', '--pyargs', 'empyric.tests',
                    '-k', 'test_experiment',
                    '-q'
                ]
            )
        elif args.test[0] in testable_features:
            # test specified feature
            pytest.main(
                [
                    '-r', 'A', '--pyargs', 'empyric.tests',
                    '-k', f'test_' + args.test[0],
                    '-q'
                ]
            )
        else:
            raise NotImplementedError(
                f'requested test ({args.test}) is not implemented.'
            )
    else:
        manager = Manager(runcard=args.runcard)
        manager.run(directory=args.directory)
