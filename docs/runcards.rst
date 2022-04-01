.. _runcard-section:

Runcards
========

Writing python scripts to run experiments can be tedious, especially when you are doing many similar experiments with slight modifications. To aid in experiment building and documentation, the Empyric library allows one to define an experiment in the runcard format. Empyric can then parse the runcard and run the experiment. In addition to providing a convenient way to automate an experiment, the runcard also serves as easy to read documentation of the experiment.

The following is an example that can be found in the "examples" folder ("examples/Henon Map Experiment/henon_runcard_example.yaml"):

.. literalinclude:: ../examples/Henon Map Experiment/henon_runcard_example.yaml
   :language: yaml

The ``Description`` section contains the name of the experiment, name of the operator, where the experiment is taking place and any relevant comments for future reference. Technically, this section is optional, but it is good practice to fill it out for future reference.

.. code-block:: yaml
   
   Description:
    name: (Unique name of the experiment; default = 'Experiment')
    operator: (Name of person running the experiment)
    platform: (Name of experimental apparatus)
    comments: (Contextual information for the experiment)

The optional ``Settings`` section contains some global settings for the experiment. The ``follow-up`` entry allows one to chain experiments; simply give the path name to another experiment runcard here. The ``step interval`` defines the minimum time to take between experiment iterations. The ``save interval`` specifies how often to save the acquired experimental data. The ``plot interval`` sets a minimum time between updates to the plots specified in the ``Plots`` section.

.. code-block:: yaml
   
   Settings: # All settings below are optional
    follow-up: (None, 'Repeat', or 'another_experiment_runcard.yaml'; default = None)
    step interval: (minimum time between experiment steps; default = 0.1 seconds)
    save interval: (minimum time between data saves to file; default = 60 seconds)
    plot interval: (minimum time between plotting operations; default = 0.1 seconds)
    
The ``Instruments`` section is where you specify which instruments from Empyric's collection the experiment will use (see :ref:`instruments-section` for the full set of supported instruments). For each specification dictionary, the top level key is the name that you endow upon the instrument. Every instrument must have a unique name. The ``type`` is the type of instrument and the ``address`` is the properly formatted address of the instrument (something like "COM3" for a serial instrument at port 3 on a Windows machine). It is also possible to alter the instrument presets by assigning values to the corresponding variable names in the ``presets`` dictionary, as well as set the postsets in a similar way.

.. code-block:: yaml

   Instruments:
    (Unique Name for an Instrument)
     type: (class name of instrument)
     address: (address value used by the adapter to locate and connect the instrument)
     presets:  # optional
      (knob name): (setting to apply to knob upon initialization of the instrument)
     postsets: # optional
      (knob name): (setting to apply to knob upon disconnection of the instrument)
    
The ``Variables`` section defines the experiment variables in relation to the instruments. Each variable must have a unique name. The knob and meter type variables must be assigned an instrument as well as the name of the knob or meter of that instrument. The expression type variables are defined by a mathematical ``expression``, using algebraic operations (``+``, ``-``, ``*``, ``/``, ``^``) and the common functions (sin, exp, log, sum, etc.) that are built into or in the math module of Python. The symbols in the expression are defined by the ``definitions`` entry which maps those symbols to any variables defined above.

.. code-block:: yaml
   
   Variables:
    (Unique Name for a Knob Variable):
     instrument: (Instrument Name)
     knob: (instrument knob name)
    (Unique Name for a Meter Variable):
     instrument: (Instrument Name)
     meter: (instrument meter name)
    (Unique Name for an Expression Variable):
     expression: (python interpretable expression, e.g. 'a + b')
     definitions:
      a: (Name of Other Variable)
      b: (Name of Another Variable)
    (Unique Name for a Parameter Variable):
     parameter: (value, e.g. '3.141592653589793')

The optional ``Alarms`` section contains alarms which can monitor any of the variables and alert the user of any concerning conditions. Each alarm is defined by the variable(s) that it is monitoring, the condition to watch for and the protocol, which tells the experiment manager what to do when an alarm is triggered. Variables can be called out by their names in the condition, or by using aliases, which are defined in the optional definitions dictionary. Possible protocols include 'hold', 'stop' and 'terminate', each of which calls the corresponding method of the ``Experiment`` instance; for 'hold' and 'stop', the experiment manager resumes the experiment when the alarm is cleared. Another option is setting the protocol to another runcard, in which case the current experiment is terminated and the experiment or process defined in the new runcard is run.

.. code-block:: yaml
   
   Alarms:
    (Name for Alarm):
     condition: (python interpretable expression, e.g. 'a > b')
     protocol: (action to take if condition evaluates to True)
     definitions:
      a: (Name of Other Variable)
      b: (Name of Another Variable)

The optional ``Plots`` section defines how to present collected data. Each plot specification requires a ``y`` entry. If no ``x`` entry is given, it assumed that the x-axis will be time. The optional ``xlabel`` and ``ylabel`` entries specify how to label the corresponding axes. A ``style`` can be selected from 'basic' (default simple plot), 'log' (logarithmic y-axis), 'symlog' (logarithmic y-axis for positive and negative values), 'averaged' (y values at the same x value are averaged together), 'errorbars' (same as averaged, but with error bars for the y values at the same x value), 'parametric' (parametric plot with a third parametric variable specified by an optional 'parameter' entry; if no parameter is specified, time will be assumed), 'order' (plot with arrows showing the order in which data was collected).

.. code-block:: yaml
   
   Plots:
    (Name for a Plot)
     x: (Variable on the x-axis)  # defaults to 'Time' is unspecified
     y: (Variable on the y-axis)
     s: (Parametric Variable)  # only used for parametric plots
     style: (plot style, e.g. 'parametric'). # defaults to 'basic' if unspecified
     options: (any other keyword arguments to pass to Matplotlib for plotting customization)

The optional ``Routines`` section defines how the experiment traverses parameter space. A routine (see available routines in :ref:`experiment-section`) sets its assigned knobs depending on the state of the experiment. In the example above, there are 2 routines, named 'Ramp Parameter' a and 'Ramp Parameter b', which are both of the ``Timecourse`` type. These ``Timecourse`` routines set the knob variables 'Parameter a' and 'Parameter b' to the values specified in the ``values`` entry at the times specified in the ``times`` entry. It is also possible to combine similar routines into a single routine. For example, the two routines in the above example can be combined into a single ``Timecourse`` routine that varies both of these parameters together:

.. code-block:: yaml

   Routines:
    (Name of a Set Routine):
     type: Set
     knobs: (knob or list of knobs this routine controls)
     values: (list of fixed values the knobs will be set to)
    (Name of a Timecourse Routine):
     type: Timecourse
     knobs: (knob or list of knobs this routine controls)
     times: (list or array of time points when knobs are set)
     values: (list or array of values the knobs will be set to at the corresponding times)
    (Name of a Sequence Routine):
     type: Sequence
     knobs: (knob or list of knobs this routine controls)
     values: (list or array of values the knobs will be set to sequentially)
    (Name of a Minimization or Maximization Routine):
     type: ('Minimization' or 'Maximization')
     knobs: (knob or list of knobs this routine controls)
     meters: (meter or list of meters to be minimized or maximized) 
             # the sum will be minimized or maximized if a list of meters is given
    
