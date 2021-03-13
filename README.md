# Empyric 
## A Python Library for Experiment Automation

Empyric, at its most basic level, is an easy to use Python interface for communication with and controlling scientific instruments, such as digital multimeters, digital oscilloscopes, and power supplies. On top of that is a general purpose experiment-building architecture, which allows the user to combine process control, measurements and data plotting in a highly customizable fashion, using a straightforward "runcard" formalism, which additionally serves the purpose of experiment documentation.

### Instruments and Adapters

Empyric contains a number of *instruments* with various associated methods of communication, such as serial or GPIB. For example, to connect to a Keithley 2400 Sourcemeter simply import the `Keithley2000` object from the library and instantiate it with its GPIB address:

```
from empyric.instruments import Keithley2400

keithley2400 = Keithley2400('GPIB0::1::INSTR')

kiethley2400.set('voltage', 10)
current = keithley2400.measure('current')
```

Communication with instruments is facilitated through Empyric's library of *adapters*. If you have an instrument that is not in the Empyric library but which uses one of the more common communication protocols (Serial, GPIB, USBTMC, Modbus, etc.), you can still make use of Empyric's adapters, which automatically manage many of the underlying details of the communication backends:

```
from empyric.instruments import Instrument
from empyric.adapters import Modbus

class MyInstrument(Instrument):
	"""
	Basic template of an instrument object in Empyric
	"""

	name = 'My Instrument'
	
	supported_adapters = ((Modbus, {'baud_rate':115200}),)
	
	knobs = ('knob',)
	meters = ('meter',)
	
	def set_knob(self, value):
		# ... set your knob
	
	def measure_meter(self):
		# ... measure your meter
	
instrument = MyInstrument('COM5::1')
adapter = Modbus(instrument)  # adapter connects to your instrument

meter_value = instr.measure_meter()

```

### Experiments

The real purpose of Empyric is to simplify and standardize construction of an experiment, and automate its execution. The two main elements of an experiment are its *variables*, which are controlled or measured by your instruments, *routines*, which is the collection of any processes that you run on your controllable variables.

