"""Read-only umbral 65 version + sha256. SSH password stdin. No env-file token grep. No PTY echo."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import paramiko

HOST, USER = "100.96.29.65", "sgpmp"
EXPECTED_VERSION = "2026-10-08T21:11:56.393005+00:00"
EXPECTED_HASH = "76c65da537337aefc8a01c1c963ecd168a6fece4560faa4e955307edfecd28c5"
HERE = Path(__file__).resolve().parent
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "reconfirm_umbral65.json"
CMD = (
    "sudo -S -u sgpmp-edge bash -c "
    "'echo ---JSON---; cat /var/lib/sgpmp-edge/umbrales.json; echo; echo ---SHA256---; "
    "sha256sum /var/lib/sgpmp-edge/umbrales.json'"
)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    password = sys.stdin.readline().rstrip("\n\r")
    if not password:
        print("NO_SSH_PASSWORD", flush=True)
        return 2
    ssh = paramiko.SSHClient()
    ssh.load_system_host_keys()
    ssh.set_missing_host_key_policy(paramiko.RejectPolicy())
    ssh.connect(
        HOST, username=USER, password=password, timeout=20,
        allow_agent=False, look_for_keys=False,
    )
    stdin, stdout, stderr = ssh.exec_command(CMD, timeout=30, get_pty=False)
    stdin.write(password + "\n")
    stdin.flush()
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    rc = stdout.channel.recv_exit_status()
    ssh.close()
    text = "\n".join(ln for ln in out.splitlines() if "password" not in ln.lower())
    version = variable = got_hash = None
    coincide = False
    try:
        json_part = text.split("---JSON---", 1)[1].split("---SHA256---", 1)[0].strip()
        hash_line = text.split("---SHA256---", 1)[1].strip().splitlines()[0]
        u = json.loads(json_part)["umbrales"]["65"]
        version = u.get("version")
        variable = u.get("variable")
        got_hash = hash_line.split()[0]
        coincide = (
            version == EXPECTED_VERSION
            and variable == "Humedad Relativa"
            and got_hash == EXPECTED_HASH
        )
    except Exception as exc:
        print("PARSE_FAIL", type(exc).__name__, flush=True)
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "ssh_rc": rc,
        "version": version,
        "variable": variable,
        "hash": got_hash,
        "esperado_version": EXPECTED_VERSION,
        "esperado_hash": EXPECTED_HASH,
        "coincide_preflight": coincide,
        "stderr_len": len(err),
        "sudo_n_not_used": True,
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("VERSION", version, flush=True)
    print("VARIABLE", variable, flush=True)
    print("HASH", got_hash, flush=True)
    print("COINCIDE", coincide, flush=True)
    return 0 if coincide else 10


if __name__ == "__main__":
    raise SystemExit(main())
