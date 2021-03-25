Runcards
========

Writing python scripts to run experiments can be tedious, especially when you are doing many similar experiments with slight modifications. To aid in experiment building and documentation, the Empyric library allows one to define an experiment via the runcard format.

The following illustrates the main features of an experiment runcard:

.. literalinclude:: henon_runcard_example.yaml
   :language: yaml

The ``Description`` section contains the name of the experiment, name of the operator, where the experiment is taking place and any relevant comments for future reference.

The ``Settings`` section contains some global settings for the experiment. The ``follow-up`` entry allows one to chain experiments; simply give the path name to another experiment runcard here. The ``step interval`` defines the minimum time to take between experiment iterations. The ``plot interval`` sets a minimum time between calls the any ``matplotlib`` plotting functions. The ``save interval`` specifies how often to save the acquired experimental data.

The ``Instruments`` section is where you specify which instruments from Empyric's collection the experiment will use. For each specification dictionary, the top level key is the name that you endow upon the instrument. The ``type`` is the class name from the collection and the ``address`` is the properly formatted address of the instrument (something like "COM3" for a serial instrument at port 3 on a Windows machine). It is also possible to alter the instrument presets by assigning values to the corresponding variable names in this dictionary. For example, The ``HenonMapper`` instrument has knobs *a* and *b*. To set *a* to 0.5 upon connection with the instruments, one would add ``a: 0.5`` within the ``Henon Mapper`` specification.