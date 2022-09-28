import os
from empyric.experiment import Variable, Experiment
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
            knobs={'Echo In': echo_in, },
            times=[1, 2, 3, 4, 5],
            values=[10, 20, 30, 40, 50]
        )

    routines = {'Step Up Timecourse': step_up_routine, }

    experiment = Experiment(variables, routines=routines, end='with routines')

    for _ in experiment:
        pass

    assert round(experiment.state['Time']) == 5
    assert round(echo_out.value) == 50
