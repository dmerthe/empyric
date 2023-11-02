import struct
import numpy as np
import time
import re
from typing import Callable

from empyric.adapters import Socket
from empyric.collection.instrument import Instrument, setter, getter, measurer
from empyric import tools


class OwonVDSScopeRaw(Instrument):
    """
    Owon VDS PC Oscilloscope.

    NOT TESTED
    """

    """Supported adapters and options."""
    supported_adapters = (
        (
            Socket,
            {
                "write_termination": b"",
                "read_termination": None,
                "timeout": 1.0,
            },
        ),
    )

    def __init__(
        self, address=None, adapter=None, presets=None, postsets=None, **kwargs
    ):
        """
        We need a modified init function for this class because we can't get the status of the knobs until we set them on this device.
        :param address: (str/int) address of instrument
        :param adapter: (Adapter) desired adapter to use for communications
        with the instrument
        :param presets: (dict) dictionary of instrument presets of the form
        {..., knob: value, ...}
        :param presets: (dict) dictionary of instrument postsets of the form
        {..., knob: value, ...}
        :param kwargs: (dict) any keyword args for the adapter
        """

        if address:
            self.address = address
        else:
            self.address = None

        adapter_connected = False
        if adapter:
            self.adapter = adapter(self, **kwargs)
        else:
            errors = []
            for _adapter, settings in self.supported_adapters:
                settings.update(kwargs)
                try:
                    self.adapter = _adapter(self, **settings)
                    adapter_connected = True
                    break
                except BaseException as error:
                    msg = (
                        f"in trying {_adapter.__name__} adapter, "
                        f"got {type(error).__name__}: {error}"
                    )
                    errors.append(msg)

            if not adapter_connected:
                message = (
                    f"unable to connect an adapter to "
                    f"instrument {self.name} at address {address}:\n"
                )
                for error in errors:
                    message = message + f"{error}\n"
                raise ConnectionError(message)

        if self.address:
            self.name = self.name + "@" + str(self.address)

        self.write(b":SDSLVER#", encode=False)
        print(self.read(nbytes=1024, decode=False))

        # Apply presets
        if presets:
            self.presets = {**self.presets, **presets}

        for knob, value in self.presets.items():
            print(knob, value)
            self.set(knob, value)
        
        self.set_state("RUN")
        time.sleep(1)
        print(self.get_state())

        for knob, value in self.presets_pt_2.items():
            print(knob, value)
            self.set(knob, value)

        # Get postsets
        if postsets:
            self.postsets = {**self.postsets, **postsets}


    class Setting():
        def __init__(self, key: str, setting_regex: bytes, to_bytes: Callable, from_bytes: Callable):
            self.key: str = key
            self.setting_regex: re.Pattern = re.compile(setting_regex, flags=re.DOTALL)
            self.to_bytes: Callable = to_bytes
            self.from_bytes: Callable = from_bytes

    _independent_settings: list[Setting] = [
        Setting("horizontal scale", b"MHRb(?P<horizontal_scale>.)",
                to_bytes=lambda value: OwonVDSScopeRaw._time_scales[value],
                from_bytes=lambda value: OwonVDSScopeRaw.reverse_lookup(OwonVDSScopeRaw._time_scales, value)),
        Setting("acquisition mode", b"MAQ(?P<acquisition_mode>.)",
                to_bytes=lambda value: OwonVDSScopeRaw._acquisition_modes[value],
                from_bytes=lambda value: OwonVDSScopeRaw.reverse_lookup(OwonVDSScopeRaw._acquisition_modes, value)),
        Setting("resolution", b"MDP(?P<resolution>.)",
                to_bytes=lambda value: OwonVDSScopeRaw._resolutions[value],
                from_bytes=lambda value: OwonVDSScopeRaw.reverse_lookup(OwonVDSScopeRaw._resolutions, value)),
        Setting("trigger channel", b"MTRs(?P<trigger_channel>.)",
                to_bytes=lambda value: int.to_bytes(value - 1, length=1, byteorder="big", signed=False),
                from_bytes=lambda value: int.from_bytes(value, byteorder="big", signed=False) + 1),
        Setting("trigger mode", b"MTRs(?P<trigger_channel>.)(?P<trigger_mode>.)",
                to_bytes=lambda value: OwonVDSScopeRaw._trigger_modes[value],
                from_bytes=lambda value: OwonVDSScopeRaw.reverse_lookup(OwonVDSScopeRaw._trigger_modes, value)),
        Setting("sweep mode", b"MTRs(?P<trigger_channel>.)e\x03(?P<sweep_mode>.)",
                to_bytes=lambda value: OwonVDSScopeRaw._sweep_modes[value],
                from_bytes=lambda value: OwonVDSScopeRaw.reverse_lookup(OwonVDSScopeRaw._sweep_modes, value)),
        Setting("trigger hold off", b"MTRs(?P<trigger_channel>.)e\x04(?P<trigger_hold_off>.{4})",
                to_bytes=lambda value: int.to_bytes(value, length=4, byteorder="big", signed=True),
                from_bytes=lambda value: int.from_bytes(value, byteorder="big", signed=True)),
        Setting("trigger edge", b"MTRs(?P<trigger_channel>.)e\x05(?P<trigger_edge>.)",
                to_bytes=lambda value: OwonVDSScopeRaw._trigger_edges[value],
                from_bytes=lambda value: OwonVDSScopeRaw.reverse_lookup(OwonVDSScopeRaw._trigger_edges, value)),
        Setting("ch1 scale", b"MCH\x00v(?P<ch1_scale>.)",
                to_bytes=lambda value: OwonVDSScopeRaw._volt_scales[value],
                from_bytes=lambda value: OwonVDSScopeRaw.reverse_lookup(OwonVDSScopeRaw._volt_scales, value)),
        Setting("ch1 coupling", b"MCH\x00c(?P<ch1_coupling>.)",
                to_bytes=lambda value: OwonVDSScopeRaw._coupling_modes[value],
                from_bytes=lambda value: OwonVDSScopeRaw.reverse_lookup(OwonVDSScopeRaw._coupling_modes, value)),
        Setting("ch1 enable", b"MCH\x00e(?P<ch1_enable>.)",
                to_bytes=lambda value: OwonVDSScopeRaw._enable_modes[value],
                from_bytes=lambda value: OwonVDSScopeRaw.reverse_lookup(OwonVDSScopeRaw._enable_modes, value)),
        Setting("ch1 bw limit", b"MCH\x00b(?P<ch1_bw_limit>.)",
                to_bytes=lambda value: OwonVDSScopeRaw._bandwidth_limits[value],
                from_bytes=lambda value: OwonVDSScopeRaw.reverse_lookup(OwonVDSScopeRaw._bandwidth_limits, value)),
        Setting("ch2 scale", b"MCH\x01v(?P<ch2_scale>.)",
                to_bytes=lambda value: OwonVDSScopeRaw._volt_scales[value],
                from_bytes=lambda value: OwonVDSScopeRaw.reverse_lookup(OwonVDSScopeRaw._volt_scales, value)),
        Setting("ch2 coupling", b"MCH\x01c(?P<ch2_coupling>.)",
                to_bytes=lambda value: OwonVDSScopeRaw._coupling_modes[value],
                from_bytes=lambda value: OwonVDSScopeRaw.reverse_lookup(OwonVDSScopeRaw._coupling_modes, value)),
        Setting("ch2 enable", b"MCH\x01e(?P<ch2_enable>.)",
                to_bytes=lambda value: OwonVDSScopeRaw._enable_modes[value],
                from_bytes=lambda value: OwonVDSScopeRaw.reverse_lookup(OwonVDSScopeRaw._enable_modes, value)),
        Setting("ch2 bw limit", b"MCH\x01b(?P<ch2_bw_limit>.)",
                to_bytes=lambda value: OwonVDSScopeRaw._bandwidth_limits[value],
                from_bytes=lambda value: OwonVDSScopeRaw.reverse_lookup(OwonVDSScopeRaw._bandwidth_limits, value)),
        Setting("ch3 scale", b"MCH\x02v(?P<ch3_scale>.)",
                to_bytes=lambda value: OwonVDSScopeRaw._volt_scales[value],
                from_bytes=lambda value: OwonVDSScopeRaw.reverse_lookup(OwonVDSScopeRaw._volt_scales, value)),
        Setting("ch3 coupling", b"MCH\x02c(?P<ch3_coupling>.)",
                to_bytes=lambda value: OwonVDSScopeRaw._coupling_modes[value],
                from_bytes=lambda value: OwonVDSScopeRaw.reverse_lookup(OwonVDSScopeRaw._coupling_modes, value)),
        Setting("ch3 enable", b"MCH\x02e(?P<ch3_enable>.)",
                to_bytes=lambda value: OwonVDSScopeRaw._enable_modes[value],
                from_bytes=lambda value: OwonVDSScopeRaw.reverse_lookup(OwonVDSScopeRaw._enable_modes, value)),
        Setting("ch3 bw limit", b"MCH\x02b(?P<ch3_bw_limit>.)",
                to_bytes=lambda value: OwonVDSScopeRaw._bandwidth_limits[value],
                from_bytes=lambda value: OwonVDSScopeRaw.reverse_lookup(OwonVDSScopeRaw._bandwidth_limits, value)),
        Setting("ch4 scale", b"MCH\x03v(?P<ch4_scale>.)",
                to_bytes=lambda value: OwonVDSScopeRaw._volt_scales[value],
                from_bytes=lambda value: OwonVDSScopeRaw.reverse_lookup(OwonVDSScopeRaw._volt_scales, value)),
        Setting("ch4 coupling", b"MCH\x03c(?P<ch4_coupling>.)",
                to_bytes=lambda value: OwonVDSScopeRaw._coupling_modes[value],
                from_bytes=lambda value: OwonVDSScopeRaw.reverse_lookup(OwonVDSScopeRaw._coupling_modes, value)),
        Setting("ch4 enable", b"MCH\x03e(?P<ch4_enable>.)",
                to_bytes=lambda value: OwonVDSScopeRaw._enable_modes[value],
                from_bytes=lambda value: OwonVDSScopeRaw.reverse_lookup(OwonVDSScopeRaw._enable_modes, value)),
        Setting("ch4 bw limit", b"MCH\x03b(?P<ch4_bw_limit>.)",
                to_bytes=lambda value: OwonVDSScopeRaw._bandwidth_limits[value],
                from_bytes=lambda value: OwonVDSScopeRaw.reverse_lookup(OwonVDSScopeRaw._bandwidth_limits, value))
        # Unknown Command: "": b"MCH(?P<channel>.)i(?P<>.)",
    ]

    _dependent_settings = [
        Setting("horizontal position", b"MHRb(?P<horizontal_position>.)",
                to_bytes=lambda value, config: int(50.0 * value / config["horizontal scale"]).to_bytes(length=4, byteorder='big', signed=True),
                from_bytes=lambda value, config: int.from_bytes(value, byteorder='big', signed=True) * config["horizontal scale"] / 25.0),
        Setting("trigger level", b"MTRs(?P<trigger_channel>.)e\x06(?P<trigger_level>.{4})",
                to_bytes=lambda value, config: int(25.0 * value / config[f"ch{config['trigger channel']} scale"]).to_bytes(length=4, byteorder='big', signed=True),
                from_bytes=lambda value, config: int.from_bytes(value, byteorder='big', signed=True) * config[f"ch{config['trigger channel']} scale"] / 25.0),
        Setting("ch1 position", b"MCH\x00z(?P<ch1_position>.{4})",
                to_bytes=lambda value, config: int(25 * value / config[f"ch1 scale"]).to_bytes(length=4, byteorder='big', signed=True),
                from_bytes=lambda value, config: int.from_bytes(value, byteorder='big', signed=True) * config["ch1 scale"] / 25.0),
        Setting("ch2 position", b"MCH\x01z(?P<ch2_position>.{4})",
                to_bytes=lambda value, config: int(25 * value / config[f"ch2 scale"]).to_bytes(length=4, byteorder='big', signed=True),
                from_bytes=lambda value, config: int.from_bytes(value, byteorder='big', signed=True) * config["ch2 scale"] / 25.0),
        Setting("ch3 position", b"MCH\x02z(?P<ch3_position>.{4})",
                to_bytes=lambda value, config: int(25 * value / config[f"ch3 scale"]).to_bytes(length=4, byteorder='big', signed=True),
                from_bytes=lambda value, config: int.from_bytes(value, byteorder='big', signed=True) * config["ch3 scale"] / 25.0),
        Setting("ch4 position", b"MCH\x03z(?P<ch4_position>.{4})",
                to_bytes=lambda value, config: int(25 * value / config[f"ch4 scale"]).to_bytes(length=4, byteorder='big', signed=True),
                from_bytes=lambda value, config: int.from_bytes(value, byteorder='big', signed=True) * config["ch4 scale"] / 25.0)
    ]

    _all_settings = _independent_settings + _dependent_settings

    knobs = (
        "horizontal scale",
        "horizontal position",
        "ch1 scale",
        "ch1 position",
        "ch2 scale",
        "ch2 position",
        "ch3 scale",
        "ch3 position",
        "ch4 scale",
        "ch4 position",
        "sweep mode",
        "trigger level",
        "trigger channel",
        "resolution",
        "acquire",
        "state",
    )

    meters = (
        "channel 1",
        "channel 2",
        "channel 3",
        "channel 4",
    )

    presets = {
        "resolution": 1e3,
        "horizontal scale": 500.0e-6,
        "ch1 scale": 1.0,
        "ch2 scale": 1.0,
        "ch3 scale": 0.1,
        "ch4 scale": 0.01,
        "ch1 coupling": "DC",
        "ch2 coupling": "DC",
        "ch3 coupling": "DC",
        "ch4 coupling": "DC",
        "ch1 enable": True,
        "ch2 enable": True,
        "ch3 enable": True,
        "ch4 enable": True,
        "acquisition mode": "SAMPLE"
    }

    presets_pt_2 = {
        "trigger source": 1,
        "trigger level": 1.0,
        "sweep mode": "AUTO"
    }


    _time_scales = {
        2.0e-9: bytearray([0]),
        5.0e-9: bytearray([1]),
        10.0e-9: bytearray([2]),
        20.0e-9: bytearray([3]),
        50.0e-9: bytearray([4]),
        100.0e-9: bytearray([5]),
        200.0e-9: bytearray([6]),
        500.0e-9: bytearray([7]),
        1.0e-6: bytearray([8]),
        2.0e-6: bytearray([9]),
        5.0e-6: bytearray([10]),  # this doesn't work because bytearray([10]) is a \n character which breaks something somewhere
        10.0e-6: bytearray([11]),
        20.0e-6: bytearray([12]),
        50.0e-6: bytearray([13]),
        100.0e-6: bytearray([14]),
        200.0e-6: bytearray([15]),
        500.0e-6: bytearray([16]),
        1.0e-3: bytearray([17]),
        2.0e-3: bytearray([18]),
        5.0e-3: bytearray([19]),
        10.0e-3: bytearray([20]),
        20.0e-3: bytearray([21]),
        50.0e-3: bytearray([22]),
        100.0e-3: bytearray([23]),
        200.0e-3: bytearray([24]),
        500.0e-3: bytearray([25]),
        1.0: bytearray([26]),
        2.0: bytearray([27]),
        5.0: bytearray([28]),
        10.0: bytearray([29]),
        20.0: bytearray([30]),
        50.0: bytearray([31]),
        100.0: bytearray([32])
    }

    _volt_scales = {
        2e-3: bytearray([0]),
        5e-3: bytearray([1]),
        10e-3: bytearray([2]),
        20e-3: bytearray([3]),
        50e-3: bytearray([4]),
        100e-3: bytearray([5]),
        200e-3: bytearray([6]),
        500e-3: bytearray([7]),
        1.0: bytearray([8]),
        2.0: bytearray([9]),
        5.0: bytearray([10]), # this doesn't work because bytearray([10]) is a \n character which breaks something somewhere
    }

    _resolutions = {
        1e3: bytearray([0]),
        1e4: bytearray([1]),
        1e5: bytearray([2]),
        1e6: bytearray([3])
        # ,
        # 5e6: bytearray([4])
    }
    
    _acquisition_modes = {
        "SAMPLE": bytearray([0]),
        "AVERAGE": bytearray([1]), # guess
        "PEAK": bytearray([2]) # guess
    }

    _sweep_modes = {
        "AUTO": bytearray([0]),
        "NORMAL": bytearray([1]),
        "SINGLE": bytearray([2])
        }

    _enable_modes = {
        True: bytearray([1]),
        False: bytearray([0])
        }

    _coupling_modes = {
        "DC": bytearray([0]),
        "AC": bytearray([1]),
        "GND": bytearray([2])
    }

    _bandwidth_limits = {
        "FULL": bytearray([0]),
        "20MHZ": bytearray([1])
    }

    _trigger_modes = {
        "EDGE": "e".encode()
        # The modes below exist but are a lot more work to implement
        #"VIDEO": "v".encode(),
        #"SLOPE": "s".encode(),
        #"PULSE": "p".encode()
    }

    _supported_trigger_modes = ["EDGE"]

    _trigger_edges = {
        "RISING": bytearray([0]),
        "FALLING": bytearray([1])
    }

    _acquiring = False

    _channels = {
        1: "CH1",
        2: "CH2",
        3: "CH3",
        4: "CH4",
    }

    ###################################################################
    ##          Utilities                                            ##
    ###################################################################

    def get_setting(self, id: str) -> Setting:
        '''
        Making the list of settings into 
        But I'm tired and need to get this working.
        '''
        try:
            setting = [item for item in self._all_settings if item.key == id][0]
        except KeyError:
            raise ValueError(f"id {id} not recognized in setting identifiers.")
        return setting

    def create_command_from_regex(self, regex: re.Pattern, command_values: dict) -> bytes:
        parameter_regex = b"(\(.+?\))"

        parameter_groups = re.findall(parameter_regex, regex.pattern)
        command_parameters = [param.replace("_", " ") for param in list(regex.groupindex.keys())]
        command: bytes = regex.pattern
        for index, group_text in enumerate(parameter_groups):
            try:
                command_bytes = command_values[command_parameters[index]]
                command = command.replace(group_text, command_bytes)
            except KeyError:
                raise ValueError(f'Parameter {command_parameters[index]} missing from command_values dictionary.')

        return command

    def set_by_command_id(self, id: str, native_value):
        setting: OwonVDSScopeRaw.Setting = self.get_setting(id)
        cmd = self.create_command_from_regex(setting.setting_regex, {id: setting.to_bytes(native_value)})
        return self.send_m_command(cmd)

    def reverse_lookup(table: dict, value):
        return [key for key, val in table.items() if val == value][0]

    def raw_query(self, question):
        self.write(question, encode=False)
        return self.read(nbytes=1024, decode=False)

    def send_m_command(self, cmd):
        cmd_prefix = ":M".encode() + struct.pack('!I', len(cmd))
        return self.write(cmd_prefix + cmd, encode=False)

    def flush_buffer(self):
        """
        This reads all the data it can from the socket.
        """
        self.read(nbytes=1e6, timeout=0.5, termination=None, decode=False)

    ###################################################################
    ##          Scope Control                                        ##
    ###################################################################

    @setter
    def set_horizontal_scale(self, scale):
        new_time_scale = tools.find_nearest(list(self._time_scales.keys()), scale)
        return self.set_by_command_id("horizontal scale", new_time_scale)

    @getter
    def get_horizontal_scale(self):
        config = None
        try:
            config = self.get_current_config()
            return config["horizontal scale"]
        except:
            print(f'ERROR: {config}')

    @setter
    def set_horizontal_position(self, offset_sec):
        return self.set_by_command_id("horizontal position", offset_sec)

    @getter
    def get_horizontal_position(self):
        return self.get_current_config()["horizontal position"]

    @setter
    def set_scale_ch(self, scale, channel=None):
        new_volt_scale = tools.find_nearest(list(self._volt_scales.keys()), scale)
        return self.set_by_command_id(f"ch{channel} scale", new_volt_scale)
    
    @setter
    def set_ch1_scale(self, scale):
        return self.set_scale_ch(scale, 1)
    
    @setter
    def set_ch2_scale(self, scale):
        return self.set_scale_ch(scale, 2)
    
    @setter
    def set_ch3_scale(self, scale):
        return self.set_scale_ch(scale, 3)
    
    @setter
    def set_ch4_scale(self, scale):
        return self.set_scale_ch(scale, 4)
    
    @getter
    def get_ch1_scale(self):
        return self.get_current_config()["ch1 scale"]
    
    @getter
    def get_ch2_scale(self):
        return self.get_current_config()["ch2 scale"]
    
    @getter
    def get_ch3_scale(self):
        return self.get_current_config()["ch3 scale"]
    
    @getter
    def get_ch4_scale(self):
        return self.get_current_config()["ch4 scale"]

    @setter
    def set_ch1_coupling(self, coupling):
        return self.set_by_command_id("ch1 coupling", coupling)
    
    @setter
    def set_ch2_coupling(self, coupling):
        return self.set_by_command_id("ch2 coupling", coupling)
    
    @setter
    def set_ch3_coupling(self, coupling):
        return self.set_by_command_id("ch3 coupling", coupling)
    
    @setter
    def set_ch4_coupling(self, coupling):
        return self.set_by_command_id("ch4 coupling", coupling)
    
    @getter
    def get_ch1_coupling(self):
        return self.get_current_config()["ch1 coupling"]
    
    @getter
    def get_ch2_coupling(self):
        return self.get_current_config()["ch2 coupling"]
    
    @getter
    def get_ch3_coupling(self):
        return self.get_current_config()["ch3 coupling"]
    
    @getter
    def get_ch4_coupling(self):
        return self.get_current_config()["ch4 coupling"]
    
    @setter
    def set_ch1_enable(self, enable=True):
        return self.set_by_command_id("ch1 enable", enable)
    
    @setter
    def set_ch2_enable(self, enable=True):
        return self.set_by_command_id("ch2 enable", enable)
    
    @setter
    def set_ch3_enable(self, enable=True):
        return self.set_by_command_id("ch3 enable", enable)
    
    @setter
    def set_ch4_enable(self, enable=True):
        return self.set_by_command_id("ch4 enable", enable)

    @getter
    def get_ch1_enable(self):
        return self.get_current_config()["ch1 enable"]
    
    @getter
    def get_ch2_enable(self):
        return self.get_current_config()["ch2 enable"]
    
    @getter
    def get_ch3_enable(self):
        return self.get_current_config()["ch3 enable"]
    
    @getter
    def get_ch4_enable(self):
        return self.get_current_config()["ch4 enable"]
    
    @setter
    def set_ch1_bw_limit(self, bw_limit):
        return self.set_by_command_id("ch1 bw limit", bw_limit)
    
    @setter
    def set_ch2_bw_limit(self, bw_limit):
        return self.set_by_command_id("ch2 bw limit", bw_limit)
    
    @setter
    def set_ch3_bw_limit(self, bw_limit):
        return self.set_by_command_id("ch3 bw limit", bw_limit)
    
    @setter
    def set_ch4_bw_limit(self, bw_limit):
        return self.set_by_command_id("ch4 bw limit", bw_limit)
    
    @getter
    def get_ch1_bw_limit(self):
        return self.get_current_config()["ch1 bw limit"]
    
    @getter
    def get_ch2_bw_limit(self):
        return self.get_current_config()["ch2 bw limit"]
    
    @getter
    def get_ch3_bw_limit(self):
        return self.get_current_config()["ch3 bw limit"]
    
    @getter
    def get_ch4_bw_limit(self):
        return self.get_current_config()["ch4 bw limit"]
    
    @getter
    def get_scale_ch(self, channel=None):
        return self.get_current_config()[f"ch{channel} scale"]

    @setter
    def set_position_ch(self, position, channel=None):
        return self.set_by_command_id(f"ch{channel} position", position)

    @getter
    def get_position_ch(self, channel=None):
        return self.get_current_config()[f"ch{channel} position"]

    @setter
    def set_resolution(self, resolution):
        if resolution not in self._resolutions:
            raise ValueError(
                f"Invalid memory depth! "
                f"Memory depth must be one of: {', '.join(self._resolutions.keys())}"
            )
        return self.set_by_command_id("resolution", resolution)

    @getter
    def get_resolution(self):
        return self.get_current_config()["resolution"]

    @setter
    def set_state(self, state: str):
        if state.upper() in ["RUN"]:
            self.write(b":SDSLRUN#", encode=False)
        elif state.upper() in ["STOP"]:
            self.write(b":SDSLSTP#", encode=False)
            # there should be a response
            time.sleep(0.5)
            self.flush_buffer()
        else:
            raise ValueError(
                "Invalid state! "
                "State must be one of: ['RUN', 'STOP']"
            )

    @setter
    def force_trigger(self):
        self.write(":SDSLFOR#")

    @getter
    def get_triggered_status(self):
        self.write(":SGDT\x0f\x00\x00\x00\x00\x00\x00\x00\x00#".encode(), encode=False)
        return not (len(self._read_GDT_response()) == 0)

    @getter
    def get_state(self):
        self.write(":SGDT\x0f\x00\x00\x00\x00\x00\x00\x00\x00#".encode(), encode=False)
        return self._read_GDT_response(state_only=True)

    @setter
    def set_acquisition_mode(self, mode):
        if (mode.upper() not in self._acquisition_modes):
            raise ValueError(
                f"Mode must be in {self._acquisition_modes}"
            )
        return self.set_by_command_id("acquisition mode", mode)

    @getter
    def get_acquisition_mode(self):
        return self.get_current_config()["acquisition mode"]

    # I don't know how to make this work. when I went looking it didn't seem to send any messages
    # @setter
    # def set_acquire_averages(self, averages):
    #     if (averages in range(0,128)):
    #         # TODO figure out command. I did some looking and did see one
    #         #self._current_state["acquisition averages"] = averages
    #     else:
    #         raise ValueError(
    #             f"Mode must be in the range 0-128"
    #         )

    # @getter
    # def get_acquire_averages(self):
    #     return self._current_state["acquire averages"]

    ###################################################################
    ##          Triggering                                           ##
    ###################################################################

    def set_edge_trigger_settings(self, channel=None, sweep_mode=None, edge=None, level=None):
        # get current settings to use if no updates are provided
        config = self.get_current_config()

        if channel is not None:
            config["trigger channel"] = channel
        #print(f"Trigger Channel: {config['trigger channel']}")
        trigger_setting : OwonVDSScopeRaw.Setting = self.get_setting("trigger channel")

        setting_ids_mapping = {
                               "sweep mode": sweep_mode,
                               "trigger edge": edge,
                               "trigger level": level
                               }
        cmd = b"MTRs" + trigger_setting.to_bytes(config["trigger channel"]) + b"e\x02\x00"
        for setting_key, setting_value in setting_ids_mapping.items():
            if setting_value is None:
                setting_value = config[setting_key]
            setting: OwonVDSScopeRaw.Setting = self.get_setting(setting_key)
            if setting_key in [s.key for s in self._dependent_settings]:
                setting_bytes = setting.to_bytes(setting_value, config)
            else:
                setting_bytes = setting.to_bytes(setting_value)
            cmd += self.create_command_from_regex(
                setting.setting_regex,
                {setting_key: setting_bytes,
                 "trigger channel": trigger_setting.to_bytes(config["trigger channel"])
                 })
        #print(cmd)
        return self.send_m_command(cmd)

    @setter
    def set_trigger_source(self, channel):
        if channel not in self._channels.keys():
            raise ValueError(
                f"trigger source must be {self._channels.keys()}."
            )
        return self.set_edge_trigger_settings(channel=channel)

    @getter
    def get_trigger_source(self):
        return self.get_current_config()["trigger channel"]

    # @setter
    # def set_trigger_mode(self, mode, channel):
    #     if mode in self._trigger_modes.keys():
    #     setting: OwonVDSScopeRaw.Setting = self.get_setting("trigger mode")
    #     cmd = self.create_command_from_regex(setting.setting_regex, {id: setting.to_bytes(native_value)})
    #     return self.send_m_command(cmd)
    #     else:
    #         raise ValueError(
    #             f"trigger mode must be {self._trigger_modes.keys()}."
    #         )

    @getter
    def get_trigger_mode(self):
        return self.get_current_config()["trigger mode"]

    @setter
    def set_sweep_mode(self, mode):
        if mode.upper() not in self._sweep_modes:
            raise ValueError(
                f"Invalid sweep mode! "
                f"Sweep mode must be one of: {', '.join(self._sweep_modes)}"
            )

        if self.get_trigger_mode() not in self._supported_trigger_modes:
            raise ValueError(
                f"Invalid trigger mode! "
                f"Trigger mode must be one of: {', '.join(self._supported_trigger_modes)}"
            )
        return self.set_edge_trigger_settings(sweep_mode=mode)

    @getter
    def get_sweep_mode(self):
        return self.get_current_config()["sweep mode"]

    @setter
    def set_trigger_level(self, level_volts):
        if self.get_trigger_mode() not in self._supported_trigger_modes:
            raise ValueError(
                f"Invalid trigger mode! "
                f"Trigger mode must be one of: {', '.join(self._supported_trigger_modes)}"
            )
        return self.set_edge_trigger_settings(level=level_volts)

    @getter
    def get_trigger_level(self):
        return self.get_current_config()["trigger level"]

    @setter
    def set_trigger_edge(self, edge):
        if edge not in self._trigger_edges.keys():
            raise ValueError(
                f"Invalid trigger edge! "
                f"Edge must be one of: {', '.join(self._trigger_edges.keys())}"
            )
        if self.get_trigger_mode() not in self._supported_trigger_modes:
            raise ValueError(
                f"Invalid trigger mode! "
                f"Trigger mode must be one of: {', '.join(self._supported_trigger_modes)}"
            )
        return self.set_edge_trigger_settings(edge=edge)


    @getter
    def get_trigger_edge(self):
        return self.get_current_config()["trigger edge"]

    @measurer
    def measure_trigger_status(self):
        return self.get_triggered_status()

    ###################################################################
    ##          Read Trace Operations                                ##
    ###################################################################

    def _read_GDT_response_channel(self):
        HEADER_LENGTH = 32
        FOOTER_LENGTH = 100
        POST_HEADER_BYTES_OFFSET = 8
        MEMORY_DEPTH_OFFSET = 24
        try:
            header_data = self.read(nbytes=HEADER_LENGTH, timeout=10.0, termination=None, decode=False)
            num_data_bytes = struct.unpack("!I", header_data[MEMORY_DEPTH_OFFSET:MEMORY_DEPTH_OFFSET+4])[0]
            num_extra_bytes = struct.unpack("!I", header_data[POST_HEADER_BYTES_OFFSET:POST_HEADER_BYTES_OFFSET+4])[0] \
                - num_data_bytes - FOOTER_LENGTH
            raw_channel_data = self.read(nbytes=num_data_bytes, timeout=10.0, termination=None, decode=False)
            junk_data = self.read(nbytes=num_extra_bytes, timeout=10.0, termination=None, decode=False)
            footer_data = self.read(nbytes=FOOTER_LENGTH, timeout=10.0, termination=None, decode=False)
        except Exception:
            raw_channel_data = None
        return raw_channel_data

    def _read_GDT_response(self, state_only=False):
        """
        This reads the abbreviated trace from the scope.
        It will contain a maximum of 4k points per channel.
        """
        raw_channel_data = []
        response = self.read(nbytes=7, timeout=10.0, termination=None, decode=False)
        if not response.startswith(b":GDT"):
            # choosing not to raise an exception because this could easily
            # happen and it need not be fatal.
            # That said, we can't decode the message if it doesn't start with
            # ":GDM.""
            print(f"Unknown message {response}")
            self.flush_buffer()
            return None
        SUCCESS_MAYBE_OFFSET = 4
        STOP_STATE_OFFSET = 5
        if state_only:
            if response[STOP_STATE_OFFSET] == 4:
                state = "STOP"
            else:
                state = "RUN"
            # print(response[STOP_STATE_OFFSET], state)
            # it might be necessary to flush a lot from the buffer
            for i in range(0, 5):
                self.flush_buffer()
            return state
        if response[SUCCESS_MAYBE_OFFSET] == '\x00' or response[SUCCESS_MAYBE_OFFSET] == 0:
            # This is some sort of error state, but we're going to say it's
            # the same as no data.
            return []
        # We now know the message will be at least 16 bytes long (from experience)
        response += self.read(nbytes=9, timeout=10.0, termination=None, decode=False)
        DATA_PRESENT_OFFSET = 6
        # print(response[DATA_PRESENT_OFFSET])
        if response[DATA_PRESENT_OFFSET] == '\x00' or response[DATA_PRESENT_OFFSET] == 0:
            # At this point we know there's no more data and that the whole
            # message will be only 16 bytes long.
            return []
        # if we're here then there's more to read
        try:
            CHANNEL_BITFIELD_OFFSET = 7
            channels_in_response = self.parse_channels_in_response(
                response[CHANNEL_BITFIELD_OFFSET])
            BYTES_PER_CHANNEL_OFFSET = 8
            bytes_per_channel = struct.unpack("!I", response[BYTES_PER_CHANNEL_OFFSET:BYTES_PER_CHANNEL_OFFSET+4])[0]
            for channel in channels_in_response:
                raw_channel_data.append(self._read_GDT_response_channel())

            # We've finished reading the GDM message now so we can read the scope config to figure out the scaling.
            config = self.get_current_config()

            # Scale channel data
            channel_data = {}
            for i, raw_data in enumerate(raw_channel_data):
                ch_id = channels_in_response[i]
                channel_data[ch_id] = self.scale_channel_data(ch_id, raw_data, config)
        except Exception:
            channel_data = []
        return channel_data

    @setter
    def set_acquire(self, _):
        """
        This is a helper function to make sure scope triggers on something before reading the data.
        """
        self._acquiring = True
        self.set_sweep_mode("SINGLE")
        trig_status = self.get_triggered_status()
        if trig_status:
            # measurement has been triggered
            pass
        else:
            # sweep needs to be reset
            time.sleep(1)
            self.set_acquire(1)


    def _read_M_response(self):
        # Read 6 bytes
        HEADER_LENGTH = 6
        REMAINING_LENGTH_OFFSET = 2
        header_data = self.read(nbytes=HEADER_LENGTH, timeout=10.0, termination=None, decode=False)
        if not header_data.startswith(b":M"):
            # choosing not to raise an exception because this could easily happen
            # and it need not be fatal.
            # That said we can't decode the message if it doesn't start with :M
            # so delete everything else in the buffer and return None.
            if len(header_data) > 0:
                self.flush_buffer()
            return None
        remaining_length = struct.unpack("!I", header_data[REMAINING_LENGTH_OFFSET:REMAINING_LENGTH_OFFSET+4])[0]
        msg = self.read(nbytes=remaining_length, timeout=10.0, termination=None, decode=False)
        config = dict()
        for setting in self._independent_settings:
            parameter_index = setting.setting_regex.groupindex[setting.key.replace(" ", "_")]
            matches = setting.setting_regex.findall(msg)
            # Guard statment to reformat matches in the case that there is only 1 match because findall doesn't always return the same nested list format
            if len(matches) > 0 and type(matches[0]) is not tuple:
                matches = [matches]
            for match in matches:
                config[setting.key] = setting.from_bytes(match[parameter_index-1])

        for setting in self._dependent_settings:
            parameter_index = setting.setting_regex.groupindex[setting.key.replace(" ", "_")]
            matches = setting.setting_regex.findall(msg)
            # Guard statment to reformat matches in the case that there is only 1 match because findall doesn't always return the same nested list format
            if len(matches) > 0 and type(matches[0]) is not tuple:
                matches = [matches]
            for match in matches:
                config[setting.key] = setting.from_bytes(match[parameter_index-1], config)
        return config


    def get_current_config(self):
        """
        This function queries the scope for the current configuration.
        This function should not be interrupted.
        """
        config = None
        # raise Exception("don't want to call this function right now")
        while config is None:
            self.write(b":SGAL#", encode=False)
            config = self._read_M_response()
            if config is not None:
                break
            time.sleep(1.0)
        return config

    def parse_channels_in_response(self, channel_bitfield):
        channels_in_response = []
        for id in self._channels.keys():
            if (1 << (id-1)) & channel_bitfield:
                channels_in_response.append(id)
        return channels_in_response

    def _read_GDM_response_channel(self):
        """
        This helper function reads a single channel within a GDM response message and returns the raw channel data.
        """
        HEADER_LENGTH = 41
        MEMORY_DEPTH_OFFSET = 21
        header_data = self.read(nbytes=HEADER_LENGTH, timeout=300.0, termination=None, decode=False)
        num_data_bytes = struct.unpack("!I", header_data[MEMORY_DEPTH_OFFSET:MEMORY_DEPTH_OFFSET+4])[0]
        raw_channel_data = self.read(nbytes=num_data_bytes, timeout=300.0, termination=None, decode=False)
        return raw_channel_data

    def _read_GDM_response(self) -> dict:
        MESSAGE_HEADER_LENGTH = 11
        response = self.read(nbytes=MESSAGE_HEADER_LENGTH, timeout=10.0, termination=None, decode=False)
        if not response.startswith(b":GDM"):
            # choosing not to raise an exception because this could easily happen
            # and it need not be fatal.
            # That said we can't decode the message if it doesn't start with :GDM
            # so delete everything else in the buffer and return None.
            self.flush_buffer()
            return None

        CHANNEL_ID_BITFIELD_OFFSET = 6

        raw_channel_data = []
        channels_in_response = self.parse_channels_in_response(
            response[CHANNEL_ID_BITFIELD_OFFSET])
        # Actually read channel data
        for channel in channels_in_response:
            raw_channel_data.append(self._read_GDM_response_channel())
        
        # We've finished reading the GDM message now so we can read the scope config to figure out the scaling.
        config = self.get_current_config()

        # Scale channel data
        channel_data = {}
        for i, raw_data in enumerate(raw_channel_data):
            ch_id = channels_in_response[i]
            channel_data[ch_id] = self.scale_channel_data(ch_id, raw_data, config)
        return channel_data

    def scale_channel_data(self, channel_id, data, config):
        scale_factor = config[f"ch{channel_id} scale"]
        offset = config[f"ch{channel_id} position"]
        return [raw * scale_factor + offset for raw in data]

    def get_times(self, waveform_type: str = "GDM") -> list[float]:
        """
        Returns a list of floats indicating the times for the datapoints in the waveforms.

        waveform_type - a string either GDM for full waveform depth or GDT for shorter response.
        """
        settings = self.get_current_config()
        if waveform_type == "GDM":
            num_samples = int(settings["resolution"])
        elif waveform_type == "GDT":
            num_samples = int(min(settings["resolution"], 4000))
        else:
            raise (ValueError, "waveform_type must be in ['GDM', 'GDT'].")
        start = -10.0 * settings["horizontal scale"] - settings["horizontal position"]
        stop = 10.0 * settings["horizontal scale"] - settings["horizontal position"]
        print(start, stop, num_samples)
        return list(np.linspace(start=start, stop=stop, num=num_samples))

    def get_waveforms(self, acquire_first: bool = True) -> dict:
        """
        Gets waveform data from the scope at full memory depth.
        The data is returned as a dictionary of lists containing the voltage values.
        The keys are the channel numbers.
        
        acquire_first - if true, the application will wait until the
            the scope triggers on a new dataset before asking for the data
        """
        self.flush_buffer()
        if acquire_first:
            self.set_acquire(1)
        self._acquiring = False
        self.write(":SGDM\x00A\x00\x00\x00\x00#".encode(), encode=False)
        return self._read_GDM_response()

    @measurer
    def measure_channel_1(self):
        return self.get_waveforms()[1]

    @measurer
    def measure_channel_2(self):
        return self.get_waveforms()[2]
    
    @measurer
    def measure_channel_3(self):
        return self.get_waveforms()[3]
    
    @measurer
    def measure_channel_4(self):
        return self.get_waveforms()[4]


    # Digits represent number of bytes in that position in the message

    # Channel settings
    # M
    #  CH for channel
    #    1 byte for channel number
    #     v for voltage scale
    #      1 bytes for index in _volt_scales
    #     z for z offset
    #      4 bytes for value, 25x factor
    #     c for coupling
    #      1 byte for index in _coupling_modes
    #     o for output enable
    #      1 byte for enable, 1 enable, 0 disable
    #     b for bandwidth limit
    #      1 byte for bandwidth limit index
 
    # Trigger settings
    # M
    #  TR for trigger
    #    s for single
    #    a for alternate
    #     1 for channel number
    #      e for edge
    #       
    #      v for video
    #      s? for slope
    #      p? for pulse







    
    # def _read_data_ADC(self, channel):
    #     volts_per_div = self.get_scale_ch(channel)
    #     resolution = self.get_resolution()
    #     voltages = []
    #     while (len(voltages) < resolution):
    #         self.write(f"*ADC? {self._channels[channel]}")
    #         raw_bytes_to_read = read_from_socket(
    #             self.adapter.backend,
    #             nbytes=4,
    #             termination=None,
    #             decode=False,
    #             timeout=self.adapter.timeout
    #         )
    #         num_bytes_to_read = int.from_bytes(raw_bytes_to_read, "big")

    #         raw_values = read_from_socket(
    #             self.adapter.backend,
    #             nbytes=num_bytes_to_read,
    #             termination=None,
    #             decode=False,
    #             timeout=self.adapter.timeout
    #         )

    #         voltages.extend([float(value/25.0*volts_per_div) for value in raw_values])

    #     return voltages

    # def _read_data(self, channel):
    #     config = self.get_current_config()
    #     save_path = self._save_traces('C:\\scratch'.upper())
    #     time.sleep(30)
    #     # previous_file_size = 0
    #     # file_size = 1
    #     # counter = 0
    #     # # while (previous_file_size != file_size):
    #     # while(file_size < config["Horizontal"]["sample depth"]+327):
    #     #     time.sleep(2) # sleep for 2 seconds so that the binary file is not opened unitl writing is complete.
    #     #     previous_file_size = file_size
    #     #     file_size = os.path.getsize(save_path)
    #     #     counter += 1
    #     # print(f'Slept {counter} times')
    #     channel_data = self._read_saved_binary_file(save_path, config)
    #     # extract data for 1 channel
    #     selected_channel = channel_data[self._channels[channel]]['trace data']
    #     return np.array(selected_channel, dtype=np.float64)

