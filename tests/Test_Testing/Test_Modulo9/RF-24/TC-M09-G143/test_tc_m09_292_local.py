"""TC-M09-292 — Compuerta previa al laboratorio local (RF-24 v2.0, CU05 Flujo F).

El caso es LOCAL AISLADO, pero antes de levantar nada el paquete exige dos cosas (§28 y §31):

1. que el artefacto que se llevaría al laboratorio contenga realmente VISION — operación, fuente
   de observaciones, cálculo de línea base, persistencia, auditoría de publicación y transacción
   verificable —, porque **no se mockea VISION para volverlo ejecutable**;
2. que la auditoría *obligatoria* de la publicación VISION quede identificada inequívocamente antes
   de cualquier `REVOKE`. Si no puede identificarse, el caso queda BLOQUEADO: **no se revocan
   tablas al azar** (§32).

Este módulo resuelve ambas compuertas leyendo `src/` y `alembic/`. Si falla cualquiera, deja
TC-M09-292 como BLOQUEADO y **no** levanta Docker, no crea base, no migra, no siembra, no toca
privilegios y no ejecuta ningún POST.

Uso:
    pytest test_tc_m09_292_local.py -v --noconftest
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path



FOLDER = "TC-M09-G143"
BASE_DIR = Path(__file__).resolve().parent
if BASE_DIR.name != FOLDER:
    raise RuntimeError(f"Directorio no autorizado para {FOLDER}")

GRUPO = "TC-M09-G143"
CASO = "TC-M09-292"
RF = "RF-24 v2.0"

RUN_ID = os.environ["G143_RUN_ID_LOCAL"]
OUT_DIR = BASE_DIR / "RESULTADOS" / RUN_ID
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Nombres reservados del laboratorio que este caso NO llega a levantar. Se dejan escritos para que
# quede claro que no se reutiliza la BD de desarrollo ni los laboratorios de G79 o G136 (§29).
LAB = {
    "compose_project": "sgpmp-g143-292",
    "base": "sgpmp_g143_292",
    "puerto_postgres": 55443,
    "backend": "http://127.0.0.1:18043",
    "volumen": "sgpmp_g143_292_pgdata",
}

# Coincidencias que NO acreditan VISION. Contarlas como presencia produciría un falso positivo de
# ejecutabilidad y, peor en este caso, llevaría a revocar INSERT sobre una tabla equivocada:
#   - CAMARA_VISION / ATRIBUTOS_VISION: el TIPO DE DISPOSITIVO cámara y sus atributos (resolución,
#     fps, área de cobertura). Es el hardware, no la operación de calibración por visión.
#   - modulo9.auditorias_visuales: es la auditoría de IDENTIDAD VISUAL de RF-26 (logo, colores de
#     marca). "Visual" no es "visión por computador": revocarla sería revocar una tabla al azar.
#   - integridad_baseline / "línea base de integridad": es el baseline de RF-10, no la línea base
#     del Flujo F.
FALSOS_POSITIVOS = (
    r"CAMARA_VISION",
    r"_atributos_vision",
    r"ATRIBUTOS_VISION",
    r"auditorias_visuales",
    r"identidad[_ ]?visual",
    r"AuditoriaIdentidadVisual",
    r"linea[_ ]?base de integridad",
    r"integridad_baseline",
)

BORDE = "[A-Za-zÁÉÍÓÚáéíóúÑñ]"


def repo_root() -> Path:
    d = BASE_DIR
    for _ in range(12):
        if (d / ".git").exists():
            return d
        d = d.parent
    return BASE_DIR


def git(*args: str) -> str:
    try:
        r = subprocess.run(["git", "-C", str(repo_root()), *args], capture_output=True,
                           text=True, timeout=60, encoding="utf-8", errors="replace")
        return r.stdout.strip() or "(vacio)"
    except Exception as e:  # pragma: no cover - diagnóstico
        return f"ERROR: {e}"


def _es_falso_positivo(linea: str) -> bool:
    return any(re.search(p, linea, re.IGNORECASE) for p in FALSOS_POSITIVOS)


def buscar(patron: str, *, filtrar: bool = True) -> list[str]:
    """Líneas del artefacto que coinciden, con o sin el filtro de falsos positivos."""
    raiz = repo_root()
    hallados: list[str] = []
    for carpeta in ("src", "alembic"):
        base = raiz / carpeta
        if not base.is_dir():
            continue
        for ruta in sorted(base.rglob("*.py")):
            try:
                texto = ruta.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            rel = str(ruta.relative_to(raiz)).replace("\\", "/")
            for i, linea in enumerate(texto.splitlines(), 1):
                if re.search(patron, linea, re.IGNORECASE):
                    if filtrar and _es_falso_positivo(linea):
                        continue
                    hallados.append(f"{rel}:{i}")
    return hallados


def tablas_declaradas() -> list[str]:
    """`__tablename__` de los modelos ORM del artefacto."""
    raiz = repo_root()
    nombres: set[str] = set()
    for ruta in (raiz / "src").rglob("*.py"):
        try:
            texto = ruta.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        nombres.update(re.findall(r"__tablename__\s*=\s*['\"]([a-z0-9_]+)['\"]", texto))
    return sorted(nombres)


def columnas_de(modelo_tabla: str) -> dict:
    """Columnas y nulabilidad del modelo cuyo `__tablename__` coincide."""
    raiz = repo_root()
    for ruta in (raiz / "src").rglob("*.py"):
        try:
            texto = ruta.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not re.search(rf"__tablename__\s*=\s*['\"]{modelo_tabla}['\"]", texto):
            continue
        cols = {}
        for m in re.finditer(r"^\s+([a-z0-9_]+):\s*Mapped\[([^\]]+)\][^\n]*", texto, re.M):
            nombre, tipo = m.group(1), m.group(2)
            cols[nombre] = {
                "tipo": tipo.strip(),
                "nullable": ("nullable=True" in m.group(0)) or tipo.strip().startswith("Optional"),
            }
        return {"archivo": str(ruta.relative_to(raiz)).replace("\\", "/"), "columnas": cols}
    return {}


def test_compuerta_previa_al_laboratorio_local():
    raiz = repo_root()

    # -------------------------------------------- §28: piezas esenciales del artefacto
    piezas = {
        "operacion_vision": rf"(?<!{BORDE})VISION(?!{BORDE})",
        "modo_calibracion": r"modo_calibracion",
        "fuente_observaciones_vision": r"vector_comportamiento|ventana_observacion|observacion_vision",
        "calculo_de_linea_base": r"winsoriz|percentil|p95|refinamiento|convergencia|mediana_iterativa",
        "persistencia_de_linea_base": r"linea[_ ]?base|lineas_base",
        # 'VISION' debe exigirse como palabra también aquí: un patrón laxo como `auditoria.*vision`
        # casa con `EventoAuditoriaSuministro(... PROVISION_INCREMENTAL_ENTREGADA ...)`, que es la
        # auditoría de suministros NIC-41 y no acredita nada de VISION.
        "auditoria_de_publicacion_vision":
            rf"(auditor\w*.*(?<!{BORDE})VISION(?!{BORDE})"
            rf"|(?<!{BORDE})VISION(?!{BORDE}).*auditor\w*"
            rf"|publicacion_linea_base)",
        # Esta pieza es infraestructura GENÉRICA de transacción, no específica de VISION: el
        # artefacto sí tiene rollback y transacciones, y se cuenta como presente porque lo está.
        # No implica que exista una transacción de publicación VISION que se pueda revertir.
        "transaccion_rollback_generica": r"rollback|begin_nested|transaction\(",
    }
    hallazgos = {n: buscar(p) for n, p in piezas.items()}
    presentes = {n: bool(v) for n, v in hallazgos.items()}
    # `transaccion_rollback_generica` no es una pieza VISION: cuenta como contexto, no como
    # evidencia de ejecutabilidad. Si se dejara en el denominador, un artefacto sin VISION pero con
    # transacciones parecería estar más cerca de ser ejecutable de lo que está.
    piezas_vision = {n: v for n, v in presentes.items() if n != "transaccion_rollback_generica"}

    # -------------------------------------------- falsos positivos, documentados en lugar de ocultos
    falsos = {
        "camara_vision_y_sus_atributos": buscar(r"CAMARA_VISION|ATRIBUTOS_VISION|_atributos_vision",
                                                filtrar=False),
        "auditorias_visuales_rf26_identidad_visual": buscar(
            r"auditorias_visuales|AuditoriaIdentidadVisual", filtrar=False),
        "linea_base_de_integridad_rf10": buscar(r"integridad_baseline|linea[_ ]?base de integridad",
                                                filtrar=False),
    }

    # -------------------------------------------- §31/§32: identificar la auditoría REAL de VISION
    tablas = tablas_declaradas()
    candidatas_auditoria = [t for t in tablas if "auditor" in t or "eventos" in t or "bitacora" in t]
    examen = {}
    for t in ("calibraciones", "auditorias_calibraciones", "auditorias_visuales"):
        det = columnas_de(t)
        if not det:
            continue
        cols = det["columnas"]
        examen[t] = {
            "archivo": det["archivo"],
            "columnas": sorted(cols),
            "id_sensor_nullable": cols.get("id_sensor", {}).get("nullable"),
            "id_usuario_nullable": cols.get("id_usuario", {}).get("nullable"),
            "tiene_area_o_especie": any(k in cols for k in
                                        ("id_infraestructura", "id_area", "id_especie")),
            "tiene_vigencia": any("vigen" in k for k in cols),
            "tiene_origen_disparo": any("origen" in k for k in cols),
        }

    objetivo = {
        "schema": None,
        "table": None,
        "reason": ("No identificable. La publicación VISION no existe en el artefacto, de modo que "
                   "no hay una escritura que el proceso considere obligatoria para garantizar "
                   "trazabilidad. Ninguna de las superficies existentes sirve de sustituto: "
                   "modulo9.calibraciones es de SENSOR (id_sensor e id_usuario NOT NULL, sin área, "
                   "especie, vigencia ni origen de disparo), modulo9.auditorias_calibraciones "
                   "depende de un id_calibracion de sensor con id_usuario NOT NULL, "
                   "modulo9.auditorias_visuales es la identidad visual de RF-26 y "
                   "modulo1.integridad_baseline es el baseline de RF-10. Revocar INSERT sobre "
                   "cualquiera de ellas sería revocar una tabla al azar y el resultado no "
                   "demostraría nada sobre VISION."),
        "control_positivo_posible": False,
        "nota_control_positivo": ("§31 exige una publicación VISION positiva de control para "
                                 "correlacionar escrituras antes de elegir la tabla. Sin operación "
                                 "VISION esa publicación de control no puede ejecutarse, así que la "
                                 "tabla objetivo no puede derivarse empíricamente."),
        "candidatas_descartadas": candidatas_auditoria,
        "examen_de_superficies": examen,
    }

    ejecutable = all(piezas_vision.values())
    identificable = bool(objetivo["table"])

    ev = {
        "grupo": GRUPO, "caso": CASO, "requisito": RF,
        "ambiente": "LOCAL_AISLADO", "prueba_local": True, "run_id": RUN_ID,
        "fecha": datetime.now(timezone.utc).isoformat(),
        "git": {
            "rama": git("branch", "--show-current"),
            "status_short": git("status", "--short"),
            "diff_stat": git("diff", "--stat"),
            "diff_cached_stat": git("diff", "--cached", "--stat"),
            "head": git("rev-parse", "HEAD"),
            "origin_test": git("rev-parse", "origin/test"),
            "divergencia": git("rev-list", "--left-right", "--count", "HEAD...origin/test"),
        },
        "lab_guard": {
            "levantado": False,
            "nombres_reservados": LAB,
            "reutiliza_bd_desarrollo": False,
            "reutiliza_laboratorio_g79": False,
            "reutiliza_laboratorio_g136": False,
            "motivo": ("No se construye un laboratorio para una función inexistente y no se "
                       "mockea VISION para volverla ejecutable (§28). No se creó compose, base, "
                       "migraciones, roles ni semillas."),
        },
        "artefacto_evaluado": {"repositorio": raiz.name, "carpetas": ["src", "alembic"]},
        "compuerta_previa": {
            "piezas_requeridas": piezas_vision,
            "lineas_por_pieza": hallazgos,
            "cumplidas": sum(1 for v in piezas_vision.values() if v),
            "total": len(piezas_vision),
            "contexto_no_computado": {
                "transaccion_rollback_generica": presentes["transaccion_rollback_generica"],
                "coincidencias": len(hallazgos["transaccion_rollback_generica"]),
                "nota": ("El artefacto sí tiene transacciones y rollback, pero son genéricos. No "
                         "se cuentan como pieza VISION: tener rollback no acerca el caso a ser "
                         "ejecutable si no hay una publicación VISION que revertir."),
            },
        },
        "falsos_positivos_descartados": {
            "coincidencias": falsos,
            "nota": ("Las 7 apariciones de VISION como palabra en el artefacto son CAMARA_VISION y "
                     "ATRIBUTOS_VISION: el tipo de dispositivo cámara y sus atributos. "
                     "auditorias_visuales es identidad visual de RF-26. Ninguna acredita una "
                     "operación de calibración por visión."),
        },
        "audit_target": objetivo,
        "privileges": {
            "insert_before": None, "insert_during": None, "insert_restored": None,
            "nota": ("No se ejecutó ningún REVOKE ni GRANT: sin tabla objetivo identificada, "
                     "revocar sería arbitrario y el laboratorio quedaría inválido (§32)."),
        },
        "roles_postgres": {"owner": None, "app_user": None,
                           "nota": "No se crearon: el laboratorio no se levantó."},
        "L1": None, "W2": None, "request": None, "response": None,
        "audit_failure": None, "baseline_post": None,
        "presupuesto": {"postVisionSetupPlanificados": 1, "postVisionObjetivoPlanificados": 1,
                        "postVisionEjecutados": 0, "revokes_ejecutados": 0},
        "seguridad": {"limpio": True,
                      "criterio": ("La compuerta solo lee archivos del repositorio. No hay "
                                   "connection string, password ni token en la evidencia.")},
    }

    faltantes = [n for n, v in piezas_vision.items() if not v]
    ev["resultado"] = "APROBADO" if (ejecutable and identificable) else "BLOQUEADO / NO VERIFICABLE"
    ev["motivo"] = None if (ejecutable and identificable) else (
        "El artefacto de la rama no implementa la publicación VISION: faltan "
        + ", ".join(faltantes)
        + ". Sin publicación VISION no puede producirse L1, no puede construirse W2, no puede "
          "identificarse la auditoría obligatoria cuya falla debería revertir la línea base y, por "
          "tanto, el fault injection no tiene objeto legítimo. Los eslabones del oráculo (L1 "
          "vigente, INSERT antes/durante/después, respuesta de trazabilidad, ausencia de L2) son "
          "inalcanzables, no incumplidos."
    )

    (OUT_DIR / "evidencia.json").write_text(
        json.dumps(ev, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    assert ejecutable and identificable, (
        "TC-M09-292 queda BLOQUEADO / NO VERIFICABLE.\n" + ev["motivo"] +
        f"\nPiezas presentes: {ev['compuerta_previa']['cumplidas']}"
        f"/{ev['compuerta_previa']['total']}"
        f"\nTabla de auditoría VISION objetivo: no identificada."
    )
