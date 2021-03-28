Instruments
===========

An instrument is generally a collection of knobs and meters that you set and measure, respectively, through an adapter (see :ref:`adapters-section`). The methods for setting knobs are of the format, ``set_knob`` or ``set('knob')``, where ``knob`` is the name of the knob. Similarly, measuring a meter is done by calling the instrument's ``measure_meter`` or ``measure('meter')`` methods, where ``meter`` is the name of the meter.

It is also possible to read a knob value from an instrument by calling the ``get_knob`` method of the instrument, if it has one. Otherwise, the last known value of the knob can obtained by retrieving the corresponding attribute of the instrument, e.g. ``power_supply.voltage`` to get the last known setpoint of knob ``voltage`` on the instrument ``power_supply``.

Each instrument has a one or more supported adapters, found by retrieving the ``supported_adapters`` attribute of the class.

The instruments listed in the collection below are supported by the empyric module, and are subclasses of the ``Instrument`` class:

.. autoclass:: empyric.collection.instrument.Instrument
   :members:


The Collection
--------------

.. toctree::
   :maxdepth: 2
	
   instruments/humans
   instruments/controllers
   instruments/supplies
   instruments/multimeters
   instruments/sourcemeters
   instruments/thermometers
   instruments/barometers
   instruments/spectrometers
   instruments/scopes


The ``HenonMapper`` is a virtual instrument that is useful for testing in the absense of a physical instrument:
   
.. autoclass:: empyric.collection.instrument.HenonMapper
   :members:
   