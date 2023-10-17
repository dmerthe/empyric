import pytest
import time
import numpy as np
from empyric.instruments import OwonVDSScope


@pytest.fixture()
def scope_resource():
    scope_addr = '127.0.0.1::5025'  # address of Siglent scope
    scope = OwonVDSScope(scope_addr)
    yield scope


def test_time_scales(scope_resource):
    for time_scale in scope_resource._time_scales:
        scope_resource.set_horz_scale(time_scale)
        assert scope_resource.get_horz_scale() == time_scale


def test_voltage_scales(scope_resource):
    for volt_scales in scope_resource._volt_scales.keys():
        scope_resource.set_scale_ch(volt_scales, 1)
        assert scope_resource.get_scale_ch(1) == volt_scales


def test_resolutions(scope_resource):
    for resolution in scope_resource._resolutions:
        scope_resource.set_resolution(resolution)
        assert scope_resource.get_resolution() == resolution

@pytest.mark.parametrize('timeout', [0.1, 0.5, 1, 2])
def test_response_timing(scope_resource, timeout):
    scope_resource.adapter.timeout = timeout
    start_time = time.time()
    response = scope_resource.get_resolution()
    response_time = time.time()
    print(f'Time Delay (timeout={timeout}): {response_time-start_time}') 

def test_trigger_mode(scope_resource):
    for trigger_mode in scope_resource._sweep_modes:
        scope_resource.set_sweep_mode(trigger_mode)
        time.sleep(1)
        assert scope_resource.get_sweep_mode() == trigger_mode

@pytest.mark.parametrize('state', ['RUN', 'STOP'])
def test_run_stop(scope_resource, state):
    scope_resource.set_sweep_mode('AUTO')
    scope_resource.set_state(state)
    time.sleep(1)
    assert scope_resource.get_state() == state
    # set back to run state
    scope_resource.set_state('RUN')
    time.sleep(1)

@pytest.mark.skip(reason='Takes a while and we know it works now')
@pytest.mark.parametrize('resolution', [1e3])
def test_save_data(scope_resource, resolution):
    scope_resource.set_resolution(resolution)
    config = scope_resource.get_current_config()
    scope_resource.set_state('RUN')
    save_path = scope_resource._save_traces('C:\\scratch'.upper())
    channel_data = scope_resource._read_saved_binary_file(save_path, config)
    print(channel_data)

def test_acquire_mode(scope_resource):
    for acquire_mode in scope_resource._acquire_modes:
        scope_resource.set_acquire_mode(acquire_mode)
        assert scope_resource.get_acquire_mode() == acquire_mode
    scope_resource.set_acquire_mode('SAMPLE')

@pytest.mark.parametrize('averages', [1, 4, 17, 128])
def test_acquire_averages(scope_resource, averages):
    scope_resource.set_acquire_mode('AVERAGE')
    scope_resource.set_acquire_averages(averages)
    assert scope_resource.get_acquire_averages() == averages
    scope_resource.set_acquire_mode('SAMPLE')
    scope_resource.set_state('RUN')

@pytest.mark.parametrize('resolution', [1e3, 1e4, 1e5, 1e6, 5e6])
def test_measure_channel(scope_resource, resolution):
    scope_resource.set_horz_scale(200e-6)
    scope_resource.set_state('RUN')
    scope_resource.set_resolution(resolution)
    scope_resource.set_scale_ch(1, 1)
    scope_resource.set_trigger_source(1)
    scope_resource.set_sweep_mode('SINGLE')
    scope_resource.set_state('RUN')
    scope_resource.set_trigger_level(1.0)
    scope_resource.set_sweep_mode('SINGLE')
    scope_resource.set_state('RUN')
    voltages = scope_resource.measure_channel_1()
    assert len(voltages) == resolution

def test_run(scope_resource):
    scope_resource.set_state('RUN')
    time.sleep(1)

    # knobs = (
    #     "horz scale",
    #     "horz position",
    #     "scale ch1",
    #     "position ch1",
    #     "scale ch2",
    #     "position ch2",
    #     "sweep mode",
    #     "trigger level",
    #     "trigger source",
    #     "sweep mode",
    #     "resolution",
    #     "acquire",
    #     "state",
    # )

    # meters = (
    #     "channel 1",
    #     "channel 2",
    # )

    # presets = {
    #     "resolution": 1e6,
    #     "sweep mode": "SINGLE",
    #     "trigger source": 1,
    # }

    # _volt_scales = {
    #     2e-3: "2mv",
    #     5e-3: "5mv",
    #     10e-3: "10mv",
    #     20e-3: "20mv",
    #     50e-3: "50mv",
    #     100e-3: "100mv",
    #     200e-3: "200mv",
    #     500e-3: "500mv",
    #     1.0: "1v",
    #     2.0: "2v",
    #     5.0: "5v",
    # }

    # _volt_div_table = {0: 1e-3, 9: 1.0}

    # _resolutions = {
    #     1e3: "1K",
    #     1e4: "10K",
    #     1e5: "100K",
    #     1e6: "1M",
    #     5e6: "5M",
    #     1e7: "10M"
    #     }

    # _sweep_modes = ["AUTO", "NORMAL", "NORM", "SINGLE", "SING"]

    # _acquiring = False

    # _channels = {
    #     1: "CH1",
    #     2: "CH2",
    #     3: "CH3",
    #     4: "CH4",
    # }
