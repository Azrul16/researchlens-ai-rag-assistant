"""Windows console launcher: its job owns and cleans up all application children."""

import ctypes
import json
import os
import subprocess
import sys
import time
import webbrowser
from ctypes import wintypes
from pathlib import Path


class BasicLimits(ctypes.Structure):
    _fields_ = [
        ("ProcessTime", ctypes.c_int64),
        ("JobTime", ctypes.c_int64),
        ("Flags", wintypes.DWORD),
        ("MinWorkingSet", ctypes.c_size_t),
        ("MaxWorkingSet", ctypes.c_size_t),
        ("ActiveProcesses", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("Priority", wintypes.DWORD),
        ("Scheduling", wintypes.DWORD),
    ]


class IoCounters(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint64) for name in (
        "ReadOperations", "WriteOperations", "OtherOperations",
        "ReadBytes", "WriteBytes", "OtherBytes",
    )]


class ExtendedLimits(ctypes.Structure):
    _fields_ = [
        ("Basic", BasicLimits), ("Io", IoCounters),
        ("ProcessMemory", ctypes.c_size_t), ("JobMemory", ctypes.c_size_t),
        ("PeakProcessMemory", ctypes.c_size_t), ("PeakJobMemory", ctypes.c_size_t),
    ]


def own_children():
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [
        wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
    ]
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    job = kernel.CreateJobObjectW(None, None)
    limits = ExtendedLimits()
    limits.Basic.Flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not job or not kernel.SetInformationJobObject(
        job, 9, ctypes.byref(limits), ctypes.sizeof(limits)
    ) or not kernel.AssignProcessToJobObject(job, kernel.GetCurrentProcess()):
        raise ctypes.WinError(ctypes.get_last_error())
    # Keep this non-inheritable handle open until process exit. Closing the
    # console closes it in the OS, terminating every child even without finally.
    return job


def main():
    if sys.platform != "win32":
        raise RuntimeError("Use this launcher on Windows.")
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    job = own_children()
    command = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File"]
    print("Starting ResearchLens AI...", flush=True)
    started = False
    try:
        subprocess.run(command + [str(root / "scripts/start.ps1")], check=True)
        started = True
        state = json.loads((root / ".logs/processes.json").read_text(encoding="utf-8-sig"))
        webbrowser.open("http://localhost:3000")
        print("\nResearchLens is running at http://localhost:3000", flush=True)
        print("Close this terminal or press Ctrl+C to stop both services.", flush=True)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        while True:
            for pid in (state["backend"], state["frontend"]):
                handle = kernel.OpenProcess(0x100000, False, pid)
                if not handle:
                    raise RuntimeError("An application service stopped. Check .logs for details.")
                try:
                    if kernel.WaitForSingleObject(handle, 0) != 258:
                        raise RuntimeError("An application service stopped. Check .logs for details.")
                finally:
                    kernel.CloseHandle(handle)
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping ResearchLens...", flush=True)
    finally:
        if started:
            subprocess.run(command + [str(root / "scripts/stop.ps1")], check=False)
        # The OS closes job on exit, also cleaning partial startup failures.
        assert job


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, subprocess.CalledProcessError, ValueError) as error:
        print(f"Could not run ResearchLens: {error}", file=sys.stderr)
        sys.exit(1)
