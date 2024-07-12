from app.models.Node import Node

class Goal(Node):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = "goal"