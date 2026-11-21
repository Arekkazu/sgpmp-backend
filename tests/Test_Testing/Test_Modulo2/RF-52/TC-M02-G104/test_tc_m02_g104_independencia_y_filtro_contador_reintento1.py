"""
TC-M02-G104 (RF-52, CU13, CA-5 / CA-6) - REINTENTO 1 (2026-09-26, TEST, tras el merge de origin/test).

El archivo original queda intacto como evidencia historica. Cambios respecto a el:

(TC-M02-264, test 2) La aserción original `db.rollback.assert_not_called()` quedo obsoleta: el buffer RF-52 E1
(`registrar_evento_bitacora` -> `_persistir`) llama `db.rollback()` cuando falla SOLO el intento de escritura de
auditoria, y luego guarda el evento en el buffer. Por el codigo de RegistrarEventoCrecimientoUseCase, el
`db.commit()` de los datos de negocio ocurre ANTES de esa llamada, asi que el rollback no los revierte. Se
reemplaza por la comprobacion real: el orden de llamadas al db es commit() y LUEGO rollback(), y la operacion
devuelve el evento. Buffer aislado por test con tmp_path (el buffer real vive en logs/, relativo al cwd).

(TC-M02-264, test 3, latencia) SIN CAMBIOS y sigue en ROJO: el buffer solo actua ante una excepcion del
repositorio (o alta carga sostenida, E3); una auditoria lenta pero sin excepcion sigue siendo sincrona dentro
de la peticion (1.00 s con una auditoria de 1.0 s). Defecto vigente.

(TC-M02-265, filtro para Contador) SIN CAMBIOS, 4/4 en verde.

Como correrlo (desde la raiz del repo; en Windows, stub de fcntl no versionado):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"; $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\test_tc_m02_g104_independencia_y_filtro_contador_reintento1.py -v         --html=<ruta>\resultados\resultado_TC-M02-G104_reintento1.html --self-contained-html
"""

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bitacora_helpers as h  # noqa: E402

from src.biological_assets.application.use_cases import _registrar_evento_bitacora as buffer_mod  # noqa: E402


class TestTCM02264FalloDeAuditoriaNoBloqueaElFlujoOperativo:

    def test_rf40_en_vivo_se_completa_y_queda_auditado(self):
        token = h.login(h.ADMIN)
        antes = h.total_bitacora(token)
        r = httpx.post(
            f'{h.BASE_URL}/activos-biologicos/{h.ID_ACTIVO_CON_FASE}/eventos/crecimiento',
            json={'tipo_medicion': 'PESO', 'valor_medicion': 1.5, 'unidad_medida': 'kg'},
            headers={'Authorization': f'Bearer {token}'}, timeout=30,
        )
        assert r.status_code == 201, r.text
        assert h.total_bitacora(token) >= antes + 1

    def test_la_operacion_se_completa_aunque_falle_el_repositorio_de_auditoria(self, tmp_path, monkeypatch):
        monkeypatch.setattr(buffer_mod, '_DIR', tmp_path)
        uc, db = h.crecimiento_use_case(h.RepositorioDeAuditoriaIntermitente())   # caido todo el tiempo
        evento, _ = uc.execute(h.ID_ACTIVO_CON_FASE, h.dto_crecimiento(), h.usuario_actual())
        assert evento is not None
        db.commit.assert_called_once()
        db.rollback.assert_called_once()   # solo el intento de auditoria fallido
        orden = [c[0] for c in db.method_calls if c[0] in ('commit', 'rollback')]
        assert orden == ['commit', 'rollback'], f'el commit de negocio debe ocurrir ANTES del rollback de auditoria: {orden}'
        assert (tmp_path / 'audit_buffer_M02.jsonl').exists(), 'el evento no auditado debe quedar en el buffer, no perderse'

    def test_la_latencia_del_repositorio_de_auditoria_no_retrasa_la_operacion(self, tmp_path, monkeypatch):
        monkeypatch.setattr(buffer_mod, '_DIR', tmp_path)
        repo = MagicMock()
        repo.registrar.side_effect = lambda evento: time.sleep(1.0)
        uc, _ = h.crecimiento_use_case(repo)
        inicio = time.perf_counter()
        uc.execute(h.ID_ACTIVO_CON_FASE, h.dto_crecimiento(), h.usuario_actual())
        transcurrido = time.perf_counter() - inicio
        assert transcurrido < 0.5, (
            f'La operacion tardo {transcurrido:.2f}s con una auditoria de 1.0s de latencia: '
            'el registro de auditoria es sincrono dentro de la peticion (sin timeout ni cola asincrona).'
        )


class TestTCM02265BitacoraFiltradaParaContador:

    def _consulta(self):
        token = h.login(h.CONTADOR)
        return h.get(
            token, h.RUTA_AUDITORIA,
            id_activo_biologico=h.ID_ACTIVO_CON_BITACORA_MIXTA,
            clasificacion_biologica='TRANSFORMACION_BIOLOGICA', page_size=100,
        )

    def test_la_consulta_responde_200_con_registros(self):
        r = self._consulta()
        assert r.status_code == 200, r.text
        assert r.json()['registros'], 'se esperaba al menos un evento TRANSFORMACION_BIOLOGICA para el activo de referencia'

    def test_solo_se_retornan_eventos_de_la_clasificacion_pedida(self):
        clasificaciones = {x['clasificacion_biologica'] for x in self._consulta().json()['registros']}
        assert clasificaciones == {'TRANSFORMACION_BIOLOGICA'}

    def test_los_eventos_vienen_en_orden_cronologico(self):
        marcas = [x['timestamp_evento'] for x in self._consulta().json()['registros']]
        assert marcas == sorted(marcas) or marcas == sorted(marcas, reverse=True), marcas

    def test_cada_evento_trae_usuario_y_modulo_responsable(self):
        for x in self._consulta().json()['registros']:
            assert x['id_usuario_responsable'] is not None
            assert x['modulo_consumidor']
