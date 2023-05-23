from empyric.instruments import Clock
from empyric.variables import Knob, Meter, Parameter, Expression


def test_variable():
    """
    Test experiment.Variable
    """

    clock = Clock()

    test_knob = Knob(instrument=clock, knob='state')

    test_meter = Meter(instrument=clock, meter='time')

    test_parameter = Parameter(parameter=5)

    test_expression = Expression(
        expression='time + offset',
        definitions={'time': test_meter, 'offset': test_parameter}
    )

    assert test_knob.value == 'STOP'
    assert test_meter.value == 0
    assert test_parameter.value == 5
    assert test_expression.value == 5
