"""
TC-M02-G104 (RF-52, CU13, CA-5 / CA-6) - Independencia de RF-52 frente a fallos y
consulta de bitacora filtrada por rol Contador.

    TC-M02-264  un fallo/latencia de RF-52 no bloquea el flujo de otros RF (ej. RF-40 registrar crecimiento)
    TC-M02-265  filtro clasificacion_biologica=TRANSFORMACION_BIOLOGICA para el Contador: solo esa
                clasificacion, en orden cronologico, con usuario/modulo responsable de cada evento

Un solo reporte para todo el TC. 265 y la linea base de 264 en vivo contra TEST; la falla/latencia de
auditoria de 264 con un repositorio falso (no se puede degradar el de TEST desde caja negra).
Los tests afirman lo que pide la ficha; si el backend no lo cumple, quedan en rojo.

Como correrlo (desde la raiz del repo):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m02_g104_independencia_y_filtro_contador.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M02-G104.html --self-contained-html
"""
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bitacora_helpers as h  # noqa: E402


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

    def test_la_operacion_se_completa_aunque_falle_el_repositorio_de_auditoria(self):
        uc, db = h.crecimiento_use_case(h.RepositorioDeAuditoriaIntermitente())   # caido todo el tiempo
        evento, _ = uc.execute(h.ID_ACTIVO_CON_FASE, h.dto_crecimiento(), h.usuario_actual())
        assert evento is not None
        db.commit.assert_called()
        db.rollback.assert_not_called()

    def test_la_latencia_del_repositorio_de_auditoria_no_retrasa_la_operacion(self):
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
