import os
import time
import glob
from empyric.experiment import Variable, Experiment, validate_runcard, Manager
from empyric.routines import Timecourse
from empyric.instruments import Clock, Echo


def test_variable():
    """
    Test experiment.Variable
    """

    clock = Clock()

    test_knob = Variable(instrument=clock, knob='state')

    test_meter = Variable(instrument=clock, meter='time')

    test_parameter = Variable(parameter=5)

    test_expression = Variable(
        expression='time + offset',
        definitions={'time': test_meter, 'offset': test_parameter}
    )

    assert test_knob.value == 'STOP'
    assert test_meter.value == 0
    assert test_parameter.value == 5
    assert test_expression.value == 5


def test_experiment(tmp_path):
    """
    Test experiment.Experiment
    """

    os.chdir(str(tmp_path))

    echo = Echo()

    echo_in = Variable(instrument=echo, knob='input')
    echo_out = Variable(instrument=echo, meter='output')

    variables = {'Echo In': echo_in, 'Echo Out': echo_out}

    step_up_routine = Timecourse(
        knobs={'Echo In': echo_in},
        times=[0.1, 0.2, 0.3, 0.4, 0.5],
        values=[10, 20, 30, 40, 50]
    )

    routines = {'Step Up Timecourse': step_up_routine, }

    experiment = Experiment(variables, routines=routines, end='with routines')

    for _ in experiment:
        time.sleep(0.001)

    # check that experiment ended on time
    assert round(experiment.state['Time'], 1) == 0.5
    assert round(echo_out.value) == 50

    # check data saving
    experiment.save()

    assert any(glob.glob('data_*.csv'))


# Use Henon runcard example for testing
test_runcard_path = os.path.abspath(
    os.path.join(
        '.', 'examples', 'Henon Map Experiment', 'henon_runcard_example.yaml'
    )
)


def test_runcard_validation():
    assert validate_runcard(test_runcard_path)


def test_manager(tmp_path):

    manager = Manager(test_runcard_path)

    # check that the runcard loaded
    assert manager.description['name'] == 'Henon Map Test'

    # Run a short version of the Henon Map example experiment
    manager.experiment.end = 3
    manager.followup = None

    manager.run(directory=tmp_path)

    assert manager.experiment.terminated
