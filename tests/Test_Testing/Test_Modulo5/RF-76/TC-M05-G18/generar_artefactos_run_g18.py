# | Fecha      | Nombre                   | Que se hizo               |
# |------------|--------------------------|---------------------------|
# | 13/11/2026 | Juan Sebastian Gutierrez | reintento INC-M05-352-G18 |
"""Generador de artefactos de corrida para TC-M05-G18 (RF-76).

Lee del staging de la corrida:
- junit_TC-M05-G18[_reintentoN].xml       (resultado de cada test)
- trazas_tc_m05_g18[_reintentoN].json     (esperado / obtenido real de cada checkpoint)
- trazas_http[_reintentoN].jsonl          (X-Request-Id de cada respuesta HTTP de TEST)
- observaciones_tc_m05_g18[_reintentoN].json (observaciones sin checkpoint)

y genera, SOLO dentro del staging (nunca en resultados/):
- resultado_TC-M05-G18[_reintentoN].json
- TC-M05-G18[_reintentoN]_resultado.md
- inyecta data-jsonblob en resultado_TC-M05-G18[_reintentoN].html

El "obtenido" de cada checkpoint es el que el propio test registro con valores reales;
los fallos se clasifican como PENDIENTE_DIAGNOSTICO.
"""
from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ZONA_USUARIO = timezone(timedelta(hours=-5))
TC = "TC-M05-G18"

# test (nombre pytest) -> id de checkpoint usado en las trazas
CHECKPOINTS: list[tuple[str, str]] = [
    ("test_g18_s1_01_dos_tratamientos_vencido_y_vigente_manana_no_revierte", "G18_S1_01"),
    ("test_g18_s1_02_retiro_vence_hoy_invoca_rf44_una_vez_y_revierte", "G18_S1_02"),
    ("test_g18_s1_03a_fin_retiro_aviso_interno_productor_y_veterinario", "G18_S1_03a"),
    ("test_g18_s1_03b_dos_tratamientos_uno_vigente_sin_aviso_fin_retiro", "G18_S1_03b"),
    ("test_g18_s2_01_falla_rf44_retorna_500_y_mensaje_reversion", "G18_S2_01"),
    ("test_g18_s2_02_falla_rf44_rollback_sin_registro_persistido", "G18_S2_02"),
    ("test_g18_s2_03_falla_rf44_mantiene_estado_activo_y_sin_notificacion", "G18_S2_03"),
    ("test_g18_s3_01_falla_calculo_fecha_fin_retiro", "G18_S3_01"),
    ("test_g18_s3_02_falla_bd_guardar_por_db_error_translator_y_rollback", "G18_S3_02"),
    ("test_g18_s3_03a_escenario_a_falla_calculo_fecha_fin_retiro_incidente", "G18_S3_03a"),
    ("test_g18_s3_03b_escenario_b_error_bd_al_guardar_incidente", "G18_S3_03b"),
    ("test_g18_s3_03c_escenario_b_tambien_falla_escritura_incidente", "G18_S3_03c"),
    ("test_g18_t00_linea_base_sandbox", "G18_T00"),
    ("test_g18_r_01_control_real_sandbox_sin_retiro_e_inocuidad", "G18_R_01"),
    ("test_g18_t99_inocuidad_post_rollback", "G18_T99"),
]
PREFIJO_OBSERVACION = "test_g18_obs_"


def _leer_json(ruta: Path, defecto: Any) -> Any:
    if not ruta.exists():
        return defecto
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return defecto


def _trazas_http_por_test(ruta: Path) -> dict[str, list[dict[str, Any]]]:
    por_test: dict[str, list[dict[str, Any]]] = {}
    if not ruta.exists():
        return por_test
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        if not linea.strip():
            continue
        try:
            item = json.loads(linea)
        except ValueError:
            continue
        por_test.setdefault(item.get("test") or "init", []).append(item)
    return por_test


def _resumen_http(trazas: list[dict[str, Any]]) -> str:
    partes = []
    for t in trazas:
        s = f"{t.get('metodo')} {t.get('ruta')} -> {t.get('status_code')}"
        if t.get("error_code"):
            s += f" ({t['error_code']})"
        if t.get("allow"):
            s += f" Allow={t['allow']}"
        s += f" [X-Request-Id={t.get('x_request_id')}]"
        partes.append(s)
    return "; ".join(partes)


def main() -> int:
    parser = argparse.ArgumentParser(description=f"Generador de artefactos de corrida {TC}")
    parser.add_argument("--staging", required=True, help="Directorio de staging de la corrida")
    parser.add_argument("--reintento", type=int, default=0, help="Numero de reintento (0 = corrida inicial)")
    parser.add_argument("--duracion-s", type=float, default=0.0, help="Duracion de la corrida en segundos")
    args = parser.parse_args()

    staging = Path(args.staging)
    sufijo = f"_reintento{args.reintento}" if args.reintento > 0 else ""
    xml_path = staging / f"junit_{TC}{sufijo}.xml"
    if not xml_path.exists():
        print(f"ERROR: no existe {xml_path.name} en el staging")
        return 2

    trazas = {t.get("test"): t for t in _leer_json(staging / f"trazas_tc_m05_g18{sufijo}.json", [])}
    http = _trazas_http_por_test(staging / f"trazas_http{sufijo}.jsonl")
    observaciones = _leer_json(staging / f"observaciones_tc_m05_g18{sufijo}.json", [])

    casos = {tc.attrib.get("name", ""): tc for tc in ET.parse(xml_path).getroot().findall(".//testcase")}

    checkpoints: list[dict[str, Any]] = []
    fallas: list[dict[str, Any]] = []
    ok = 0
    for nombre_test, id_cp in CHECKPOINTS:
        tc = casos.get(nombre_test)
        traza = trazas.get(id_cp)
        if tc is None:
            estado, obtenido, esperado = "PENDIENTE_DIAGNOSTICO", "El test no aparece en el JUnit de la corrida", ""
        else:
            fallo = tc.find("failure") if tc.find("failure") is not None else tc.find("error")
            esperado = (traza or {}).get("esperado", "")
            if traza is not None:
                obtenido = traza.get("obtenido", "")
            elif fallo is not None:
                obtenido = (fallo.attrib.get("message") or fallo.text or "").strip()
            else:
                obtenido = "El test no registro traza"
            estado = "OK" if fallo is None and traza is not None and traza.get("estado") == "OK" else "PENDIENTE_DIAGNOSTICO"
            if fallo is not None:
                fallas.append({
                    "checkpoint": id_cp,
                    "test": nombre_test,
                    "clasificacion": "PENDIENTE_DIAGNOSTICO",
                    "junit": (fallo.attrib.get("message") or fallo.text or "").strip()[:1500],
                })
        resumen_http = _resumen_http(http.get(nombre_test, []))
        if resumen_http:
            obtenido = f"{obtenido} | HTTP: {resumen_http}"
        if estado == "OK":
            ok += 1
        checkpoints.append({"paso": id_cp, "esperado": esperado, "obtenido": obtenido, "estado": estado})

    total = len(checkpoints)
    falla = total - ok
    veredicto = "Aprobado" if total > 0 and falla == 0 else "Rechazado"
    tests_observacion = sorted(n for n in casos if n.startswith(PREFIJO_OBSERVACION))
    obs_tests_estado = {
        n: ("OK" if casos[n].find("failure") is None and casos[n].find("error") is None else "PENDIENTE_DIAGNOSTICO")
        for n in tests_observacion
    }
    resultado = {
        "tc": TC,
        "reintento": args.reintento,
        "summary": {"total": total, "ok": ok, "falla": falla, "veredicto": veredicto},
        "checkpoints": checkpoints,
        "observaciones": observaciones,
        "tests_de_observacion": obs_tests_estado,
        "fallas": fallas,
    }

    json_path = staging / f"resultado_{TC}{sufijo}.json"
    json_path.write_text(json.dumps(resultado, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Generado: {json_path.name}")

    html_path = staging / f"resultado_{TC}{sufijo}.html"
    if html_path.exists():
        html = html_path.read_text(encoding="utf-8")
        if 'id="data-jsonblob"' not in html:
            blob = ('<script id="data-jsonblob" type="application/json">'
                    f"{json.dumps(resultado, ensure_ascii=False)}</script>")
            html = html.replace("</body>", f"{blob}</body>") if "</body>" in html else html + blob
            html_path.write_text(html, encoding="utf-8")
            print(f"Inyectado data-jsonblob en {html_path.name}")

    ahora = datetime.now(ZONA_USUARIO).strftime("%Y-%m-%d %H:%M:%S")
    md = [
        f"# Resultado de prueba: {TC} (reintento {args.reintento})",
        "",
        f"- Veredicto: {veredicto} ({ok}/{total} OK, {falla} pendientes de diagnostico)",
        f"- Fecha: {ahora} (America/Bogota)",
        f"- Duracion: {args.duracion_s:.2f} s",
        "",
        "| # | Paso | Esperado | Obtenido | Estado |",
        "|---|------|----------|----------|--------|",
    ]
    for i, cp in enumerate(checkpoints, 1):
        celdas = [str(cp[k]).replace("|", "/").replace("\n", " ") for k in ("paso", "esperado", "obtenido", "estado")]
        md.append(f"| {i} | " + " | ".join(celdas) + " |")
    md += ["", "## Observaciones (sin checkpoint)"]
    if observaciones:
        for o in observaciones:
            md.append(f"- {o.get('observacion')}: `{json.dumps(o.get('datos'), ensure_ascii=False)}`")
    else:
        md.append("- (ninguna registrada)")
    md_path = staging / f"{TC}{sufijo}_resultado.md"
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"Generado: {md_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
