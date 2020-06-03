# A human is just another instrument

from mercury.instruments.basics import *

class ConsoleUser(Instrument):

    name = 'User'

    knobs = ('prompt',  # message or query to send to user
             'cooldown')  # minimum time before sending repeat messages

    meters = ('response',)

    def __init__(self, address=None, backend=None):

        self.knob_values = {'prompt': ''}

    def set_prompt(self, prompt):
        self.knob_values['prompt'] = prompt

    def set_cooldown(self, cooldown):
        self.know_values['cooldown'] = cooldown

    def measure_response(self):

        if time.time() >= self.last_sent + self.know_values['cooldown'] or new_message:  # don't spam people
            return input(self.knob_values['prompt'] )

    def disconnect(self):
        return

class SMSUser(Instrument, TwilioDevice):

    name = 'SMSUser'

    knobs = ('prompt',  # message or query to send to user
             'wait time', # time to wait for a user response
             'cooldown')  # minimum time before sending repeat messages

    meters = ('response',)

    def __init__(self, address, backend='twilio'):

        phone_number = address
        self.connect(phone_number)

        self.knob_values = {'prompt': '', 'wait time': 5*60, 'cooldown':30*60}

        # Find last received message
        self.last_sent = -np.inf
        _, self.last_received = self.read()

    def set_prompt(self, prompt):

        new_message = (self.knob_values['prompt'] != prompt)
        self.knob_values['prompt'] = prompt

        if time.time() >= self.last_sent + self.know_values['cooldown'] or new_message:  # don't spam people
            self.write(prompt)

    def set_wait_time(self, wait_time):
        self.knob_values['wait time'] = wait_time

    def set_cooldown(self, cooldown):
        self.know_values['cooldown'] = cooldown

    def measure_response(self):

        waiting  = True
        wait_time = self.knob_values['wait time']

        start_time = time.time()

        while waiting:  # wait for a response
            body, date_received = self.read()  # get the most recent SMS

            time_difference = date_received - self.last_received

            # Check if a the message is new
            if time_difference.total_seconds() > 0:
                waiting = False

            if time.time() - start_time > wait_time:
                body, date_received = 'NO REPLY', datetime.datetime.fromtimestamp(0)

        self.last_received = date_received
        return body
