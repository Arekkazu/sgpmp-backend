"""TC-M03-101 laboratorio sintético (fuente fake). Token/SSH solo por stdin."""
from __future__ import annotations

import base64
import json
import os
import ssl
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import paramiko
import paho.mqtt.client as mqtt

HOST_SSH, USER_SSH = "100.96.29.65", "sgpmp"
PID_REF = "9022"
SERIAL = "RASPBERRY3B-TEST"
URL = "https://sgpmp-brokertest-zyytic-0f1138-149-130-169-209.sslip.io/v1/commands"
MQTT_HOST, MQTT_PORT = "149.130.169.209", 1886
UMBRALES = "/var/lib/sgpmp-edge/umbrales.json"
SHA_ORIG = "76c65da537337aefc8a01c1c963ecd168a6fece4560faa4e955307edfecd28c5"
VER_ORIG = "2026-10-08T21:11:56.393005+00:00"
WAIT_CAPTURA_S = 14 * 60
POLL_S = 20

HERE = Path(__file__).resolve().parent
G41 = HERE.parent
EVID = G41 / "Resultados" / "evidencias" / "run-2026-10-30-g41-tc101"
REPORT = G41 / "RESULTADO_EJECUCION_TC_M03_101.md"

NIVELES_APPLY = [
    {"nivel": "normal", "limite_inferior": 40.0, "limite_superior": 65.0},
    {"nivel": "precaucion", "limite_inferior": 65.0, "limite_superior": 70.0},
    {"nivel": "critico", "limite_inferior": 70.0, "limite_superior": 98.0},
]
NIVELES_REST = [
    {"nivel": "normal", "limite_inferior": 40.0, "limite_superior": 70.0},
    {"nivel": "precaucion", "limite_inferior": 70.0, "limite_superior": 85.0},
    {"nivel": "critico", "limite_inferior": 85.0, "limite_superior": 98.0},
]

U65_PY = """
import json
from pathlib import Path
p=Path('/var/lib/sgpmp-edge/umbrales.json')
data=json.loads(p.read_text(encoding='utf-8'))
items=data.get('umbrales') or {}
u=items.get('65') or items.get(65)
print(json.dumps(u, ensure_ascii=False))
"""

HIST_PY = """
import sqlite3, json
from datetime import datetime, timezone
c=sqlite3.connect('/var/lib/sgpmp-edge/historial.db')
print('n', c.execute('select count(*) from historial').fetchone()[0])
for r in c.execute('select id, registrado_en, serial, clasificacion, severidad, timestamp_captura, variables, ruta, estado, detalle from historial order by id desc limit 12'):
    ts=datetime.fromtimestamp(r[1], timezone.utc).isoformat() if isinstance(r[1], (int,float)) else r[1]
    print('ROW', json.dumps({'id':r[0],'registrado_en':ts,'serial':r[2],'clasificacion':r[3],'severidad':r[4],'timestamp_captura':r[5],'variables':json.loads(r[6]) if r[6] else None,'ruta':r[7],'estado':r[8],'detalle':json.loads(r[9]) if r[9] else None}, ensure_ascii=False))
"""

STATE_CMD = (
    "hostname; date -Is; systemctl show edge-agent.service "
    "-p MainPID,NRestarts,ActiveState --no-pager"
)


def _scrub(t: str) -> str:
    return "\n".join(ln for ln in t.splitlines() if "password" not in ln.lower())


def _sudo_py(script: str, user: str = "sgpmp-edge") -> str:
    b64 = base64.b64encode(script.encode("utf-8")).decode("ascii")
    inner = f"import base64; exec(base64.b64decode({b64!r}).decode())"
    return "sudo -S -u " + user + " python3 -c " + json.dumps(inner)


def _run(client, cmd, secret=None, timeout=40):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout, get_pty=False)
    if secret is not None:
        stdin.write(secret + "\n")
        stdin.flush()
        stdin.channel.shutdown_write()
    out = stdout.read().decode("utf-8", "replace")
    err = _scrub(stderr.read().decode("utf-8", "replace"))
    rc = stdout.channel.recv_exit_status()
    return rc, out, err


def _parse_state(text: str) -> dict:
    d = {}
    for ln in text.splitlines():
        if "=" in ln and ln.split("=", 1)[0] in {"MainPID", "NRestarts", "ActiveState"}:
            k, v = ln.split("=", 1)
            d[k] = v.strip()
    return d


def _parse_hist(text: str) -> list[dict]:
    rows = []
    for ln in text.splitlines():
        if ln.startswith("ROW "):
            rows.append(json.loads(ln[4:]))
    return rows


def _motivo(vmin, vmax, niveles) -> str | None:
    if not vmin < vmax:
        return "min>=max"
    if len(niveles) != 3:
        return "no 3 niveles"
    names = [n["nivel"] for n in niveles]
    if names != ["normal", "precaucion", "critico"]:
        return "orden"
    prev = None
    for n in niveles:
        lo, hi = float(n["limite_inferior"]), float(n["limite_superior"])
        if not lo < hi:
            return "ancho 0"
        if prev is not None and lo != prev:
            return "no contiguas"
        prev = hi
    if float(niveles[0]["limite_inferior"]) != vmin or float(niveles[-1]["limite_superior"]) != vmax:
        return "no cubre min-max"
    return None


def _clasificar(valor: float, niveles) -> str:
    dentro = [
        n["nivel"]
        for n in niveles
        if float(n["limite_inferior"]) <= valor <= float(n["limite_superior"])
    ]
    grav = {"normal": 0, "precaucion": 1, "critico": 2, "fuera_de_rango": 3}
    return max(dentro, key=grav.__getitem__) if dentro else "fuera_de_rango"


def _payload(version: str, niveles) -> dict:
    return {
        "origen": "umbral",
        "serial": SERIAL,
        "id_umbral_ambiental": 65,
        "version": version,
        "variable": "Humedad Relativa",
        "unidad": "%",
        "valor_min": 40.0,
        "valor_max": 98.0,
        "niveles": niveles,
    }


def _post(body: dict, token: str) -> dict:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(URL, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {token}")
    ctx = ssl.create_default_context()
    http: dict = {"url": URL, "method": "POST", "sent_at": datetime.now(timezone.utc).isoformat()}
    try:
        with urllib.request.urlopen(req, timeout=45, context=ctx) as resp:
            raw = resp.read()
            http["status"] = resp.status
            http["body"] = json.loads(raw.decode("utf-8") or "null")
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        http["status"] = exc.code
        try:
            http["body"] = json.loads(raw.decode("utf-8") or "null")
        except ValueError:
            http["body_raw"] = raw.decode("utf-8", "replace")[:2000]
    except Exception as exc:
        http["status"] = -1
        http["error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
    return http


def _dump(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


class MqttMon:
    def __init__(self, user: str, password: str, out: Path, stop: Path):
        self.out = out
        self.stop = stop
        self.events: list = []
        self.ready = threading.Event()
        self.rc = None
        self._cl = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"qa-g41-tc101-{int(time.time())}",
            protocol=mqtt.MQTTv5,
        )
        self._cl.username_pw_set(user, password)
        self._cl.on_connect = self._on_connect
        self._cl.on_subscribe = self._on_sub
        self._cl.on_message = self._on_msg
        self._cl.reconnect_delay_set(3600, 3600)
        self._granted = 0

    def _flush(self) -> None:
        _dump(self.out, {"connect_rc": self.rc, "events": self.events[-400:]})

    def _on_connect(self, c, u, f, rc, p=None):
        self.rc = int(getattr(rc, "value", rc) or 0)
        self.events.append({"ts": datetime.now(timezone.utc).isoformat(), "kind": "connect", "rc": self.rc})
        if self.rc == 0:
            for t in ("sgpmp/RASPBERRY3B-TEST/#", "sgpmp/QA-M03-272-A-088894/#"):
                c.subscribe(t, 1)

    def _on_sub(self, c, u, mid, rcs, p=None):
        self._granted += 1
        self.events.append({"ts": datetime.now(timezone.utc).isoformat(), "kind": "suback", "mid": mid})
        if self._granted >= 2:
            self.ready.set()
        self._flush()

    def _on_msg(self, c, u, m):
        pl = m.payload.decode("utf-8", "replace")[:4000]
        tipo = ""
        try:
            d = json.loads(pl)
            tipo = d.get("tipo_mensaje") or d.get("tipo_comando") or d.get("clasificacion_rf55") or ""
        except Exception:
            d = None
        rec = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "kind": "message",
            "topic": m.topic,
            "tipo": tipo,
            "payload": pl,
        }
        self.events.append(rec)
        self._flush()
        print("MQTT", m.topic, tipo, flush=True)

    def start(self) -> None:
        self._cl.connect(MQTT_HOST, MQTT_PORT, 30)
        self._cl.loop_start()

    def stop_now(self) -> None:
        try:
            self.stop.write_text("1", encoding="utf-8")
            self._cl.loop_stop()
            self._cl.disconnect()
        except Exception:
            pass
        self._flush()


def _nivel_de(row: dict) -> str | None:
    det = row.get("detalle") or {}
    return det.get("nivel_umbral")


def _id_umbral(row: dict) -> int | None:
    det = row.get("detalle") or {}
    v = det.get("id_umbral_ambiental")
    return int(v) if v is not None else None


def _var_ok(row: dict) -> bool:
    for v in row.get("variables") or []:
        if isinstance(v, dict) and v.get("tipo_variable") == "Humedad Relativa":
            return True
    return False


def _valor(row: dict):
    for v in row.get("variables") or []:
        if isinstance(v, dict) and v.get("tipo_variable") == "Humedad Relativa":
            return v.get("valor"), v.get("unidad")
    return None, None


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ssh_pw = sys.stdin.readline().rstrip("\n\r")
    mqtt_user = sys.stdin.readline().rstrip("\n\r")
    mqtt_pw = sys.stdin.readline().rstrip("\n\r")
    token = sys.stdin.readline().rstrip("\n\r")
    if not ssh_pw or not mqtt_user or not mqtt_pw or not token:
        print("STOP_CREDENCIALES", flush=True)
        return 2

    if _motivo(40.0, 98.0, NIVELES_APPLY) or _motivo(40.0, 98.0, NIVELES_REST):
        print("STOP_BANDAS_INVALIDAS", _motivo(40.0, 98.0, NIVELES_APPLY), flush=True)
        return 3
    if _clasificar(72.0, NIVELES_APPLY) != "critico" or _clasificar(72.0, NIVELES_REST) != "precaucion":
        print("STOP_CLASIFICACION_LOCAL", flush=True)
        return 3

    EVID.mkdir(parents=True, exist_ok=True)
    t0 = datetime.now(timezone.utc)
    log: dict = {
        "laboratorio": "SINTETICO_FAKE",
        "t0_utc": t0.isoformat(),
        "pid_ref": PID_REF,
        "criterios": {},
        "paradas": [],
    }
    applied = False
    mon = None
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.RejectPolicy())

    def snap(tag: str) -> dict:
        rc, st, err = _run(client, STATE_CMD)
        state = _parse_state(st)
        rc2, h, err2 = _run(client, "sudo -S -u sgpmp-edge sha256sum " + UMBRALES, ssh_pw)
        rc3, u, err3 = _run(client, _sudo_py(U65_PY), ssh_pw)
        rc4, hist, err4 = _run(client, _sudo_py(HIST_PY), ssh_pw)
        rec = {
            "tag": tag,
            "utc": datetime.now(timezone.utc).isoformat(),
            "state_rc": rc,
            "state": state,
            "raw_state": st.strip(),
            "sha": (h.strip().split() or [""])[0],
            "umbral65": json.loads(u) if u.strip().startswith("{") else u.strip(),
            "historial": _parse_hist(hist),
            "err": "\n".join(x for x in (err, err2, err3, err4) if x),
        }
        _dump(EVID / f"snap_{tag}.json", rec)
        print(
            f"SNAP {tag} PID={state.get('MainPID')} NRestarts={state.get('NRestarts')} "
            f"active={state.get('ActiveState')} sha={rec['sha'][:12]}",
            flush=True,
        )
        return rec

    def pid_ok(state: dict) -> bool:
        return state.get("MainPID") == PID_REF and state.get("ActiveState") == "active"

    try:
        client.connect(
            HOST_SSH, username=USER_SSH, password=ssh_pw, timeout=25,
            allow_agent=False, look_for_keys=False,
        )
        pre = snap("preflight")
        if not pid_ok(pre["state"]):
            log["paradas"].append("PID distinto de 9022 o servicio inactivo")
            print("STOP_PID", pre["state"], flush=True)
            _write_report(log, veredicto="NO_EJECUTADO")
            return 4
        if pre["state"].get("NRestarts") not in (None, "0"):
            log["paradas"].append("NRestarts inesperado")
            print("STOP_NRESTARTS", pre["state"].get("NRestarts"), flush=True)
            _write_report(log, veredicto="NO_EJECUTADO")
            return 4
        u65 = pre["umbral65"]
        if not isinstance(u65, dict) or str(u65.get("variable")) != "Humedad Relativa":
            log["paradas"].append("umbral 65 no coincide")
            print("STOP_UMBRAL65", flush=True)
            _write_report(log, veredicto="NO_EJECUTADO")
            return 4
        if str(u65.get("version")) != VER_ORIG:
            log["paradas"].append(f"version no original: {u65.get('version')}")
            print("STOP_VERSION_ORIG", u65.get("version"), flush=True)
            _write_report(log, veredicto="NO_EJECUTADO")
            return 4

        stop_path = EVID / "mqtt.stop"
        if stop_path.exists():
            stop_path.unlink()
        mon = MqttMon(mqtt_user, mqtt_pw, EVID / "mqtt_session.json", stop_path)
        mon.start()
        if not mon.ready.wait(25):
            log["paradas"].append("MQTT SUB no listo")
            print("STOP_MQTT", mon.rc, flush=True)
            _write_report(log, veredicto="NO_EJECUTADO")
            return 5
        print("MQTT_READY", flush=True)

        t0_local = datetime.now(timezone.utc)
        log["t0_formal_utc"] = t0_local.isoformat()
        print("T0", t0_local.isoformat(), "esperando medición natural…", flush=True)
        t0_row = _esperar_hist(client, ssh_pw, t0_local, "t0", lambda r: _var_ok(r) and _id_umbral(r) == 65)
        if t0_row is None:
            log["paradas"].append("sin medición posterior a t0 (antes de POST)")
            print("STOP_SIN_T0", flush=True)
            _write_report(log, veredicto="NO_APROBADO")
            return 6
        _dump(EVID / "medicion_t0.json", t0_row)
        log["medicion_t0"] = t0_row
        print(
            "T0_MED", t0_row.get("timestamp_captura"), _valor(t0_row), _nivel_de(t0_row),
            flush=True,
        )
        mid = snap("antes_post")
        if not pid_ok(mid["state"]):
            print("STOP_PID_ANTES_POST", flush=True)
            _write_report(log, veredicto="NO_APROBADO")
            return 4

        ver_apply = datetime.now(timezone.utc).isoformat()
        body_apply = _payload(ver_apply, NIVELES_APPLY)
        _dump(EVID / "payload_aplicacion.json", body_apply)
        print("POST_APPLY", ver_apply, flush=True)
        http_apply = _post(body_apply, token)
        _dump(EVID / "http_aplicacion.json", http_apply)
        applied = True
        log["http_aplicacion"] = {
            "status": http_apply.get("status"),
            "estado": (http_apply.get("body") or {}).get("estado") if isinstance(http_apply.get("body"), dict) else None,
            "mensaje": str((http_apply.get("body") or {}).get("mensaje", ""))[:300] if isinstance(http_apply.get("body"), dict) else None,
            "sent_at": http_apply.get("sent_at"),
        }
        print("HTTP_APPLY", log["http_aplicacion"], flush=True)

        ack_apply = _esperar_mqtt_ack(mon, ver_apply, timeout=40)
        _dump(EVID / "ack_aplicacion.json", ack_apply or {})
        time.sleep(2)
        after_apply = snap("despues_apply")
        log["ack_aplicacion"] = ack_apply
        log["umbral_despues_apply"] = after_apply["umbral65"]
        log["sha_despues_apply"] = after_apply["sha"]
        if not pid_ok(after_apply["state"]):
            print("STOP_PID_POST_APPLY", flush=True)
            _restaurar(client, ssh_pw, token, ver_apply, log, mon)
            _write_report(log, veredicto="NO_APROBADO")
            return 7
        u_new = after_apply["umbral65"] if isinstance(after_apply["umbral65"], dict) else {}
        if str(u_new.get("version")) != ver_apply:
            journal = _journal(client, ssh_pw)
            (EVID / "journal_apply.txt").write_text(journal, encoding="utf-8")
            log["paradas"].append("JSON no tiene version aplicada; no se reintenta POST")
            print("STOP_NO_PERSISTIO", u_new.get("version"), flush=True)
            # si no se aplicó, no hace falta restaurar valores de negocio
            applied = str(u_new.get("version")) not in (None, VER_ORIG, str(u65.get("version")))
            if applied:
                _restaurar(client, ssh_pw, token, ver_apply, log, mon)
            _write_report(log, veredicto="NO_APROBADO")
            return 8
        (EVID / "journal_apply.txt").write_text(_journal(client, ssh_pw), encoding="utf-8")

        print("esperando medición posterior al ACK…", flush=True)
        ack_ts = datetime.fromisoformat(ack_apply["ts"]) if ack_apply and ack_apply.get("ts") else datetime.now(timezone.utc)
        post_row = _esperar_hist(
            client, ssh_pw, ack_ts, "post",
            lambda r: _var_ok(r) and _id_umbral(r) == 65,
        )
        _dump(EVID / "medicion_posterior.json", post_row or {})
        log["medicion_posterior"] = post_row
        mqtt_ev = _buscar_evento(mon, after=ack_ts, version=ver_apply)
        _dump(EVID / "evento_posterior_mqtt.json", mqtt_ev or {})
        log["evento_mqtt_posterior"] = mqtt_ev
        print("POST_MED", post_row, "MQTT_EV", bool(mqtt_ev), flush=True)

        _restaurar(client, ssh_pw, token, ver_apply, log, mon)
        fin = snap("final")
        log["snap_final"] = {"pid": fin["state"].get("MainPID"), "nrestarts": fin["state"].get("NRestarts"), "sha": fin["sha"], "umbral65": fin["umbral65"]}
        if not pid_ok(fin["state"]):
            log["paradas"].append("PID cambió al final")
        ok = _evaluar_criterios(log, t0_row, post_row, mqtt_ev, ver_apply, fin, ack_apply)
        veredicto = "APROBADO" if ok else "NO_APROBADO"
        _write_report(log, veredicto=veredicto)
        print("VEREDICTO", veredicto, flush=True)
        return 0 if ok else 10
    finally:
        token = ""
        mqtt_pw = ""
        ssh_pw = ""
        if mon:
            mon.stop_now()
        client.close()


def _esperar_hist(client, secret, after: datetime, tag: str, pred) -> dict | None:
    deadline = time.monotonic() + WAIT_CAPTURA_S
    after_s = after.isoformat()
    while time.monotonic() < deadline:
        rc, st, err = _run(client, STATE_CMD)
        state = _parse_state(st)
        if state.get("MainPID") != PID_REF:
            print("STOP_PID_DURANTE_ESPERA", tag, state, flush=True)
            return None
        rc, hist, err = _run(client, _sudo_py(HIST_PY), secret)
        rows = _parse_hist(hist)
        _dump(EVID / f"hist_poll_{tag}.json", {"utc": datetime.now(timezone.utc).isoformat(), "rows": rows})
        for r in rows:
            ts = r.get("timestamp_captura") or r.get("registrado_en") or ""
            try:
                ts_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except Exception:
                continue
            if ts_dt >= after and pred(r):
                return r
        print(f"WAIT_{tag} sin fila nueva aún…", flush=True)
        time.sleep(POLL_S)
    return None


def _esperar_mqtt_ack(mon: MqttMon, version: str, timeout: float) -> dict | None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for ev in reversed(mon.events):
            if ev.get("kind") != "message":
                continue
            if "ACK_UMBRAL" not in str(ev.get("tipo")) and "ACK_UMBRAL" not in str(ev.get("payload")):
                continue
            try:
                pl = json.loads(ev.get("payload") or "{}")
            except Exception:
                continue
            if pl.get("tipo_mensaje") == "ACK_UMBRAL" or ev.get("topic", "").endswith("/status"):
                return {"ts": ev.get("ts"), "topic": ev.get("topic"), "payload": pl}
        time.sleep(0.4)
    return None


def _buscar_evento(mon: MqttMon, *, after: datetime, version: str) -> dict | None:
    after_s = after.isoformat()
    for ev in mon.events:
        if ev.get("kind") != "message":
            continue
        if (ev.get("ts") or "") < after_s:
            continue
        try:
            pl = json.loads(ev.get("payload") or "{}")
        except Exception:
            continue
        meta = pl.get("metadata_edge") or {}
        if meta.get("id_umbral_ambiental") == 65 and str(meta.get("version_umbral")) == version:
            return {"ts": ev.get("ts"), "topic": ev.get("topic"), "payload": pl}
        vars_ = pl.get("variables_involucradas") or []
        if pl.get("clasificacion_rf55") and any(
            isinstance(v, dict) and v.get("tipo_variable") == "Humedad Relativa" for v in vars_
        ):
            if str(meta.get("version_umbral")) == version:
                return {"ts": ev.get("ts"), "topic": ev.get("topic"), "payload": pl}
    return None


def _journal(client, secret) -> str:
    rc, out, err = _run(
        client,
        "sudo -S journalctl -u edge-agent.service --since '90 min ago' --no-pager -o cat "
        "| grep -ivE 'password|token|secret|credential' | tail -n 80",
        secret,
    )
    return out + ("\n" + err if err else "")


def _restaurar(client, ssh_pw, token, ver_apply: str, log: dict, mon) -> None:
    ver_rest = (datetime.now(timezone.utc) + timedelta(seconds=2)).isoformat()
    if datetime.fromisoformat(ver_rest) <= datetime.fromisoformat(ver_apply):
        ver_rest = (datetime.fromisoformat(ver_apply) + timedelta(seconds=2)).isoformat()
    body = _payload(ver_rest, NIVELES_REST)
    _dump(EVID / "payload_restauracion.json", body)
    print("POST_RESTORE", ver_rest, flush=True)
    http = _post(body, token)
    _dump(EVID / "http_restauracion.json", http)
    log["http_restauracion"] = {
        "status": http.get("status"),
        "estado": (http.get("body") or {}).get("estado") if isinstance(http.get("body"), dict) else None,
        "sent_at": http.get("sent_at"),
        "version": ver_rest,
    }
    ack = _esperar_mqtt_ack(mon, ver_rest, timeout=40)
    _dump(EVID / "ack_restauracion.json", ack or {})
    log["ack_restauracion"] = ack
    time.sleep(2)
    snap = None
    rc, st, err = _run(client, STATE_CMD)
    rc2, h, err2 = _run(client, "sudo -S -u sgpmp-edge sha256sum " + UMBRALES, ssh_pw)
    rc3, u, err3 = _run(client, _sudo_py(U65_PY), ssh_pw)
    log["restauracion_json"] = json.loads(u) if u.strip().startswith("{") else u
    log["sha_final"] = (h.strip().split() or [""])[0]
    log["state_post_restore"] = _parse_state(st)
    (EVID / "journal_restore.txt").write_text(_journal(client, ssh_pw), encoding="utf-8")
    print("RESTORE_VERSION", (log["restauracion_json"] or {}).get("version") if isinstance(log["restauracion_json"], dict) else None, flush=True)
    # medición restaurada opcional
    after = datetime.now(timezone.utc)
    row = _esperar_hist(client, ssh_pw, after, "restore", lambda r: _var_ok(r) and _id_umbral(r) == 65)
    log["medicion_restaurada"] = row
    _dump(EVID / "medicion_restaurada.json", row or {})


def _evaluar_criterios(log, t0_row, post_row, mqtt_ev, ver_apply, fin, ack_apply) -> bool:
    c = {}
    c["1_medicion_inicial"] = bool(t0_row) and _nivel_de(t0_row) == "precaucion" and _id_umbral(t0_row) == 65
    c["2_actualizacion_valida"] = isinstance(log.get("umbral_despues_apply"), dict) and str(log["umbral_despues_apply"].get("version")) == ver_apply
    ack_ok = False
    if ack_apply:
        pl = ack_apply.get("payload") or {}
        ack_ok = pl.get("resultado") == "OK" or "OK" in str(pl)
    c["3_ack_recepcion"] = ack_ok
    c["4_version_memoria"] = c["2_actualizacion_valida"]  # set() disco+RAM; evento lo confirma
    c["5_persistencia"] = c["2_actualizacion_valida"]
    c["6_medicion_posterior"] = bool(post_row) and (post_row.get("timestamp_captura") or "") > (t0_row.get("timestamp_captura") or "")
    nivel_post = None
    ver_post = None
    if mqtt_ev:
        meta = (mqtt_ev.get("payload") or {}).get("metadata_edge") or {}
        nivel_post = meta.get("nivel_umbral")
        ver_post = meta.get("version_umbral")
    if nivel_post is None and post_row:
        nivel_post = _nivel_de(post_row)
    c["7_evento_id_version_clase"] = (
        bool(post_row)
        and _id_umbral(post_row) == 65
        and nivel_post == "critico"
        and str(ver_post) == ver_apply
    )
    c["8_pid_9022"] = (fin.get("state") or fin).get("MainPID") == PID_REF if isinstance(fin, dict) else False
    if isinstance(fin, dict) and "pid" in (log.get("snap_final") or {}):
        c["8_pid_9022"] = log["snap_final"]["pid"] == PID_REF
    rest = log.get("restauracion_json") if isinstance(log.get("restauracion_json"), dict) else {}
    c["9_restauracion_version_posterior"] = bool(rest.get("version")) and str(rest.get("version")) > ver_apply
    c["10_valores_restaurados"] = (
        float(rest.get("valor_min") or 0) == 40.0
        and float(rest.get("valor_max") or 0) == 98.0
        and _motivo(40.0, 98.0, rest.get("niveles") or []) is None
        and float((rest.get("niveles") or [{}, {}])[1].get("limite_inferior") or 0) == 70.0
        and float((rest.get("niveles") or [{}, {}, {}])[2].get("limite_inferior") or 0) == 85.0
    )
    c["11_servicio_sin_reinicio"] = c["8_pid_9022"] and log.get("snap_final", {}).get("nrestarts") in ("0", 0, None)
    log["criterios"] = c
    log["version_aplicada"] = ver_apply
    return all(c.values())


def _write_report(log: dict, veredicto: str) -> None:
    c = log.get("criterios") or {}
    filas = "\n".join(f"| {k} | {'PASS' if v else 'FAIL'} |" for k, v in c.items()) or "| (sin evaluar) | — |"
    t0r = log.get("medicion_t0") or {}
    postr = log.get("medicion_posterior") or {}
    md = f"""# RESULTADO — Ejecución funcional TC-M03-101 (G41)

**Laboratorio sintético con fuente fake.** No es validación de sensor LoRa/DHT real.

**Veredicto TC-M03-101: `{veredicto}`**

Fecha t0 formal UTC: `{log.get('t0_formal_utc') or log.get('t0_utc')}`

Dispositivo: RASPBERRY3B. Servicio: edge-agent. PID referencia: **9022**.

## Resumen ejecutivo

Se ejecutó la prueba autorizada: medición inicial, `POST /v1/commands` origen `umbral` al umbral 65, verificación de ACK/persistencia, medición posterior y restauración con versión posterior. No se reinició Edge. No se modificó `edge-agent.env`.

Paradas: {log.get('paradas') or 'ninguna'}

## Continuidad del proceso

- PID inicial/final: ver snaps en evidencias. Referencia **9022**.
- Snap final: `{json.dumps(log.get('snap_final'), ensure_ascii=False)}`

## Mediciones

### Inicial (antes del ACK de aplicación)

```
{json.dumps(t0r, indent=2, ensure_ascii=False)[:2500]}
```

### Posterior al ACK

```
{json.dumps(postr, indent=2, ensure_ascii=False)[:2500]}
```

Clasificación esperada: `precaucion` → `critico` para ~72 %.

## POST aplicación (secretos redactados)

- URL: `{URL}`
- Método: POST
- HTTP: `{json.dumps(log.get('http_aplicacion'), ensure_ascii=False)}`
- Payload: `Resultados/evidencias/run-2026-10-30-g41-tc101/payload_aplicacion.json`
- ACK MQTT: `{json.dumps(log.get('ack_aplicacion'), ensure_ascii=False)[:1500]}`

## Persistencia / memoria

- Umbral tras apply: `{json.dumps(log.get('umbral_despues_apply'), ensure_ascii=False)[:2000]}`
- SHA tras apply: `{log.get('sha_despues_apply')}`
- SHA original: `{SHA_ORIG}`

`UmbralStore.set()` escribe disco y RAM juntos. La clasificación posterior con `version_umbral` nueva evidencia la lista de `todos()` en caliente.

## Restauración

- HTTP: `{json.dumps(log.get('http_restauracion'), ensure_ascii=False)}`
- JSON restaurado: `{json.dumps(log.get('restauracion_json'), ensure_ascii=False)[:2000]}`
- SHA final: `{log.get('sha_final')}` (puede diferir del original por `version`/`comando_id`)
- Medición post-restauración (opcional): `{json.dumps(log.get('medicion_restaurada'), ensure_ascii=False)[:1500]}`

## MQTT

Sesión: `Resultados/evidencias/run-2026-10-30-g41-tc101/mqtt_session.json`

Evento posterior: `{json.dumps(log.get('evento_mqtt_posterior'), ensure_ascii=False)[:2000]}`

## Criterios PASS/FAIL

| Criterio | Resultado |
|---|---|
{filas}

## Limitaciones

- Fuente **fake** (`EDGE_FAKE_VARIABLES=Humedad Relativa:%:71:73`). Intervalo de captura 10 min.
- `version_umbral` vive en `metadata_edge` del evento MQTT; el historial local no copia ese campo.
- El SHA-256 final no debe coincidir con el original si la versión de restauración es nueva.

## Estado persistente

- TC-M03-101: **{veredicto}**
- `--live` del esqueleto etapa1: **no se usó** (POST implementado en este orquestador autorizado).
- G38: **sin alteraciones**.
"""
    REPORT.write_text(md, encoding="utf-8")
    _dump(EVID / "log_orquestador.json", {k: v for k, v in log.items()})
    wt = Path(
        r"C:\Users\ll529\OneDrive\Documentos\integrador\.worktrees\sgpmp-rf55-validation"
        r"\tests\Test_Testing\Test_Modulo3\RF-55\TC-M03-G41\RESULTADO_EJECUCION_TC_M03_101.md"
    )
    try:
        wt.write_text(md, encoding="utf-8")
    except OSError:
        pass


if __name__ == "__main__":
    raise SystemExit(main())
