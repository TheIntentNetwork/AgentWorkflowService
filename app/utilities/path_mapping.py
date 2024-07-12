def get_value_from_path(data, path):
    keys = path.split('.')
    for key in keys:
        data = data[key]
    return data

def set_value_from_path(data, path, value):
    keys = path.split('.')
    for key in keys[:-1]:
        data = data.setdefault(key, {})
    data[keys[-1]] = value
def get_value_from_path(data, path):
    keys = path.split('.')
    for key in keys:
        data = data[key]
    return data

def set_value_from_path(data, path, value):
    keys = path.split('.')
    for key in keys[:-1]:
        data = data.setdefault(key, {})
    data[keys[-1]] = value
