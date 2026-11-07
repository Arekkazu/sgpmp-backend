"""
TC-M09-G128 (RF-23, G128-02) - Ataques a LoRaWAN - reintento1.

Ficha: "Pendiente de decision de alcance LoRaWAN. El chequeo estructural ya
existe en Test_Modulo9/RF-23/TC-M09-G128 (2/2)." Ese chequeo previo (sesion
2026-10-04/05, commit `cfa905d0`, autor del equipo) se perdio del arbol de
trabajo cuando RF-21/22/23 se reestructuro a la numeracion "-02"
(2026-10-06) -- segui existiendo en el historial de git, asi que este
archivo lo RECUPERA y actualiza (nombre de archivo al dia, sin cambios de
fondo en la logica) en vez de reescribirlo desde cero.

Replay de join-request LoRaWAN y unicidad de claves de sesion (devnonce/
appskey/nwkskey) son propiedades de un servidor de red LoRaWAN (join
server). Esta ejecucion NO produce un pass/fail de negocio: re-verifica en
el codigo y DDL actuales que el backend sigue sin ningun soporte LoRaWAN,
para que la decision de alcance del equipo (¿LoRaWAN entra en RF-23?) se
tome con evidencia vigente. El TC sigue en estado Pendiente/Bloqueado hasta
esa decision -- NO es ejecutable como ataque real sin un gateway/servidor
LoRaWAN, que el stack no incluye.

Como correrlo:
    python -m pytest tests/Test_Testing/Test_Modulo9/RF-23/TC-M09-G128/test_tc_m09_g128_sin_soporte_lorawan_reintento1.py -v \
        --html=resultados/resultado_TC-M09-G128_reintento1.html --self-contained-html
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[5]
SCOPES = ["src", "alembic", "anotaciones"]

CODIGO = re.compile(
    r"^\s*(import|from|class|def)\s.*lorawan|^\s*\w*lorawan\w*\s*[=(:]|"
    r"^\s*\w*(devnonce|appskey|nwkskey)\w*\s*[=(:]",
    re.I,
)
DDL = re.compile(r"^\s*(CREATE|ALTER)\s.*(lorawan|devnonce|appskey|nwkskey|join_request)", re.I)


def _archivos_con_lorawan():
    """Solo cuenta codigo y DDL reales; comentarios, docstrings y COMMENT ON no son soporte."""
    hallazgos = []
    for scope in SCOPES:
        base = REPO_ROOT / scope
        if not base.is_dir():
            continue
        for p in base.rglob("*"):
            if not p.is_file() or "__pycache__" in p.parts:
                continue
            if p.suffix == ".py":
                patron = CODIGO
            elif p.suffix == ".sql":
                patron = DDL
            else:
                continue
            for linea in p.read_text(encoding="utf-8", errors="ignore").splitlines():
                if linea.lstrip().startswith("#"):
                    continue
                if patron.search(linea):
                    hallazgos.append(str(p.relative_to(REPO_ROOT)))
                    break
    return hallazgos


def test_no_existe_soporte_lorawan_en_el_backend():
    hallazgos = _archivos_con_lorawan()
    assert hallazgos == [], f"Aparecio codigo/DDL LoRaWAN real, reabrir el TC: {hallazgos}"


def test_el_contrato_de_configuracion_no_acepta_protocolo_lorawan():
    dto = (REPO_ROOT / "src/configuration/infrastructure/dto/configurar_remotamente_dto.py").read_text(
        encoding="utf-8"
    )
    assert "protocolo" not in dto, "Aparecio el campo protocolo, revisar TC-M09-G69 y G128"
