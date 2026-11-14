"""Cierre de SOLO LECTURA del RUN de TC-M09-G139.

Por qué existe
--------------
Ejecución 2 (reejecución completa post-fix del PR #550). Los veinte controles
funcionales de `test_g139_v2.py` pasaron: TC-M09-282 devolvió 422
VISION_NO_DISPONIBLE, la corrida N publicó la línea base y la corrida N−1 devolvió
el 422 LINEA_BASE_NO_CALCULADA del contrato dejando la calibración FALLIDA en etapa
FILTRADO sin sustituir la línea base. El único control que no llegó a ejecutarse fue
`test_21_auditoria_rf10`, y por un defecto de MI automatización, no del producto: la
consulta pedía `tamano=100` y `GET /auditoria/` acepta como máximo 50, de modo que
respondió 400 VAL_ENTRADA antes de leer un solo evento. El límite ya está corregido
en la suite.

El paquete prohíbe repetir un POST funcional que ya recibió respuesta (§47) y fija el
presupuesto en 3 calibraciones y 3 lotes (§46), que quedó agotado y correcto. Las
verificaciones posteriores sólo pueden hacerse con GET o SELECT de solo lectura, y eso
es lo que hace este cierre: reconstruye el estado de la ejecución desde `evidencia.json`
y vuelve a ejecutar los MISMOS oráculos de la suite (`test_21_auditoria_rf10` y
`test_22_cuadro_y_cierre`, importados, no reescritos) para no duplicar criterios.

Cero POST funcionales. Cero DML. Cero artefactos nuevos: se actualizan `evidencia.json`
y `automation_manifest.json` del RUN vigente.

Uso:  G139_RUN_ID=run-... G139_ADM_PASSWORD=... python cierre_lectura_g139.py
"""
from __future__ import annotations

import datetime
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_g139_v2 as suite  # noqa: E402  (requiere G139_RUN_ID en el entorno)


def _fecha(valor: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(valor)


def main() -> int:
    run_dir = suite.RUN_DIR
    ruta = run_dir / "evidencia.json"
    if not ruta.is_file():
        print(f"ABORTADO: no existe {ruta}")
        return 2
    previo = json.loads(ruta.read_text(encoding="utf-8"))
    if previo.get("run_id") != suite.RUN_ID:
        print(f"ABORTADO: la evidencia es del RUN {previo.get('run_id')}, no de {suite.RUN_ID}")
        return 2
    if previo.get("execution_number") != suite.EJECUCION:
        print(f"ABORTADO: la evidencia es de la ejecución {previo.get('execution_number')}")
        return 2

    # La evidencia de la ejecución en curso es la fuente del estado; no se recalcula nada.
    suite.E.clear()
    suite.E.update(previo)
    casos = suite.E["casos"]
    cN, cN1 = casos["TC-M09-283-N"], casos["TC-M09-283-N-1"]
    presupuesto = suite.E["presupuesto"]
    if presupuesto != {"post_calibracion": 3, "post_vision": 3, "reintentos": 0}:
        print(f"ABORTADO: presupuesto inesperado en la evidencia: {presupuesto}")
        return 2

    suite.ESTADO.update({
        "abortado": None,
        "post_hechos": set(),
        "N": suite.E["valor_N"]["N"],
        "N1": suite.E["valor_N"]["N_menos_1"],
        "camara_id": suite.E["fixture"]["camara_creada"]["id"],
        "ID_N": cN["id_calibracion_vision"],
        "ID_N1": cN1["calibracion_fallida"]["id_calibracion_vision"],
        "BASELINE_N": cN["baseline_POST"]["id_calibracion_vision"],
        # La ejecución 2 no persistió el T_BEFORE de TC-282 (ya corregido en la suite):
        # se toma el del intento N−1 menos 5 minutos, que cubre con holgura los 11 s que
        # duró la suite completa y deja el tramo de TC-282 dentro de la ventana consultada.
        "T_BEFORE_282": _fecha(
            casos["TC-M09-282"]["baseline_PRE"].get("T_BEFORE")
            or cN1["baseline_PRE"]["T_BEFORE"]) - datetime.timedelta(
                minutes=0 if casos["TC-M09-282"]["baseline_PRE"].get("T_BEFORE") else 5),
        "T_BEFORE_N1": _fecha(cN1["baseline_PRE"]["T_BEFORE"]),
        "T_AFTER_N1": _fecha(cN1["T_AFTER"]),
        "conservada": True,
    })

    # Sólo el Administrador: la auditoría RF-10 es lo único que falta leer.
    clave = os.environ.get("G139_ADM_PASSWORD")
    if not clave:
        print("ABORTADO: falta G139_ADM_PASSWORD en el entorno (no se persiste).")
        return 2
    try:
        suite.API.login(suite.ADM[0], clave, "admin")
    except AssertionError:
        suite.API.login(suite.ADM_ALT[0], clave, "admin")

    # Mismos oráculos de la suite, sin reescribirlos.
    suite.test_21_auditoria_rf10()
    suite.test_22_cuadro_y_cierre()

    suite.E["cierre_lectura"] = {
        "script": "EvaluacionV2/automation/cierre_lectura_g139.py",
        "ejecutado": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "motivo": ("completar §45 (auditoría RF-10) tras un defecto de automatización en la "
                   "consulta: se pedía tamano=100 y GET /auditoria/ admite 50 como máximo, "
                   "así que devolvió 400 VAL_ENTRADA sin leer eventos. El límite ya está "
                   "corregido en test_g139_v2.py."),
        "oraculos_reutilizados": ["test_21_auditoria_rf10", "test_22_cuadro_y_cierre"],
        "post_funcionales_adicionales": 0,
        "lotes_m03_adicionales": 0,
        "dml": 0,
        "presupuesto_sin_cambios": presupuesto,
    }
    suite.E["defecto_de_automatizacion_ejecucion_2"] = {
        "donde": "test_21_auditoria_rf10 — consulta GET /auditoria/",
        "sintoma": ("HTTP 400 VAL_ENTRADA, field `tamano`: «Input should be less than or "
                    "equal to 50»"),
        "naturaleza": "AUTOMATIZACIÓN (QA). No es un defecto del producto.",
        "impacto_en_el_producto": "NINGUNO: no se emitió ningún POST por este fallo.",
        "pytest_xml": ("refleja la ejecución real de la suite: 22 collected, 20 passed, "
                       "1 failed (este control) y 1 skipped (el cierre, que dependía de él). "
                       "No se maquilla; la verificación se completó por GET en este cierre."),
        "correccion": "tamano=50 en test_g139_v2.py",
    }
    suite.guardar_evidencia()
    suite._escribir_manifest()

    aud = suite.E["auditoria_rf10"]
    print("AUDITORÍA RF-10")
    print("  TC-M09-282      :", aud["TC282"]["encontrada"],
          "evento", aud["TC282"]["verificado"]["id_evento"],
          aud["TC282"]["verificado"]["resultado"],
          aud["TC282"]["verificado"]["codigo_error"])
    print("  TC-M09-283 N    :", aud["TC283_N"]["encontrada"],
          "evento", casos["TC-M09-283-N"]["auditoria"]["id_evento"],
          casos["TC-M09-283-N"]["auditoria"]["resultado"])
    v = aud["TC283_N_MINUS_1"]["verificado"]
    print("  TC-M09-283 N−1  :", aud["TC283_N_MINUS_1"]["encontrada"],
          "evento", v["id_evento"], v["resultado"], v["codigo_error"],
          v["estado"], v["etapa_fallo"], "IP", v["direccion_ip"],
          "en ventana", v["en_ventana_del_intento"])
    print("RESULTADO:", json.dumps(suite.E["resultado"], ensure_ascii=False))
    print("POST adicionales:", 0, "· DML:", 0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
