from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer
import numpy as np

class VectorDatabase:
    def __init__(self):
        # Load a pre-trained Sentence Transformer model
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        # Assuming self.db_vectors is a dictionary where keys are goal IDs and values are the vector representations of those goals
        # This is a placeholder. In a real application, this data might come from a database or be dynamically generated.
        self.db_vectors = {}
        self.goal_ids = list(self.db_vectors.keys())  # List of goal IDs for reference

    def encode_goal(self, goal_text):
        # Use the Sentence Transformer model to encode the goal text into a vector
        return self.model.encode(goal_text, convert_to_tensor=True)
    
    def find_similar_goals(self, goal_text):
        goal_vector = self.encode_goal(goal_text).reshape(1, -1)
        similarities = {}
        for goal_id, db_vector in self.db_vectors.items():
            # Ensure db_vector is in the correct shape for cosine_similarity calculation
            db_vector = np.array(db_vector).reshape(1, -1)
            # Calculate cosine similarity
            similarity = cosine_similarity(goal_vector, db_vector)
            similarities[goal_id] = similarity[0][0]
        
        # Sort the goals by similarity
        sorted_similarities = sorted(similarities.items(), key=lambda item: item[1], reverse=True)
        
        # Return the top N most similar goals, here N could be a predefined number or based on a similarity threshold
        top_n = 5  # Example: top 5 similar goals
        return [goal_id for goal_id, _ in sorted_similarities[:top_n]]