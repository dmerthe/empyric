# A human is just another instrument
import time

from empyric.adapters import *
from empyric.instruments import *

class ConsoleUser(Instrument):

    name = 'ConsoleUser'

    supported_adapters = (
        (Adapter, {}),
    )

    knobs = ('prompt',  # message or query to send to user
             'cooldown')  # minimum time before sending repeat messages

    presets = {'cooldown':0}

    meters = ('response',)

    last_message = ''
    last_sent = float('-inf')

    @setter
    def set_prompt(self, prompt):
        self.prompt = prompt

    @setter
    def set_cooldown(self, cooldown):
        self.cooldown = cooldown

    @measurer
    def measure_response(self):

        new_message = (self.prompt != self.last_message)

        if time.time() >= self.last_sent + self.cooldown or new_message:  # don't spam user

            self.last_response = input(self.prompt)

            self.last_sent = time.time()
            self.last_message = self.prompt

        return self.last_response
