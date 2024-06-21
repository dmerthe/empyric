import argparse
import logging

from empyric.tools import logger

try:
    import pytest
except ImportError:
    pytest = None

from empyric.experiment import Manager

from empyric.tools import logger, log_stream_handler

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

    parser.add_argument(
        "-b", "--debug", nargs="*", help="set logger level to DEBUG"
    )

    parser.add_argument(
        "-i", "--info", nargs="*", help="set logger level to INFO"
    )

    args = parser.parse_args()

    if args.debug is not None:
        logger.setLevel(logging.DEBUG)
        log_stream_handler.setLevel(logging.DEBUG)
        logger.info("Logger level set to DEBUG")

    if args.info is not None:
        logger.setLevel(logging.INFO)
        log_stream_handler.setLevel(logging.INFO)
        logger.info("Logger level set to INFO")

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
    else:
        manager = Manager(runcard=args.runcard)
        manager.run(directory=args.directory)
