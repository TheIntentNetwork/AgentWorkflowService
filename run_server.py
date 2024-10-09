from scalene import scalene_profiler
import subprocess
import sys

if __name__ == "__main__":
    scalene_profiler.start()
    try:
        subprocess.run([sys.executable, "minimal_app.py"], check=True)
    finally:
        scalene_profiler.stop()