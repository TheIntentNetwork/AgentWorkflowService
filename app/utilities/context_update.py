from functools import wraps
import json

class ContextUpdate:
    def update(self, data, path, value):
        raise NotImplementedError("This method should be overridden by subclasses")

class ListUpdate(ContextUpdate):
    def update(self, data, path, value):
        keys = path.split('.')
        for key in keys[:-1]:
            data = data.setdefault(key, [])
        data[keys[-1]].append(value)
        return data

class StringUpdate(ContextUpdate):
    def update(self, data, path, value):
        # Split the path into keys using '.' as the delimiter
        keys = path.split('.')
        # Iterate over all keys except the last one
        for key in keys[:-1]:
            # If the key is not in data or the value is not a dictionary, set it to an empty dictionary
            if key not in data or not isinstance(data[key], dict):
                data[key] = {}
            # Move to the next level in the dictionary
            data = data[key]
        # Set the value at the final key
        data[keys[-1]] = value
        # Return the updated data
        return data

class JSONUpdate(ContextUpdate):
    def update(self, data, path, value):
        keys = path.split('.')
        for key in keys[:-1]:
            data = data.setdefault(key, {})
        data[keys[-1]] = json.dumps(value)
        return data

class ContextUpdateManager:
    def __init__(self):
        self.update_handlers = {}

    def register_handler(self, handler_type, handler):
        self.update_handlers[handler_type] = handler

    def get_handler(self, handler_type):
        return self.update_handlers.get(handler_type, ContextUpdate)

context_update_manager = ContextUpdateManager()
context_update_manager.register_handler('list', ListUpdate())
context_update_manager.register_handler('string', StringUpdate())
context_update_manager.register_handler('json', JSONUpdate())
