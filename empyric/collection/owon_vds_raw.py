import struct
import numpy as np
import time


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
                "write_termination": "",
                "read_termination": None,
                "timeout": 0.5,
            },
        ),
    )

    knobs = (
        "horz scale",
        "horz position",
        "scale ch1",
        "position ch1",
        "scale ch2",
        "position ch2",
        "scale ch3",
        "position ch3",
        "scale ch4",
        "position ch4",
        "sweep mode",
        "trigger level",
        "trigger source",
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
        "sweep mode": "NORMAL",
        "trigger source": 1,
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
        5.0e-6: bytearray([10]),
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
        5.0: bytearray([10]),
    }

    _volt_div_table = {0: 1e-3, 9: 1.0}

    _resolutions = {
        1e3: bytearray([0]),
        1e4: bytearray([1]),
        1e5: bytearray([2]),
        1e6: bytearray([3]),
        5e6: bytearray([4])
    }

    _sweep_modes = {
        "AUTO": bytearray([0]),
        "NORMAL": bytearray([1]),
        "SINGLE": bytearray([2])
        }

    _acquire_modes = {
        "SAMPLE": bytearray([0]),
        "AVERAGE": bytearray([1]), # guess
        "PEAK": bytearray([2]) # guess
    }

    _coupling_modes = {
        "DC": bytearray([0]),
        "AC": bytearray([1]),
        "GND": bytearray([2])
    }

    _trigger_modes = {
        "EDGE": "e".encode(),
        "VIDEO": "v".encode(),
        "SLOPE": "s".encode(),
        "PULSE": "p".encode()
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

    _command_identifiers = {
        #"get version": bytearray.fromhex('3a5344534c56455223'),
        "get version": ":SDSLVER#".encode(),
        #"set horz scale": bytearray.fromhex('4d485262'),
        "set horz scale": "MHRb".encode(),
        #"set horz position": bytearray.fromhex('4d485276'),
        "set horz position": "MHRv".encode(),
        "set ch1 scale": bytearray.fromhex('4d43480076'),
        "set ch2 scale": bytearray.fromhex('4d43480176'),
        "set ch3 scale": bytearray.fromhex('4d43480276'),
        "set ch4 scale": bytearray.fromhex('4d43480376'),
        "trigger ": "MTR".encode(),
        "set sweep mode": bytearray.fromhex('03'),
        "set trigger hold off": bytearray.fromhex('04'),
        "set trigger edge": bytearray.fromhex('05'),
        "set trigger level": bytearray.fromhex('06'),
        "get traces short": bytearray.fromhex('3a534744540f000000000000000023'),
        "get traces full": bytearray.fromhex('3a5347444d00410000000023'),
        "run": bytearray.fromhex('3a5344534c52554e23')
    }

    # Digits represent number of bytes in that position in the message

    # Channel settings
    # M
    #  CH for channel
    #    1 byte for channel number
    #     v for voltage scale
    #      1 bytes for index in _volt_scales
    #     z for z offset
    #      4 bytes for value, 25x factor
    #     o for coupling
    #      1 byte for index in _coupling_modes
 
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


    _current_state = {
        "horz scale": None,
        "horz position": None,
        "ch1 scale": None,
        "ch1 position": None,
        "ch2 scale": None,
        "ch2 position": None,
        "ch3 scale": None,
        "ch3 position": None,
        "ch4 scale": None,
        "ch5 position": None,
        "trigger source": 1,
        "trigger mode": "EDGE",
        "trigger level": 0.0,
        "trigger edge": None,
        "sweep mode": None,
        "resolution": None,
        "state": None,
        "acquire mode": None,
        "acquire averages": None
    }

    def raw_query(self, question):
        return self.query(question, encode=False, decode=False)

    def send_m_command(self, cmd):
        cmd_prefix = ":M".encode() + struct.pack('!I', len(cmd))
        return self.write(cmd_prefix + cmd, encode=False)

    @setter
    def set_horz_scale(self, scale):
        new_time_scale = find_nearest(list(self._time_scales.keys()), scale)

        result = self.send_m_command(
            self._command_identifiers["set horz scale"]
            + self._time_scales[new_time_scale])
        if result == "Success":
            self._current_state["horz scale"] = new_time_scale

    @getter
    def get_horz_scale(self):
        return self._current_state["horz scale"]

    @setter
    def set_horz_position(self, offset_sec):
        SCALE_FACTOR = 50
        offset_raw = int(SCALE_FACTOR*(offset_sec / self.get_horz_scale()))

        result = self.send_m_command(
            self._command_identifiers["set horz position"]
            + struct.pack('!I', offset_raw))
        if result == "Success":
            self._current_state["horz position"] = offset_sec

    @getter
    def get_horz_position(self):
        return self._current_state["horz position"]

    def _set_scale_ch(self, channel, scale):
        new_volt_scale = find_nearest(list(self._volt_scales.keys()), scale)
        channel_name = self._channels[channel]

        result = self.send_m_command(
            self._command_identifiers[f"set {channel_name.lower()} scale"]
            + self._time_scales[new_volt_scale])
        if result == "Success":
            self._current_state[f"{channel_name.lower()} scale"] = new_volt_scale

    def _get_scale_ch(self, channel):
        channel_name = self._channels[channel]
        return self._current_state[f"{channel_name.lower()} scale"]

    def _set_position_ch(self, channel, position):
        SCALE_FACTOR = 25
        channel_name = self._channels[channel].lower()
        position_raw = int(SCALE_FACTOR*(position / self._get_scale_ch(channel)))

        result = self.send_m_command(
            self._command_identifiers[f"set {channel_name} position"]
            + struct.pack('!I', position_raw))
        if result == "Success":
            self._current_state[f"{channel_name} position"] = position
        pass

    @setter
    def set_scale_ch(self, scale, channel=None):
        self._set_scale_ch(channel, scale)

    @getter
    def get_scale_ch(self, channel=None):
        return self._get_scale_ch(channel)

    @setter
    def set_position_ch(self, position, channel=None):
        self._set_position_ch(channel, position)

    @getter
    def get_position_ch(self, channel=None):
        channel_name = self._channels[channel].lower()
        return self._current_state[f"{channel_name.lower()} position"]
    
    ###################################################################
    ##          Triggering                                           ##
    ###################################################################

    @setter
    def set_trigger_source(self, source):
        if source in self._channels.keys():
            # Scope has no command to set trigger source.
            # Instead set all the other trigger parameters
            self._current_state[f"trigger source"] = source
            self.set_trigger_mode(self.get_trigger_mode())
            self.set_sweep_mode(self.get_sweep_mode())
            self.set_trigger_edge(self.get_trigger_edge())
            self.set_trigger_level(self.get_trigger_level())
            
        else:
            raise ValueError(
                f"trigger source must be {self._channels.keys()}."
            )

    @getter
    def get_trigger_source(self):
        return self._current_state[f"trigger source"]

    @setter
    def set_trigger_mode(self, mode):
        if mode in self._trigger_modes.keys():
            self._current_state["trigger mode"] = mode
        else:
            raise ValueError(
                f"trigger mode must be {self._trigger_modes.keys()}."
            )

    @getter
    def get_trigger_mode(self):
        return self._current_state["trigger mode"]

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
        
        trigger_channel_index = self.get_trigger_source() - 1

        result = self.send_m_command(
            "MTRs".encode()
            + struct.pack('B', trigger_channel_index)
            + self._trigger_modes[self.get_trigger_mode()]
            + self._command_identifiers["set sweep mode"]
            + self._sweep_modes[mode])
        if result == "Success":
            self._current_state["sweep mode"] = mode

    @getter
    def get_sweep_mode(self):
        return self._current_state["sweep mode"]

    @setter
    def set_trigger_level(self, level_volts):
        if self.get_trigger_mode() not in self._supported_trigger_modes:
            raise ValueError(
                f"Invalid trigger mode! "
                f"Trigger mode must be one of: {', '.join(self._supported_trigger_modes)}"
            )
        
        trigger_channel_index = self.get_trigger_source() - 1

        scale = self._get_scale_ch(self.get_trigger_source())

        level_scaled = int(25 * level_volts / scale)

        result = self.send_m_command(
            "MTRs".encode()
            + struct.pack('B', trigger_channel_index)
            + self._trigger_modes[self.get_trigger_mode()]
            + self._command_identifiers["set trigger level"]
            + struct.pack('!i', level_scaled))
        if result == "Success":
            self._current_state["trigger level"] = level_volts

    @getter
    def get_trigger_level(self):
        return self._current_state["trigger level"]
    

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
        
        trigger_channel_index = self.get_trigger_source() - 1

        result = self.send_m_command(
            "MTRs".encode()
            + struct.pack('B', trigger_channel_index)
            + self._trigger_modes[self.get_trigger_mode()]
            + self._command_identifiers["set trigger edge"]
            + self._trigger_edges[edge])
        if result == "Success":
            self._current_state["trigger edge"] = edge

    @getter
    def get_trigger_edge(self):
        return self._current_state["trigger edge"]

    @measurer
    def measure_trigger_status(self):
        return self.get_triggered_status()

    ###################################################################
    ##          Operations                                           ##
    ###################################################################

    @setter
    def set_resolution(self, resolution):
        if resolution in self._resolutions:
            self.send_m_command(
                "MDP".encode()
                + self._resolutions[resolution]
            )
        else:
            raise ValueError(
                f"Invalid memory depth! "
                f"Memory depth must be one of: {', '.join(self._resolutions.keys())}"
            )

    @getter
    def get_resolution(self):
        return self._current_state["resolution"]

    @setter
    def set_state(self, state):
        if state.upper() in ["RUN"]:
            self.write(":SDSLRUN#")
            self._current_state["state"] = "RUN"
        elif state.upper() in ["STOP"]:
            self.write(":SDSLSTP#")
            self._current_state["state"] = "STOP"
        else:
            raise ValueError(
                "Invalid state! "
                "State must be one of: ['RUN', 'STOP']"
            )

    @setter
    def force_trigger(self):
        self.write(":SDSLFOR#")

    def flush_buffer(self):
        """
        Not sure how to do this yet.
        """
        self.read(n_bytes=1e6, timeout=0.1, termination=None, decode=False)

    def read_GDT_response_channel(self):
        HEADER_LENGTH = 32
        FOOTER_LENGTH = 100
        POST_HEADER_BYTES_OFFSET = 8
        MEMORY_DEPTH_OFFSET = 24
        header_data = self.read(n_bytes=HEADER_LENGTH, timeout=1.0, termination=None, decode=False)
        num_data_bytes = struct.decode("!I", header_data[MEMORY_DEPTH_OFFSET:MEMORY_DEPTH_OFFSET+4])
        num_extra_bytes = struct.decode("!I", header_data[POST_HEADER_BYTES_OFFSET:POST_HEADER_BYTES_OFFSET+4]) \
            - num_data_bytes - FOOTER_LENGTH
        raw_channel_data = self.read(n_bytes=num_data_bytes, timeout=1.0, termination=None, decode=False)
        junk_data = self.read(n_bytes=num_extra_bytes, timeout=1.0, termination=None, decode=False)
        footer_data = self.read(n_bytes=FOOTER_LENGTH, timeout=1.0, termination=None, decode=False)
        return raw_channel_data

    def read_GDT_response(self):
        raw_data = []
        response = self.read(n_bytes=7, timeout=1.0, termination=None, decode=False)
        if not response.startswith(":GDT"):
            # choosing not to raise an exception because this could easily
            # happen and it need not be fatal.
            # That said, we can't decode the message if it doesn't start with
            # ":GDM.""
            self.flush_buffer()
            return None
        SUCCESS_MAYBE_OFFSET = 4
        if response[SUCCESS_MAYBE_OFFSET] == '\x00':
            # This is some sort of error state, but we're going to say it's
            # the same as no data.
            return []
        # We now know the message will be at least 16 bytes long (from experience)
        response += self.read(n_bytes=9, timeout=1.0, termination=None, decode=False)
        DATA_PRESENT_OFFSET = 6
        if response[DATA_PRESENT_OFFSET] == '\x00':
            # At this point we know there's no more data and that the whole
            # message will be only 16 bytes long.
            return []
        # if we're here then there's more to read
        CHANNEL_BITFIELD_OFFSET = 7
        channels_in_response = self.parse_channels_in_response(
            response[CHANNEL_BITFIELD_OFFSET])
        BYTES_PER_CHANNEL_OFFSET = 8
        bytes_per_channel = struct.decode("!I", response[BYTES_PER_CHANNEL_OFFSET:BYTES_PER_CHANNEL_OFFSET+4])
        for channel in channels_in_response:
            raw_data.append(self.read_GDT_response_channel())
        # now to do the scaling
        # TODO do scaling
        return raw_data



    @getter
    def get_triggered_status(self):
        self.write(":SGDT\x0f\x00\x00\x00\x00\x00\x00\x00\x00#".encode(), encode=False)
        return not (len(self.read_GDT_response()) == 0)

    @getter
    def get_state(self):
        return self._current_state["state"]

    @setter
    def set_acquire_mode(self, mode):
        if (mode.upper() in self._acquire_modes):
            self.send_m_command("MAQ".encode()+self._acquire_modes[mode.upper()])
            self._current_state["acquire mode"] = mode.upper()
        else:
            raise ValueError(
                f"Mode must be in {self._acquire_modes}"
            )

    @getter
    def get_acquire_mode(self):
        return self._current_state["acquire mode"]

    @setter
    def set_acquire_averages(self, averages):
        if (averages in range(0,128)):
            # TODO figure out command
            self._current_state["acquire averages"] = averages
        else:
            raise ValueError(
                f"Mode must be in the range 0-128"
            )

    @getter
    def get_acquire_averages(self):
        return self._current_state["acquire averages"]

    @setter
    def set_acquire(self, _):
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

    def _read_data_ADC(self, channel):
        volts_per_div = self.get_scale_ch(channel)
        resolution = self.get_resolution()
        voltages = []
        while (len(voltages) < resolution):
            self.write(f"*ADC? {self._channels[channel]}")
            raw_bytes_to_read = read_from_socket(
                self.adapter.backend,
                nbytes=4,
                termination=None,
                decode=False,
                timeout=self.adapter.timeout
            )
            num_bytes_to_read = int.from_bytes(raw_bytes_to_read, "big")

            raw_values = read_from_socket(
                self.adapter.backend,
                nbytes=num_bytes_to_read,
                termination=None,
                decode=False,
                timeout=self.adapter.timeout
            )

            voltages.extend([float(value/25.0*volts_per_div) for value in raw_values])

        return voltages

    def _read_data(self, channel):
        config = self.get_current_config()
        save_path = self._save_traces('C:\\scratch'.upper())
        time.sleep(30)
        # previous_file_size = 0
        # file_size = 1
        # counter = 0
        # # while (previous_file_size != file_size):
        # while(file_size < config["Horizontal"]["sample depth"]+327):
        #     time.sleep(2) # sleep for 2 seconds so that the binary file is not opened unitl writing is complete.
        #     previous_file_size = file_size
        #     file_size = os.path.getsize(save_path)
        #     counter += 1
        # print(f'Slept {counter} times')
        channel_data = self._read_saved_binary_file(save_path, config)
        # extract data for 1 channel
        selected_channel = channel_data[self._channels[channel]]['trace data']
        return np.array(selected_channel, dtype=np.float64)

    
    def get_current_config(self):
        return {
            "Horizontal": {
                "scale": self.get_horz_scale(),
                "offset": self.get_horz_position(),
                "sample depth": self.get_resolution()
            },
            "CH1": {
                "scale": self.get_scale_ch(1),
                "offset": self.get_position_ch(1)
            },
            "CH2": {
                "scale": self.get_scale_ch(2),
                "offset": self.get_position_ch(2)
            },
            "CH3": {
                "scale": self.get_scale_ch(3),
                "offset": self.get_position_ch(3)
            },
            "CH4": {
                "scale": self.get_scale_ch(4),
                "offset": self.get_position_ch(4)
            }
        }

    def parse_channels_in_response(self, channel_bitfield):
        channels_in_response = []
        for id in self._channels.keys():
            if (1 << (id-1)) & channel_bitfield:
                channels_in_response.append(id)
        return channels_in_response

    def read_GDM_response_channel(self):
        HEADER_LENGTH = 41
        MEMORY_DEPTH_OFFSET = 21
        header_data = self.read(n_bytes=HEADER_LENGTH, timeout=1.0, termination=None, decode=False)
        num_data_bytes = struct.decode("!I", header_data[MEMORY_DEPTH_OFFSET:MEMORY_DEPTH_OFFSET+4])
        raw_channel_data = self.read(n_bytes=num_data_bytes, timeout=1.0, termination=None, decode=False)
        return raw_channel_data

    def read_GDM_response(self) -> dict:
        MESSAGE_HEADER_LENGTH = 11
        response = self.read(n_bytes=MESSAGE_HEADER_LENGTH, timeout=1.0, termination=None, decode=False)
        if not response.startswith(":GDM"):
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
            raw_channel_data.append(self.read_GDM_response_channel())

        # Scale channel data
        channel_data = {}
        for i, channel in enumerate(raw_channel_data):
            ch_id = channels_in_response[i]
            channel_data[ch_id] = self.scale_channel_data(ch_id)

        return channel_data

    def scale_channel_data(self, channel_id, data, config):
        scale_factor = config[f'CH{channel_id}']["scale"]
        offset = config[f'CH{channel_id}']["offset"]
        return [raw * scale_factor + offset for raw in data]

    @getter
    def get_times(self, waveform_type: str = "GDM") -> list(float):
        """
        Returns a list of floats indicating the times for the datapoints in the waveforms.

        waveform_type - a string either GDM for full waveform depth or GDT for shorter response.
        """
        settings = self.get_current_config()
        if waveform_type == "GDM":
            num_samples = settings["Horizontal"]["sample depth"]
        elif waveform_type == "GDT":
            num_samples = min(settings["Horizontal"]["sample depth"], 4000)
        else:
            raise (ValueError, "waveform_type must be in ['GDM', 'GDT'].")
        start = -10.0 * settings["Horizontal"]["scale"] - settings["Horizontal"]["offset"]
        stop = 10.0 * settings["Horizontal"]["scale"] - settings["Horizontal"]["offset"]
        return list(np.linspace(start=start, stop=stop, num=num_samples))

    @getter
    def get_waveforms(self, acquire_first: bool = True) -> dict:
        """
        Gets waveform data from the scope at full memory depth.
        The data is returned as a dictionary of lists containing the voltage values.
        The keys are the channel numbers.
        
        acquire_first - if true, the application will wait until the
            the scope triggers on a new dataset before asking for the data
        """
        if acquire_first:
            self.set_acquire()
        self.write(":SGDM\x00A\x00\x00\x00\x00#".encode(), encode=False)
        return self.read_GDM_response()

    @measurer
    def measure_channel_1(self):
        if not self._acquiring:
            self.set_acquire(True)

        self._acquiring = False

        data = self._read_data(1)

        return data

    @measurer
    def measure_channel_2(self):
        if not self._acquiring:
            self.set_acquire(True)

        self._acquiring = False

        self.write(":WAV:BEG CH2")

        data = self._read_data(2)

        self.write(":WAV:END CH2")

        return data[1]
