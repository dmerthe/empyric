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
        "channel 1 mode",
        "channel 2 mode",
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
        "channel 2 burst polarity"
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

    def _set_channel_n_waveform(self, n, is_basic_param=False, **kwargs):
        # If the mode is being switched from basic/burst, the desired returned waveform should be opposite
        if "mode" in kwargs:
            waveform_dict = self._get_channel_n_waveform(n, mode_override=True)
        else:    
            waveform_dict = self._get_channel_n_waveform(n)
            # # Check the validity of keyword args
            # for key in kwargs:
            #     if key.upper() not in waveform_dict and key.upper() != "CWVTP":
            #         raise ValueError(
            #             f"parameter {key} is not valid for waveform type "
            #             f'{kwargs["WVTP"]}'
            #         )

        # Get burst mode state
        if waveform_dict.get("STATE") == None:
            burst_mode = "basic"
        else:
            burst_mode = "burst"

        # note: consider making a "is basic wave param" boolean argument. if so, the command is sent with basic wave structure.
        # Create appropriate command based on basic/burst waveform mode
        if burst_mode == "basic" or is_basic_param:
            parameter_string = f"C{n}:BSWV " + ",".join(
                [f"{key.upper()},{value}" for key, value in kwargs.items()]
            )
        else:
            # For burst waveforms only, the wavetype parameter must be corrected
            parameter_string = f"C{n}:BTWV "
            for key, value in kwargs.items():
                if key == "CWVTP":
                    parameter_string += f"CARR,WVTP,{value}, "
                else:
                    parameter_string += f"{key.upper()},{value}, "

        # Changing the waveform parameters can cause the relative phase
        # of the two channels to shift
        self.equal_phase = OFF

        self.write(parameter_string)

    def _get_channel_n_waveform(self, n, mode_override = False):
        # Determine if burst mode is on by querying state
        bt_response = self.query(f"C{n}:BTWV?")[3:]
        burst_mode_on = True
        key_correction = False
        if "BTWV STATE,OFF" in bt_response:
            burst_mode_on = False

        if burst_mode_on:
            if mode_override == True: 
                # Mode is changing from burst to basic, return basic dictionary
                self.write(f"C{n}:BTWV STATE, OFF")  # turn burst mode off
                response = self.query(f"C{n}:BSWV?")
                response = response.split(f"C{n}:BSWV ")[1].split(",")
            else:
                # Burst mode is active and unchanged, return active dictionary
                burst_response = bt_response.split(f"BTWV ")[1].split("CARR,")[0]
                carrier_response = bt_response.split(f"BTWV ")[1].split("CARR,")[1]
                response = (burst_response + carrier_response).split(",")
                key_correction = True
        else:
            if mode_override == True: 
                # Mode is changing from basic to burst, return burst dictionary
                self.write(f"C{n}:BTWV STATE, ON")  # turn burst mode on
                bt_response = self.query(f"C{n}:BTWV?")[3:]
                burst_response = bt_response.split(f"BTWV ")[1].split("CARR,")[0]
                carrier_response = bt_response.split(f"BTWV ")[1].split("CARR,")[1]
                response = (burst_response + carrier_response).split(",")
                key_correction = True
            else:
                # Basic mode is active and unchanged, return active dictionary
                response = self.query(f"C{n}:BSWV?")
                response = response.split(f"C{n}:BSWV ")[1].split(",")
        
        keys = response[::2]
        values = response[1::2]

        waveform_dict = {key: value for key, value in zip(keys, values)}

        # If returned dictionary is for burst mode, correct key name for wavetype
        if key_correction:
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
        
    def _get_mode(self, n):
        knob_name = "get_" + f"channel {n} mode".replace(" ", "_")
        return self.__getattribute__(knob_name)().lower()
        
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
        if self._get_mode(1) == "burst":
            # send the burst (carrier) waveform key
            self._set_channel_n_waveform(1, cwvtp=waveform)
        else:
            self._set_channel_n_waveform(1, wvtp=waveform)

    @getter
    def get_channel_1_waveform(self) -> String:
        if self._get_mode(1) == "burst":
            return self._get_channel_n_waveform(1)["CARR,WVTP"]
        else:
            return self._get_channel_n_waveform(1)["WVTP"]

    @setter
    def set_channel_2_waveform(self, waveform: String):
        if self._get_mode(2) == "burst":
            # send the burst (carrier) waveform key
            self._set_channel_n_waveform(2, cwvtp=waveform)
        else:
            self._set_channel_n_waveform(2, wvtp=waveform)

    @getter
    def get_channel_2_waveform(self) -> String:
        if self._get_mode(2) == "burst":
            return self._get_channel_n_waveform(2)["CARR,WVTP"]
        else:
            return self._get_channel_n_waveform(2)["WVTP"]

    # Waveform high level
    @setter
    def set_channel_1_high_level(self, high_level: Union[Float, String]):
        self._set_channel_n_waveform(1, is_basic_param=True, hlev=f"{high_level}")

    @getter
    def get_channel_1_high_level(self) -> Float:
        high_level_str = self._get_channel_n_waveform(1).get("HLEV", "nan")

        return float(high_level_str.replace("V", ""))

    @setter
    def set_channel_2_high_level(self, high_level: Union[Float, String]):
        self._set_channel_n_waveform(2, is_basic_param=True, hlev=f"{high_level}")

    @getter
    def get_channel_2_high_level(self) -> Float:
        high_level_str = self._get_channel_n_waveform(2).get("HLEV", "nan")

        return float(high_level_str.replace("V", ""))

    # Waveform low level
    @setter
    def set_channel_1_low_level(self, low_level: Union[Float, String]):
        self._set_channel_n_waveform(1, is_basic_param=True, llev=f"{low_level}")

    @getter
    def get_channel_1_low_level(self) -> Float:
        low_level_str = self._get_channel_n_waveform(1).get("LLEV", "nan")

        return float(low_level_str.replace("V", ""))

    @setter
    def set_channel_2_low_level(self, low_level: Union[Float, String]):
        self._set_channel_n_waveform(2, is_basic_param=True, llev=f"{low_level}")

    @getter
    def get_channel_2_low_level(self) -> Float:
        low_level_str = self._get_channel_n_waveform(2).get("LLEV", "nan")

        return float(low_level_str.replace("V", ""))

    # Waveform frequency
    @setter
    def set_channel_1_frequency(self, frequency: Union[Float, String]):
        self._set_channel_n_waveform(1, frq=f"{frequency}")

    @getter
    def get_channel_1_frequency(self) -> Float:
        freq_str = self._get_channel_n_waveform(1).get("FRQ", "nan")

        return float(freq_str.replace("HZ", ""))

    @setter
    def set_channel_2_frequency(self, frequency: Union[Float, String]):
        self._set_channel_n_waveform(2, frq=f"{frequency}")

    @getter
    def get_channel_2_frequency(self) -> Float:
        freq_str = self._get_channel_n_waveform(2).get("FRQ", "nan")

        return float(freq_str.replace("HZ", ""))

    # Pulse width
    @setter
    def set_channel_1_pulse_width(self, width: Union[Float, String]):
        self._set_channel_n_waveform(1, width=f"{width}")

    @getter
    def get_channel_1_pulse_width(self) -> Float:
        width_str = self._get_channel_n_waveform(1).get("WIDTH", "nan")

        return float(width_str.replace("S", ""))

    @setter
    def set_channel_2_pulse_width(self, width: Union[Float, String]):
        self._set_channel_n_waveform(2, width=f"{width}")

    @getter
    def get_channel_2_pulse_width(self) -> Float:
        width_str = self._get_channel_n_waveform(2).get("WIDTH", "nan")

        return float(width_str.replace("S", ""))

    # Pulse rise
    @setter
    def set_channel_1_pulse_rise(self, rise: Union[Float, String]):
        self._set_channel_n_waveform(1, rise=f"{rise}")

    @getter
    def get_channel_1_pulse_rise(self) -> Float:
        delay_str = self._get_channel_n_waveform(1).get("RISE", "nan")

        return float(delay_str.replace("S", ""))

    @setter
    def set_channel_2_pulse_rise(self, rise: Union[Float, String]):
        self._set_channel_n_waveform(2, rise=f"{rise}")

    @getter
    def get_channel_2_pulse_rise(self) -> Float:
        delay_str = self._get_channel_n_waveform(2).get("RISE", "nan")

        return float(delay_str.replace("S", ""))

    # Pulse fall
    @setter
    def set_channel_1_pulse_fall(self, fall: Union[Float, String]):
        self._set_channel_n_waveform(1, fall=f"{fall}")

    @getter
    def get_channel_1_pulse_fall(self) -> Float:
        delay_str = self._get_channel_n_waveform(1).get("FALL", "nan")

        return float(delay_str.replace("S", ""))

    @setter
    def set_channel_2_pulse_fall(self, fall: Union[Float, String]):
        self._set_channel_n_waveform(2, fall=f"{fall}")

    @getter
    def get_channel_2_pulse_fall(self) -> Float:
        delay_str = self._get_channel_n_waveform(2).get("FALL", "nan")

        return float(delay_str.replace("S", ""))

    # Pulse delay
    @setter
    def set_channel_1_pulse_delay(self, delay: Union[Float, String]):
        self._set_channel_n_waveform(1, dly=f"{delay}")

    @getter
    def get_channel_1_pulse_delay(self) -> Float:
        delay_str = self._get_channel_n_waveform(1).get("DLY", "nan")

        return float(delay_str.replace("S", ""))

    @setter
    def set_channel_2_pulse_delay(self, delay: Union[Float, String]):
        self._set_channel_n_waveform(2, dly=f"{delay}")

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

    # Burst/basic mode
    @setter
    def set_channel_1_mode(self, mode: String):
        self._set_channel_n_waveform(1, mode=mode)
    @getter
    def get_channel_1_mode(self) -> String:
        dct = self._get_channel_n_waveform(1)
        if dct.get("STATE") == None:
            return "BASIC"
        else:
            return "BURST"

    @setter
    def set_channel_2_mode(self, mode: String):
        self._set_channel_n_waveform(2, mode=mode)

    @getter
    def get_channel_2_mode(self) -> String:
        dct = self._get_channel_n_waveform(2)
        if dct.get("STATE") == None:
            return "BASIC"
        else:
            return "BURST"
    
    # Burst period
    @setter
    def set_channel_1_burst_period(self, period: Union[Float, String]):
        self._set_channel_n_waveform(1, prd=f"{period}")

    @getter
    def get_channel_1_burst_period(self) -> Float:
        prd_str = self._get_channel_n_waveform(1).get("PRD", "nan")

        return float(prd_str.replace("S", ""))
    

    @setter
    def set_channel_2_burst_period(self, period: Union[Float, String]):
        self._set_channel_n_waveform(2, prd=f"{period}")

    @getter
    def get_channel_2_burst_period(self) -> Float:
        prd_str = self._get_channel_n_waveform(2).get("PRD", "nan")

        return float(prd_str.replace("S", ""))
    
    # Burst trigger source
    @setter
    def set_channel_1_burst_trigger_source(self, trigsrc: String):
        self._set_channel_n_waveform(1, trsr=f"{trigsrc}")

    @getter
    def get_channel_1_burst_trigger_source(self) -> String:
        trs = self._get_channel_n_waveform(1).get("TRSR", "nan")

        return trs
    

    @setter
    def set_channel_2_burst_trigger_source(self, trigsrc: String):
        self._set_channel_n_waveform(2, trsr=f"{trigsrc}")

    @getter
    def get_channel_2_burst_trigger_source(self) -> String:
        trs = self._get_channel_n_waveform(2).get("TRSR", "nan")

        return trs
    
    # Burst trigger delay
    @setter
    def set_channel_1_burst_trigger_delay(self, delay: Union[Float, String]):
        self._set_channel_n_waveform(1, dlay=f"{delay}")

    @getter
    def get_channel_1_burst_trigger_delay(self) -> Float:
        dlay_str = self._get_channel_n_waveform(1).get("DLAY", "nan")

        return float(dlay_str.replace("S", ""))
    

    @setter
    def set_channel_2_burst_trigger_delay(self, delay: Union[Float, String]):
        self._set_channel_n_waveform(2, dlay=f"{delay}")

    @getter
    def get_channel_2_burst_trigger_delay(self) -> Float:
        dlay_str = self._get_channel_n_waveform(2).get("DLAY", "nan")

        return float(dlay_str.replace("S", ""))
    
    # Burst trigger edge
    @setter
    def set_channel_1_burst_trigger_edge(self, edge: String):
        self._set_channel_n_waveform(1, edge=f"{edge}")

    @getter
    def get_channel_1_burst_trigger_edge(self) -> String:
        return self._get_channel_n_waveform(1).get("EDGE")

    @setter
    def set_channel_2_burst_trigger_edge(self, edge: String):
        self._set_channel_n_waveform(2, edge=f"{edge}")

    @getter
    def get_channel_2_burst_trigger_edge(self) -> String:
        return self._get_channel_n_waveform(2).get("EDGE")
    
    # Burst cycles
    @setter
    def set_channel_1_burst_cycles(self, cycles: String):
        self._set_channel_n_waveform(1, time=f"{cycles}")

    @getter
    def get_channel_1_burst_cycles(self) -> Float:
        return self._get_channel_n_waveform(1).get("TIME")

    @setter
    def set_channel_2_burst_cycles(self, cycles: Float):
        self._set_channel_n_waveform(2, time=f"{cycles}")

    @getter
    def get_channel_2_burst_cycles(self) -> String:
        return self._get_channel_n_waveform(2).get("TIME")
    
    # Burst polarity
    @setter
    def set_channel_1_burst_polarity(self, polarity: String):
        self._set_channel_n_waveform(1, plrt=f"{polarity}")

    @getter
    def get_channel_1_burst_polarity(self) -> Float:
        return self._get_channel_n_waveform(1).get("PLRT")

    @setter
    def set_channel_2_burst_polarity(self, polarity: Float):
        self._set_channel_n_waveform(2, plrt=f"{polarity}")

    @getter
    def get_channel_2_burst_polarity(self) -> String:
        return self._get_channel_n_waveform(2).get("PLRT")