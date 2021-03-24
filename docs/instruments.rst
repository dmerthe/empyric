Instruments
===========

The instruments listed below are supported by the empyric module. All supported instruments are subclasses of the ``Instrument`` class:

.. autoclass:: empyric.collection.instrument.Instrument
   :members:

An instrument is generally a collection of knobs and meters that you set and measure, respectively, through an adapter (see :ref:`adapters-section`). The methods for setting knobs are of the format, ``set_knob_name`` or ``set('knob_name')``, where ``knob_name`` is the name of the knob. Similarly, measuring a meter is done by calling the instrument's ``measure_meter_name`` or ``measure('meter_name')`` methods.

Often, it is also possible to read a knob value from an instrument, which is done by calling the ``get_knob_name`` method of the instrument, if it has one.

The Collection
--------------

.. toctree::
   :maxdepth: 2

   sourcemeters
   barometers
   spectrometers

Virtual Instruments
-------------------

The ``HenonMapper`` class is useful for testing in the absense of a physical instrument:
   
.. autoclass:: empyric.collection.instrument.HenonMapper
   :members:
   