import cProfile
import pstats
import io
import subprocess
import sys

def run_server():
    subprocess.run([sys.executable, "app.py"])

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