import argparse
from abc import ABC
from numpy import ndarray
from pandas import Series, DataFrame

try:
    import pytest
except ImportError:
    pytest = None

from empyric.experiment import Manager


# List of testable features.
# Tests are invoked at the command line with `empyric --test <feature>`
testable_features = [
    'experiment',  # tests Variable, Experiment and Manager classes (default)

    # Adpaters
    'serial',
    'gpib',
    'usb',
    'modbus',
    'phidget'
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

        if pytest is None:
            raise ImportError('pytest is not installed')

        if len(args.test) == 0:  # test main classes in experiment.py
            pytest.main(
                [
                    '-r', 'A', '--pyargs', 'empyric.tests',
                    '-k', 'test_experiment',
                    '-q'
                ]
            )

        elif all([feature in testable_features for feature in args.test]):
            # test specified features
            test_names = ['test_' + name for name in args.test]

            pytest.main(
                [
                    '-r', 'A', '--pyargs', 'empyric.tests',
                    '-k', ' or '.join(test_names),
                    '-q'
                ]
            )

        else:

            raise NotImplementedError(
                '\n' + '\n'.join(
                    [
                        f'Requested test of {feature} is not implement'
                        for feature in args.test
                        if feature not in testable_features
                    ]
                )
            )
    else:
        manager = Manager(runcard=args.runcard)
        manager.run(directory=args.directory)

class Toggle(ABC):

    def __init__(self, on_or_off: str):
        self.on = True if on_or_off.lower() == 'on' else False

    def __bool__(self):
        return True if self.on else False

    def __eq__(self, other):
        return True if self.on == other.on else False


ON = Toggle('ON')
OFF = Toggle('OFF')


class Array(ABC):
    """
    Abstract base class for all array-like types, essentially any commonly
    used type that can be indexed
    """
    pass


Array.register(list)
Array.register(tuple)
Array.register(ndarray)
Array.register(Series)
Array.register(DataFrame)
