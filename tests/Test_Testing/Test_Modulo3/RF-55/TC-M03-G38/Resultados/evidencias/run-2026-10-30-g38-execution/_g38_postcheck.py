"""After POST: journal + sha256. SSH password stdin. No token."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import paramiko

HOST, USER = "100.96.29.65", "sgpmp"
HERE = Path(__file__).resolve().parent
EXPECTED_HASH = "76c65da537337aefc8a01c1c963ecd168a6fece4560faa4e955307edfecd28c5"
EXPECTED_VERSION = "2026-10-08T21:11:56.393005+00:00"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    esc = sys.argv[1] if len(sys.argv) > 1 else "x"
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

    def run(cmd: str, pty: bool = False) -> tuple[int, str, str]:
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=40, get_pty=pty)
        if "sudo -S" in cmd:
            stdin.write(password + "\n")
            stdin.flush()
        out = stdout.read().decode("utf-8", "replace")
        err = stderr.read().decode("utf-8", "replace")
        rc = stdout.channel.recv_exit_status()
        return rc, out, err

    rcj, outj, errj = run(
        "journalctl -u edge-agent --since '8 min ago' --no-pager -o cat 2>&1 | "
        "grep -E 'UMBRAL|ACK|umbral|65|Humedad|valor_min|motivo|ERROR' | tail -n 60"
    )
    (HERE / f"journal_{esc}.txt").write_text(
        outj + (("\n---STDERR---\n" + errj) if errj.strip() else ""), encoding="utf-8"
    )
    rch, outh, _ = run(
        "sudo -S -u sgpmp-edge bash -c "
        "'echo ---JSON---; cat /var/lib/sgpmp-edge/umbrales.json; echo; echo ---SHA256---; "
        "sha256sum /var/lib/sgpmp-edge/umbrales.json'"
    )
    ssh.close()
    text = "\n".join(ln for ln in outh.splitlines() if "password" not in ln.lower())
    version = got_hash = None
    try:
        json_part = text.split("---JSON---", 1)[1].split("---SHA256---", 1)[0].strip()
        hash_line = text.split("---SHA256---", 1)[1].strip().splitlines()[0]
        u = json.loads(json_part)["umbrales"]["65"]
        version = u.get("version")
        got_hash = hash_line.split()[0]
    except Exception as exc:
        print("PARSE_FAIL", type(exc).__name__, flush=True)
    hash_ok = got_hash == EXPECTED_HASH
    ver_ok = version == EXPECTED_VERSION and version is not None
    meta = {
        "escenario": esc,
        "journal_rc": rcj,
        "hash_rc": rch,
        "version": version,
        "hash": got_hash,
        "hash_igual_preflight": hash_ok,
        "version_igual_preflight": ver_ok,
    }
    (HERE / f"hash_{esc}_despues.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print("HASH", got_hash, flush=True)
    print("VERSION", version, flush=True)
    print("HASH_IGUAL", hash_ok, flush=True)
    print("VERSION_IGUAL", ver_ok, flush=True)
    if not hash_ok or not ver_ok:
        return 10
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
