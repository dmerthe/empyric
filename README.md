# Empyric Experiment Automation Library

Empyric, at its most basic level, is an easy to use interface for communication with and controlling scientific instruments, such as digital multimeters, digital oscilloscopes, and power supplies. On top of that is a general purpose experiment-building architecture, which allows the user to combine process control, measurements and data plotting in a highly customizable fashion, using a straightforward "runcard" formalism, which additionally serves the purpose of experiment documentation.

At its core, Empyric contains a number of instrument objects with various associated methods of communication, such as serial or GPIB. For example, to connect to a Keithley 2400 Sourcemeter simply import the `Keithley2000` object from the library and instantiate it with its GPIB address:

```
from empyric.instruments import Keithley2400
keithley2400 = Keithley2400('GPIB0::1::INSTR')
```
