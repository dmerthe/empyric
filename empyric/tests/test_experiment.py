# Tests for the basic features of empyric

import os
import time
import glob
from empyric.variables import Knob, Meter
from empyric.experiment import Experiment, validate_runcard, Manager
from empyric.routines import Timecourse
from empyric.instruments import Echo


def test_experiment(tmp_path):
    """
    Test experiment.Experiment
    """

    os.chdir(str(tmp_path))

    echo = Echo()

    echo_in = Knob(instrument=echo, knob="input")
    echo_out = Meter(instrument=echo, meter="output")

    variables = {"Echo In": echo_in, "Echo Out": echo_out}

    step_up_routine = Timecourse(
        knobs={"Echo In": echo_in},
        times=[0.1, 0.2, 0.3, 0.4, 0.5],
        values=[10, 20, 30, 40, 50],
    )

    routines = {
        "Step Up Timecourse": step_up_routine,
    }

    experiment = Experiment(variables, routines=routines, end="with routines")

    for _ in experiment:
        time.sleep(0.001)

    # check that experiment ended on time
    assert round(experiment.state["Time"], 1) == 0.5
    assert round(echo_out.value) == 50

    # check data saving
    experiment.save()

    assert any(glob.glob("data_*.csv"))


# Use Henon runcard example for testing
tests_dir = os.path.dirname(__file__)

test_runcard_path = os.path.abspath(
    os.path.join(tests_dir, "henon_runcard_example.yaml")
)


def test_runcard_validation():
    try:
        assert os.path.isfile(test_runcard_path)
    except AssertionError:
        raise AssertionError(
            "test runcard 'henon_runcard_example.yaml' was not found in "
            "installed package. This is normally configured by pip running "
            "setup.py. For a proper install, please use pip or similar."
        )

    assert validate_runcard(test_runcard_path)


def test_manager(tmp_path):
    manager = Manager(test_runcard_path)

    # Check that the runcard loaded
    assert manager.description["name"] == "Henon Map Experiment"

    # Run a short version of the Henon Map example experiment
    manager.experiment.end = 10
    manager.followup = None

    manager.run(directory=tmp_path)

    assert manager.experiment.terminated
