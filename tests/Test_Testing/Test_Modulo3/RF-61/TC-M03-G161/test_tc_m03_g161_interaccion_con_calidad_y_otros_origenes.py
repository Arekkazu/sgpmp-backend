"""
TC-M03-G161 (RF-61 v1.2 Dependencias de integración Fase 2/Restricción
3/Entradas, CU-17) - "Interacción con calidad del dato y otros orígenes
(dependencias de integración de Fase 2)." Grupo NUEVO.

Código bajo prueba:
    src/telemetry/application/use_cases/ingesta/ingerir_telemetria_use_case.py
        (clases `IngerirTelemetriaUseCase` y `SincronizarBufferUseCase`)
    src/telemetry/application/use_cases/ingesta/procesar_lectura_confirmada_use_case.py
    src/telemetry/application/use_cases/inferencia/recibir_evento_edge_use_case.py
    src/telemetry/domain/entities/vinculacion_lectura.py
    src/telemetry/infrastructure/workers/postcommit_worker.py
    src/telemetry/infrastructure/repositories/postcommit_repository.py

REEJECUTADO 2026-10-30 CONTRA CÓDIGO POST-MERGE (origin/test, 2026-10-29,
DEV-44 Leandro) -- este TC nunca se había reverificado. HALLAZGO
PRINCIPAL (e) COMPLETAMENTE INVERTIDO por un cambio arquitectónico de
fondo: la vinculación ya NO vive dentro de `IngerirTelemetriaUseCase.execute()`
(esa clase ya ni siquiera recibe un `vincular_use_case` por constructor:
sus únicos parámetros son `db, ingesta_port, dispositivo_port,
bitacora_repo, catalogo_port`). La vinculación se movió a una etapa
genérica del worker post-commit, `EtapaPostcommit.RF61`
(`ProcesarLecturaConfirmadaUseCase.vincular_lectura()`), que se dispara
para CUALQUIER fila de `TelemetriaModel` ya confirmada --
`postcommit_repository.py::_fuente()` resuelve la fuente de la etapa RF61
como `TelemetriaModel, 'id_telemetria'` sin distinguir cómo llegó esa
fila. El propio módulo lo dice explícitamente en su docstring:
"Progreso durable por responsabilidad, INDEPENDIENTE DEL CANAL DE
ENTRADA".

Y la razón por la que esto aplica también a BUFFER_LOCAL: `SincronizarBufferUseCase.execute()`
(Flujo C) no tiene una vía de persistencia propia -- por cada registro del
lote llama literalmente a `self._factory()` (que construye un
`IngerirTelemetriaUseCase` nuevo) y luego `use_case.execute(registro, gateway_id)`,
exactamente la MISMA función que usa la vía de tiempo real. No hay dos
caminos de persistencia: hay uno solo, reutilizado en bucle. Por lo tanto
toda fila de `BUFFER_LOCAL` queda en la misma tabla `TelemetriaModel` que
una fila de tiempo real, y la etapa `RF61` del worker post-commit la
recoge exactamente igual.

(a) RF-62, lectura con calidad insuficiente no debe alimentar M06 aunque
    CONFIRMADA -- HALLAZGO ACTUALIZADO (el mecanismo cambió de lugar, la
    conclusión práctica no): `ProcesarLecturaConfirmadaUseCase.vincular_lectura()`
    no mira `estado_calidad` en absoluto, solo evita duplicar la
    vinculación (`if self.lecturas.vinculacion(identificador) is None`).
    Más aún: `_ESTADOS_PERSISTIDOS = {'LECTURA_VALIDA', 'FUERA_DE_RANGO',
    'ERROR_CALIBRACION'}` en `ingerir_telemetria_use_case.py` confirma que
    incluso una lectura con calidad degradada (`FUERA_DE_RANGO`,
    `ERROR_CALIBRACION`) SÍ se persiste y por lo tanto SÍ se vincula --
    no solo falta el filtro en la vinculación, el propio punto de entrada
    no distingue "válida" de "degradada" para este propósito. Sigue sin
    poder materializarse el escenario completo "M06 recibe una CONFIRMADA
    de mala calidad" porque, como ya confirmó TC-M03-G155, M06 no tiene
    ningún consumidor real.
(b) RF-55, eventos edge vinculados con el mismo mecanismo -- HALLAZGO
    VIGENTE SIN CAMBIOS: `RecibirEventoEdgeUseCase` persiste a través de
    `EventoEdgeRepository` (una tabla distinta a `TelemetriaModel`), por
    lo que la etapa genérica `RF61` del worker nunca se dispara para
    estos eventos -- siguen sin vincularse a ningún activo biológico.
(c) RF-60, periodos de inactividad considerados en la resolución
    retrospectiva -- NO EVALUABLE: no existe ninguna "resolución
    retrospectiva" (Subcomponente B, ya confirmado inexistente en
    TC-M03-G152) a la que los periodos de inactividad de RF-60 pudieran
    aportar contexto.
(d) Cambio de calidad post-vinculación no debe alterar la vinculación
    pero sí el filtrado de M06 -- NO EVALUABLE: mismo motivo que (a), M06
    no filtra nada porque no consume nada.
(e) origen_dato TIEMPO_REAL/BUFFER_LOCAL distinguidos -- HALLAZGO
    INVERTIDO EN LA MITAD QUE IMPORTA: ya no es cierto que BUFFER_LOCAL
    "no se vincula en absoluto" -- SÍ se vincula, por el mismo camino que
    tiempo real (ver arriba). Lo que sigue sin existir es el campo
    `origen_dato` en `VinculacionLectura` -- pero como ambos orígenes
    ahora reciben exactamente el mismo tratamiento, la ausencia de ese
    campo ya no oculta una diferencia de comportamiento real entre ellos
    (antes sí la ocultaba).

Cómo se prueba: inspección directa de las tres rutas de ingesta
(tiempo real, buffer, edge), del worker post-commit y de
`postcommit_repository.py` + inspección de los campos de
`VinculacionLectura`.

Como correrlo (Windows necesita el stub de fcntl):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:SECRET_KEY = "test"
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m03_g161_interaccion_con_calidad_y_otros_origenes.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M03-G161.html --self-contained-html
"""
from __future__ import annotations

import inspect
from dataclasses import fields
from pathlib import Path

import pytest

from src.telemetry.application.use_cases.ingesta.ingerir_telemetria_use_case import (
    IngerirTelemetriaUseCase,
    SincronizarBufferUseCase,
)
from src.telemetry.domain.entities.vinculacion_lectura import VinculacionLectura

REPO_ROOT = Path(__file__).resolve().parents[5]
ARCHIVO_INGESTA = REPO_ROOT / 'src/telemetry/application/use_cases/ingesta/ingerir_telemetria_use_case.py'
ARCHIVO_LECTURA_CONFIRMADA = REPO_ROOT / 'src/telemetry/application/use_cases/ingesta/procesar_lectura_confirmada_use_case.py'
ARCHIVO_WORKER = REPO_ROOT / 'src/telemetry/infrastructure/workers/postcommit_worker.py'
ARCHIVO_POSTCOMMIT_REPO = REPO_ROOT / 'src/telemetry/infrastructure/repositories/postcommit_repository.py'


class TestSubCasoEBufferLocalAhoraSiSeVinculaIgualQueTiempoReal:
    def test_ingerir_telemetria_ya_no_recibe_vincular_use_case_por_constructor(self):
        """La vinculacion ya no vive dentro de IngerirTelemetriaUseCase."""
        firma = inspect.signature(IngerirTelemetriaUseCase.__init__)
        pytest.fail(
            f"HALLAZGO INVERTIDO (cambio de arquitectura): IngerirTelemetriaUseCase.__init__ ya "
            f"NO declara ningun parametro de vinculacion -- parametros reales: "
            f"{sorted(firma.parameters)!r}. La ronda anterior asumia que la vinculacion vivia "
            f"aqui."
        ) if not any('vincul' in p.lower() for p in firma.parameters) else None

    def test_sincronizar_buffer_reutiliza_la_misma_funcion_de_ingesta_que_tiempo_real(self):
        """HALLAZGO (e) INVERTIDO: no hay dos caminos de persistencia -- hay
        uno solo, reutilizado en bucle por el Flujo C."""
        fuente = ARCHIVO_INGESTA.read_text(encoding='utf-8')
        bloque = fuente[fuente.index('class SincronizarBufferUseCase'):]
        pytest.fail(
            "HALLAZGO (e) INVERTIDO: SincronizarBufferUseCase.execute() SI reutiliza "
            "IngerirTelemetriaUseCase (via self._factory()/use_case.execute(registro, "
            "gateway_id)) para cada registro del lote -- BUFFER_LOCAL ya NO es un camino "
            "separado sin vinculacion; es literalmente el mismo camino que TIEMPO_REAL."
        ) if '_factory()' in bloque and 'use_case.execute(' in bloque else None

    def test_la_etapa_rf61_del_worker_postcommit_es_generica_por_tabla_no_por_canal(self):
        """Confirma el mecanismo real que hace posible la inversion de (e):
        la etapa RF61 se resuelve por TelemetriaModel/id_telemetria para
        cualquier fila que no sea heartbeat/vision/auditoria/transicion,
        sin mirar que caso de uso la inserto."""
        texto = ARCHIVO_POSTCOMMIT_REPO.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO INVERTIDO, MECANISMO CONFIRMADO: postcommit_repository.py::_fuente() "
            "resuelve el valor por defecto como (TelemetriaModel, 'id_telemetria', 'LECTURA') "
            "para la etapa RF61 -- independiente del canal de entrada, tal como dice el propio "
            "docstring del modulo ('independiente del canal de entrada')."
        ) if "return TelemetriaModel.__table__, 'id_telemetria', 'LECTURA'" in texto else None

    def test_el_worker_si_invoca_vincular_lectura_como_etapa_rf61(self):
        texto = ARCHIVO_WORKER.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO INVERTIDO: postcommit_worker.py SI mapea EtapaPostcommit.RF61 a "
            "_lectura(db).vincular_lectura(i), construyendo VincularLecturaActivoUseCase con "
            "el adaptador real ActivoBiologicoM02Adapter."
        ) if 'EtapaPostcommit.RF61:' in texto and 'vincular_lectura' in texto else None

    def test_vinculacion_lectura_sigue_sin_tener_campo_origen_dato(self):
        """La mitad del hallazgo (e) que SI sigue vigente: el campo no
        existe -- pero ya no oculta una diferencia real de comportamiento,
        porque ambos origenes se tratan igual (ver tests de arriba)."""
        nombres_campos = {f.name for f in fields(VinculacionLectura)}
        pytest.fail(
            f"HALLAZGO (e) VIGENTE (pero ya no oculta nada): VinculacionLectura declara "
            f"{sorted(nombres_campos)!r} -- sigue sin existir 'origen_dato'."
        ) if 'origen_dato' not in nombres_campos else None


class TestSubCasoBEventosEdgeNuncaSeVinculan:
    def test_recibir_evento_edge_no_invoca_ninguna_vinculacion(self):
        archivo = REPO_ROOT / 'src/telemetry/application/use_cases/inferencia/recibir_evento_edge_use_case.py'
        texto = archivo.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO (b): recibir_evento_edge_use_case.py no menciona 'vinculacion' en ningun "
            "punto -- los eventos generados en el procesamiento edge (RF-55) no quedan "
            "vinculados a ningun activo biologico, ni con el mecanismo de RF-53 ni con ninguno."
        ) if 'vinculacion' not in texto.lower() else None

    def test_recibir_evento_edge_persiste_en_una_tabla_distinta_a_telemetria(self):
        archivo = REPO_ROOT / 'src/telemetry/application/use_cases/inferencia/recibir_evento_edge_use_case.py'
        texto = archivo.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO (b) VIGENTE, RAZON ESTRUCTURAL CONFIRMADA: recibir_evento_edge_use_case.py "
            "persiste via EventoEdgeRepository (no TelemetriaModel) -- por eso la etapa generica "
            "RF61 del worker post-commit nunca se dispara para estos eventos, a diferencia de "
            "BUFFER_LOCAL/TIEMPO_REAL."
        ) if 'EventoEdgeRepository' in texto and 'TelemetriaModel' not in texto else None


class TestSubCasoAyDSinFiltroDeCalidadEnLaVinculacionMismaRazonNuevoLugar:
    def test_vincular_lectura_no_filtra_por_estado_calidad_solo_evita_duplicar(self):
        texto = ARCHIVO_LECTURA_CONFIRMADA.read_text(encoding='utf-8')
        bloque = texto[texto.index('def vincular_lectura'):texto.index('def evaluar_lectura')]
        pytest.fail(
            f"HALLAZGO (a)/(d) ACTUALIZADO (mecanismo nuevo, conclusion similar): "
            f"vincular_lectura() no menciona estado_calidad -- su unico guardia es evitar "
            f"duplicar la vinculacion si ya existe. Bloque real: {bloque.strip()!r}."
        ) if 'estado_calidad' not in bloque else None

    def test_incluso_lecturas_de_calidad_degradada_se_persisten_y_por_tanto_se_vinculan(self):
        fuente = ARCHIVO_INGESTA.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO (a)/(d) ACTUALIZADO: _ESTADOS_PERSISTIDOS incluye 'FUERA_DE_RANGO' y "
            "'ERROR_CALIBRACION' junto a 'LECTURA_VALIDA' -- hasta una lectura de calidad "
            "degradada se persiste (y por tanto se vincula via la etapa RF61 generica); el "
            "filtro de calidad no discrimina en ningun punto de esta cadena."
        ) if "_ESTADOS_PERSISTIDOS = {'LECTURA_VALIDA', 'FUERA_DE_RANGO', 'ERROR_CALIBRACION'}" in fuente else None
