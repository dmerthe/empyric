import argparse
import logging

debugging = False

try:
    import pytest
except ImportError:
    pytest = None

from empyric.experiment import Manager


# List of testable features.
# Tests are invoked at the command line with `empyric --test <feature>`
testable_features = [
    "experiment",  # tests Variable, Experiment and Manager classes (default)
    "variable",  # tests Knob, Meter, Parameter and Expression
    # Adapters
    "serial",
    "gpib",
    "usb",
    "modbus",
    "phidget",
]


def execute():
    parser = argparse.ArgumentParser(description="Empyric Command Line Interface")

    parser.add_argument(
        "-r",
        "--runcard",
        type=str,
        required=False,
        default=None,
        help="path of experiment runcard to execute",
    )

    parser.add_argument(
        "-d",
        "--directory",
        type=str,
        default=None,
        help="directory to write data and plots to",
    )

    parser.add_argument(
        "-t", "--test", nargs="*", help="test empyric installation and components"
    )

    parser.add_argument("-b", "--debug", nargs='?', default='True')

    args = parser.parse_args()

    if args.test is not None:
        if pytest is None:
            raise ImportError("pytest is not installed")

        if len(args.test) == 0:  # test main classes in experiment.py
            pytest.main(
                ["-r", "A", "--pyargs", "empyric.tests", "-k", "test_experiment", "-q"]
            )

        elif all([feature in testable_features for feature in args.test]):
            # test specified features
            test_names = ["test_" + name for name in args.test]

            pytest.main(
                [
                    "-r",
                    "A",
                    "--pyargs",
                    "empyric.tests",
                    "-k",
                    " or ".join(test_names),
                    "-q",
                ]
            )

        else:
            raise NotImplementedError(
                "\n"
                + "\n".join(
                    [
                        f"Requested test of {feature} is not implemented"
                        for feature in args.test
                        if feature not in testable_features
                    ]
                )
            )
    elif args.debug is not None:

    else:
        manager = Manager(runcard=args.runcard)
        manager.run(directory=args.directory)


# Set up logging
logger = logging.getLogger(__name__)

logfile_handler = logging.FileHandler('empyric.log')
logfile_handler.setLevel(logging.INFO)

logstream_handler = logging.StreamHandler()

