.. _gui-section:

The Experiment GUI and Plotting 
===============================

The ``graphics`` module of empyric provides a graphical user interface
(GUI) through the ``ExperimentGUI`` class, with which a user can monitor
and interact with an experiment, and the ``Plotter`` class which
provides some shortcuts for generating plots of experiment data.


The ``Plotter`` class takes a pandas DataFrame as its only required
argument, and plot settings are defined by the optional ``settings``
keyword argument. The given DataFrame must have a 'time' column and
datetime indices. If no plot settings are specified, it is assumed that
all columns except the 'time' column in the DataFrame are to be
plotted against the 'time' column, in one plot. The private methods of 
``Plotter`` listed below should not be used directly, but are called from 
the ``plot`` method based on the plot settings.

 .. autoclass:: empyric.graphics.Plotter
    :members:
    :private-members:


The ``ExperimentGUI`` class takes an instance of ``Experiment`` as its
only required argument. It can also be optionally equipped with alarms,
a set of instruments, an experiment name, and plot specifications
through keyword arguments. When a ``Manager`` is instantiated with a
runcard, it constructs and runs an instance of this GUI.

 .. autoclass:: empyric.graphics.ExperimentGUI 
    :members:
