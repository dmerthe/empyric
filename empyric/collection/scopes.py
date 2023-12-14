import socket
import struct
import numpy as np
from empyric.adapters import *
from empyric.collection.instrument import *
from empyric.types import Float, Array, Integer, String
from empyric.tools import read_from_socket, write_to_socket, find_nearest
import os
import time
import re
from typing import Callable


class TekTDSScope(Instrument):
    """
    Tektronix oscillscope of the TDS200, TDS1000/2000, TDS1000B/2000B,
    TPS2000 series.

    Although there are up to four channels, the constructor checks the model
    number for the actual number of supported channels. With the 2-channel
    models, any methods relating to channels 3 or 4 will take no action.

    2-Channel models: TXX1001, TXX1002, TXX1012, TXX2002, TXX2012, TXX2022

    4-channel models: TXX2004, TXX2014
    """

    name = "TekScope"

    supported_adapters = ((USB, {"timeout": 10}),)

    knobs = (
        "horz scale",
        "horz position",
        "ch1 scale",
        "ch1 position",
        "ch2 scale",
        "ch2 position",
        "ch3 scale",
        "ch3 position",
        "ch4 scale",
        "ch4 position",
        "trigger level",
    )

    meters = (
        "channel 1",
        "channel 2",
        "channel 3",
        "channel 4",
    )

    channels = 0

    two_channel_models = [1001, 1002, 1012, 2002, 2012, 2022]
    four_channel_models = [2004, 2014]

    def __init__(self, *args, **kwargs):
        # Check for number of channels before standard initialization
        adapter = USB(Instrument(args[0]))

        self.model = int(re.search("\d\d\d\d", adapter.query("*IDN?"))[0])

        adapter.disconnect()

        if self.model in self.two_channel_models:
            self.channels = 2
        elif self.model in self.four_channel_models:
            self.channels = 4

        super().__init__(*args, **kwargs)

    # Horizontal

    @setter
    def set_horz_scale(self, scale: Float):
        self.write("HOR:SCA %.3e" % scale)

    @getter
    def get_horz_scale(self) -> Float:
        return float(self.query("HOR:SCA?"))

    @setter
    def set_horz_position(self, position: Float):
        self.write("HOR:POS %.3e" % position)

    @getter
    def get_horz_position(self) -> Float:
        return float(self.query("HOR:POS?"))

    # Channel 1

    @setter
    def set_ch1_scale(self, scale: Float):
        self.write("CH1:SCA %.3e" % scale)

    @getter
    def get_ch1_scale(self) -> Float:
        return float(self.query("CH1:SCA?"))

    @setter
    def set_ch1_position(self, position: Float):
        self.write("CH1:POS %.3e" % position)

    @getter
    def get_ch1_position(self) -> Float:
        return float(self.query("CH1:POS?"))

    @measurer
    def measure_channel_1(self) -> Array:
        return self._measure_channel(1)

    # Channel 2

    @setter
    def set_ch2_scale(self, scale: Float):
        self.write("CH2:SCA %.3e" % scale)

    @getter
    def get_ch2_scale(self) -> Float:
        return float(self.query("CH2:SCA?"))

    @setter
    def set_ch2_position(self, position: Float):
        self.write("CH2:POS %.3e" % position)

    @getter
    def get_ch2_position(self) -> Float:
        return float(self.query("CH2:POS?"))

    @measurer
    def measure_channel_2(self) -> Array:
        return self._measure_channel(2)

    # Channel 3

    @setter
    def set_ch3_scale(self, scale: Float):
        if self.channels > 2:
            self.write("CH3:SCA %.3e" % scale)
        else:
            return np.nan

    @getter
    def get_ch3_scale(self) -> Float:
        if self.channels > 2:
            return float(self.query("CH3:SCA?"))
        else:
            return np.nan

    @setter
    def set_ch3_position(self, position: Float):
        if self.channels > 2:
            self.write("CH3:POS %.3e" % position)
        else:
            return np.nan

    @getter
    def get_ch3_position(self) -> Float:
        if self.channels > 2:
            return float(self.query("CH3:POS?"))
        else:
            return np.nan

    @measurer
    def measure_channel_3(self) -> Array:
        if self.channels > 2:
            return self._measure_channel(3)
        else:
            return [np.nan]

    # Channel 4

    @setter
    def set_ch4_scale(self, scale: Float):
        if self.channels > 2:
            self.write("CH4:SCA %.3e" % scale)
        else:
            return np.nan

    @getter
    def get_ch4_scale(self) -> Float:
        if self.channels > 2:
            return float(self.query("CH4:SCA?"))
        else:
            return np.nan

    @setter
    def set_ch4_position(self, position: Float):
        if self.channels > 2:
            self.write("CH4:POS %.3e" % position)
        else:
            return np.nan

    @getter
    def get_ch4_position(self) -> Float:
        if self.channels > 2:
            return float(self.query("CH4:POS?"))
        else:
            return np.nan

    @measurer
    def measure_channel_4(self) -> Array:
        if self.channels > 2:
            return self._measure_channel(4)
        else:
            return [np.nan]

    # Trigger

    @setter
    def set_trigger_level(self, level: Float):
        self.write("TRIG:MAI:LEV %.3e" % level)

    @getter
    def get_trigger_level(self) -> Float:
        return float(self.query("TRIG:MAI:LEV?"))

    def _measure_channel(self, n):
        self.write("DAT:ENC ASCI")  # ensure ASCII encoding of data
        self.write("DAT:SOU CH%d" % n)  # switch to channel n

        scale_factor = float(self.query("WFMPRE:YMULT?"))
        zero = float(self.query("WFMPRE:YZERO?"))
        offset = float(self.query("WFMPRE:YOFF?"))

        self.write("ACQ:STATE RUN")  # acquire the waveform

        while int(self.query("BUSY?")):
            time.sleep(0.25)  # wait for acquisition to complete

        normal_timeout = self.adapter.timeout
        self.adapter.timeout = 60

        response = self.query("CURVE?")

        str_data = response.split(",")

        self.adapter.timeout = normal_timeout

        return np.array(
            [(float(datum) - offset) * scale_factor + zero for datum in str_data]
        )


class MulticompProScope(Instrument):
    """
    Multicomp Pro PC Oscilloscope.

    NOT TESTED
    """

    """Supported adapters and options."""
    supported_adapters = (
        (
            Socket,
            {
                "write_termination": "\n",
                "read_termination": "\n",
                "timeout": 60,  # waveform retrieval may take some extra time
            },
        ),
        (
            USB, {"timeout": 10}
        ),
    )

    knobs = (
        "horz scale",
        "horz position",
        "scale ch1",
        "position ch1",
        "scale ch2",
        "position ch2",
        "sweep mode",
        "trigger level",
        "trigger source",
        "sweep mode",
        "resolution",
        "acquire",
        "state",
    )

    meters = (
        "channel 1",
        "channel 2",
    )

    presets = {
        "resolution": "100000",
        "sweep mode": "SINGLE",
        "trigger source": 1,
    }

    _time_scales = {
        2e-9: "2.0ns",
        5e-9: "5.0ns",
        10e-9: "10ns",
        20e-9: "20ns",
        50e-9: "50ns",
        100e-9: "100ns",
        200e-9: "200ns",
        500e-9: "500ns",
        1e-6: "1.0us",
        2e-6: "2.0us",
        5e-6: "5.0us",
        10e-6: "10us",
        20e-6: "20us",
        50e-6: "50us",
        100e-6: "100us",
        200e-6: "200us",
        500e-6: "500us",
        1e-3: "1.0ms",
        2e-3: "2.0ms",
        5e-3: "5.0ms",
        10e-3: "10ms",
        20e-3: "20ms",
        50e-3: "50ms",
        100e-3: "100ms",
        200e-3: "200ms",
        500e-3: "500ms",
        1: "1.0s",
        2: "2.0s",
        5: "5.0s",
        10: "10s",
        20: "20s",
        50: "50s",
        100: "100s",
    }

    _volt_scales = {
        2e-3: "2mv",
        5e-3: "5mv",
        10e-3: "10mv",
        20e-3: "20mv",
        50e-3: "50mv",
        100e-3: "100mv",
        200e-3: "200mv",
        500e-3: "500mv",
        1.0: "1v",
        2.0: "2v",
        5.0: "5v",
    }

    _volt_div_table = {0: 1e-3, 9: 1.0}

    _resolutions = {1e3: "1K", 1e4: "10K", 1e5: "100K", 1e6: "1M", 1e7: "10M"}

    _sweep_modes = ["AUTO", "NORMAL", "NORM", "SINGLE", "SING"]

    _acquiring = False

    @setter
    def set_horz_scale(self, scale):
        new_time_scale = find_nearest(list(self._time_scales.keys()), scale)

        self.write(":HORI:SCAL " + self._time_scales[new_time_scale])

    @getter
    def get_horz_scale(self):
        time_scales_rev = {val: key for key, val in self._time_scales.items()}

        time_scale_str = self.query(":HORI:SCAL?")[:-2]

        return time_scales_rev[time_scale_str]

    @setter
    def set_horz_position(self, offset):
        self.write(":HORI:OFFS " + str(offset))

    @getter
    def get_horz_position(self):
        return float(self.query(":HORI:OFFS?")[:-2])

    def _set_scale_ch(self, channel, scale):
        new_volt_scale = find_nearest(list(self._volt_scales.keys()), scale)

        scale_str = self._volt_scales[new_volt_scale]

        self.write((":CHAN%d:SCAL " % channel) + scale_str)

    def _get_scale_ch(self, channel):
        volt_scale_str = self.query(":CHAN%d:SCAL?" % channel)[:-2]

        if "mv" in volt_scale_str.lower():
            return 1e-3 * float(volt_scale_str[:-2])
        elif "v" in volt_scale_str.lower():
            return float(volt_scale_str[:-1])
        else:
            return float("nan")

    def _set_position_ch(self, channel, position):
        self.write((":CHAN%d:OFFS " % channel) + str(position))

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
        return float(self.query(":CHAN%d:OFFS?" % channel)[:-2])

    @setter
    def set_sweep_mode(self, mode):
        if mode.upper() not in self._sweep_modes:
            raise ValueError(
                f"Invalid sweep mode! "
                f"Sweep mode must be one of: {', '.join(self._sweep_modes)}"
            )

        self.write(":TRIG:SING:SWE " + mode.upper())

    @getter
    def get_sweep_mode(self):
        return self.query(":TRIG:SING:SWE?")[:-2].upper()

    @setter
    def set_trigger_source(self, source):
        self.write(":TRIG:SING:EDGE:SOUR CH%d" % int(source))

    @getter
    def get_trigger_source(self):
        source = self.query(":TRIG:SING:EDGE:SOUR?")[:-2]

        if source == "CH1":
            return 1
        elif source == "CH2":
            return 2

    @setter
    def set_trigger_level(self, level_volts):
        trigger_source = self.get_trigger_source()

        scale = self._get_scale_ch(trigger_source)

        level_div = str(level_volts / scale)

        self.write(":TRIG:SING:EDGE:LEV " + level_div)

    @getter
    def get_trigger_level(self):
        trigger_source = self.get_trigger_source()

        scale = self._get_scale_ch(trigger_source)

        return float(self.query(":TRIG:SING:EDGE:LEV?")[:-2]) * scale

    @measurer
    def measure_trigger_status(self):
        return self.query(":TRIG:STATUS?")[:-2]

    @setter
    def set_resolution(self, resolution):
        if resolution not in self._resolutions:
            raise ValueError(
                f"Invalid memory depth! "
                f"Memory depth must be one of: {', '.join(self._resolutions)}"
            )

        self.write(":ACQ:DEPMEM " + self._resolutions[resolution])

    @getter
    def get_resolution(self):
        res_rev = {val: key for key, val in self._resolutions.items()}

        return res_rev[self.query(":ACQ:DEPMEM?")[:-2]]

    @setter
    def set_state(self, state):
        if state.upper() in ["RUN", "STOP"]:
            self.write(f":{state.upper()}")

    @setter
    def set_acquire(self, _):
        self._acquiring = True

        self.set_sweep_mode("SINGLE")

        trig_status = self.measure_trigger_status()

        if trig_status == "TRIG":
            # measurement has been triggered
            pass
        else:
            # sweep needs to be reset
            time.sleep(0.1)
            self.set_acquire(1)

    def _read_preamble(self, channel):
        info_dict = {}

        preamble = self.query(":WAV:PRE?", binary=True)

        header, info = preamble[:11], preamble[11:]

        if header != b"#9000000000":  # indicates empty data buffer
            try:
                # First 8 bytes is an integer signature, used for verification
                ver_int = 651058244139746640
                verified = struct.unpack("<q", info[:8])[0] == ver_int

                if verified:
                    if channel == 1:
                        scale = self._volt_div_table[
                            struct.unpack("<h", info[260:262])[0]
                        ]
                        zero = struct.unpack("<f", info[268:272])[0]
                    else:
                        scale = self._volt_div_table[
                            struct.unpack("<h", info[262:264])[0]
                        ]
                        zero = struct.unpack("<f", info[272:276])[0]

                    sample_rate = struct.unpack("<f", info[316:320])[0] * 1e6
                    # Hz

                    info_dict["scale"] = scale
                    info_dict["zero"] = zero
                    info_dict["sample rate"] = sample_rate
                else:
                    print(
                        f"Warning: {self.name} received unverified "
                        f"signature when reading from channel {channel}"
                    )

            except struct.error:
                print(
                    f"Warning: {self.name} received truncated preamble when "
                    f"reading from channel {channel}"
                )

        self._sample_rate = info["sample rate"]

        return info_dict

    def _read_data(self, channel):
        info = self._read_preamble(channel)

        if info:
            scale = info["scale"]
            zero = info["zero"]
        else:
            return None

        # Only 256k data points can be read at a time
        resolution = int(
            self.get_resolution().replace("K", "000").replace("M", "000000")
        )

        if resolution < 256000:  # can get all data in one pass
            self.write(":WAV:RANG 0, %d" % resolution)

            raw_response = self.query(":WAV:FETC?", binary=True)

            header, byte_data = raw_response[:11], raw_response[11:]

            data_len = int(header[2:]) // 2

            voltages = scale * (
                np.array(struct.unpack(f"<{data_len}h", byte_data), dtype=float) / 6400
                - zero
            )

        else:  # need to read data in chunks; max chunk size is 256k
            offset, size = 0, 200000

            voltages = np.empty(resolution)

            while offset + size <= resolution:
                self.write(":WAV:RANG %d, %d" % (offset, size))

                raw_response = self.query(":WAV:FETC?", binary=True)

                header, byte_data = raw_response[:11], raw_response[11:]

                data_len = int(header[2:]) // 2

                voltages[offset : offset + size] = scale * (
                    np.array(struct.unpack(f"<{data_len}h", byte_data), dtype=float)
                    / 6400
                    - zero
                )

                offset += size

        if len(voltages) != resolution:
            print(
                f"Warning: {self.name} received truncated data "
                f"for channel {channel}; discarding"
            )
            return None

        return voltages

    @measurer
    def measure_channel_1(self):
        if not self._acquiring:
            self.set_acquire(True)

        self._acquiring = False

        self.write(":WAV:BEG CH1")

        data = self._read_data(1)

        self.write(":WAV:END CH1")

        return data[1]

    @measurer
    def measure_channel_2(self):
        if not self._acquiring:
            self.set_acquire(True)

        self._acquiring = False

        self.write(":WAV:BEG CH2")

        data = self._read_data(2)

        self.write(":WAV:END CH2")

        return data[1]


class SiglentSDS1000(Instrument):
    """
    Siglent SDS1000 series digital oscilloscope
    """

    name = "SiglentSDS1000"

    supported_adapters = (
        (
            Socket,
            {
                "write_termination": "\n",
                "read_termination": "\n",
                "timeout": 60,  # waveform retrieval may take some extra time
            },
        ),
    )

    knobs = (
        "horz scale",
        "horz position",
        "ch1 scale",
        "ch1 position",
        "ch2 scale",
        "ch2 position",
        "ch3 scale",
        "ch3 position",
        "ch4 scale",
        "ch4 position",
        "trigger source",
        "trigger level",
        "acquire mode",
        "memory size",
        "averages",
    )

    meters = ("ch1 waveform", "ch2 waveform", "ch3 waveform", "ch4 waveform")

    horz_scales = [
        1e-9,
        2e-9,
        5e-9,
        10e-9,
        20e-9,
        50e-9,
        100e-9,
        200e-9,
        500e-9,
        1e-6,
        2e-6,
        5e-6,
        10e-6,
        20e-6,
        50e-6,
        100e-6,
        200e-6,
        500e-6,
        1e-3,
        2e-3,
        5e-3,
        10e-3,
        20e-3,
        50e-3,
        100e-3,
        200e-3,
        500e-3,
        1.0,
        2.0,
        5.0,
        10.0,
        20.0,
        50.0,
        100.0,  # seconds
    ]

    _trg_src = None

    # Time axis control
    @setter
    def set_horz_scale(self, scale: Float):
        nearest_scale = find_nearest(self.horz_scales, scale, overestimate=True)

        self.write(f"TDIV {nearest_scale}S")

        return nearest_scale

    @getter
    def get_horz_scale(self) -> Float:
        response = self.query("TDIV?").split("TDIV ")[-1][:-1]

        try:
            response = float(response)
        except ValueError:
            return np.nan

        return response

    @setter
    def set_horz_position(self, position: Float):
        self.write(f"TRDL {position}S")

    @getter
    def get_horz_position(self) -> Float:
        response = self.query("TRDL?").split("TRDL ")[-1][:-1]

        try:
            response = float(response)
        except ValueError:
            return np.nan

        return response

    # Channel control base functions
    def _set_chn_scale(self, n, scale):
        self.write("C%d:VDIV %.3eV" % (n, float(scale)))

    def _get_chn_scale(self, n):
        response = self.query("C%d:VDIV?" % n).split("C%d:VDIV " % n)[-1][:-1]

        try:
            response = float(response)
        except ValueError:
            return np.nan

        return response

    def _set_chn_position(self, n, position):
        self.write("C%d:OFST %.3eV" % (n, float(position)))

    def _get_chn_position(self, n):
        response = self.query("C%d:OFST?" % n).split("C%d:OFST " % n)[-1][:-1]

        try:
            response = float(response)
        except ValueError:
            return np.nan

        return response

    # Channel 1 control
    @setter
    def set_ch1_scale(self, scale: Float):
        self._set_chn_scale(1, scale)

    @getter
    def get_ch1_scale(self) -> Float:
        return self._get_chn_scale(1)

    @setter
    def set_ch1_position(self, position: Float):
        self._set_chn_position(1, position)

    @getter
    def get_ch1_position(self) -> Float:
        return self._get_chn_position(1)

    # Channel 2 control
    @setter
    def set_ch2_scale(self, scale: Float):
        self._set_chn_scale(2, scale)

    @getter
    def get_ch2_scale(self) -> Float:
        return self._get_chn_scale(2)

    @setter
    def set_ch2_position(self, position: Float):
        self._set_chn_position(2, position)

    @getter
    def get_ch2_position(self) -> Float:
        return self._get_chn_position(2)

    # Channel 3 control
    @setter
    def set_ch3_scale(self, scale: Float):
        self._set_chn_scale(3, scale)

    @getter
    def get_ch3_scale(self) -> Float:
        return self._get_chn_scale(3)

    @setter
    def set_ch3_position(self, position: Float):
        self._set_chn_position(3, position)

    @getter
    def get_ch3_position(self) -> Float:
        return self._get_chn_position(3)

    # Channel 4 control
    @setter
    def set_ch4_scale(self, scale: Float):
        self._set_chn_scale(4, scale)

    @getter
    def get_ch4_scale(self) -> Float:
        return self._get_chn_scale(4)

    @setter
    def set_ch4_position(self, position: Float):
        self._set_chn_position(4, position)

    @getter
    def get_ch4_position(self) -> Float:
        return self._get_chn_position(4)

    # Trigger control
    @setter
    def set_trigger_level(self, level: Float):
        trg_src = self.get_trigger_source()

        self.write(f"C{trg_src}:TRLV {level}V")

    @getter
    def get_trigger_level(self) -> Float:
        trg_src = self.get_trigger_source()

        if trg_src > 0:
            response = self.query(f"C{trg_src}:TRLV?").split("TRLV ")[-1][:-1]
        else:
            return np.nan

        try:
            response = float(response)
        except ValueError:
            return np.nan

        return response

    @setter
    def set_trigger_source(self, source: Integer):
        self.write(f"TRSE EDGE,SR,C{int(source)},OFF")

    @getter
    def get_trigger_source(self) -> Integer:
        response = self.query("TRSE?").split("SR,C")[-1][0]

        try:
            response = int(response)
        except ValueError:
            return -1

        return response

    @setter
    def set_acquire_mode(self, mode: String):
        if mode.upper() in ["SAMPLING", "PEAK_DETECT", "HIGH_RES"]:
            self.write(f"ACQW {mode.upper()}")
        elif mode.upper() == "AVERAGE":
            if not hasattr(self, "averages"):
                self.set_averages(4)

            self.write(f"ACQW AVERAGE,{int(self.averages)}")

        else:
            return None

    @getter
    def get_acquire_mode(self) -> String:
        response = self.query("ACQW?").split("ACQW ")[-1]

        if "AVERAGE" in response:  # also includes # of averages
            return "AVERAGE"
        else:
            return response

    @setter
    def set_memory_size(self, size: Integer):
        self.write(f"MSIZ {int(size)}")

        return self.get_memory_size()

    @getter
    def get_memory_size(self) -> Integer:
        response = self.query("MSIZ?").split("MSIZ ")[-1]

        if "K" in response:
            response = float(response.replace("K", "e3"))
        elif "M" in response:
            response = float(response.replace("M", "e6"))

        try:
            response = int(response)
        except ValueError:
            return -1

        return response

    @setter
    def set_averages(self, averages: Integer):
        valid = [4] + [2**i for i in range(4, 11)]

        averages = find_nearest(valid, averages)

        self.write(f"AVGA {averages}")

    @getter
    def get_averages(self) -> Integer:
        response = self.query("AVGA?").split("AVGA ")[-1]

        try:
            response = int(response)
        except ValueError:
            return -1

        return response

    # Channel measurements
    def _measure_chn_waveform(self, n):
        # Set trigger mode to NORMAL
        self.write("TRMD NORM")

        # Wait for trigger
        triggered = False
        wait_time = 0.0
        while not triggered and wait_time < 30.0:
            status = self.query("INR?")
            triggered = status == "INR 8193"
            wait_time += 0.25
            time.sleep(0.25)

        if not triggered:
            return None

        # Enable channel if needed
        channel_enabled = "ON" in self.query("C%d:TRA?" % n)
        if not channel_enabled:
            self.write("C%d:TRA ON" % n)
            time.sleep(3)

        self.write("WFSU SP,0,NP,0,FP,0")  # setup to get all data points

        def is_terminated(message):
            try:
                size = int(message[13:22])
            except ValueError:
                return False

            data_length = len(message[22:-2])

            if data_length == size:
                return True
            else:
                return False

        self.adapter.read_termination = is_terminated

        def validator(response):
            """
            Checks for correct header, size, message length and termination.
            """

            if response is None:
                return False
            elif len(response) == 0:
                return False

            header = response[:13]
            if header != (b"C%d:WF DAT2,#9" % n):
                return False

            size = response[13:22]
            try:
                size = int(size)
            except ValueError:
                return False

            data = response[22:-2]
            if len(data) != size:
                return False

            termination = response[-2:]
            if termination != b"\n\n":
                return False

            return True

        response = self.query("C%d:WF? DAT2" % n, decode=False, validator=validator)

        self.adapter.read_termination = "\n"  # restore normal read termination

        header, size, waveform = response[:13], response[13:22], response[22:-2]
        size = int(size)

        # convert bytes to integers
        waveform = np.array(struct.unpack("b" * size, waveform), dtype=np.float64)

        scale = self._get_chn_scale(n)
        pos = self._get_chn_position(n)

        waveform = (scale / 25.0) * waveform - pos

        return waveform

    @measurer
    def measure_ch1_waveform(self) -> Array:
        return self._measure_chn_waveform(1)

    @measurer
    def measure_ch2_waveform(self) -> Array:
        return self._measure_chn_waveform(2)

    @measurer
    def measure_ch3_waveform(self) -> Array:
        return self._measure_chn_waveform(3)

    @measurer
    def measure_ch4_waveform(self) -> Array:
        return self._measure_chn_waveform(4)

    @measurer
    def measure_sample_rate(self) -> Float:
        response = self.query_read_until_response_helper("SARA?")[5:-4]

        try:
            response = float(response)
        except ValueError:
            return np.nan

        return response

class OwonVDSScope(Instrument):
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
                    self.adapter.backend.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, int(8e6))
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
        def __init__(self, key: str, setting_regex: bytes, to_bytes: Callable,
                     from_bytes: Callable):
            self.key: str = key
            self.setting_regex: re.Pattern = re.compile(setting_regex, flags=re.DOTALL)
            self.to_bytes: Callable = to_bytes
            self.from_bytes: Callable = from_bytes

    _independent_settings: list[Setting] = [
        Setting("horizontal scale", b"MHRb(?P<horizontal_scale>.)",
                to_bytes=lambda value: OwonVDSScope._time_scales[value],
                from_bytes=lambda value: OwonVDSScope.reverse_lookup(
                    OwonVDSScope._time_scales, value)),
        Setting("acquisition mode", b"MAQ(?P<acquisition_mode>.)",
                to_bytes=lambda value: OwonVDSScope._acquisition_modes[value],
                from_bytes=lambda value: OwonVDSScope.reverse_lookup(
                    OwonVDSScope._acquisition_modes, value)),
        Setting("resolution", b"MDP(?P<resolution>.)",
                to_bytes=lambda value: OwonVDSScope._resolutions[value],
                from_bytes=lambda value: OwonVDSScope.reverse_lookup(
                    OwonVDSScope._resolutions, value)),
        Setting("trigger channel", b"MTRs(?P<trigger_channel>.)",
                to_bytes=lambda value: int.to_bytes(value - 1, length=1,
                                                    byteorder="big", signed=False),
                from_bytes=lambda value: int.from_bytes(value, byteorder="big",
                                                        signed=False) + 1),
        Setting("trigger mode", b"MTRs(?P<trigger_channel>.)(?P<trigger_mode>.)",
                to_bytes=lambda value: OwonVDSScope._trigger_modes[value],
                from_bytes=lambda value: OwonVDSScope.reverse_lookup(
                    OwonVDSScope._trigger_modes, value)),
        Setting("sweep mode", b"MTRs(?P<trigger_channel>.)e\x03(?P<sweep_mode>.)",
                to_bytes=lambda value: OwonVDSScope._sweep_modes[value],
                from_bytes=lambda value: OwonVDSScope.reverse_lookup(
                    OwonVDSScope._sweep_modes, value)),
        Setting("trigger hold off",
                b"MTRs(?P<trigger_channel>.)e\x04(?P<trigger_hold_off>.{4})",
                to_bytes=lambda value: int.to_bytes(value, length=4, byteorder="big",
                                                    signed=True),
                from_bytes=lambda value: int.from_bytes(value, byteorder="big",
                                                        signed=True)),
        Setting("trigger edge", b"MTRs(?P<trigger_channel>.)e\x05(?P<trigger_edge>.)",
                to_bytes=lambda value: OwonVDSScope._trigger_edges[value],
                from_bytes=lambda value: OwonVDSScope.reverse_lookup(
                    OwonVDSScope._trigger_edges, value)),
        Setting("ch1 scale", b"MCH\x00v(?P<ch1_scale>.)",
                to_bytes=lambda value: OwonVDSScope._volt_scales[value],
                from_bytes=lambda value: OwonVDSScope.reverse_lookup(
                    OwonVDSScope._volt_scales, value)),
        Setting("ch1 coupling", b"MCH\x00c(?P<ch1_coupling>.)",
                to_bytes=lambda value: OwonVDSScope._coupling_modes[value],
                from_bytes=lambda value: OwonVDSScope.reverse_lookup(
                    OwonVDSScope._coupling_modes, value)),
        Setting("ch1 enable", b"MCH\x00e(?P<ch1_enable>.)",
                to_bytes=lambda value: OwonVDSScope._enable_modes[value],
                from_bytes=lambda value: OwonVDSScope.reverse_lookup(
                    OwonVDSScope._enable_modes, value)),
        Setting("ch1 bw limit", b"MCH\x00b(?P<ch1_bw_limit>.)",
                to_bytes=lambda value: OwonVDSScope._bandwidth_limits[value],
                from_bytes=lambda value: OwonVDSScope.reverse_lookup(
                    OwonVDSScope._bandwidth_limits, value)),
        Setting("ch2 scale", b"MCH\x01v(?P<ch2_scale>.)",
                to_bytes=lambda value: OwonVDSScope._volt_scales[value],
                from_bytes=lambda value: OwonVDSScope.reverse_lookup(
                    OwonVDSScope._volt_scales, value)),
        Setting("ch2 coupling", b"MCH\x01c(?P<ch2_coupling>.)",
                to_bytes=lambda value: OwonVDSScope._coupling_modes[value],
                from_bytes=lambda value: OwonVDSScope.reverse_lookup(
                    OwonVDSScope._coupling_modes, value)),
        Setting("ch2 enable", b"MCH\x01e(?P<ch2_enable>.)",
                to_bytes=lambda value: OwonVDSScope._enable_modes[value],
                from_bytes=lambda value: OwonVDSScope.reverse_lookup(
                    OwonVDSScope._enable_modes, value)),
        Setting("ch2 bw limit", b"MCH\x01b(?P<ch2_bw_limit>.)",
                to_bytes=lambda value: OwonVDSScope._bandwidth_limits[value],
                from_bytes=lambda value: OwonVDSScope.reverse_lookup(
                    OwonVDSScope._bandwidth_limits, value)),
        Setting("ch3 scale", b"MCH\x02v(?P<ch3_scale>.)",
                to_bytes=lambda value: OwonVDSScope._volt_scales[value],
                from_bytes=lambda value: OwonVDSScope.reverse_lookup(
                    OwonVDSScope._volt_scales, value)),
        Setting("ch3 coupling", b"MCH\x02c(?P<ch3_coupling>.)",
                to_bytes=lambda value: OwonVDSScope._coupling_modes[value],
                from_bytes=lambda value: OwonVDSScope.reverse_lookup(
                    OwonVDSScope._coupling_modes, value)),
        Setting("ch3 enable", b"MCH\x02e(?P<ch3_enable>.)",
                to_bytes=lambda value: OwonVDSScope._enable_modes[value],
                from_bytes=lambda value: OwonVDSScope.reverse_lookup(
                    OwonVDSScope._enable_modes, value)),
        Setting("ch3 bw limit", b"MCH\x02b(?P<ch3_bw_limit>.)",
                to_bytes=lambda value: OwonVDSScope._bandwidth_limits[value],
                from_bytes=lambda value: OwonVDSScope.reverse_lookup(
                    OwonVDSScope._bandwidth_limits, value)),
        Setting("ch4 scale", b"MCH\x03v(?P<ch4_scale>.)",
                to_bytes=lambda value: OwonVDSScope._volt_scales[value],
                from_bytes=lambda value: OwonVDSScope.reverse_lookup(
                    OwonVDSScope._volt_scales, value)),
        Setting("ch4 coupling", b"MCH\x03c(?P<ch4_coupling>.)",
                to_bytes=lambda value: OwonVDSScope._coupling_modes[value],
                from_bytes=lambda value: OwonVDSScope.reverse_lookup(
                    OwonVDSScope._coupling_modes, value)),
        Setting("ch4 enable", b"MCH\x03e(?P<ch4_enable>.)",
                to_bytes=lambda value: OwonVDSScope._enable_modes[value],
                from_bytes=lambda value: OwonVDSScope.reverse_lookup(
                    OwonVDSScope._enable_modes, value)),
        Setting("ch4 bw limit", b"MCH\x03b(?P<ch4_bw_limit>.)",
                to_bytes=lambda value: OwonVDSScope._bandwidth_limits[value],
                from_bytes=lambda value: OwonVDSScope.reverse_lookup(
                    OwonVDSScope._bandwidth_limits, value))
        # Unknown Command: "": b"MCH(?P<channel>.)i(?P<>.)",
    ]

    _dependent_settings = [
        Setting("horizontal position", b"MHRv(?P<horizontal_position>.)",
                to_bytes=lambda value, config: int(
                    50.0 * value / config["horizontal scale"]).to_bytes(length=4,
                                                                        byteorder='big',
                                                                        signed=True),
                from_bytes=lambda value, config: int.from_bytes(value, byteorder='big',
                                                                signed=True) * config[
                                                     "horizontal scale"] / 25.0),
        Setting("trigger level",
                b"MTRs(?P<trigger_channel>.)e\x06(?P<trigger_level>.{4})",
                to_bytes=lambda value, config: int(25.0 * value / config[
                    f"ch{config['trigger channel']} scale"]).to_bytes(length=4,
                                                                      byteorder='big',
                                                                      signed=True),
                from_bytes=lambda value, config: int.from_bytes(value, byteorder='big',
                                                                signed=True) * config[
                                                     f"ch{config['trigger channel']} scale"] / 25.0),
        Setting("ch1 position", b"MCH\x00z(?P<ch1_position>.{4})",
                to_bytes=lambda value, config: int(
                    25 * value / config[f"ch1 scale"]).to_bytes(length=4,
                                                                byteorder='big',
                                                                signed=True),
                from_bytes=lambda value, config: int.from_bytes(value, byteorder='big',
                                                                signed=True) * config[
                                                     "ch1 scale"] / 25.0),
        Setting("ch2 position", b"MCH\x01z(?P<ch2_position>.{4})",
                to_bytes=lambda value, config: int(
                    25 * value / config[f"ch2 scale"]).to_bytes(length=4,
                                                                byteorder='big',
                                                                signed=True),
                from_bytes=lambda value, config: int.from_bytes(value, byteorder='big',
                                                                signed=True) * config[
                                                     "ch2 scale"] / 25.0),
        Setting("ch3 position", b"MCH\x02z(?P<ch3_position>.{4})",
                to_bytes=lambda value, config: int(
                    25 * value / config[f"ch3 scale"]).to_bytes(length=4,
                                                                byteorder='big',
                                                                signed=True),
                from_bytes=lambda value, config: int.from_bytes(value, byteorder='big',
                                                                signed=True) * config[
                                                     "ch3 scale"] / 25.0),
        Setting("ch4 position", b"MCH\x03z(?P<ch4_position>.{4})",
                to_bytes=lambda value, config: int(
                    25 * value / config[f"ch4 scale"]).to_bytes(length=4,
                                                                byteorder='big',
                                                                signed=True),
                from_bytes=lambda value, config: int.from_bytes(value, byteorder='big',
                                                                signed=True) * config[
                                                     "ch4 scale"] / 25.0)
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
        "horizontal scale": 1.0e-6,
        "ch1 scale": 1.0,
        "ch2 scale": 1.0,
        "ch3 scale": 1.0,
        "ch4 scale": 1.0,
        "ch1 coupling": "DC",
        "ch2 coupling": "DC",
        "ch3 coupling": "DC",
        "ch4 coupling": "DC",
        "ch1 enable": True,
        "ch2 enable": True,
        "ch3 enable": True,
        "ch4 enable": True,
        "acquisition mode": "SAMPLE",
        "trigger hold off": 1
    }

    # TODO: Rename as channel-dependent presets
    presets_pt_2 = {
        "trigger source": 1,
        "trigger level": 1.0,
        "sweep mode": "AUTO"
        # "ch1 position": 0.0,
        # "ch2 position": 0.0,
        # "ch3 position": 0.0,
        # "ch4 position": 0.0,
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
        # this doesn't work because bytearray([10]) is a \n character which breaks something somewhere
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
        # this doesn't work because bytearray([10]) is a \n character which breaks something somewhere
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
        "AVERAGE": bytearray([1]),  # guess
        "PEAK": bytearray([2])  # guess
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
        # "VIDEO": "v".encode(),
        # "SLOPE": "s".encode(),
        # "PULSE": "p".encode()
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

    def create_command_from_regex(self, regex: re.Pattern,
                                  command_values: dict) -> bytes:
        parameter_regex = b"(\(.+?\))"

        parameter_groups = re.findall(parameter_regex, regex.pattern)
        command_parameters = [param.replace("_", " ") for param in
                              list(regex.groupindex.keys())]
        command: bytes = regex.pattern
        for index, group_text in enumerate(parameter_groups):
            try:
                command_bytes = command_values[command_parameters[index]]
                command = command.replace(group_text, command_bytes)
            except KeyError:
                raise ValueError(
                    f'Parameter {command_parameters[index]} missing from command_values dictionary.')

        return command

    def set_by_command_id(self, id: str, native_value):
        setting: OwonVDSScope.Setting = self.get_setting(id)
        if id in [s.key for s in self._dependent_settings]:
            config = self.get_current_config()
            cmd = self.create_command_from_regex(
                setting.setting_regex,
                {id: setting.to_bytes(native_value, config)}
            )
        else:
            cmd = self.create_command_from_regex(
                setting.setting_regex,
                {id: setting.to_bytes(native_value)}
            )
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
        new_time_scale = find_nearest(list(self._time_scales.keys()), scale)
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
        new_volt_scale = find_nearest(list(self._volt_scales.keys()), scale)
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

    def set_edge_trigger_settings(self, channel=None, sweep_mode=None, edge=None,
                                  level=None, hold_off=None):
        # get current settings to use if no updates are provided
        config = self.get_current_config()

        if channel is not None:
            config["trigger channel"] = channel
        # print(f"Trigger Channel: {config['trigger channel']}")
        trigger_setting: OwonVDSScope.Setting = self.get_setting("trigger channel")

        setting_ids_mapping = {
            "sweep mode": sweep_mode,
            "trigger edge": edge,
            "trigger level": level,
            "trigger hold off": hold_off
        }
        cmd = b"MTRs" + trigger_setting.to_bytes(
            config["trigger channel"]) + b"e\x02\x00"
        for setting_key, setting_value in setting_ids_mapping.items():
            if setting_value is None:
                setting_value = config[setting_key]
            setting: OwonVDSScope.Setting = self.get_setting(setting_key)
            if setting_key in [s.key for s in self._dependent_settings]:
                setting_bytes = setting.to_bytes(setting_value, config)
            else:
                setting_bytes = setting.to_bytes(setting_value)
            cmd += self.create_command_from_regex(
                setting.setting_regex,
                {setting_key: setting_bytes,
                 "trigger channel": trigger_setting.to_bytes(config["trigger channel"])
                 })
        # print(cmd)
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
    #     setting: OwonVDSScope.Setting = self.get_setting("trigger mode")
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

    @getter
    def set_trigger_hold_off(self, hold_off):
        return self.set_edge_trigger_settings(hold_off=hold_off)

    @getter
    def get_trigger_hold_off(self, hold_off):
        return self.get_current_config()["trigger hold off"]

    ###################################################################
    ##          Read Trace Operations                                ##
    ###################################################################

    def _read_GDT_response_channel(self):
        HEADER_LENGTH = 32
        FOOTER_LENGTH = 100
        POST_HEADER_BYTES_OFFSET = 8
        MEMORY_DEPTH_OFFSET = 24
        try:
            header_data = self.read(nbytes=HEADER_LENGTH, timeout=10.0,
                                    termination=None, decode=False)
            num_data_bytes = struct.unpack("!I", header_data[
                                                 MEMORY_DEPTH_OFFSET:MEMORY_DEPTH_OFFSET + 4])[
                0]
            num_extra_bytes = struct.unpack("!I", header_data[
                                                  POST_HEADER_BYTES_OFFSET:POST_HEADER_BYTES_OFFSET + 4])[
                                  0] \
                              - num_data_bytes - FOOTER_LENGTH
            raw_channel_bytes = self.read(nbytes=num_data_bytes, timeout=10.0,
                                         termination=None, decode=False)
            raw_channel_data = struct.unpack("b"*len(raw_channel_bytes), raw_channel_bytes)
            junk_data = self.read(nbytes=num_extra_bytes, timeout=10.0,
                                  termination=None, decode=False)
            footer_data = self.read(nbytes=FOOTER_LENGTH, timeout=10.0,
                                    termination=None, decode=False)
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
            # ":GDT.""
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
        if response[SUCCESS_MAYBE_OFFSET] == '\x00' or response[
            SUCCESS_MAYBE_OFFSET] == 0:
            # This is some sort of error state, but we're going to say it's
            # the same as no data.
            return []
        # We now know the message will be at least 16 bytes long (from experience)
        response += self.read(nbytes=9, timeout=10.0, termination=None, decode=False)
        DATA_PRESENT_OFFSET = 6
        # print(response[DATA_PRESENT_OFFSET])
        if response[DATA_PRESENT_OFFSET] == '\x00' or response[
            DATA_PRESENT_OFFSET] == 0:
            # At this point we know there's no more data and that the whole
            # message will be only 16 bytes long.
            return []
        # if we're here then there's more to read
        try:
            CHANNEL_BITFIELD_OFFSET = 7
            channels_in_response = self.parse_channels_in_response(
                response[CHANNEL_BITFIELD_OFFSET])
            BYTES_PER_CHANNEL_OFFSET = 8
            bytes_per_channel = struct.unpack("!I", response[
                                                    BYTES_PER_CHANNEL_OFFSET:BYTES_PER_CHANNEL_OFFSET + 4])[
                0]
            for channel in channels_in_response:
                raw_channel_data.append(self._read_GDT_response_channel())

            # We've finished reading the GDM message now so we can read the scope config to figure out the scaling.
            config = self.get_current_config()

            # Scale channel data
            channel_data = {}
            for i, raw_data in enumerate(raw_channel_data):
                ch_id = channels_in_response[i]
                channel_data[ch_id] = self.scale_channel_data(ch_id, raw_data, config)
        except Exception as e:
            print(f'Exception reading channel data: {e}')
            channel_data = []
        return channel_data

    @setter
    def set_acquire(self, _):
        """
        This is a helper function to make sure scope triggers on something before reading the data.
        """
        self._acquiring = True
        self.set_sweep_mode("SINGLE")
        count = 0
        while count < 10:
            trig_status = self.get_triggered_status()
            time.sleep(1)
            if trig_status:
                break
            count += 1
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
        header_data = self.read(nbytes=HEADER_LENGTH, timeout=10.0, termination=None,
                                decode=False)
        if not header_data.startswith(b":M"):
            # choosing not to raise an exception because this could easily happen
            # and it need not be fatal.
            # That said we can't decode the message if it doesn't start with :M
            # so delete everything else in the buffer and return None.
            if len(header_data) > 0:
                self.flush_buffer()
            return None
        remaining_length = struct.unpack("!I", header_data[
                                               REMAINING_LENGTH_OFFSET:REMAINING_LENGTH_OFFSET + 4])[
            0]
        msg = self.read(nbytes=remaining_length, timeout=10.0, termination=None,
                        decode=False)
        config = dict()
        for setting in self._independent_settings:
            parameter_index = setting.setting_regex.groupindex[
                setting.key.replace(" ", "_")]
            matches = setting.setting_regex.findall(msg)
            # Guard statment to reformat matches in the case that there is only 1 match because findall doesn't always return the same nested list format
            if len(matches) > 0 and type(matches[0]) is not tuple:
                matches = [matches]
            for match in matches:
                config[setting.key] = setting.from_bytes(match[parameter_index - 1])

        for setting in self._dependent_settings:
            parameter_index = setting.setting_regex.groupindex[
                setting.key.replace(" ", "_")]
            matches = setting.setting_regex.findall(msg)
            # Guard statment to reformat matches in the case that there is only 1 match because findall doesn't always return the same nested list format
            if len(matches) > 0 and type(matches[0]) is not tuple:
                matches = [matches]
            for match in matches:
                config[setting.key] = setting.from_bytes(match[parameter_index - 1],
                                                         config)
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
            if (1 << (id - 1)) & channel_bitfield:
                channels_in_response.append(id)
        return channels_in_response

    def _read_GDM_response_channel(self):
        """
        This helper function reads a single channel within a GDM response message and returns the raw channel data.
        """
        HEADER_LENGTH = 41
        MEMORY_DEPTH_OFFSET = 1
        print("Reading channel header")
        header_data = self.read(nbytes=HEADER_LENGTH, timeout=30.0, termination=None,
                                decode=False)
        num_data_bytes = \
        struct.unpack("!I", header_data[MEMORY_DEPTH_OFFSET:MEMORY_DEPTH_OFFSET + 4])[0]
        print(f"Reading channel bytes. Expecting {num_data_bytes}")
        raw_channel_bytes = self.read(nbytes=num_data_bytes, timeout=30.0,
                                     termination=None, decode=False)
        raw_channel_data = struct.unpack("b"*len(raw_channel_bytes), raw_channel_bytes)
        return raw_channel_data

    def _read_GDM_response(self) -> dict:
        MESSAGE_HEADER_LENGTH = 11
        response = self.read(nbytes=MESSAGE_HEADER_LENGTH, timeout=10.0,
                             termination=None, decode=False)
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
            print(f"Reading channel {channel}")
            raw_channel_data.append(self._read_GDM_response_channel())

        # We've finished reading the GDM message now so we can read the scope config to figure out the scaling.
        config = self.get_current_config()
        print("ready to scale")
        # Scale channel data
        channel_data = {}
        for i, raw_data in enumerate(raw_channel_data):
            ch_id = channels_in_response[i]
            channel_data[ch_id] = self.scale_channel_data(ch_id, raw_data, config)
        return channel_data

    def scale_channel_data(self, channel_id, data, config):
        scale_factor = config[f"ch{channel_id} scale"]
        offset = config[f"ch{channel_id} position"]
        return [(raw / 25.0) * scale_factor + offset for raw in data]

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
        MAX_SAMPLE_RATE = 250e6
        if settings["resolution"]/(20*settings["horizontal scale"]) <= MAX_SAMPLE_RATE:
            start_div = -10.0
            stop_div = 10.0
        else:
            # Not all samples fit on screen
            start_div = -1.0 * settings["resolution"]/(MAX_SAMPLE_RATE*settings["horizontal scale"]) /2
            stop_div = settings["resolution"]/(MAX_SAMPLE_RATE*settings["horizontal scale"]) / 2
        start = start_div * settings["horizontal scale"] - settings["horizontal position"]
        stop = stop_div * settings["horizontal scale"] - settings["horizontal position"]
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
