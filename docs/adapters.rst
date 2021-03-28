.. _adapters-section:

Adapters
========

Every instrument in the instrument collection supports one or more adapters, which facilitate communications between the PC and the instrument. The appropriate adapter depends on which drivers are installed and/or the operating system on the computer. When initializing an instrument Empyric will go through its ``supported_adapters`` tuple and determine which is the best choice for the PC configuration, and instantiate the corresponding adapter object from the choices below.

The write, read and query methods of the adapters are wrapped by a ``chaperone`` function, which monitors communications and handles issues. When a communication failure occurs, such as no response, an empty response or an improper response, the chaperone attempts to repeat the method call, up to a maximum number of times as set by the ``max_attempts`` attribute of the adapter. If it reaches this maximum number of attempts, it resets the adapter, up to ``max_reconnects`` times, and again attempts to repeat the method call up to ``max_attempts`` times. If both the reconnects and attempts reach their limits, a ``ConnectionError`` is raised.

The ``chaperone`` function also aids in multithreading: when multiple communications are attempted simultaneously with the same instrument, the ``chaperone`` function enqueues each write, read or query method until the communication channel is free.

Each wrapped write, read and query method accepts a ``validator`` function as an optional keyword argument. A ``validator``` takes as its only argument the response of the unwrapped write/read/query method, and returns ``True`` if the response is of the correct form or ``False`` if it is not. The ``chaperone`` function checks the returned value of the ``validator`` function, if one is provided, to assess if the communication was successful.

.. automodule:: empyric.adapters
   :members:
   :exclude-members: chaperone, PrologixGPIBUSB, VISA
