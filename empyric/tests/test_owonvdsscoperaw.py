import pytest
import time
import numpy as np
from empyric.instruments import OwonVDSScopeRaw


@pytest.fixture(scope="module")
def scope_resource():
    scope_addr = '10.50.1.12::2000'  # address of Siglent scope
    scope = OwonVDSScopeRaw(scope_addr)
    yield scope


def test_connect(scope_resource):
    assert scope_resource.adapter.connected is True


def test_get_config(scope_resource):
    print(scope_resource.get_current_config())


def test_resolutions(scope_resource):
    for resolution in scope_resource._resolutions:
        scope_resource.set_resolution(resolution)
        time.sleep(1)
        assert scope_resource.get_resolution() == resolution


def test_time_scales(scope_resource):
    for time_scale in scope_resource._time_scales:
        scope_resource.set_horizontal_scale(time_scale)
        time.sleep(1)
        assert scope_resource.get_horizontal_scale() == time_scale


def test_voltage_scales(scope_resource):
    for volt_scales in scope_resource._volt_scales.keys():
        scope_resource.set_scale_ch(volt_scales, 1)
        assert scope_resource.get_scale_ch(1) == volt_scales


@pytest.mark.parametrize('timeout', [0.1, 0.5, 1, 2])
def test_response_timing(scope_resource, timeout):
    scope_resource.adapter.timeout = timeout
    start_time = time.time()
    response = scope_resource.get_resolution()
    response_time = time.time()
    print(f'Time Delay (timeout={timeout}): {response_time-start_time}') 

# TODO: Only checks channel 1
def test_sweep_mode(scope_resource):
    scope_resource.set_trigger_source(1)
    for sweep_mode in scope_resource._sweep_modes:
        scope_resource.set_sweep_mode(sweep_mode)
        time.sleep(1)
        print(scope_resource.get_triggered_status())
        assert scope_resource.get_sweep_mode() == sweep_mode

@pytest.mark.parametrize('state', ['RUN', 'STOP'])
def test_run_stop(scope_resource, state):
    scope_resource.set_sweep_mode('AUTO')
    scope_resource.set_state(state)
    time.sleep(1)
    assert scope_resource.get_state() == state
    # set back to run state
    scope_resource.set_state('RUN')
    time.sleep(1)

def test_acquire_mode(scope_resource):
    for acquire_mode in scope_resource._acquisition_modes:
        scope_resource.set_acquisition_mode(acquire_mode)
        time.sleep(1)
        assert scope_resource.get_acquisition_mode() == acquire_mode
    scope_resource.set_acquisition_mode('SAMPLE')

@pytest.mark.parametrize('resolution', [1e3, 1e4, 1e5, 1e6])  # , 5e6])
def test_measure_channel(scope_resource, resolution):
    scope_resource.set_horizontal_scale(200e-6)
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


@pytest.mark.parametrize('resolution', [1e3, 1e4, 1e5, 1e6])  # , 5e6])
def test_get_times_channel(scope_resource, resolution):
    scope_resource.set_horizontal_scale(200e-6)
    scope_resource.set_state('RUN')
    scope_resource.set_resolution(resolution)
    scope_resource.set_scale_ch(1, 1)
    scope_resource.set_trigger_source(1)
    scope_resource.set_sweep_mode('SINGLE')
    scope_resource.set_state('RUN')
    scope_resource.set_trigger_level(1.0)
    scope_resource.set_sweep_mode('SINGLE')
    scope_resource.set_state('RUN')
    times = scope_resource.get_times()
    assert len(times) == resolution


def test_bandwidth_limit(scope_resource):
    scope_resource.set_ch1_bw_limit("20MHZ")
    time.sleep(1.0)
    assert scope_resource.get_ch1_bw_limit() == "20MHZ"
    scope_resource.set_ch1_bw_limit("FULL")
    time.sleep(1.0)
    assert scope_resource.get_ch2_bw_limit() == "FULL"
    scope_resource.set_ch2_bw_limit("20MHZ")
    time.sleep(1.0)
    assert scope_resource.get_ch2_bw_limit() == "20MHZ"
    scope_resource.set_ch2_bw_limit("FULL")
    time.sleep(1.0)
    assert scope_resource.get_ch2_bw_limit() == "FULL"
    scope_resource.set_ch3_bw_limit("20MHZ")
    time.sleep(1.0)
    assert scope_resource.get_ch3_bw_limit() == "20MHZ"
    scope_resource.set_ch3_bw_limit("FULL")
    time.sleep(1.0)
    assert scope_resource.get_ch3_bw_limit() == "FULL"
    scope_resource.set_ch4_bw_limit("20MHZ")
    time.sleep(1.0)
    assert scope_resource.get_ch4_bw_limit() == "20MHZ"
    scope_resource.set_ch4_bw_limit("FULL")
    time.sleep(1.0)
    assert scope_resource.get_ch4_bw_limit() == "FULL"

@pytest.mark.parametrize('coupling', ["AC", "GND", "DC"])
def test_coupling(scope_resource, coupling):
    scope_resource.set_ch1_coupling(coupling)
    time.sleep(0.5)
    scope_resource.get_state()
    assert scope_resource.get_ch1_coupling() == coupling
    scope_resource.set_ch1_coupling(coupling)
    time.sleep(0.5)
    scope_resource.get_state()
    assert scope_resource.get_ch2_coupling() == coupling
    scope_resource.set_ch2_coupling(coupling)
    time.sleep(0.5)
    scope_resource.get_state()
    assert scope_resource.get_ch2_coupling() == coupling
    scope_resource.set_ch2_coupling(coupling)
    time.sleep(0.5)
    scope_resource.get_state()
    assert scope_resource.get_ch2_coupling() == coupling
    scope_resource.set_ch3_coupling(coupling)
    time.sleep(0.5)
    assert scope_resource.get_ch3_coupling() == coupling
    scope_resource.set_ch3_coupling(coupling)
    time.sleep(0.5)
    scope_resource.get_state()
    assert scope_resource.get_ch3_coupling() == coupling
    scope_resource.set_ch4_coupling(coupling)
    time.sleep(0.5)
    scope_resource.get_state()
    assert scope_resource.get_ch4_coupling() == coupling
    scope_resource.set_ch4_coupling(coupling)
    time.sleep(0.5)
    scope_resource.get_state()
    assert scope_resource.get_ch4_coupling() == coupling


@pytest.mark.parametrize('enable', [False, True])
def test_enable(scope_resource, enable):
    scope_resource.set_ch1_enable(enable)
    time.sleep(0.5)
    assert scope_resource.get_ch1_enable() == enable
    scope_resource.set_ch1_enable(enable)
    time.sleep(0.5)
    assert scope_resource.get_ch2_enable() == enable
    scope_resource.set_ch2_enable(enable)
    time.sleep(0.5)
    assert scope_resource.get_ch2_enable() == enable
    scope_resource.set_ch2_enable(enable)
    time.sleep(0.5)
    assert scope_resource.get_ch2_enable() == enable
    scope_resource.set_ch3_enable(enable)
    time.sleep(0.5)
    assert scope_resource.get_ch3_enable() == enable
    scope_resource.set_ch3_enable(enable)
    time.sleep(0.5)
    assert scope_resource.get_ch3_enable() == enable
    scope_resource.set_ch4_enable(enable)
    time.sleep(0.5)
    assert scope_resource.get_ch4_enable() == enable
    scope_resource.set_ch4_enable(enable)
    time.sleep(0.5)
    assert scope_resource.get_ch4_enable() == enable



"""
@pytest.mark.skip(reason='Takes a while and we know it works now')
@pytest.mark.parametrize('resolution', [1e3])
def test_save_data(scope_resource, resolution):
    scope_resource.set_resolution(resolution)
    config = scope_resource.get_current_config()
    scope_resource.set_state('RUN')
    save_path = scope_resource._save_traces('C:\\scratch'.upper())
    channel_data = scope_resource._read_saved_binary_file(save_path, config)
    print(channel_data)


@pytest.mark.parametrize('averages', [1, 4, 17, 128])
def test_acquire_averages(scope_resource, averages):
    scope_resource.set_acquire_mode('AVERAGE')
    scope_resource.set_acquire_averages(averages)
    assert scope_resource.get_acquire_averages() == averages
    scope_resource.set_acquire_mode('SAMPLE')
    scope_resource.set_state('RUN')

"""