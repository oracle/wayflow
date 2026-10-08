<a id="serialization"></a>

# Serialization / Deserialization

## Base classes

<a id="serializableobject"></a>

### *class* wayflowcore.serialization.serializer.SerializableObject(\_\_metadata_info_\_=None, id=None)

Abstract base class for WayFlow components that can be serialized and deserialized.

This class provides a common interface for objects that need to be converted to and from a dictionary representation.

* **Parameters:**
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **id** (*str* *|* *None*)

#### *classmethod* get_component(component_type)

* **Return type:**
  `Type`[[`SerializableObject`](#wayflowcore.serialization.serializer.SerializableObject)]
* **Parameters:**
  **component_type** (*str*)

## Serialization

<a id="serializationcontext"></a>

### *class* wayflowcore.serialization.context.SerializationContext(root, plugins=None)

SerializationContext helps ensure that duplicated objects
(e.g. reused steps in a nested Flow) are serialized only once.

* **Parameters:**
  * **root** (*Any*)
  * **plugins** (*List* *[*[*WayflowSerializationPlugin*](#wayflowcore.serialization.plugins.WayflowSerializationPlugin) *]*  *|* *None*)

#### check_obj_is_already_serialized(obj)

Returns True if the object has already been serialized

* **Parameters:**
  **obj** (`Any`) – The original, non-serialized object
* **Return type:**
  `bool`

#### get_all_referenced_objects()

Returns the dict containing all referenced objects

* **Return type:**
  `Dict`[`str`, `Any`]

#### *static* get_reference(obj)

Returns the formatted string that is used by the serialization context to reference the
object

* **Parameters:**
  **obj** (`Any`) – The original, non-serialized object
* **Return type:**
  `str`

#### get_reference_dict(obj)

Returns a dict that contains a single entry “$ref”

* **Parameters:**
  **obj** (`Any`) – The original, non-serialized object
* **Return type:**
  `Dict`[`str`, `str`]

#### get_serialization_plugin_for_object(obj)

* **Return type:**
  [`WayflowSerializationPlugin`](#wayflowcore.serialization.plugins.WayflowSerializationPlugin)
* **Parameters:**
  **obj** ([*SerializableObject*](#wayflowcore.serialization.serializer.SerializableObject))

#### is_root(obj)

Check if one object is the root of the ongoing serialization process

* **Parameters:**
  **obj** (`Any`) – The original, non-serialized object
* **Return type:**
  `bool`

#### record_obj_dict(obj, obj_as_dict)

Records the serialization-as-dict of a serialized object

* **Parameters:**
  * **obj** (`Any`) – The original, non-serialized object
  * **obj_as_dict** (`Dict`[`Any`, `Any`]) – The object serialized as a dict
* **Return type:**
  `None`

#### start_serialization(obj)

Records that the serialization of an object will start. If the object has already been
serialized, then it should do nothing, but if the serialization has started and not
completed, then an error is raised because one object is referencing itself, which we do
not support.

* **Parameters:**
  **obj** (`Any`) – The original, non-serialized object
* **Return type:**
  `None`

<a id="serialize"></a>

### wayflowcore.serialization.serializer.serialize(obj, serialization_context=None, plugins=None)

Serializes an object into a YAML string representation.

* **Parameters:**
  * **obj** ([`SerializableObject`](#wayflowcore.serialization.serializer.SerializableObject)) – Object to serialize.
  * **serialization_context** (`Optional`[[`SerializationContext`](#wayflowcore.serialization.context.SerializationContext)]) – Context for serialization operations. Keeps track of serialized objects to avoid serializing them several times.
    If not provided, a new `SerializationContext` will be created with the object as its root.
  * **plugins** (`Optional`[`List`[[`WayflowSerializationPlugin`](#wayflowcore.serialization.plugins.WayflowSerializationPlugin)]]) – List of plugins to be used in the SerializationContext.
    If a serialization context instance is provided, this list is ignored.
* **Return type:**
  `str`
* **Returns:**
  A YAML string representation of the object.

### Examples

```pycon
>>> from wayflowcore.serialization.serializer import serialize
>>>
>>> serialized_assistant_as_str = serialize(assistant)
```

## Deserialization

<a id="deserializationcontext"></a>

### *class* wayflowcore.serialization.context.DeserializationContext(plugins=None)

* **Parameters:**
  **plugins** (*List* *[*[*WayflowDeserializationPlugin*](#wayflowcore.serialization.plugins.WayflowDeserializationPlugin) *]*  *|* *None*)

#### add_referenced_objects(new_referenced_objects)

* **Return type:**
  `None`
* **Parameters:**
  **new_referenced_objects** (*Dict* *[**str* *,* *Dict* *[**Any* *,* *Any* *]* *]*)

#### check_reference_is_already_deserialized(object_reference)

Returns True if the object is already deserialized

* **Parameters:**
  **object_reference** (`str`) – The reference of the object being deserialized
* **Return type:**
  `bool`

#### get_deserialization_plugin_for_object(obj_type)

* **Return type:**
  [`WayflowDeserializationPlugin`](#wayflowcore.serialization.plugins.WayflowDeserializationPlugin)
* **Parameters:**
  **obj_type** (*Type* *[*[*SerializableObject*](#wayflowcore.serialization.serializer.SerializableObject) *]*)

#### get_deserialized_object(object_reference)

Returns the object already deserialized

* **Parameters:**
  **object_reference** (`str`) – The reference of the object being deserialized
* **Return type:**
  `Any`

#### get_referenced_dict(object_reference)

Returns the object object_as_dict for a given object reference

* **Parameters:**
  **object_reference** (`str`) – The reference of the object being deserialized
* **Return type:**
  `Dict`[`Any`, `Any`]

#### recorddeserialized_object(object_reference, deserialized_object)

Records the object deserialized, such that it may be reused during the deserialization
process

* **Parameters:**
  * **object_reference** (`str`) – The reference of the object being deserialized
  * **deserialized_object** (*Any*)
* **Return type:**
  `None`

#### start_deserialization(object_reference)

Records that the deserialization of an object will start. If the object has already been
deserialized, then it should do nothing, but if the deserialization has started and not
completed, then an error is raised because one object is referencing itself, which we do
not support.

* **Parameters:**
  **object_reference** (`str`) – The reference of the object being deserialized
* **Return type:**
  `None`

<a id="deserialize"></a>

### wayflowcore.serialization.serializer.deserialize(deserialization_type, obj, deserialization_context=None, plugins=None)

Deserializes an object from its text representation and its corresponding class.

* **Parameters:**
  * **deserialization_type** (`Type`[`TypeVar`(`T`, bound= [`SerializableObject`](#wayflowcore.serialization.serializer.SerializableObject))]) – The type of the object to be deserialized.
  * **obj** (`str`) – The text representation of the object to be deserialized.
  * **deserialization_context** (`Optional`[[`DeserializationContext`](#wayflowcore.serialization.context.DeserializationContext)]) – Context for deserialization operations, to avoid deserializing a same object twice.
    If not provided, a new `DeserializationContext` will be created.
  * **plugins** (`Optional`[`List`[[`WayflowDeserializationPlugin`](#wayflowcore.serialization.plugins.WayflowDeserializationPlugin)]]) – List of plugins to be used in the DeserializationContext.
    If a deserialization context instance is provided, this list is ignored.
* **Return type:**
  `TypeVar`(`T`, bound= [`SerializableObject`](#wayflowcore.serialization.serializer.SerializableObject))
* **Returns:**
  The deserialized object.

### Examples

```pycon
>>> from wayflowcore.serialization.serializer import deserialize
>>> from wayflowcore.flow import Flow
>>>
>>> new_assistant = deserialize(Flow, serialized_assistant_as_str)
```

<a id="autodeserialize"></a>

### wayflowcore.serialization.serializer.autodeserialize(obj, deserialization_context=None, plugins=None)

Deserializes an object from its text representation.

* **Parameters:**
  * **obj** (`str`) – The text representation of the object to be deserialized.
  * **deserialization_context** (`Optional`[[`DeserializationContext`](#wayflowcore.serialization.context.DeserializationContext)]) – Context for deserialization operations, to avoid deserializing a same object twice.
    If not provided, a new `DeserializationContext` will be created.
  * **plugins** (`Optional`[`List`[[`WayflowDeserializationPlugin`](#wayflowcore.serialization.plugins.WayflowDeserializationPlugin)]]) – List of plugins to be used in the DeserializationContext.
    If a deserialization context instance is provided, this list is ignored.
* **Return type:**
  [`SerializableObject`](#wayflowcore.serialization.serializer.SerializableObject)
* **Returns:**
  The deserialized object.

### Examples

```pycon
>>> from wayflowcore.serialization.serializer import autodeserialize
>>>
>>> new_assistant = autodeserialize(serialized_assistant_as_str)
```

## Plugins

WayFlow Plugins are the expected mean that users can use to introduce new concepts and components, or extensions to existing ones,
such that they can be integrated seamlessly into the serialization, deserialization, and Agent Spec conversion processes
of WayFlow.

<a id="wayflowserializationplugin"></a>

### *class* wayflowcore.serialization.plugins.WayflowSerializationPlugin

Base class for a Wayflow Plugin.

#### *abstract* convert_to_agentspec(conversion_context, runtime_component, referenced_objects)

Convert a Wayflow component to Agent Spec

* **Return type:**
  `Component`
* **Parameters:**
  * **conversion_context** ([*WayflowToAgentSpecConversionContext*](agentspec.md#wayflowcore.agentspec._agentspecconverter.WayflowToAgentSpecConversionContext))
  * **runtime_component** ([*SerializableObject*](#wayflowcore.serialization.serializer.SerializableObject))
  * **referenced_objects** (*Dict* *[**str* *,* *Component* *]*)

#### *abstract property* plugin_name *: str*

Return the plugin name.

#### *abstract property* plugin_version *: str*

Return the plugin version.

#### *abstract property* required_agentspec_serialization_plugins *: List[ComponentSerializationPlugin]*

Indicate what Agent Spec serialization plugins are required for this WayFlow converter

#### serialize(obj, serialization_context)

Serialize a component that the plugin should support.

* **Return type:**
  `Dict`[`str`, `Any`]
* **Parameters:**
  * **obj** ([*SerializableObject*](#wayflowcore.serialization.serializer.SerializableObject))
  * **serialization_context** ([*SerializationContext*](#wayflowcore.serialization.context.SerializationContext))

#### *abstract property* supported_component_types *: List[str]*

Indicate what component types the plugin supports.

<a id="wayflowdeserializationplugin"></a>

### *class* wayflowcore.serialization.plugins.WayflowDeserializationPlugin

Base class for a Wayflow Plugin.

#### *abstract* convert_to_wayflow(conversion_context, agentspec_component, tool_registry, converted_components)

Convert an Agent Spec component to Wayflow

* **Return type:**
  `Any`
* **Parameters:**
  * **conversion_context** ([*AgentSpecToWayflowConversionContext*](agentspec.md#wayflowcore.agentspec._runtimeconverter.AgentSpecToWayflowConversionContext))
  * **agentspec_component** (*Component*)
  * **tool_registry** (*dict* *[**str* *,* [*ServerTool*](tools.md#wayflowcore.tools.servertools.ServerTool) *|* *Callable* *[* *[* *...* *]* *,* *Any* *]* *]*)
  * **converted_components** (*Dict* *[**str* *,* *Any* *]*)

#### deserialize(obj_type, input_dict, deserialization_context)

* **Return type:**
  [`SerializableObject`](#wayflowcore.serialization.serializer.SerializableObject)
* **Parameters:**
  * **obj_type** (*Type* *[*[*SerializableObject*](#wayflowcore.serialization.serializer.SerializableObject) *]*)
  * **input_dict** (*Dict* *[**str* *,* *Any* *]*)
  * **deserialization_context** ([*DeserializationContext*](#wayflowcore.serialization.context.DeserializationContext))

#### *abstract property* plugin_name *: str*

Return the plugin name.

#### *abstract property* plugin_version *: str*

Return the plugin version.

#### *abstract property* required_agentspec_deserialization_plugins *: List[ComponentDeserializationPlugin]*

Indicate what Agent Spec deserialization plugins are required for this WayFlow converter

#### *abstract property* supported_component_types *: List[str]*

Indicate what component types the plugin supports.
