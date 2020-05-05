# A Human is just another instrument

from basics import *

class User(Instrument):

    name = 'User'

    supported_backends = ['console','twilio']

    knobs = ('message',)

    meters = ('reply',)

    def __init__(self, *args, **kwargs):

        if len(args) > 0:
            self.address = args[0]
        else:
            self.address = None

        self.backend = kwargs.pop('backend', 'console')

        if self.backend == 'twilio':
            self.connection = TwilioDevice(self.address)
        if self.backend == 'console':
            self.connection = ConsoleDevice()

        self.knob_values = {knob: test_df[knob].iloc[0] for knob in User.knobs}

    def set_message(self, message):

        if self.knob_values['message'] != message: # prevents spamming; only send message if message has changed
            self.knob_values['message'] = message
            self.connection.write(message)

    def measure_reply(self):

        return self.connection.query(self.knob_values['message'])

    def disconnect(self):
        pass
