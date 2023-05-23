.. _instruments-section:

Instruments
===========

An instrument, both physically and within Empyric, is essentially an ensemble of knobs that you set and meters that you measure. Commands to perform these actions are mediated by an adapter (see :ref:`adapters-section`). The methods for setting knobs are of the format, ``set_knob`` or ``set('knob')``, where ``knob`` is the name of the knob. Similarly, measuring a meter is done by calling the instrument's ``measure_meter`` or ``measure('meter')`` methods, where ``meter`` is the name of the meter.

It is also possible to read a knob value from an instrument by calling the ``get_knob`` method of the instrument, if it has one. Otherwise, the last known value of the knob can obtained by retrieving the corresponding attribute of the instrument, e.g. ``instrument.knob`` to get the last known setpoint of ``knob`` on the ``instrument``.

Each instrument has a one or more supported adapters, found by retrieving the ``supported_adapters`` attribute of the class; each element of this tuple contains the adapter class and any non-default settings of that adapter required to communicate with this  instrument.

The supported instruments listed below are subclasses of the ``Instrument`` class:

.. autoclass:: empyric.collection.instrument.Instrument
   :members:
   :undoc-members:

An instance of an instrument from the collection of instruments below can be initialized by importing from ``empyric.instruments``. For example, instantiating a Keithley 2400 sourcemeter is done with the command sequence,

.. code-block::

   from empyric.instruments import Keithley2400
   sourcemeter = Keithley2400(1)  # if GPIB address is 1

.. _collection-section:

Supported Instruments
---------------------

.. toctree::
   :maxdepth: 2
   
   instruments/virtual
   instruments/humans
   instruments/controllers
   instruments/supplies
   instruments/generators
   instruments/multimeters
   instruments/sourcemeters
   instruments/thermometers
   instruments/barometers
   instruments/spectrometers
   instruments/scopes
   instruments/io
