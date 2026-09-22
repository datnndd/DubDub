# -*- coding: utf-8 -*-
import subprocess
import sys
import time
from videotrans.core.proc_registry import (
    register_proc,
    unregister_proc,
    has_active_procs,
    kill_job_procs,
    get_current_job_id,
    set_current_job_id,
)


def test_context_job_id():
    assert get_current_job_id() is None
    set_current_job_id("job_xyz")
    assert get_current_job_id() == "job_xyz"
    set_current_job_id(None)
    assert get_current_job_id() is None


def test_proc_registration():
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(10)"])
    try:
        register_proc("job_proc_test", proc)
        assert has_active_procs("job_proc_test") is True

        unregister_proc("job_proc_test", proc)
        assert has_active_procs("job_proc_test") is False
    finally:
        proc.kill()
        proc.wait()


def test_kill_job_procs():
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(10)"])
    register_proc("job_kill_test", proc)
    assert has_active_procs("job_kill_test") is True

    kill_job_procs("job_kill_test")
    # Wait for process to exit
    proc.wait(timeout=5.0)
    assert proc.poll() is not None
    assert has_active_procs("job_kill_test") is False
