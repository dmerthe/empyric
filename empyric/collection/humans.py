# A human is just another instrument
import time

from empyric.adapters import *
from empyric.collection.instrument import *
from empyric.types import String, Float


class ConsoleUser(Instrument):
    """
    Virtual instrument that queries a human operator via the Python console

    The prompt is what the user is asked; the cooldown is the minimum time
    between input requests
    """

    name = 'ConsoleUser'

    supported_adapters = (
        (Adapter, {}),
    )

    knobs = ('prompt',  # message or query to send to user
             'cooldown')  # minimum time before sending repeat messages

    presets = {
        'cooldown': 0,
        'prompt': '?'
    }

    meters = ('response',)

    response = ''

    last_prompt = ''
    last_sent = float('-inf')

    @setter
    def set_prompt(self, prompt: String):
        pass

    @setter
    def set_cooldown(self, cooldown: Float):
        pass

    @measurer
    def measure_response(self) -> String:

        new_prompt = (self.prompt != self.last_prompt)

        if time.time() >= self.last_sent + self.cooldown or new_prompt:

            response = input(self.prompt)

            self.last_prompt = self.prompt

        return response
