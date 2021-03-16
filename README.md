# Empyric 
## A Python Library for Experiment Automation

Empyric, at its most basic level, is an easy to use Python interface for communication with and controlling scientific instruments, such as digital multimeters, digital oscilloscopes, and power supplies. On top of that is a general purpose experiment-building architecture, which allows the user to combine process control, measurements and data plotting in a highly customizable fashion, using a straightforward "runcard" formalism, which additionally serves the purpose of experiment documentation.

### Instruments and Adapters

Empyric contains a number of *instruments* with various associated methods of communication, such as serial or GPIB. For example, to connect to a Keithley 2400 Sourcemeter simply import the `Keithley2400` object from the library and instantiate it with its GPIB address:

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

The real purpose of Empyric is to simplify and standardize construction of an experiment, and automate its execution. The two main elements of an experiment are its *variables* which are controlled and/or measured by your instruments, and *routines* which are the various processes that you run on your controllable variables.

*Variables* come in three flavors: knobs, meters and expressions. A knob is a variable that you can directly control through an instrument, such as voltage from a power supply. A meter is a variable that you directly measure through an instrument, such as temperature from a thermocouple. In some cases, a meter can be controlled indirectly through a feedback loop. For example, PID temperature controllers provide a temperature knob (the setpoint) as well as a temperature meter (the actual temperature measured with a thermocouple or RTD). An expression is a variable that is evaluated in terms of other experiment variables, such as the power delivered by a power supply being the product of the voltage knob value and the current meter value.

Here is an example showing how to define and use experiment variables in Empyric:
```
from empyric.experiment import Variable
from empyric.instruments import Keithley2400

keithley2400 = Keithley2400('GPIB0::1::INSTR')

voltage = Variable(instrument=keithley2400, knob='voltage')
current = Variable(instrument=keithley2400, meter='current')
power = Variable(expression='V * I', definitions={'V':voltage, 'I':current})

voltage.value = 10 # sets the voltage of the Keithley 2400 to 10 V

# Obtain 10 measurements of current and power sourced by the Keithley 2400
measurements = [[current.value, power.value] for i in range(10)]
```
Assigning a value to the `value` property of a knob-type variable commands the corresponding instrument to set the associated knob accordingly, and the value is stored in the corresponding attribute of the instrument. Calling the `value` property of a meter-type variable commands the corresponding instrument to record a measurement of the associated meter, and then return the value as well as store it as an attribute of the instrument. Calling the `value` property of an expression-type variable retrieves the values of the variables that define it from the stored attributes of the corresponding knobs, meters and other expressions; it does not trigger any new measurements. Therefore, for repeated calls, be sure to trigger measurements or retrievals of the values of any defining variables prior to each evaluation of the expression.

*Routines* allow one to define the trajectory that an experiment takes through parameter space over the duration of the experiment. Every routine has a start and end, assigned variables and assigned values. Routines update their associated variables based on a supplied state, indicating current time and values of all variables. The most basic routine is the hold routine:
```
import time

# ... define variable1 and variable2 as instances of Variable from above

variables = {'Variable 1':variable1, 'Variable 2':variable2}
values = [10, 20]

# Hold variable1 at a value of 10, and variable2 at a value of 20 for 60 seconds
hold = Hold(variables, values, start=0, end=60)

start_time = time.time()

while True:

	t = time.time() - start_time  # get time since beginning of process
	
	state = {'time': t, 'Variable 1': None, 'Variable 2': None} # define a process state
	
	new_values = hold.update(state)  # get the updated values from the hold routine
	
	state.update(new_values) # update the process state
	
	print(state)  # prints "{'time': t, 'Variable 1': 10, 'Variable 2': 20}"
	
	if t > 60:
		break

```