import os
import json
import redis

def embeddable(agent):
    def decorator(tool_name):
        def wrapper(*args, **kwargs):
            # Extract the function name
            function_name = tool_name.__name__

            # Extract the inputs and outputs
            inputs = args
            outputs = tool_name(*args, **kwargs)

            # Define the common schema for function call records
            record = {
                "function_name": function_name,
                "inputs": [],
                "outputs": [],
                "tool_context": agent.tool_context,
                "function_context": agent.function_context
            }

            # Add input descriptions
            for param_name, param_value in kwargs.items():
                record["inputs"].append({
                    "name": param_name,
                    "description": agent.input_descriptions.get(param_name, "")
                })

            # Add output descriptions
            for output in outputs:
                record["outputs"].append({
                    "name": output,
                    "description": agent.output_descriptions.get(output, "")
                })

            # Connect to Redis
            r = redis.Redis(host=os.getenv("REDIS_URL").split('//')[1].split(':')[0], port=6379, db=0)

            # Embed the record into the Redis stack vector embeddings database
            r.lpush("function_calls", json.dumps(record))

            # Return the outputs
            return outputs

        return wrapper
    return decorator
