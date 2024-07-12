from abc import ABC, abstractmethod

class IExecutionService(ABC):
    
    @abstractmethod
    def get_dependencies(self):
        pass
    
    @abstractmethod
    def register_outputs(self):
        pass

    
    @abstractmethod

    def assign_agents(self):
        pass
    
    @abstractmethod

    def notify_status(self):
        pass

    
    @abstractmethod
    def execute(self):
        pass