from app.models.Node import Node
from typing import List, Dict, Any
from app.utilities.logger import get_logger

class Model(Node):
    type: str = "model"
    collection: List[Dict[str, Any]] = []

    async def execute(self):
        logger = get_logger('Model')
        logger.info(f"Executing model: {self.name}")
        
        # Execute child nodes
        for node_data in self.collection:
            node = await Node.create(**node_data, session_id=self.session_id)
            await node.execute()

    @classmethod
    async def create(cls, **model_data):
        logger = get_logger('Model')
        logger.info(f"Creating model: {model_data.get('name')}")
        
        model = await super().create(**model_data)
        context_manager = model.service_registry.get('context_manager')
        model_context = await context_manager.get_model_context(model.name)
        model.collection = model_context.get('collection', [])
        
        logger.info(f"Model {model.name} created with {len(model.collection)} child nodes")
        return model

    async def get_dependencies(self):
        logger = get_logger('Model')
        logger.info(f"Getting dependencies for model: {self.name}")
        
        # Get dependencies for the model itself
        await super().get_dependencies()
        
        # Get dependencies for child nodes
        for node_data in self.collection:
            node = await Node.create(**node_data, session_id=self.session_id)
            await node.get_dependencies()

    async def clear_dependencies(self):
        logger = get_logger('Model')
        logger.info(f"Clearing dependencies for model: {self.name}")
        
        # Clear dependencies for the model itself
        await super().clear_dependencies()
        
        # Clear dependencies for child nodes
        for node_data in self.collection:
            node = await Node.create(**node_data, session_id=self.session_id)
            await node.clear_dependencies()
