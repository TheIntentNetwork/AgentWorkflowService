# CreateNodes Class Not Fully Defined Error

## Error Message

```
ERROR:asyncio:Task exception was never retrieved
future: <Task finished name='Task-6' coro=<EventManager.__event_listener() done, defined at C:\Users\Bryan\Source\Repos\AgentWorkflowService\app\services\events\event_manager.py:125> exception=PydanticUserError('`CreateNodes` is not fully defined; you should define `Agent`, then call `CreateNodes.model_rebuild()`.')>
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
  File "C:\Users\Bryan\Source\Repos\AgentWorkflowService\app\models\Agent.py", line 364, in init_oai
    self._update_assistant()
  File "C:\Users\Bryan\Source\Repos\AgentWorkflowService\app\models\Agent.py", line 406, in _update_assistant
    "tools": self.get_oai_tools(),
             ^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\Bryan\Source\Repos\AgentWorkflowService\app\models\Agent.py", line 573, in get_oai_tools
    schema = tool.openai_schema
             ^^^^^^^^^^^^^^^^^^
  File "C:\Users\Bryan\Source\Repos\AgentWorkflowService\app\tools\base_tool.py", line 54, in openai_schema
    schema = super(BaseTool, cls).openai_schema
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "c:\Users\Bryan\Source\Repos\AgentWorkflowService\.venv\Lib\site-packages\instructor\function_calls.py", line 30, in openai_schema
    schema = cls.model_json_schema()
             ^^^^^^^^^^^^^^^^^^^^^^^
  File "c:\Users\Bryan\Source\Repos\AgentWorkflowService\.venv\Lib\site-packages\pydantic\main.py", line 433, in model_json_schema
    return model_json_schema(
           ^^^^^^^^^^^^^^^^^^
  File "c:\Users\Bryan\Source\Repos\AgentWorkflowService\.venv\Lib\site-packages\pydantic\json_schema.py", line 2236, in model_json_schema
    cls.__pydantic_validator__.rebuild()
  File "c:\Users\Bryan\Source\Repos\AgentWorkflowService\.venv\Lib\site-packages\pydantic\_internal\_mock_val_ser.py", line 55, in rebuild
    raise PydanticUserError(self._error_message, code=self._code)
pydantic.errors.PydanticUserError: `CreateNodes` is not fully defined; you should define `Agent`, then call `CreateNodes.model_rebuild()`.
```

## Possible Causes

1. **Class Definition Order**: The `CreateNodes` class might be referenced before it is fully defined.
2. **Forward References**: Forward references in Pydantic models need to be resolved correctly.

## Solution

1. **Ensure Class Definition Order**: Make sure that the `CreateNodes` class is defined before it is used.
2. **Call `model_rebuild()`**: After defining the `CreateNodes` class, call `CreateNodes.model_rebuild()` to resolve any forward references.

## Example

```python
from pydantic import BaseModel

class CreateNodes(BaseModel):
    # Define the class attributes here

# Call model_rebuild() to resolve forward references
CreateNodes.model_rebuild()
```

## References

- [Pydantic Documentation: Class not fully defined](https://errors.pydantic.dev/2.7/u/class-not-fully-defined)
