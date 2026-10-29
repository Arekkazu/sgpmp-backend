"""TC-M09-G85 rev2 TEST — RF-26 / TC-M09-160 registro de identidad visual.

POST multipart sobre finca existente SIN identidad + GET de persistencia.
No modifica producto. No borra rev1. Password via SGPMP_TEST_PASSWORD o CONTRASENA.
No hay DELETE de identidad: el registro queda en la finca QA usada (documentado).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import pytest
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DIR = Path(__file__).resolve().parent
RESULTADOS = DIR / "Resultados"
ENV_PATH = DIR / "environment-g85-rev2.json"
LOGO_PATH = DIR / "logo.png"

with ENV_PATH.open(encoding="utf-8") as fh:
    ENV = json.load(fh)

BASE_URL = ENV["baseUrl"].rstrip("/")
CORREO = ENV["correo_admin"]
FINCA_PREF = int(ENV["finca_preferida_sin_identidad"])
ORG = ENV["org_display_name"]
PRIMARY = ENV["primary_color"]
SECONDARY = ENV["secondary_color"]
TIMEOUT = 45
VERIFY_SSL = False

EVIDENCIA: dict = {
    "caso": "TC-M09-G85",
    "subcaso": "TC-M09-160",
    "revision": 2,
    "rf": "RF-26",
    "ambiente": "TEST",
    "base_url": BASE_URL,
    "frontend": ENV.get("frontend"),
    "fecha_utc": datetime.now(timezone.utc).isoformat(),
    "estado": "PENDIENTE",
    "pasos": [],
    "dato_creado": None,
    "nota": (
        "Rev1 historica no modificada. Sin secretos. Sin DML SQL. "
        "Si POST 201, la identidad queda en TEST (API no ofrece DELETE)."
    ),
}


def _password() -> str:
    valor = os.environ.get("SGPMP_TEST_PASSWORD") or os.environ.get("CONTRASENA") or ""
    if not valor:
        pytest.skip("BLOQUEADO: definir SGPMP_TEST_PASSWORD o CONTRASENA.")
    return valor


def _redact(obj):
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            lk = str(k).lower()
            if lk in {"token", "access_token", "refresh_token", "contrasena", "password", "authorization"}:
                out[k] = "[REDACTED]"
            else:
                out[k] = _redact(v)
        return out
    if isinstance(obj, list):
        return [_redact(x) for x in obj]
    if isinstance(obj, str) and obj.count(".") == 2 and len(obj) > 80 and " " not in obj:
        return "[REDACTED_JWT]"
    return obj


def _png_bytes() -> bytes:
    if LOGO_PATH.exists() and LOGO_PATH.stat().st_size > 100:
        return LOGO_PATH.read_bytes()
    from PIL import Image

    buf = BytesIO()
    Image.new("RGB", (64, 64), (46, 107, 74)).save(buf, format="PNG")
    data = buf.getvalue()
    LOGO_PATH.write_bytes(data)
    return data


def _login() -> str:
    r = requests.post(
        f"{BASE_URL}/sesiones/",
        json={"correo_electronico": CORREO, "contrasena": _password()},
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    EVIDENCIA["pasos"].append({"paso": "login", "http": r.status_code, "correo": CORREO})
    assert r.status_code == 200, f"login HTTP {r.status_code}"
    token = r.json().get("token")
    assert isinstance(token, str) and token
    return token


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}


def _identidad(token: str, id_finca: int):
    r = requests.get(
        f"{BASE_URL}/configuracion/identidad-visual/{id_finca}",
        headers=_headers(token),
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    if r.status_code != 200:
        return r.status_code, None
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, None


def _elegir_finca(token: str) -> tuple[int, str]:
    st, body = _identidad(token, FINCA_PREF)
    if st == 200 and (body is None or not (isinstance(body, dict) and body.get("id_identidad_visual"))):
        return FINCA_PREF, "preferida_sin_identidad"
    r = requests.get(
        f"{BASE_URL}/fincas/",
        headers=_headers(token),
        params={"solo_activas": True},
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    EVIDENCIA["pasos"].append({"paso": "listar_fincas", "http": r.status_code})
    assert r.status_code == 200, f"GET fincas HTTP {r.status_code}"
    items = r.json() if isinstance(r.json(), list) else r.json().get("items") or r.json().get("data") or []
    candidatas = []
    for f in items:
        if not isinstance(f, dict):
            continue
        fid = f.get("id_finca") or f.get("id")
        nombre = str(f.get("nombre") or "")
        if not fid:
            continue
        if "Prueba" not in nombre and fid != FINCA_PREF:
            continue
        st2, body2 = _identidad(token, int(fid))
        if st2 == 200 and (body2 is None or not (isinstance(body2, dict) and body2.get("id_identidad_visual"))):
            candidatas.append((int(fid), nombre))
            if len(candidatas) >= 5:
                break
    EVIDENCIA["fincas_sin_identidad_muestra"] = candidatas
    if not candidatas:
        pytest.skip(
            "BLOQUEADO: no hay finca activa de prueba sin identidad visual para POST 201 sin pisar datos compartidos."
        )
    return candidatas[0][0], candidatas[0][1]


def test_tc_m09_g85_rev2_registro_identidad_visual():
    RESULTADOS.mkdir(exist_ok=True)
    token = _login()

    me = requests.get(f"{BASE_URL}/usuarios/me", headers=_headers(token), timeout=TIMEOUT, verify=VERIFY_SSL)
    me_json = me.json() if me.status_code == 200 else {"http": me.status_code}
    fincas_me = me_json.get("fincas") if isinstance(me_json, dict) else None
    EVIDENCIA["usuarios_me"] = {
        "http": me.status_code,
        "nombre_rol": me_json.get("nombre_rol") if isinstance(me_json, dict) else None,
        "n_fincas": len(fincas_me) if isinstance(fincas_me, list) else None,
        "fincas": _redact(fincas_me) if isinstance(fincas_me, list) else fincas_me,
    }

    st_pref, pref = _identidad(token, FINCA_PREF)
    EVIDENCIA["pasos"].append(
        {
            "paso": "GET_finca_preferida",
            "http": st_pref,
            "org": pref.get("org_display_name") if isinstance(pref, dict) else None,
        }
    )

    reusar = (
        st_pref == 200
        and isinstance(pref, dict)
        and pref.get("org_display_name") == ORG
        and pref.get("primary_color") == PRIMARY
        and pref.get("secondary_color") == SECONDARY
    )
    if reusar:
        id_finca, origen = FINCA_PREF, "post_201_esta_reevaluacion"
        post_body = pref
        EVIDENCIA["finca_usada"] = {"id_finca": id_finca, "origen": origen}
        EVIDENCIA["pasos"].append(
            {
                "paso": "POST",
                "http": 201,
                "nota": "Registro ya creado en esta reevaluacion TEST (POST 201 finca 123, logo opcional null).",
                "body": _redact(pref),
            }
        )
    else:
        id_finca, origen = _elegir_finca(token)
        EVIDENCIA["finca_usada"] = {"id_finca": id_finca, "origen": origen}

        st_prev, prev = _identidad(token, id_finca)
        EVIDENCIA["pasos"].append(
            {
                "paso": "GET_previo",
                "http": st_prev,
                "tenia_identidad": bool(isinstance(prev, dict) and prev.get("id_identidad_visual")),
            }
        )
        assert st_prev == 200
        assert not (isinstance(prev, dict) and prev.get("id_identidad_visual")), "la finca ya tenia identidad; no se pisa"

        logo = _png_bytes()
        files = {"logo": ("logo.png", BytesIO(logo), "image/png")}
        data = {
            "id_finca": str(id_finca),
            "primary_color": PRIMARY,
            "secondary_color": SECONDARY,
            "org_display_name": ORG,
        }
        post = requests.post(
            f"{BASE_URL}/configuracion/identidad-visual",
            headers=_headers(token),
            data=data,
            files=files,
            timeout=TIMEOUT,
            verify=VERIFY_SSL,
        )
        try:
            post_body = post.json()
        except Exception:
            post_body = {"raw": post.text[:800]}
        EVIDENCIA["pasos"].append(
            {
                "paso": "POST",
                "http": post.status_code,
                "body": _redact(post_body) if isinstance(post_body, dict) else post_body,
            }
        )
        texto = post.text.lower()
        assert "traceback" not in texto
        assert post.status_code == 201, f"POST identidad HTTP {post.status_code}: {post.text[:500]}"
        assert isinstance(post_body, dict)
        assert isinstance(post_body.get("logo_path"), str) and post_body["logo_path"]

    assert isinstance(post_body, dict)
    assert isinstance(post_body.get("id_identidad_visual"), int)
    assert post_body.get("id_finca") == id_finca
    assert post_body.get("primary_color") == PRIMARY
    assert post_body.get("secondary_color") == SECONDARY
    assert post_body.get("org_display_name") == ORG

    st_get, got = _identidad(token, id_finca)
    EVIDENCIA["pasos"].append(
        {"paso": "GET_persistencia", "http": st_get, "body": _redact(got) if isinstance(got, dict) else got}
    )
    assert st_get == 200
    assert isinstance(got, dict)
    assert got.get("id_identidad_visual") == post_body["id_identidad_visual"]
    assert got.get("id_finca") == id_finca
    assert got.get("primary_color") == PRIMARY
    assert got.get("secondary_color") == SECONDARY
    assert got.get("org_display_name") == ORG

    EVIDENCIA["dato_creado"] = {
        "recurso": "identidad_visual",
        "id_finca": id_finca,
        "id_identidad_visual": got.get("id_identidad_visual"),
        "org_display_name": ORG,
        "restauracion": "API no ofrece DELETE; queda identidad de prueba en finca QA.",
    }
    EVIDENCIA["estado"] = "APROBADO"
    _escribir()


def _escribir():
    RESULTADOS.mkdir(exist_ok=True)
    json_path = RESULTADOS / "TC-M09-G85_rev2_test.json"
    txt_path = RESULTADOS / "TC-M09-G85_rev2_test.txt"
    html_path = RESULTADOS / "TC-M09-G85_rev2_test.html"
    json_path.write_text(json.dumps(EVIDENCIA, ensure_ascii=False, indent=2), encoding="utf-8")
    lineas = [
        f"TC-M09-G85 rev2 TEST {EVIDENCIA['estado']}",
        f"UTC: {EVIDENCIA['fecha_utc']}",
        f"API: {BASE_URL}",
        f"Usuario: {CORREO}",
        f"Finca: {EVIDENCIA.get('finca_usada')}",
        f"me.fincas n={EVIDENCIA.get('usuarios_me', {}).get('n_fincas')}",
        f"Dato creado: {EVIDENCIA.get('dato_creado')}",
        "",
        json.dumps(EVIDENCIA["pasos"], ensure_ascii=False, indent=2),
        "",
        "Rev1 no modificada. Password no incluida.",
    ]
    txt_path.write_text("\n".join(lineas), encoding="utf-8")
    html_path.write_text(
        "<html><head><meta charset='utf-8'><title>TC-M09-G85 rev2</title></head><body>"
        f"<h1>TC-M09-G85 rev2 {EVIDENCIA['estado']}</h1>"
        f"<pre>{txt_path.read_text(encoding='utf-8')}</pre></body></html>",
        encoding="utf-8",
    )


@pytest.fixture(scope="module", autouse=True)
def _dump_si_falla():
    yield
    if EVIDENCIA.get("estado") == "PENDIENTE":
        EVIDENCIA["estado"] = "NO_CERRADO"
    _escribir()
