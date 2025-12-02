.. _serialization:

Serialization / Deserialization
===============================

Base classes
------------

.. _serializableobject:
.. autoclass:: wayflowcore.serialization.serializer.SerializableObject


Serialization
-------------

.. _serialize:
.. autofunction:: wayflowcore.serialization.serializer.serialize


Deserialization
---------------

.. _deserialize:
.. autofunction:: wayflowcore.serialization.serializer.deserialize

.. _autodeserialize:
.. autofunction:: wayflowcore.serialization.serializer.autodeserialize


Plugins
-------

WayFlow Plugins are the expected mean that users can use to introduce new concepts and components, or extensions to existing ones,
such that they can be integrated seamlessly into the serialization, deserialization, and Agent Spec conversion processes
of WayFlow.

.. _wayflowserializationplugin:
.. autoclass:: wayflowcore.serialization.plugins.WayflowSerializationPlugin

.. _wayflowdeserializationplugin:
.. autoclass:: wayflowcore.serialization.plugins.WayflowDeserializationPlugin
