from fastapi import FastAPI
import time
import cProfile
import pstats
import io
import uvicorn

app = FastAPI()

@app.get("/")
def read_root():
    time.sleep(0.1)  # Simulate some work
    return {"Hello": "World"}

@app.get("/items/{item_id}")
def read_item(item_id: int):
    time.sleep(0.2)  # Simulate more work
    return {"item_id": item_id}

def run_server():
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    profiler = cProfile.Profile()
    profiler.enable()
    try:
        run_server()
    except KeyboardInterrupt:
        pass
    finally:
        profiler.disable()
        s = io.StringIO()
        ps = pstats.Stats(profiler, stream=s).sort_stats('cumulative')
        ps.print_stats()
        with open('profile_results.txt', 'w') as f:
            f.write(s.getvalue())
        print("Profile results saved to profile_results.txt")