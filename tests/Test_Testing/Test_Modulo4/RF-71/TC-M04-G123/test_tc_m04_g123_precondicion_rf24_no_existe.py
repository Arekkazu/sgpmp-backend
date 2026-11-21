"""
TC-M04-G123 (RF-71 v2.0 RFC-009 precondición de volumen, CU-18) -
"Precondición de auditoría de M09 (RF-24) para la calibración en sitio."
Caso NUEVO introducido por la RFC-009 v1.1.

RELACIÓN CON TC-M04-G102/G122 (hallazgos raíz): `CALIBRACION_EN_SITIO` no
es una entrada reconocida en ningún punto del sistema; el RF-24 real
(`src/configuration/domain/entities/calibracion.py`) es un registro de
ganancia/offset por sensor individual, sin ningún concepto de "tres
auditorías" ni de "ventana de 72 horas de datos limpios".

(a) Endpoint de verificación previa que reporte el estado de las tres
    auditorías y las horas acumuladas -- HALLAZGO: no existe
    `GET .../calibration-readiness` ni ningún equivalente. El único
    endpoint real sobre calibración (`ConsultarCalibracionesUseCase.
    listar_por_sensor`) solo lista registros de calibración de un
    sensor -- no cuenta auditorías ni acumula horas de datos limpios.
(b)-(f) -- NO EVALUABLES: todos dependen de una precondición
    (RF-24-como-auditoría + ventana de 72h) que no existe en ningún
    punto del sistema real. El RF-24 verdadero no tiene ningún concepto
    de "tercera auditoría" del cual pudiera arrancar un conteo de horas,
    ni ningún estado de "completo"/"incompleto" que pudiera consultarse
    ni invalidarse.

Cómo se prueba: grep exhaustivo de términos de precondición de
calibración + inspección directa de `ConsultarCalibracionesUseCase`.

Como correrlo (Windows necesita el stub de fcntl):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:SECRET_KEY = "test"
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m04_g123_precondicion_rf24_no_existe.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M04-G123.html --self-contained-html
"""
from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from src.configuration.application.use_cases.sensores.registrar_calibracion_use_case import (
    ConsultarCalibracionesUseCase,
)

REPO_ROOT = Path(__file__).resolve().parents[5]


class TestNoExisteEndpointDeVerificacionPreviaDeCalibracion:
    @pytest.mark.parametrize('termino', [
        'calibration_readiness', 'tres_auditorias', 'datos_limpios', 'auditorias_completadas',
    ])
    def test_termino_de_precondicion_no_existe_en_ningun_lado(self, termino):
        archivos = [
            str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / 'src').rglob('*.py')
            if termino in p.read_text(encoding='utf-8', errors='ignore')
        ]
        pytest.fail(
            f"HALLAZGO: '{termino}' no existe en ningun archivo de src/ (encontrados: "
            f"{archivos or 'ninguno'})."
        ) if not archivos else None

    def test_consultar_calibraciones_solo_lista_no_cuenta_auditorias_ni_horas(self):
        firma = inspect.signature(ConsultarCalibracionesUseCase.listar_por_sensor)
        parametros = set(firma.parameters)
        pytest.fail(
            f"HALLAZGO (a): el unico caso de uso de consulta real sobre calibracion "
            f"(ConsultarCalibracionesUseCase.listar_por_sensor{tuple(parametros)!r}) solo lista "
            f"registros de un sensor -- no cuenta 'tres auditorias', no acumula horas de datos "
            f"limpios, no calcula ningun estado de 'listo para calibrar en sitio'."
        )
