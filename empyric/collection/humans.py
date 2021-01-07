# A human is just another instrument
import time

from empyric.adapters import *
from empyric.instruments import Instrument

class ConsoleUser(Instrument):

    name = 'ConsoleUser'

    supported_adapters = (
        (Adapter, {})
    )

    knobs = ('prompt',  # message or query to send to user
             'cooldown')  # minimum time before sending repeat messages

    meters = ('response',)

    last_message = ''
    last_sent = float('-inf')

    def set_prompt(self, prompt):
        self.knob_values['prompt'] = prompt

    def set_cooldown(self, cooldown):
        self.know_values['cooldown'] = cooldown

    def measure_response(self):

        new_message = (self.knob_values['prompt'] != self.last_message)

        if time.time() >= self.last_sent + self.knob_values['cooldown'] or new_message:  # don't spam people
            self.last_response = input(self.knob_values['prompt'] )
            return self.last_response
        else:
            self.last_response
