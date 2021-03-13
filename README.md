# Empyric 
## A Python Library for Experiment Automation

### Basics

Empyric, at its most basic level, is an easy to use Python interface for communication with and controlling scientific instruments, such as digital multimeters, digital oscilloscopes, and power supplies. On top of that is a general purpose experiment-building architecture, which allows the user to combine process control, measurements and data plotting in a highly customizable fashion, using a straightforward "runcard" formalism, which additionally serves the purpose of experiment documentation.

Empyric contains a number of *instruments* with various associated methods of communication, such as serial or GPIB. For example, to connect to a Keithley 2400 Sourcemeter simply import the `Keithley2000` object from the library and instantiate it with its GPIB address:

```
from empyric.instruments import Keithley2400

keithley2400 = Keithley2400('GPIB0::1::INSTR')

kiethley2400.set('voltage', 10)
current = keithley2400.measure('current')
```

Communication with instruments is facilitated through Empyric's library of *adapters*. If you have an instrument that is not in the Empyric library but which uses one of the more common communication protocols (Serial, GPIB, USBTMC, Modbus, etc.), you can still make use of Empyric's adapters, which automatically manage many of the underlying details of the communication backends:

```
from empyric.adapters import Modbus
from empyric.instruments import Instrument  # stand-in for you custom instrument

instr = Instrument('COM5::1')  # serial port 5, slave address 1
adapter = Modbus(instr, baud_rate=115200)

instr.measure('whatever')

```


