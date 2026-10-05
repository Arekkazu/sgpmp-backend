"""
TC-M09-G128 (RF-23, TC-M09-254/255) - Reintento 2 (2026-10-04).

Ambos casos (replay de join-request LoRaWAN, unicidad de claves de sesion) son
propiedades de un servidor de red LoRaWAN. Este reintento NO produce un pass
ni un fail del sistema: re-verifica en el codigo actual que el backend sigue sin
ningun soporte LoRaWAN, para que la decision de alcance del equipo se tome con
evidencia vigente. El TC sigue en estado Pendiente hasta que el equipo confirme
si LoRaWAN entra en RF-23.
"""
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]
SCOPES = ['src', 'alembic', 'anotaciones']


CODIGO = re.compile(r"^\s*(import|from|class|def)\s.*lorawan|^\s*\w*lorawan\w*\s*[=(:]|^\s*\w*(devnonce|appskey|nwkskey)\w*\s*[=(:]", re.I)
DDL = re.compile(r"^\s*(CREATE|ALTER)\s.*(lorawan|devnonce|appskey|nwkskey|join_request)", re.I)


def _archivos_con_lorawan():
    """Solo cuenta codigo y DDL reales; comentarios, docstrings y COMMENT ON no son soporte."""
    hallazgos = []
    for scope in SCOPES:
        for p in (REPO_ROOT / scope).rglob('*'):
            if not p.is_file() or '__pycache__' in p.parts:
                continue
            if p.suffix == '.py':
                patron = CODIGO
            elif p.suffix == '.sql':
                patron = DDL
            else:
                continue
            for linea in p.read_text(encoding='utf-8', errors='ignore').splitlines():
                if linea.lstrip().startswith('#'):
                    continue
                if patron.search(linea):
                    hallazgos.append(str(p.relative_to(REPO_ROOT)))
                    break
    return hallazgos


def test_no_existe_soporte_lorawan_en_el_backend():
    hallazgos = _archivos_con_lorawan()
    # Los unicos archivos esperados son documentacion que MENCIONA LoRaWAN como ausente.
    assert hallazgos == [], f'aparecio codigo/DDL LoRaWAN real, reabrir el TC: {hallazgos}'


def test_el_contrato_de_configuracion_no_acepta_protocolo_lorawan():
    dto = (REPO_ROOT / 'src/configuration/infrastructure/dto/configurar_remotamente_dto.py').read_text(encoding='utf-8')
    assert 'protocolo' not in dto, 'aparecio el campo protocolo, revisar TC-M09-G69 y G128'
