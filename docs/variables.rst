.. _variables-section:

Variables
=================================
Variables represent the quantities of interest in an experiment. The classes
below provide a layer of abstraction away from the particular hardware or
software origin of the variable value. Each variable has a `value` property
which evaluates the variable when called, e.g. 'foo = variable.value'. If the
variable is settable, such as a `Knob` or `Parameter`, the value property can
be set by assignment, e.g. `knob.value = foo`.

.. autoclass:: empyric.variables.Variable
   :members:
   :private-members: _settable

|

.. autoclass:: empyric.variables.Knob
   :members:
   :private-members: _settable

|

.. autoclass:: empyric.variables.Meter
   :members:
   :private-members: _settable

|

.. autoclass:: empyric.variables.Expression
   :members:
   :private-members: _settable

|

.. autoclass:: empyric.variables.Remote
   :members:
   :private-members: _settable

|

.. autoclass:: empyric.variables.Parameter
   :members:
   :private-members: _settable