# Empyric 
## A Python Library for Experiment Automation

For more details, [read the docs](https://empyric.readthedocs.io/en/latest/).

Empyric, at its most basic level, is an easy-to-use Python interface for communication with and controlling laboratory instruments, such as digital multimeters, oscilloscopes, and power supplies. On top of that is a general purpose experiment-building architecture, which allows the user to combine process control, measurements and data plotting in a highly customizable fashion, using a straightforward "runcard" formalism, which additionally serves the purpose of experiment documentation.

The preferred way to install Empyric is using [poetry](https://python-poetry.org/). Within your preferred environment and within the empyric root directory, make sure poetry is install and then install empyric:
```commandline
pip install poetry
poetry install
```

Empyric can also be installed with pip:
```commandline
pip install empyric
```
This works with either Python 3.11 or 3.12. (Empyric relies on Matplotlib for plotting, which does not yet support Python 3.13).

### Instruments and Adapters

Empyric contains a number of *instruments* with various associated methods of communication, such as serial or GPIB. For example, to remotely control a Keithley 2400 Sourcemeter from your PC, simply import the `Keithley2400` object from the library and instantiate it with its GPIB address:

```
from empyric.instruments import Keithley2400

keithley2400 = Keithley2400(1)  # if GPIB address is 1

kiethley2400.set_voltage(10)  # sets output voltage to 10 volts
current = keithley2400.measure_current()  # measures current in amperes
```

Communication with instruments is facilitated through Empyric's library of *adapters*. If you have an instrument that is not in the Empyric library but which uses one of the more common communication protocols (Serial, GPIB, USBTMC, Modbus, etc.), you can still make use of Empyric's adapters, which automatically manage many of the underlying details of the communication backends:

```
from empyric.instruments import Instrument
from empyric.adapters import Modbus

class MyInstrument(Instrument):
	"""
	Basic template of an instrument object in Empyric
	"""

	name = 'MyInstrument'
	
	supported_adapters = ((Modbus, {'baud_rate':115200}),)
	
	knobs = ('some knob',)
	meters = ('some meter',)
	
	def set_some_knob(self, value):
		# set your knob
	
	def measure_some_meter(self):
		# measure your meter
	
instrument = MyInstrument('COM5::1')  # connect to your instrument

some_meter_value = instrument.measure_some_meter()  # take a measurement

```

### Experiments

The real purpose of Empyric is to simplify and standardize construction of an experiment, and automate its execution. The two main elements of an experiment are its *variables* which are controlled and/or measured by your instruments, and *routines* which are the various processes that you run on your controllable variables.

*Variables* come in five flavors: knobs, meters, expressions, parameters and remotes. A knob is a variable that you can directly control through an instrument, such as voltage from a power supply. A meter is a variable that you directly measure through an instrument, such as temperature from a thermocouple. In some cases, a meter can be controlled indirectly through a feedback loop. For example, PID temperature controllers provide a temperature knob (the setpoint) as well as a temperature meter (the actual temperature measured with a thermocouple or RTD). An expression is a variable that is evaluated in terms of other experiment variables, such as the power delivered by a power supply being the product of the voltage knob value and the current meter value. A parameter is a user-defined value that is relevant to the experiment, such as a unit conversion factor, a variable setpoint (e.g. used in a routine) or a quantity that must be manually logged. A remote variable is a variable defined in another experiment with a server routine running, that can be read or controlled remotely. A variable's value can be read and set through its `value` property.

Here is an example showing how to define and use variables in Empyric:
```
from empyric.variables import Knob, Meter, Parameter, Expression
from empyric.instruments import Keithley2400

keithley2400 = Keithley2400(1)

voltage = Knob(instrument=keithley2400, knob='voltage')
current = Meter(instrument=keithley2400, meter='current')
milliwatt = Parameter(parameter = 1e-3)
power = Expression(expression='V * I / mW', definitions={'V':voltage, 'I':current, 'mW':milliwatt})

voltage.value = 10 # sets the voltage of the Keithley 2400 to 10 V

# Obtain 10 measurements of current, voltage and power sourced by a Keithley 2400
measurements = [[current.value, voltage.value, power.value] for i in range(10)]
```

*Routines* allow one to define the trajectory that an experiment takes through parameter space over the duration of the experiment. Every routine has a set of knobs that it updates based on a given state, containing the current time (in seconds) and values of all relevant variables. The most basic routine is the `Set` routine:
```
import time

# ... define knob1 and knob2 as instances of Knob from above

knobs = {'Knob 1': knob1, 'Knob 2': knob2}
values = [10, 20]

# Keep knob1 at a value of 10, and knob2 at a value of 20 for 60 seconds
set_routine = Set(knobs, values, start=0, end=60)

start_time = time.time()

state = {'Time': 0, 'Knob 1': None, 'Knob 2': None} # define a process state

while state['Time'] <= 60:
	
	state['Time'] = time.time() - start_time  # update process time
	
	set_routine.update(state) # update process state, based on the set routine
	
	state['Knob 1] = knob1.value
	state['Knob 2] = knob2.value
	
	print(state)  # prints "{'Time': ..., 'Knob 1': 10, 'Knob 2': 20}"
```

An *Experiment* monitors a set of variables as a set of routines takes action on them. In Empyric, the `Experiment` object is an iterable that updates routines and records data on each iteration, which has a defined state. It also has `start`, `hold` and `stop` methods which initiate/resume the experiment, holds routines while continuing to measure meters, and stops all routines and measurements, respectively. The `terminate` method saves the collected data to a file in the working directory and raises the `StopIteration` exception. An experiment will terminate automatically when all routines are finished. See henon_python_eaxmple.py in the 'examples/Henon Map Experiment' directory to see how a basic experiment is set up as a python script. This particular example uses a virtual instrument (`HenonMapper`), so the only requirement to run it is having Python installed along with the usual scientific packages (numpy, scipy, pandas and matplotlib).