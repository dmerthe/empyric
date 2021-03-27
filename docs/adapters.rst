.. _adapters-section:

Adapters
========

Every instrument in the instrument collection supports one or more adapters, which facilitate communications between the PC and the instrument. The appropriate adapter depends on which drivers are installed and/or the operating system on the PC. When initializing an instrument Empyric will go through its ``supported_adapters`` tuple and determine which is the best choice for the PC configuration, and instantiate the corresponding adapter object from the choices below.

.. automodule:: empyric.adapters
   :members:
   :exclude-members: chaperone, PrologixGPIBUSB, VISA
