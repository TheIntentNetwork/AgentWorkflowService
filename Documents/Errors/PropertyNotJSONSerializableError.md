# Property Not JSON Serializable Error

## Error Message

```
ERROR:asyncio:Task exception was never retrieved
future: <Task finished name='Task-6' coro=<EventManager.__event_listener() done, defined at C:\Users\Bryan\Source\Repos\AgentWorkflowService\app\services\events\event_manager.py:125> exception=TypeError('Object of type property is not JSON serializable')>
Traceback (most recent call last):
  ...
  File "C:\Users\Bryan\AppData\Local\Programs\Python\Python311\Lib\json\encoder.py", line 180, in default
    raise TypeError(f'Object of type {o.__class__.__name__} '
TypeError: Object of type property is not JSON serializable
```

## Possible Causes

1. **JSON Serialization of Property Objects**: The error occurs when trying to JSON serialize an object of type `property`. This typically happens when a class property (created using the `@property` decorator) is being included in a JSON serialization process.

2. **Incorrect Data Structure**: A `property` object might have been inadvertently included in a data structure that is being JSON serialized.

3. **Custom Encoder Issues**: If a custom JSON encoder is being used, it might not be handling `property` objects correctly.

## Solutions

1. **Exclude Properties from Serialization**:
   - If using Pydantic, ensure that properties are not included in the `model_dump()` or `dict()` output.
   - For custom serialization, explicitly exclude property objects.

2. **Convert Properties to Regular Attributes**:
   - If the property values need to be serialized, consider converting them to regular attributes before serialization.

3. **Custom JSON Encoder**:
   - Implement a custom JSON encoder that can handle `property` objects.

## Example Fix

```python
from pydantic import BaseModel, Field

class MyClass(BaseModel):
    regular_field: str
    
    @property
    def some_property(self) -> str:
        return f"Property: {self.regular_field}"

    def model_dump(self, *args, **kwargs):
        kwargs.setdefault("exclude", set()).add("some_property")
        return super().model_dump(*args, **kwargs)

# Usage
my_instance = MyClass(regular_field="test")
serialized_data = my_instance.model_dump()  # some_property will be excluded
```

This approach ensures that the `property` is excluded from JSON serialization, avoiding the TypeError.

## References

- [Python property decorator](https://docs.python.org/3/library/functions.html#property)
- [JSON encoding in Python](https://docs.python.org/3/library/json.html#json.JSONEncoder)
- [Pydantic custom JSON encoding](https://docs.pydantic.dev/latest/usage/model_config/#custom-json-encoders)
# TypeError: Object of type property is not JSON serializable

## Error Message

```
ERROR:asyncio:Task exception was never retrieved
future: <Task finished name='Task-6' coro=<EventManager.__event_listener() done, defined at C:\Users\Bryan\Source\Repos\AgentWorkflowService\app\services\events\event_manager.py:125> exception=TypeError('Object of type property is not JSON serializable')>
Traceback (most recent call last):
  File "C:\Users\Bryan\Source\Repos\AgentWorkflowService\app\services\events\event_manager.py", line 147, in __event_listener
    await type_class.handle(key, action, context)
  File "C:\Users\Bryan\Source\Repos\AgentWorkflowService\app\models\Task.py", line 90, in handle 
    await instance.execute()
  File "C:\Users\Bryan\Source\Repos\AgentWorkflowService\app\models\Task.py", line 195, in execute
    agency = Agency(agency_chart=agency_chart, shared_instructions="", session_id=self.session_id)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\Bryan\Source\Repos\AgentWorkflowService\app\models\agency.py", line 114, in __init__
    self._init_agents()
  File "C:\Users\Bryan\Source\Repos\AgentWorkflowService\app\models\agency.py", line 628, in _init_agents
    agent.init_oai()
  File "C:\Users\Bryan\Source\Repos\AgentWorkflowService\app\models\Agent.py", line 363, in init_oai
    self._update_assistant()
  File "C:\Users\Bryan\Source\Repos\AgentWorkflowService\app\models\Agent.py", line 413, in _update_assistant
    self.assistant = self.client.beta.assistants.update(
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "c:\Users\Bryan\Source\Repos\AgentWorkflowService\.venv\Lib\site-packages\openai\resources\beta\assistants.py", line 303, in update
    return self._post(
           ^^^^^^^^^^^
  File "c:\Users\Bryan\Source\Repos\AgentWorkflowService\.venv\Lib\site-packages\openai\_base_client.py", line 1240, in post
    return cast(ResponseT, self.request(cast_to, opts, stream=stream, stream_cls=stream_cls))    
                           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^     
  File "c:\Users\Bryan\Source\Repos\AgentWorkflowService\.venv\Lib\site-packages\openai\_base_client.py", line 921, in request
    return self._request(
           ^^^^^^^^^^^^^^
  File "c:\Users\Bryan\Source\Repos\AgentWorkflowService\.venv\Lib\site-packages\openai\_base_client.py", line 942, in _request
    request = self._build_request(options)
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "c:\Users\Bryan\Source\Repos\AgentWorkflowService\.venv\Lib\site-packages\openai\_base_client.py", line 484, in _build_request
    return self._client.build_request(  # pyright: ignore[reportUnknownMemberType]
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "c:\Users\Bryan\Source\Repos\AgentWorkflowService\.venv\Lib\site-packages\httpx\_client.py", line 357, in build_request
    return Request(
           ^^^^^^^^
  File "c:\Users\Bryan\Source\Repos\AgentWorkflowService\.venv\Lib\site-packages\httpx\_models.py", line 340, in __init__
    headers, stream = encode_request(
                      ^^^^^^^^^^^^^^^
  File "c:\Users\Bryan\Source\Repos\AgentWorkflowService\.venv\Lib\site-packages\httpx\_content.py", line 212, in encode_request
    return encode_json(json)
           ^^^^^^^^^^^^^^^^^
  File "c:\Users\Bryan\Source\Repos\AgentWorkflowService\.venv\Lib\site-packages\httpx\_content.py", line 175, in encode_json
    body = json_dumps(json).encode("utf-8")
           ^^^^^^^^^^^^^^^^
  File "C:\Users\Bryan\AppData\Local\Programs\Python\Python311\Lib\json\__init__.py", line 231, in dumps
    return _default_encoder.encode(obj)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\Bryan\AppData\Local\Programs\Python\Python311\Lib\json\encoder.py", line 200, in encode
    chunks = self.iterencode(o, _one_shot=True)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\Bryan\AppData\Local\Programs\Python\Python311\Lib\json\encoder.py", line 258, in iterencode
    return _iterencode(o, 0)
           ^^^^^^^^^^^^^^^^^
  File "C:\Users\Bryan\AppData\Local\Programs\Python\Python311\Lib\json\encoder.py", line 180, in default
    raise TypeError(f'Object of type {o.__class__.__name__} '
TypeError: Object of type property is not JSON serializable
```

## Possible Causes

1. **JSON serialization of `property` objects**: The error occurs when trying to serialize a Python `property` object to JSON. This typically happens when a class attribute is defined as a `property` and an instance of that class is being serialized.

2. **Incorrect data structure**: The data structure being passed to the JSON serializer might contain `property` objects, which are not directly serializable.

3. **Custom JSON encoders**: If custom JSON encoders are being used, they might not be properly handling `property` objects.

## Solutions

1. **Exclude properties from serialization**: 
   - If using Pydantic, you can use the `model_dump()` or `dict()` methods with the `exclude` parameter to exclude properties from serialization.
   - Example:
     ```python
     data = model.model_dump(exclude={'property_field'})
     ```

2. **Convert properties to regular attributes**:
   - Before serialization, you can create a new dictionary with only the serializable attributes.
   - Example:
     ```python
     serializable_data = {k: v for k, v in vars(obj).items() if not isinstance(v, property)}
     ```

3. **Implement a custom JSON encoder**:
   - Create a custom JSON encoder that handles `property` objects.
   - Example:
     ```python
     from json import JSONEncoder
     
     class CustomEncoder(JSONEncoder):
         def default(self, obj):
             if isinstance(obj, property):
                 return obj.fget(obj)  # or some other representation
             return super().default(obj)
     
     json.dumps(data, cls=CustomEncoder)
     ```

## Example Fix

Here's an example of how you might fix this issue using Pydantic:

```python
from pydantic import BaseModel, Field

class MyModel(BaseModel):
    regular_field: str
    property_field: str = Field(exclude=True)

    @property
    def property_field(self):
        return f"Computed value: {self.regular_field}"

# When serializing
my_instance = MyModel(regular_field="test")
serialized_data = my_instance.model_dump()  # property_field will be excluded
```

This approach ensures that the `property` is excluded from JSON serialization, avoiding the TypeError.

## References

- [Python property() function](https://docs.python.org/3/library/functions.html#property)
- [Pydantic Field exclusion](https://docs.pydantic.dev/latest/usage/models/#field-exclusion)
- [JSON encoder and decoder](https://docs.python.org/3/library/json.html#json.JSONEncoder)
