"""
TC-M03-G161 (RF-61 v1.2 Dependencias de integración Fase 2/Restricción
3/Entradas, CU-17) - "Interacción con calidad del dato y otros orígenes
(dependencias de integración de Fase 2)." Grupo NUEVO.

Código bajo prueba:
    src/telemetry/application/use_cases/ingesta/ingerir_telemetria_use_case.py
        (clases `IngerirTelemetriaUseCase` y `SincronizarBufferUseCase`)
    src/telemetry/application/use_cases/inferencia/recibir_evento_edge_use_case.py
    src/telemetry/domain/entities/vinculacion_lectura.py

HALLAZGO PRINCIPAL (e), el más grave del grupo: `SincronizarBufferUseCase`
(la vía que procesa datos de `BUFFER_LOCAL`, RF-53 Flujo C / RF-54) NUNCA
invoca `vincular_use_case` -- ninguna lectura sincronizada desde buffer
queda jamás vinculada a ningún activo biológico. Solo
`IngerirTelemetriaUseCase.execute()` (la vía de tiempo real) llama a
`self.vincular_use_case.execute(...)`, inmediatamente después de
persistir la telemetría, sin condicionarlo a `estado_calidad`. Esto no es
"TIEMPO_REAL y BUFFER_LOCAL se distinguen correctamente" (e) -- es que
BUFFER_LOCAL no se vincula EN ABSOLUTO, mientras que TIEMPO_REAL sí. Y
ninguno de los dos casos puede distinguirse después, porque
`VinculacionLectura` no tiene ningún campo `origen_dato`.

HALLAZGO (b): `RecibirEventoEdgeUseCase` (RF-55) tampoco invoca nunca
`vincular_use_case` ni ningún repositorio de vinculación -- los eventos
generados en el procesamiento edge no quedan vinculados a ningún activo
biológico, ni con el mismo mecanismo que RF-53 ni con ninguno.

(a) RF-62, lectura con calidad insuficiente no debe alimentar M06 aunque
    CONFIRMADA -- NO EVALUABLE / HALLAZGO COMPUESTO: `IngerirTelemetriaUseCase`
    invoca la vinculación sin mirar `estado_calidad` en absoluto (no hay
    ningún filtro combinado); y, como ya confirmó TC-M03-G155, M06 no
    tiene ningún consumidor real que pudiera aplicar ese filtro de
    todos modos -- el escenario que (a) pide probar no tiene en qué
    materializarse en ninguno de los dos extremos de la cadena.
(b) RF-55, eventos edge vinculados con el mismo mecanismo -- HALLAZGO:
    ver arriba -- no se vinculan en absoluto.
(c) RF-60, periodos de inactividad considerados en la resolución
    retrospectiva -- NO EVALUABLE: no existe ninguna "resolución
    retrospectiva" (Subcomponente B, ya confirmado inexistente en
    TC-M03-G152) a la que los periodos de inactividad de RF-60 pudieran
    aportar contexto.
(d) Cambio de calidad post-vinculación no debe alterar la vinculación
    pero sí el filtrado de M06 -- NO EVALUABLE: mismo motivo que (a), M06
    no filtra nada porque no consume nada.
(e) origen_dato TIEMPO_REAL/BUFFER_LOCAL distinguidos -- HALLAZGO: ver
    arriba -- no hay distinción porque BUFFER_LOCAL simplemente no se
    vincula, y el campo que debería registrar el origen no existe.

Cómo se prueba: inspección directa de las tres rutas de ingesta
(tiempo real, buffer, edge) + inspección de los campos de
`VinculacionLectura`.

Como correrlo (Windows necesita el stub de fcntl):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:SECRET_KEY = "test"
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m03_g161_interaccion_con_calidad_y_otros_origenes.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M03-G161.html --self-contained-html
"""
from __future__ import annotations

from dataclasses import fields
from pathlib import Path

import pytest

from src.telemetry.domain.entities.vinculacion_lectura import VinculacionLectura

REPO_ROOT = Path(__file__).resolve().parents[5]
ARCHIVO_INGESTA = REPO_ROOT / 'src/telemetry/application/use_cases/ingesta/ingerir_telemetria_use_case.py'


def _bloque_clase(nombre_clase: str, siguiente_clase: str | None) -> str:
    texto = ARCHIVO_INGESTA.read_text(encoding='utf-8')
    inicio = texto.index(f'class {nombre_clase}')
    fin = texto.index(f'class {siguiente_clase}', inicio) if siguiente_clase else len(texto)
    return texto[inicio:fin]


class TestSubCasoEBufferLocalNuncaSeVinculaTiempoRealSi:
    def test_ingerir_telemetria_tiempo_real_si_invoca_vinculacion(self):
        bloque = _bloque_clase('IngerirTelemetriaUseCase', 'SincronizarBufferUseCase')
        assert 'self.vincular_use_case.execute(' in bloque

    def test_sincronizar_buffer_nunca_invoca_vinculacion(self):
        bloque = _bloque_clase('SincronizarBufferUseCase', None)
        pytest.fail(
            "HALLAZGO (e): SincronizarBufferUseCase (la via de BUFFER_LOCAL) no invoca "
            "vincular_use_case en ningun punto -- las lecturas sincronizadas desde buffer nunca "
            "quedan vinculadas a ningun activo biologico, a diferencia de la via de tiempo real."
        ) if 'vincular' not in bloque.lower() else None

    def test_vinculacion_lectura_no_tiene_campo_origen_dato(self):
        nombres_campos = {f.name for f in fields(VinculacionLectura)}
        pytest.fail(
            f"HALLAZGO (e): VinculacionLectura declara {sorted(nombres_campos)!r} -- ningun "
            f"campo 'origen_dato'. Aunque existiera la distincion de comportamiento (que no "
            f"existe, ver arriba), no habria donde registrarla."
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


class TestSubCasoAyDSinFiltroCombinadoDeCalidadYVinculacion:
    def test_la_vinculacion_en_tiempo_real_no_depende_del_estado_de_calidad(self):
        bloque = _bloque_clase('IngerirTelemetriaUseCase', 'SincronizarBufferUseCase')
        # Busca especificamente un 'if' que condicione la llamada a vincular_use_case
        # usando estado_calidad -- no basta con que la palabra aparezca cerca (p. ej.
        # el parametro de bitacora_repo.registrar_exito aparece justo antes, sin
        # relacion con si se vincula o no).
        bloque_antes_de_vincular = bloque.split('self.vincular_use_case.execute(')[0]
        ultimo_if = bloque_antes_de_vincular.rfind('if ')
        condicion_del_ultimo_if = bloque_antes_de_vincular[ultimo_if:ultimo_if + 120] if ultimo_if != -1 else ''
        pytest.fail(
            f"HALLAZGO (a)/(d): la condicion 'if' mas cercana antes de "
            f"vincular_use_case.execute() es {condicion_del_ultimo_if!r} -- no menciona "
            f"estado_calidad. La vinculacion se ejecuta siempre tras persistir la telemetria, "
            f"sin ningun filtro de calidad. Como M06 tampoco consume nada (TC-M03-G155), el "
            f"escenario de 'calidad insuficiente pero CONFIRMADA' no tiene ningun punto real "
            f"donde materializarse."
        ) if 'estado_calidad' not in condicion_del_ultimo_if else None
