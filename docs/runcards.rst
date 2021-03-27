Runcards
========

Writing python scripts to run experiments can be tedious, especially when you are doing many similar experiments with slight modifications. To aid in experiment building and documentation, the Empyric library allows one to define an experiment in the runcard format. Empyric can then parse the runcard and run the experiment. In addition to providing a convenient way to automate an experiment, the runcard also serves as easy to read documentation of the experiment.

The following illustrates a typical experiment runcard:

.. literalinclude:: ../empyric/examples/Henon Map Experiment/henon_runcard_example.yaml
   :language: yaml

The ``Description`` section contains the name of the experiment, name of the operator, where the experiment is taking place and any relevant comments for future reference.

The optional ``Settings`` section contains some global settings for the experiment. The ``follow-up`` entry allows one to chain experiments; simply give the path name to another experiment runcard here. The ``step interval`` defines the minimum time to take between experiment iterations. The ``plot interval`` sets a minimum time between calls the any ``matplotlib`` plotting functions. The ``save interval`` specifies how often to save the acquired experimental data.

The ``Instruments`` section is where you specify which instruments from Empyric's collection the experiment will use. For each specification dictionary, the top level key is the name that you endow upon the instrument (here it is "Henon Mapper"). Every instrument must have a unique name. The ``type`` is the class name from the collection and the ``address`` is the properly formatted address of the instrument (something like "COM3" for a serial instrument at port 3 on a Windows machine; the HenonMapper virtual instrument here uses a dummy address of 1). It is also possible to alter the instrument presets by assigning values to the corresponding variable names in this dictionary. The entries ``a: 0`` and ``b: 0`` set both knobs *a* and *b* to 0 immediately upon creation of the ``HenonMapper`` instance.

The ``Variables`` section defines the experiment variables in relation to the instruments. Each variable must have a unique name. The knob and meter type variables must be assigned an instrument as well as the name of the knob or meter. The expression type variables are defined by a mathematical ``expression``, using algebraic operations (+, -, *, /, ^) and the common functions (sin, exp, log, sum, etc.) that are built into or in the math module of Python. The symbols in the expression are defined by the ``definitions`` entry which maps those symbols to any variables defined above.

The optional ``Alarms`` section contains alarms which can monitor any of the variables and alert the user of any concerning conditions. Each alarm is defined by the variable that it is monitoring, the condition to watch for and the protocol, which tells the experiment manager what to do when an alarm is triggered. Possible protocols include 'hold', 'stop' and 'terminate', each of which calls the corresponding method of the ``Experiment`` instance; for 'hold' and 'stop', the experiment manager resumes the experiment when the alarm is cleared. Another option is setting the protocol to another runcard, in which case the current experiment is terminated and the experiment or process defined in the new runcard is built and run.

The optional ``Plots`` section defines how to present collected data. Each plot specification requires a ``y`` entry. If no ``x`` entry is given, it assumed that the x-axis will be time. The optional ``xlabel`` and ``ylabel`` entries specify how to label the corresponding axes. A ``style`` can be selected from 'basic' (default simple plot), 'log' (logarithmic y-axis), 'symlog' (logarithmic y-axis for positive and negative values), 'averaged' (y values at the same x value are averaged together), 'errorbars' (same as averaged, but with error bars for the y values at the same x value), 'parametric' (parametric plot with a third parametric variable specified by an optional 'parameter' entry; if no parameter is specified, time will be assumed as the parameter), 'order' (plot with arrows showing the order in which data was collected).

The optional ``Routines`` section defines how the experiment traverses parameter space. A routine (see available routines in :ref:`experiment-section`) sets its assigned knob variables depending on the state of the experiment. In the example above, there are 2 routines, named 'Ramp Parameter' a and 'Ramp Parameter b', which are both of the ``Timecourse`` type. These ``Timecourse`` routines set the variables 'Parameter a' and 'Parameter b' to the values specified in the ``values`` entry at the times specified in the ``times`` entry. It is also possible to combined similar routines into a single routine. For example, the two routines in this example can be combined into a single ``Timecourse`` routine that varies both of these parameters together:

.. code-block:: yaml

   Routines: 
    Ramp Parameters a and b:
     type: Timecourse
     variables: [Parameter a, Parameter b]
     times: [ [0.0, 0.0, 1.4, 1.4] , [0.0, 0.0, 1.4, 1.4] ]
     values: [ [0.0, 0.0, 1.4, 1.4] , [0.0, 0.0, 0.3, 0.3] ]