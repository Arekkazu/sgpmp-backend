"""
TC-M04-G122 (RF-71 v2.0 RFC-009 modo_generacion, CU-18) - "Calibración en
sitio de extremo a extremo (modo_generacion = CALIBRACION_EN_SITIO)."
Caso NUEVO introducido por la RFC-009 v1.1; no existía en la ficha
anterior.

RELACIÓN CON TC-M04-G102/G106/G115 (hallazgos raíz): `modo_generacion` no
existe en ningún archivo de `src/` ni en el DDL (G102); el único
procedimiento de precondición real (`sp_iniciar_ciclo_reentrenamiento`)
no reconoce `CALIBRACION_EN_SITIO` como trigger válido -- causaría
`TRIGGER_INVALIDO` (G106/G115).

(a)-(g) -- HALLAZGO ÚNICO, que invalida el caso completo: no existe
    ningún camino por el cual un Administrador o Veterinario pueda
    iniciar un proceso con `modo_generacion = CALIBRACION_EN_SITIO`,
    porque ese campo nunca se declaró en ningún DTO, ninguna entidad ni
    ningún endpoint. No hay "fases aplicables a este modo" que recorrer,
    ni "conjunto de métricas que difiera del de reentrenamiento" que
    comparar, porque no hay ningún código que distinga el origen de una
    versión como `CALIBRACION_EN_SITIO` frente a `REENTRENAMIENTO` --
    ambos conceptos son, para el sistema real, indistinguibles porque
    ninguno de los dos existe como campo almacenado (ver TC-M04-G112(a)).
    Este es el mismo bloqueo que la propia ficha anticipa ("el flujo de
    la calibración en sitio no está descrito en el cuerpo de la ficha
    v2.0"), confirmado ahora contra el código real en lugar de contra el
    documento del RF.

Cómo se prueba: confirmación de que ningún DTO, entidad ni endpoint de
M04 declara `modo_generacion`, y de que el procedimiento de precondición
real rechaza `CALIBRACION_EN_SITIO` como trigger.

Como correrlo (Windows necesita el stub de fcntl):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:SECRET_KEY = "test"
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m04_g122_calibracion_en_sitio_e2e_no_existe.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M04-G122.html --self-contained-html
"""
from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from src.prediction.domain.entities.version_modelo import VersionModelo
from src.prediction.infrastructure.dto.registrar_version_modelo_dto import RegistrarVersionModeloDTO

REPO_ROOT = Path(__file__).resolve().parents[5]


class TestCalibracionEnSitioNoExisteComoConceptoAlcanzable:
    def test_ningun_dto_de_m04_declara_modo_generacion(self):
        firma = inspect.signature(RegistrarVersionModeloDTO.__init__)
        parametros = set(firma.parameters)
        pytest.fail(
            f"HALLAZGO: RegistrarVersionModeloDTO no declara 'modo_generacion' -- parametros "
            f"reales: {sorted(parametros)!r}. No hay ningun campo por el cual declarar que una "
            f"version proviene de CALIBRACION_EN_SITIO."
        ) if 'modo_generacion' not in parametros else None

    def test_version_modelo_no_distingue_origen_calibracion_de_reentrenamiento(self):
        from dataclasses import fields
        nombres_campos = {f.name for f in fields(VersionModelo)}
        assert 'modo_generacion' not in nombres_campos

    def test_el_procedimiento_de_precondicion_rechaza_calibracion_en_sitio_como_trigger(self):
        texto_ddl = (REPO_ROOT / 'alembic/baseline/esquema_baseline.sql').read_text(
            encoding='utf-8', errors='ignore')
        bloque = texto_ddl[texto_ddl.index('CREATE PROCEDURE modulo4.sp_iniciar_ciclo_reentrenamiento'):]
        bloque = bloque[:bloque.index('ALTER PROCEDURE modulo4.sp_iniciar_ciclo_reentrenamiento')]
        pytest.fail(
            "HALLAZGO: sp_iniciar_ciclo_reentrenamiento solo reconoce PROGRAMADO/MANUAL/"
            "DEGRADACION -- CALIBRACION_EN_SITIO cae en el ELSE y lanza TRIGGER_INVALIDO. No "
            "existe ningun camino, ni siquiera dormido en SQL, para iniciar una calibracion en "
            "sitio."
        ) if "WHEN 'CALIBRACION_EN_SITIO'" not in bloque else None
