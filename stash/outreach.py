from twilio.rest import Client

client = Client("AC2adbf0c1d8877fd83462fddb044b1ecd", "6c176312ec91dcb732fc96f4214ec499")

# change the "from_" number to your Twilio number and the "to" number
# to the phone number you signed up for Twilio with, or upgrade your
# account to send SMS to any phone number
client.messages.create(to="+17863983685",
                       from_="+12064017596",
                       body="bitch where's my money")

class