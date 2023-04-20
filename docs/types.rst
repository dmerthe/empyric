.. _types-section:

Data Types
=================================
In order to standardize data handling in Empyric, values of variables as well
as instrument knobs and meters are funneled into the following data types.
Booleans, Integers, Floats, Strings and Arrays are stored internally as
`numpy.bool_`, `numpy.int64`, `numpy.float64`, `numpy.str_` and
`numpy.ndarray`, respectively.

.. autoclass:: empyric.types.Type
   :members:

.. autoclass:: empyric.types.Boolean
   :members:

|

.. autoclass:: empyric.types.Toggle
   :members:

|

.. autoclass:: empyric.types.Integer
   :members:

|

.. autoclass:: empyric.types.Float
   :members:

|

.. autoclass:: empyric.types.String
   :members:

|

.. autoclass:: empyric.types.Array
   :members:

.. autofunction:: empyric.types.recast
