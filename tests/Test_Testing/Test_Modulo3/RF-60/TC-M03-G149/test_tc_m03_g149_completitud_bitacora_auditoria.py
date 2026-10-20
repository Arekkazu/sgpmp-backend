"""
TC-M03-G149 (RF-60 CA-15/Fase 9/Salida 7/E1, CU-15) - "Completitud de la
bitácora de auditoría (RF-63)." Grupo NUEVO (sin TC previo).

Código bajo prueba: búsqueda exhaustiva de `tipo_evento=` en todo
`src/telemetry/`.

HALLAZGO PRINCIPAL (invalida (b) por completo): de los 7 tipos de evento
que pide la Fase 9/Salida 7 (`HEARTBEAT_RECIBIDO`, `ESTADO_CAMBIADO`,
`ALERTA_TECNICA_GENERADA`, `DISPOSITIVO_RECONECTADO`,
`MANTENIMIENTO_INICIADO`, `MANTENIMIENTO_COMPLETADO`,
`INTENTO_NO_AUTORIZADO`), **CERO existen tal cual en el código** (grep
exhaustivo, 0 coincidencias para cada uno de los 7 nombres literales). El
ÚNICO evento de auditoría que RF-60 emite alguna vez es
`'TRANSICION_MANTENIMIENTO_MANUAL'` (`aplicar_mantenimiento_dispositivo_use_case.py`,
confirmado también en TC-M03-G144) -- un nombre distinto, que además cubre
TANTO "iniciar mantenimiento" COMO "completarlo" con el mismo tipo (no hay
`MANTENIMIENTO_INICIADO` separado de `MANTENIMIENTO_COMPLETADO`).

Más grave: `recibir_heartbeat_use_case.py` -- el caso de uso que procesa
CADA heartbeat, cada cambio de estado automático, cada alerta técnica y
cada reconexión -- **no recibe ningún `auditoria_repo` en su constructor en
absoluto** (a diferencia de `AplicarMantenimientoDispositivoUseCase`, que sí
tiene uno opcional). Es decir: no es que falten 4 de los 7 tipos de evento
por un detalle de nombres -- es que NINGÚN heartbeat, cambio de estado
automático, alerta técnica o reconexión queda auditado en RF-63, nunca, por
ningún nombre. Esto también reconfirma, desde un ángulo más amplio, el
hallazgo ya documentado en TC-M03-272(b)/TC-M03-G135 para
`INTENTO_NO_AUTORIZADO` (OWASP A09): es un caso particular de un vacío
mucho más grande -- toda la vía de heartbeat carece de auditoría.

(a) CA-15 "cada evento de RF-60 queda registrado con timestamp, device_id,
    tipo de evento, estado anterior y nuevo, causa_primaria y usuario
    responsable" -- CONFIRMADO solo para el único evento real
    (`TRANSICION_MANTENIMIENTO_MANUAL`, vía `aplicar_mantenimiento_...`);
    HALLAZGO para todo lo demás (heartbeats, transiciones automáticas,
    alertas, reconexiones): no se audita en absoluto.
(b) catálogo de 6+1 tipos -- HALLAZGO: 0 de 7 existen con esos nombres; 1
    de 7 (MANTENIMIENTO) existe con un nombre distinto y sin dividir en
    INICIADO/COMPLETADO.
(c) "traza continua sin saltos" -- HALLAZGO: lo opuesto es cierto -- un
    ciclo completo ACTIVO->SIN_SEÑAL->INACTIVO->EN_MANTENIMIENTO->ACTIVO
    tendría, como MUCHO, una sola entrada de auditoría (la transición
    manual a/desde EN_MANTENIMIENTO) de las 4 transiciones del ciclo; las
    3 automáticas (ACTIVO->SIN_SEÑAL->INACTIVO, y el regreso final a
    ACTIVO vía heartbeat) no dejan ninguna fila en RF-63.
(d) "los campos de diagnóstico no contienen credenciales ni access_key" --
    CONFIRMADO trivialmente para el único evento real que existe (su
    `accion_detallada` solo trae id_dispositivo_iot/estados/motivo, nunca
    credenciales) -- no hay nada más que revisar porque no hay más eventos.

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
    """(b): de los 7 tipos de la Fase 9/Salida 7, confirmar cuantos existen."""

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
    """(a)/(c): confirma que la via de heartbeat (la que cubre 3 de las 4
    transiciones del ciclo de ejemplo de (c)) no tiene NINGUN repositorio
    de auditoria RF-63 en su constructor."""

    def test_recibir_heartbeat_use_case_no_recibe_auditoria_repo(self):
        firma = inspect.signature(RecibirHeartbeatUseCase.__init__)
        nombres_parametros = set(firma.parameters.keys())
        pytest.fail(
            f"HALLAZGO (a)/(c): RecibirHeartbeatUseCase.__init__ no declara ningun parametro de "
            f"auditoria -- parametros reales: {sorted(nombres_parametros)!r}. A diferencia de "
            f"AplicarMantenimientoDispositivoUseCase (que si tiene un auditoria_repo opcional, ver "
            f"TC-M03-G144), esta via no tiene ningun punto de conexion con RF-63 en absoluto -- ni "
            f"heartbeats, ni cambios de estado automaticos, ni alertas, ni reconexiones quedan "
            f"auditados."
        ) if not any('auditoria' in p.lower() for p in nombres_parametros) else None

    def test_evaluar_estado_dispositivos_use_case_tampoco_audita(self):
        firma = inspect.signature(EvaluarEstadoDispositivosUseCase.__init__)
        nombres_parametros = set(firma.parameters.keys())
        pytest.fail(
            f"HALLAZGO (a)/(c): EvaluarEstadoDispositivosUseCase.__init__ (el job periodico que "
            f"detecta SIN_SEÑAL/INACTIVO) tampoco declara ningun parametro de auditoria RF-63 -- "
            f"parametros reales: {sorted(nombres_parametros)!r}. Ninguna transicion automatica de "
            f"estado queda registrada en la bitacora de auditoria."
        ) if not any('auditoria' in p.lower() for p in nombres_parametros) else None
