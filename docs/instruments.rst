Instruments
===========

The instruments listed below are supported by the empyric module. All supported instruments are subclasses of the ``Instrument`` class:

.. autoclass:: empyric.collection.instrument.Instrument
   :members:

An instrument is generally a collection of knobs and meters that you control through an adapter (see `adapters`_).

Virtual Instruments
-------------------

The ``HenonMapper`` class is useful for testing in the absense of a physical instrument:
   
.. autoclass:: empyric.collection.instrument.HenonMapper
   :members:
   