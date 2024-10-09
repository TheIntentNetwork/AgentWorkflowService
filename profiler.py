import cProfile
from functools import wraps
import inspect
import pstats
import io
import time
import os
import psutil
from memory_profiler import memory_usage
import threading
import asyncio

class Profiler:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Profiler, cls).__new__(cls)
            cls._instance.initialize()
        return cls._instance

    def initialize(self):
        self.output_dir = 'profiling_results'
        os.makedirs(self.output_dir, exist_ok=True)
        self.cpu_profiler = cProfile.Profile()
        self.is_profiling = False
        self.profiling_interval = 60  # seconds

    def start_profiling(self):
        if not self.is_profiling:
            self.is_profiling = True
            self.cpu_profiler.enable()
            threading.Thread(target=self._periodic_profiling, daemon=True).start()

    def stop_profiling(self):
        if self.is_profiling:
            self.is_profiling = False
            self.cpu_profiler.disable()
            self._save_cpu_profile()

    def _periodic_profiling(self):
        while self.is_profiling:
            self._capture_memory_profile()
            self._capture_system_resources()
            time.sleep(self.profiling_interval)

    def _capture_memory_profile(self):
        mem_usage = memory_usage(-1, interval=0.1, timeout=1)
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        with open(f"{self.output_dir}/memory_profile_{timestamp}.txt", 'w') as f:
            f.write(f"Memory usage: {mem_usage}\n")
            f.write(f"Peak memory usage: {max(mem_usage)} MiB\n")

    def _capture_system_resources(self):
        process = psutil.Process()
        cpu_percent = process.cpu_percent(interval=1)
        memory_info = process.memory_info()
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        with open(f"{self.output_dir}/system_resources_{timestamp}.txt", 'w') as f:
            f.write(f"CPU Usage: {cpu_percent}%\n")
            f.write(f"Memory Usage: {memory_info.rss / (1024 * 1024):.2f} MiB\n")
            f.write(f"Virtual Memory: {memory_info.vms / (1024 * 1024):.2f} MiB\n")

    def _save_cpu_profile(self):
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        s = io.StringIO()
        ps = pstats.Stats(self.cpu_profiler, stream=s).sort_stats('cumulative')
        ps.print_stats()
        with open(f"{self.output_dir}/cpu_profile_{timestamp}.txt", 'w') as f:
            f.write(s.getvalue())

# Create a single instance of the Profiler
profiler = Profiler()

def profile_async(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        profiler.start_profiling()
        try:
            return await func(*args, **kwargs)
        finally:
            profiler.stop_profiling()
    return wrapper

def profile_generator(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        profiler.start_profiling()
        try:
            async for item in func(*args, **kwargs):
                yield item
        finally:
            profiler.stop_profiling()
    return wrapper

def profile_sync(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        profiler.start_profiling()
        try:
            return func(*args, **kwargs)
        finally:
            profiler.stop_profiling()
    return wrapper