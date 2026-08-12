import os
import platform
import subprocess
import logging
from typing import Optional, Tuple

logger = logging.getLogger("harika.tools.process_verifier")


def verify_os_process(process_name: str, pid: Optional[int] = None, pid_only: bool = False) -> Tuple[bool, Optional[int], Optional[str], Optional[str]]:
    """
    Queries OS process table to verify whether a process is actively running.
    Returns: (verified: bool, pid: Optional[int], process_name: Optional[str], error: Optional[str])
    """
    clean_name = process_name.strip().lower()

    if platform.system().lower() == "windows":
        exec_name = clean_name if clean_name.endswith(".exe") else f"{clean_name}.exe"
        if pid_only and pid:
            try:
                cmd_pid = ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV"]
                out_pid = subprocess.check_output(cmd_pid, text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                lines_pid = [line.strip() for line in out_pid.strip().split("\n") if line.strip() and not line.startswith("INFO:")]
                if len(lines_pid) > 1:
                    parts = lines_pid[1].split(",")
                    p_name = parts[0].strip('"')
                    return True, pid, p_name, None
            except Exception as e:
                return False, pid, exec_name, f"OS tasklist PID query failed: {str(e)}"
            return False, None, exec_name, f"Process '{exec_name}' with PID {pid} was not found in active OS task list."
        try:
            cmd = ["tasklist", "/FI", f"IMAGENAME eq {exec_name}", "/FO", "CSV"]
            creation_flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            output = subprocess.check_output(cmd, text=True, creationflags=creation_flags)
            lines = [line.strip() for line in output.strip().split("\n") if line.strip() and not line.startswith("INFO:")]
            if len(lines) > 1:
                parts = lines[1].split(",")
                p_name = parts[0].strip('"')
                found_pid = int(parts[1].strip('"')) if len(parts) > 1 and parts[1].strip('"').isdigit() else pid
                logger.info(f"[ProcessVerifier] Verified OS process '{p_name}' running with PID {found_pid}.")
                return True, found_pid, p_name, None
        except Exception as e:
            logger.warning(f"[ProcessVerifier] Tasklist query failed for '{exec_name}': {e}")
            return False, pid, exec_name, f"OS tasklist query failed: {str(e)}"

        if pid:
            try:
                cmd_pid = ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV"]
                out_pid = subprocess.check_output(cmd_pid, text=True, creationflags=creation_flags)
                lines_pid = [line.strip() for line in out_pid.strip().split("\n") if line.strip() and not line.startswith("INFO:")]
                if len(lines_pid) > 1:
                    parts = lines_pid[1].split(",")
                    p_name = parts[0].strip('"')
                    return True, pid, p_name, None
            except Exception:
                pass

        return False, None, exec_name, f"Process '{exec_name}' was not found in active OS task list."

    else:
        # Linux / Darwin (macOS) fallback
        try:
            out = subprocess.check_output(["pgrep", "-f", clean_name], text=True)
            pids = [int(p.strip()) for p in out.strip().split() if p.strip().isdigit()]
            if pids:
                logger.info(f"[ProcessVerifier] Verified POSIX process '{clean_name}' running with PID {pids[0]}.")
                return True, pids[0], clean_name, None
        except Exception as e:
            logger.warning(f"[ProcessVerifier] pgrep query failed for '{clean_name}': {e}")

        return False, None, clean_name, f"Process '{clean_name}' was not found in active OS process table."


def is_process_running(process_name: str, pid: Optional[int] = None) -> bool:
    verified, _, _, _ = verify_os_process(process_name, pid=pid)
    return verified
