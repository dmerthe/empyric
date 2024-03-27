.. _experiment-section:

Experiments
=================================

There are two kinds of experiments to choose from: ``Experiment`` and
``AsyncExperiment``.

An ``Experiment`` is an iterable that updates its variables
and routines in a synchronized fashion. On each iteration it spawns threads to
update each routine, waits until all routines are updated, spawns threads to
update each variable, waits until all variables are updated and then returns
the ``state`` of the experiment. The benefit of this is that on each iteration,
there is a well-defined state of the variables, and clear cause and effect
with knobs being changed by routines and the ensuing response of the variables
being recorded afterwards. The drawback is that the speed of iterations is
limited by the slowest update process.

An ``AsyncExperiment`` is used the same way as an ``Experiment`` but
the updating of variables and routines is executed asynchronously and as quickly
as possible. The advantage is that iterations are generally faster and the
``state`` is updated more frequently. The downside is that iterations may miss
some variable values and the causality between routines changing variables and
the responses of variables to those changes may be less clear.


.. autoclass:: empyric.experiment.Experiment
   :members:

|

.. autoclass:: empyric.experiment.AsyncExperiment
   :members:

|

.. autoclass:: empyric.experiment.Alarm
   :members:

|
.. autoclass:: empyric.experiment.Manager
   :members:
