"""Account for, and stop, only descendants of a child we started."""

import psutil


class OwnedProcessTree:
    def __init__(self, pid):
        self.root = psutil.Process(pid)
        self.known = {(self.root.pid, self.root.create_time()): self.root}

    def sample(self):
        # Windows virtualenv launchers run Python in another process. Counting
        # just the launcher misses nearly all model memory.
        for process in list(self.known.values()):
            try:
                if not process.is_running():
                    continue
                for child in process.children(recursive=True):
                    self.known[(child.pid, child.create_time())] = child
            except psutil.NoSuchProcess:
                continue
        total = 0
        for process in self.known.values():
            try:
                if process.is_running():
                    total += process.memory_info().rss
            except psutil.NoSuchProcess:
                continue
        return total

    def stop(self):
        # Process objects include creation time: a recycled PID is not killed.
        self.sample()
        owned = list(reversed(list(self.known.values())))
        for process in owned:
            try:
                if process.is_running():
                    process.kill()
            except psutil.NoSuchProcess:
                pass
        psutil.wait_procs(owned, timeout=5)
