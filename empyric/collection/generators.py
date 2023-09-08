# Function/signal generators
from typing import Union

from empyric.adapters import Socket
from empyric.instruments import Instrument, setter, getter, measurer
from empyric.types import ON, OFF, Toggle, Integer, String, Float, recast


class SiglentSDG1000(Instrument):
    supported_adapters = (
        (Socket, {"write_termination": "\n", "read_termination": "\n"}),
    )

    knobs = (
        "channel 1 output",
        "channel 2 output",
        "channel 1 load",
        "channel 2 load",
        "channel 1 polarity",
        "channel 2 polarity",
        "channel 1 waveform",
        "channel 2 waveform",
        "channel 1 high level",
        "channel 2 high level",
        "channel 1 low level",
        "channel 2 low level",
        "channel 1 frequency",
        "channel 2 frequency",
        "channel 1 pulse width",
        "channel 2 pulse width",
        "channel 1 pulse rise",
        "channel 2 pulse rise",
        "channel 1 pulse fall",
        "channel 2 pulse fall",
        "channel 1 pulse delay",
        "channel 2 pulse delay",
        "channel 1 invert",
        "channel 2 invert",
        "equal phase",
        # BURST MODE PARAMETERS
        "channel 1 burst mode",
        "channel 2 burst mode",
        "channel 1 burst period",
        "channel 2 burst period",
        "channel 1 burst trigger source",
        "channel 2 burst trigger source",
        "channel 1 burst trigger delay",
        "channel 2 burst trigger delay",
        "channel 1 burst trigger edge",
        "channel 2 burst trigger edge",
        "channel 1 burst cycles",
        "channel 2 burst cycles",
        "channel 1 burst polarity",
        "channel 2 burst polarity",
    )

    wave_forms = ("SINE", "SQUARE", "RAMP", "PULSE", "NOISE", "ARB", "DC", "PRBS", "IQ")

    def _set_channel_n_output(self, n, output: Toggle, load: String, polarity: String):
        self.write(f"C{n}:OUTP {output},LOAD,{load},PLRT,{polarity}")

    def _get_channel_n_output(self, n) -> Toggle:
        response = self.query("C%d:OUTP?" % n).split(",")

        if response[0] == ("C%d:OUTP ON" % n):
            output = ON
        elif response[0] == ("C%d:OUTP OFF" % n):
            output = OFF
        else:
            raise ValueError(
                f"while trying to get output state of {self.name}, "
                f"got corrupted response {response}"
            )

        load = response[2]

        if response[4] == "NOR":
            polarity = "normal"
        elif response[4] == "INVT":
            polarity = "inverted"
        else:
            raise ValueError(
                f"while trying to get output state of {self.name}, "
                f"got corrupted response {response}"
            )

        return output, load, polarity

    def _set_channel_n_basic_waveform(self, n, **kwargs):
        waveform_dict = self._get_channel_n_waveform(n)

        for key in kwargs:
            if key.upper() not in waveform_dict:
                raise ValueError(
                    f"parameter {key} is not valid for waveform type "
                    f'{kwargs["WVTP"]}'
                )

        parameter_string = f"C{n}:BSWV " + ",".join(
            [f"{key.upper()},{value}" for key, value in kwargs.items()]
        )

        # Changing the waveform parameters can cause the relative phase
        # of the two channels to shift
        self.equal_phase = OFF

        self.write(parameter_string)

    def _set_channel_n_burst_waveform(self, n, **kwargs):
        waveform_dict = self._get_channel_n_waveform(n, mode="burst")

        if "wvtp" in kwargs:
            kwargs["CARR,WVTP"] = kwargs.pop("wvtp")

        for key in kwargs:
            if key.upper() not in waveform_dict:
                raise ValueError(
                    f"parameter {key} is not valid for burst waveform type "
                    f'{kwargs["CARR,WVTP"]}'
                )

        # For burst waveforms only, the wavetype parameter must be corrected
        parameter_string = f"C{n}:BTWV " + ",".join(
            [f"{key.upper()},{value}" for key, value in kwargs.items()]
        )

        # Changing the waveform parameters can cause the relative phase
        # of the two channels to shift
        self.equal_phase = OFF

        self.write(parameter_string)

    def _get_channel_n_waveform(self, n, mode="basic"):
        if mode.lower() == "burst":
            bt_response = self.query(f"C{n}:BTWV?")[3:]
            # Temporarily remove "carr" prefix to create waveform dictionary
            carrier_response = bt_response.split(f"BTWV ")[1].split("CARR,")[1]
            bt_response = bt_response.split(f"BTWV ")[1].split("CARR,")[0]
            response = (bt_response + carrier_response).split(",")
        else:
            bs_response = self.query(f"C{n}:BSWV?")
            response = bs_response.split(f"C{n}:BSWV ")[1].split(",")

        keys = response[::2]
        values = response[1::2]

        waveform_dict = {key: value for key, value in zip(keys, values)}

        # Adjust name of wavetype key for non-basic waveforms
        if mode.lower() != "basic":
            waveform_dict["CARR,WVTP"] = waveform_dict.pop("WVTP")

        return waveform_dict

    def _set_channel_n_invert(self, n, state: Toggle):
        if state == ON:
            self.write("C%d:INVT ON" % n)
        elif state == OFF:
            self.write("C%d:INVT OFF" % n)

    def _get_channel_n_invert(self, n):
        response = self.query("C%d:INVT?" % n)

        if "ON" in response:
            return ON
        if "OFF" in response:
            return OFF

    # Output
    @setter
    def set_channel_1_output(self, output: Toggle):
        _, load, polarity = self._get_channel_n_output(1)

        self._set_channel_n_output(1, output, load, polarity)

    @getter
    def get_channel_1_output(self) -> Toggle:
        return self._get_channel_n_output(1)[0]

    @setter
    def set_channel_2_output(self, output: Toggle):
        _, load, polarity = self._get_channel_n_output(2)

        self._set_channel_n_output(2, output, load, polarity)

    @getter
    def get_channel_2_output(self) -> Toggle:
        return self._get_channel_n_output(2)[0]

    # Load
    @setter
    def set_channel_1_load(self, load: String):
        output, _, polarity = self._get_channel_n_output(1)

        self._set_channel_n_output(1, output, load, polarity)

    @getter
    def get_channel_1_load(self) -> String:
        return self._get_channel_n_output(1)[1]

    @setter
    def set_channel_2_load(self, load: String):
        output, _, polarity = self._get_channel_n_output(2)

        self._set_channel_n_output(2, output, load, polarity)

    @getter
    def get_channel_2_load(self) -> String:
        return self._get_channel_n_output(2)[1]

    # Polarity
    @setter
    def set_channel_1_polarity(self, polarity: String):
        output, load, _ = self._get_channel_n_output(1)

        self._set_channel_n_output(1, output, load, polarity)

    @getter
    def get_channel_1_polarity(self) -> String:
        return self._get_channel_n_output(1)[1]

    @setter
    def set_channel_2_polarity(self, polarity: String):
        output, load, _ = self._get_channel_n_output(2)

        self._set_channel_n_output(2, output, load, polarity)

    @getter
    def get_channel_2_polarity(self) -> String:
        return self._get_channel_n_output(2)[1]

    # Waveform type
    @setter
    def set_channel_1_waveform(self, waveform: String):
        if self.get_channel_1_burst_state == ON:
            self._set_channel_n_burst_waveform(1, wvtp=waveform)
        else:
            self._set_channel_n_basic_waveform(1, wvtp=waveform)

    @getter
    def get_channel_1_waveform(self) -> String:
        if self.get_channel_1_burst_state == ON:
            return self._get_channel_n_waveform(1, mode="burst")["CARR,WVTP"]
        else:
            return self._get_channel_n_waveform(1)["WVTP"]

    @setter
    def set_channel_2_waveform(self, waveform: String):
        if self.get_channel_2_burst_state == ON:
            self._set_channel_n_burst_waveform(2, wvtp=waveform)
        else:
            self._set_channel_n_basic_waveform(2, wvtp=waveform)

    @getter
    def get_channel_2_waveform(self) -> String:
        if self.get_channel_2_burst_state == ON:
            return self._get_channel_n_waveform(2, mode="burst")["CARR,WVTP"]
        else:
            return self._get_channel_n_waveform(2)["WVTP"]

    # Waveform high level
    @setter
    def set_channel_1_high_level(self, high_level: Union[Float, String]):
        self._set_channel_n_basic_waveform(1, hlev=f"{high_level}")

    @getter
    def get_channel_1_high_level(self) -> Float:
        high_level_str = self._get_channel_n_waveform(1).get("HLEV", "nan")

        return float(high_level_str.replace("V", ""))

    @setter
    def set_channel_2_high_level(self, high_level: Union[Float, String]):
        self._set_channel_n_basic_waveform(2, hlev=f"{high_level}")

    @getter
    def get_channel_2_high_level(self) -> Float:
        high_level_str = self._get_channel_n_waveform(2).get("HLEV", "nan")

        return float(high_level_str.replace("V", ""))

    # Waveform low level
    @setter
    def set_channel_1_low_level(self, low_level: Union[Float, String]):
        self._set_channel_n_basic_waveform(1, llev=f"{low_level}")

    @getter
    def get_channel_1_low_level(self) -> Float:
        low_level_str = self._get_channel_n_waveform(1).get("LLEV", "nan")

        return float(low_level_str.replace("V", ""))

    @setter
    def set_channel_2_low_level(self, low_level: Union[Float, String]):
        self._set_channel_n_basic_waveform(2, llev=f"{low_level}")

    @getter
    def get_channel_2_low_level(self) -> Float:
        low_level_str = self._get_channel_n_waveform(2).get("LLEV", "nan")

        return float(low_level_str.replace("V", ""))

    # Waveform frequency
    @setter
    def set_channel_1_frequency(self, frequency: Union[Float, String]):
        self._set_channel_n_basic_waveform(1, frq=f"{frequency}")

    @getter
    def get_channel_1_frequency(self) -> Float:
        freq_str = self._get_channel_n_waveform(1).get("FRQ", "nan")

        return float(freq_str.replace("HZ", ""))

    @setter
    def set_channel_2_frequency(self, frequency: Union[Float, String]):
        self._set_channel_n_basic_waveform(2, frq=f"{frequency}")

    @getter
    def get_channel_2_frequency(self) -> Float:
        freq_str = self._get_channel_n_waveform(2).get("FRQ", "nan")

        return float(freq_str.replace("HZ", ""))

    # Pulse width
    @setter
    def set_channel_1_pulse_width(self, width: Union[Float, String]):
        self._set_channel_n_basic_waveform(1, width=f"{width}")

    @getter
    def get_channel_1_pulse_width(self) -> Float:
        width_str = self._get_channel_n_waveform(1).get("WIDTH", "nan")

        return float(width_str.replace("S", ""))

    @setter
    def set_channel_2_pulse_width(self, width: Union[Float, String]):
        self._set_channel_n_basic_waveform(2, width=f"{width}")

    @getter
    def get_channel_2_pulse_width(self) -> Float:
        width_str = self._get_channel_n_waveform(2).get("WIDTH", "nan")

        return float(width_str.replace("S", ""))

    # Pulse rise
    @setter
    def set_channel_1_pulse_rise(self, rise: Union[Float, String]):
        self._set_channel_n_basic_waveform(1, rise=f"{rise}")

    @getter
    def get_channel_1_pulse_rise(self) -> Float:
        delay_str = self._get_channel_n_waveform(1).get("RISE", "nan")

        return float(delay_str.replace("S", ""))

    @setter
    def set_channel_2_pulse_rise(self, rise: Union[Float, String]):
        self._set_channel_n_basic_waveform(2, rise=f"{rise}")

    @getter
    def get_channel_2_pulse_rise(self) -> Float:
        delay_str = self._get_channel_n_waveform(2).get("RISE", "nan")

        return float(delay_str.replace("S", ""))

    # Pulse fall
    @setter
    def set_channel_1_pulse_fall(self, fall: Union[Float, String]):
        self._set_channel_n_basic_waveform(1, fall=f"{fall}")

    @getter
    def get_channel_1_pulse_fall(self) -> Float:
        delay_str = self._get_channel_n_waveform(1).get("FALL", "nan")

        return float(delay_str.replace("S", ""))

    @setter
    def set_channel_2_pulse_fall(self, fall: Union[Float, String]):
        self._set_channel_n_basic_waveform(2, fall=f"{fall}")

    @getter
    def get_channel_2_pulse_fall(self) -> Float:
        delay_str = self._get_channel_n_waveform(2).get("FALL", "nan")

        return float(delay_str.replace("S", ""))

    # Pulse delay
    @setter
    def set_channel_1_pulse_delay(self, delay: Union[Float, String]):
        self._set_channel_n_basic_waveform(1, dly=f"{delay}")

    @getter
    def get_channel_1_pulse_delay(self) -> Float:
        delay_str = self._get_channel_n_waveform(1).get("DLY", "nan")

        return float(delay_str.replace("S", ""))

    @setter
    def set_channel_2_pulse_delay(self, delay: Union[Float, String]):
        self._set_channel_n_basic_waveform(2, dly=f"{delay}")

    @getter
    def get_channel_2_pulse_delay(self) -> Float:
        delay_str = self._get_channel_n_waveform(2).get("DLY", "nan")

        return float(delay_str.replace("S", ""))

    # Output inversion
    @setter
    def set_channel_1_invert(self, state: Toggle):
        self._set_channel_n_invert(1, state)

    @getter
    def get_channel_1_invert(self) -> Toggle:
        return self._get_channel_n_invert(1)

    @setter
    def set_channel_2_invert(self, state: Toggle):
        self._set_channel_n_invert(2, state)

    @getter
    def get_channel_2_invert(self) -> Toggle:
        return self._get_channel_n_invert(2)

    # Equalize phase of both channels
    @setter
    def set_equal_phase(self, state: Toggle):
        if state == ON:
            self.write("EQPHASE")

    # Burst activated
    @setter
    def set_channel_1_burst_state(self, state: Toggle):
        self._set_channel_n_burst_waveform(1, state)

    @getter
    def get_channel_1_burst_state(self) -> Toggle:
        return self._get_channel_n_waveform(1, mode="burst")["STATE"]

    @setter
    def set_channel_2_burst_state(self, state: Toggle):
        self._set_channel_n_burst_waveform(2, state)

    @getter
    def get_channel_2_burst_state(self) -> Toggle:
        return self._get_channel_n_waveform(2, mode="burst")["STATE"]

    # Burst period
    @setter
    def set_channel_1_burst_period(self, period: Union[Float, String]):
        self._set_channel_n_burst_waveform(1, prd=f"{period}")

    @getter
    def get_channel_1_burst_period(self) -> Float:
        prd_str = self._get_channel_n_waveform(1, mode="burst").get("PRD", "nan")

        return float(prd_str.replace("S", ""))

    @setter
    def set_channel_2_burst_period(self, period: Union[Float, String]):
        self._set_channel_n_burst_waveform(2, prd=f"{period}")

    @getter
    def get_channel_2_burst_period(self) -> Float:
        prd_str = self._get_channel_n_waveform(2, mode="burst").get("PRD", "nan")

        return float(prd_str.replace("S", ""))

    # Burst trigger source
    @setter
    def set_channel_1_burst_trigger_source(self, trsr: String):
        self._set_channel_n_burst_waveform(1, trsr)

    @getter
    def get_channel_1_burst_trigger_source(self) -> String:
        return self._get_channel_n_waveform(1, mode="burst").get("TRSR", "?")

    @setter
    def set_channel_2_burst_trigger_source(self, trsr: String):
        self._set_channel_n_burst_waveform(2, trsr)

    @getter
    def get_channel_2_burst_trigger_source(self) -> String:
        return self._get_channel_n_waveform(2, mode="burst").get("TRSR", "?")

    # Burst trigger delay
    @setter
    def set_channel_1_burst_trigger_delay(self, delay: Union[Float, String]):
        self._set_channel_n_burst_waveform(1, dlay=f"{delay}")

    @getter
    def get_channel_1_burst_trigger_delay(self) -> Float:
        dlay_str = self._get_channel_n_waveform(1, mode="burst").get("DLAY", "nan")

        return float(dlay_str.replace("S", ""))

    @setter
    def set_channel_2_burst_trigger_delay(self, delay: Union[Float, String]):
        self._set_channel_n_burst_waveform(2, dlay=f"{delay}")

    @getter
    def get_channel_2_burst_trigger_delay(self) -> Float:
        dlay_str = self._get_channel_n_waveform(2, mode="burst").get("DLAY", "nan")

        return float(dlay_str.replace("S", ""))

    # Burst trigger edge
    @setter
    def set_channel_1_burst_trigger_edge(self, edge: String):
        self._set_channel_n_burst_waveform(1, edge)

    @getter
    def get_channel_1_burst_trigger_edge(self) -> String:
        return self._get_channel_n_waveform(1, mode="burst").get("EDGE", "?")

    @setter
    def set_channel_2_burst_trigger_edge(self, edge: String):
        self._set_channel_n_burst_waveform(2, edge)

    @getter
    def get_channel_2_burst_trigger_edge(self) -> String:
        return self._get_channel_n_waveform(2, mode="burst").get("EDGE", "?")

    # Burst cycles
    @setter
    def set_channel_1_burst_cycles(self, time: Float):
        self._set_channel_n_burst_waveform(1, time)

    @getter
    def get_channel_1_burst_cycles(self) -> Float:
        return float(self._get_channel_n_waveform(1, mode="burst").get("TIME", "nan"))

    @setter
    def set_channel_2_burst_cycles(self, cycles: Float):
        self._set_channel_n_burst_waveform(2, time=f"{cycles}")

    @getter
    def get_channel_2_burst_cycles(self) -> Float:
        return float(self._get_channel_n_waveform(2, mode="burst").get("TIME", "nan"))

    # Burst polarity
    @setter
    def set_channel_1_burst_polarity(self, plrt: String):
        self._set_channel_n_burst_waveform(1, plrt)

    @getter
    def get_channel_1_burst_polarity(self) -> String:
        return self._get_channel_n_waveform(1, mode="burst").get("PLRT", "?")

    @setter
    def set_channel_2_burst_polarity(self, plrt: String):
        self._set_channel_n_burst_waveform(2, plrt)

    @getter
    def get_channel_2_burst_polarity(self) -> String:
        return self._get_channel_n_waveform(2, mode="burst").get("PLRT", "?")
