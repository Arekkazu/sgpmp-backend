"""
TC-M03-G149 (RF-60 CA-15/Fase 9/Salida 7/E1, CU-15) - "Completitud de la
bitácora de auditoría (RF-63)."

Código bajo prueba: búsqueda exhaustiva de `tipo_evento=` en todo
`src/telemetry/`.

HALLAZGO PRINCIPAL: de los 7 tipos de evento que pide la Fase 9/Salida 7
(`HEARTBEAT_RECIBIDO`, `ESTADO_CAMBIADO`, `ALERTA_TECNICA_GENERADA`,
`DISPOSITIVO_RECONECTADO`, `MANTENIMIENTO_INICIADO`,
`MANTENIMIENTO_COMPLETADO`, `INTENTO_NO_AUTORIZADO`), CERO existen tal
cual en el código. El ÚNICO evento de auditoría que RF-60 emite alguna
vez es `'TRANSICION_MANTENIMIENTO_MANUAL'`
(`aplicar_mantenimiento_dispositivo_use_case.py`) -- un nombre distinto,
que además cubre TANTO "iniciar mantenimiento" COMO "completarlo" con el
mismo tipo.

Más grave: `recibir_heartbeat_use_case.py` -- el caso de uso que procesa
CADA heartbeat, cada cambio de estado automático, cada alerta técnica y
cada reconexión -- no recibe ningún `auditoria_repo` en su constructor en
absoluto.

(a) CA-15 -- CONFIRMADO solo para el único evento real
    (`TRANSICION_MANTENIMIENTO_MANUAL`); HALLAZGO para todo lo demás.
(b) catálogo de 6+1 tipos -- HALLAZGO: 0 de 7 existen con esos nombres.
(c) "traza continua sin saltos" -- HALLAZGO: lo opuesto es cierto.
(d) "los campos de diagnóstico no contienen credenciales" -- CONFIRMADO
    trivialmente para el único evento real que existe.

Cómo se prueba: grep exhaustivo + confirmación directa de la ausencia de
`auditoria_repo` en el constructor de `RecibirHeartbeatUseCase` y de
`EvaluarEstadoDispositivosUseCase`.

Como correrlo:
    python -m pytest <ruta>\\test_tc_m03_g149_completitud_bitacora_auditoria.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M03-G149.html --self-contained-html
"""
from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from src.telemetry.application.use_cases.infraestructura.evaluar_estado_dispositivos_use_case import (
    EvaluarEstadoDispositivosUseCase,
)
from src.telemetry.application.use_cases.infraestructura.recibir_heartbeat_use_case import (
    RecibirHeartbeatUseCase,
)

REPO_ROOT = Path(__file__).resolve().parents[5]
_CATALOGO_FASE9 = (
    'HEARTBEAT_RECIBIDO', 'ESTADO_CAMBIADO', 'ALERTA_TECNICA_GENERADA',
    'DISPOSITIVO_RECONECTADO', 'MANTENIMIENTO_INICIADO',
    'MANTENIMIENTO_COMPLETADO', 'INTENTO_NO_AUTORIZADO',
)


class TestSubCasoBCatalogoDeSieteTiposDeEvento:
    @pytest.mark.parametrize('tipo_evento', _CATALOGO_FASE9)
    def test_tipo_de_evento_no_existe_en_el_codigo(self, tipo_evento):
        archivos = [
            str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / 'src' / 'telemetry').rglob('*.py')
            if tipo_evento in p.read_text(encoding='utf-8', errors='ignore')
        ]
        pytest.fail(
            f"HALLAZGO (b): '{tipo_evento}' no existe en ningun archivo de src/telemetry/ "
            f"(encontrados: {archivos or 'ninguno'})."
        ) if not archivos else None

    def test_el_unico_evento_real_de_mantenimiento_no_distingue_iniciado_de_completado(self):
        archivo = REPO_ROOT / 'src/telemetry/application/use_cases/infraestructura/aplicar_mantenimiento_dispositivo_use_case.py'
        texto = archivo.read_text(encoding='utf-8')
        assert "'TRANSICION_MANTENIMIENTO_MANUAL'" in texto
        pytest.fail(
            "HALLAZGO (b): el unico tipo de evento real relacionado con mantenimiento es "
            "'TRANSICION_MANTENIMIENTO_MANUAL' -- se usa igual tanto para pasar A "
            "EN_MANTENIMIENTO como para SALIR de el, sin distinguir MANTENIMIENTO_INICIADO de "
            "MANTENIMIENTO_COMPLETADO como pide el catalogo."
        )


class TestSubCasoARecibirHeartbeatNoAuditaNada:
    def test_recibir_heartbeat_use_case_no_recibe_auditoria_repo(self):
        firma = inspect.signature(RecibirHeartbeatUseCase.__init__)
        nombres_parametros = set(firma.parameters.keys())
        pytest.fail(
            f"HALLAZGO (a)/(c): RecibirHeartbeatUseCase.__init__ no declara ningun parametro de "
            f"auditoria -- parametros reales: {sorted(nombres_parametros)!r}."
        ) if not any('auditoria' in p.lower() for p in nombres_parametros) else None

    def test_evaluar_estado_dispositivos_use_case_tampoco_audita(self):
        firma = inspect.signature(EvaluarEstadoDispositivosUseCase.__init__)
        nombres_parametros = set(firma.parameters.keys())
        pytest.fail(
            f"HALLAZGO (a)/(c): EvaluarEstadoDispositivosUseCase.__init__ tampoco declara "
            f"ningun parametro de auditoria -- parametros reales: {sorted(nombres_parametros)!r}."
        ) if not any('auditoria' in p.lower() for p in nombres_parametros) else None
