from typing import Any, Dict
import weakref

class ResourceTracker:
    def __init__(self):
        self.resources: Dict[str, Dict[int, weakref.ref]] = {}

    def track(self, resource_type: str, instance: Any):
        if resource_type not in self.resources:
            self.resources[resource_type] = {}
        self.resources[resource_type][id(instance)] = weakref.ref(instance)

    def get_count(self, resource_type: str) -> int:
        return len([ref for ref in self.resources.get(resource_type, {}).values() if ref() is not None])

    def get_all_counts(self) -> Dict[str, int]:
        return {rt: self.get_count(rt) for rt in self.resources}

# Create a global instance of ResourceTracker
resource_tracker = ResourceTracker()
