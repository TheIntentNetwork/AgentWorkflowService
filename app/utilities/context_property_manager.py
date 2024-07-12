from functools import wraps
import json

class ContextPropertyManager:
    def __init__(self):
        self.property_handlers = {}

    def property_handler(self, handler_type):
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            self.property_handlers[handler_type] = func
            return wrapper
        return decorator

    def handle_property(self, handler_type, *args, **kwargs):
        if handler_type in self.property_handlers:
            return self.property_handlers[handler_type](*args, **kwargs)
        else:
            raise ValueError(f"No handler found for type: {handler_type}")

context_property_manager = ContextPropertyManager()

# Example handlers
@context_property_manager.property_handler('list')
def handle_list_property(data, path, value):
    keys = path.split('.')
    for key in keys[:-1]:
        data = data.setdefault(key, [])
    data[keys[-1]].append(value)
    return data

@context_property_manager.property_handler('string')
def handle_string_property(data, path, value):
    keys = path.split('.')
    for key in keys[:-1]:
        data = data.setdefault(key, "")
    data[keys[-1]] = value
    return data

@context_property_manager.property_handler('json')
def handle_json_property(data, path, value):
    keys = path.split('.')
    for key in keys[:-1]:
        data = data.setdefault(key, {})
    data[keys[-1]] = json.dumps(value)
    return data
