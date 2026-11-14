"""
TC-M02-G106 (RF-52, CU13, CA-9 / CA-11 / Restriccion 6) - Correlacion con RF-63,
verificacion de hash_integridad y bloqueo de escritura directa en la bitacora.

    TC-M02-267  id_evento_correlacionado enlaza el registro de RF-52 con el de RF-63 (y viceversa)
    TC-M02-268  el hash recalculado coincide con el almacenado
    TC-M02-269  insercion directa en la bitacora fuera del flujo interno -> rechazada

Un solo reporte para todo el TC, en vivo contra TEST (+ evidencia estructural del repo).
Los tests afirman lo que pide la ficha; si el backend no lo cumple, quedan en rojo.

Como correrlo (desde la raiz del repo):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m02_g106_correlacion_hash_y_escritura.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M02-G106.html --self-contained-html
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bitacora_helpers as h  # noqa: E402


class TestTCM02267CorrelacionConRF63:

    def test_los_eventos_de_asociacion_iot_de_rf52_apuntan_a_su_registro_en_rf63(self):
        token = h.login(h.ADMIN)
        filas = h.get(token, h.RUTA_AUDITORIA, tipo_evento='ASOCIACION_IOT_CREADA', page_size=50).json()['registros']
        assert filas, 'se esperaban registros ASOCIACION_IOT_CREADA generados por RF-49'
        sin_correlacion = [f['id_bitacora'] for f in filas if not f['id_evento_correlacionado']]
        assert not sin_correlacion, (
            f'{len(sin_correlacion)} de {len(filas)} registros ASOCIACION_IOT_CREADA tienen id_evento_correlacionado nulo: '
            'ningun caso de uso de biological_assets asigna ese campo (RF-49 solo escribe en la bitacora de M02).'
        )

    def test_los_registros_de_rf63_exponen_la_correlacion_de_vuelta_hacia_rf52(self):
        token = h.login(h.ADMIN)
        items = h.get(token, '/iot/auditoria', page_size=5).json()['items']
        assert items
        campos = set().union(*(i.keys() for i in items))
        assert any('correl' in c for c in campos), f'RF-63 no expone ningun campo de correlacion (campos: {sorted(campos)})'


class TestTCM02268HashDeIntegridad:

    def test_el_hash_recalculado_coincide_con_el_almacenado_en_300_registros(self):
        token = h.login(h.ADMIN)
        distintos = []
        for pagina in (1, 2, 3):
            for r in h.get(token, h.RUTA_AUDITORIA, page_size=100, pagina=pagina).json()['registros']:
                if h.recalcular_hash(r) != r['hash_integridad']:
                    distintos.append(r['id_bitacora'])
        assert distintos == [], f'registros con hash distinto: {distintos[:10]}'

    def test_alterar_el_contenido_de_un_registro_invalida_su_hash(self):
        token = h.login(h.ADMIN)
        registro = h.get(token, h.RUTA_AUDITORIA, page_size=1).json()['registros'][0]
        assert h.recalcular_hash(registro) == registro['hash_integridad']
        alterado = {**registro, 'resultado': 'ALTERADO'}
        assert h.recalcular_hash(alterado) != registro['hash_integridad']


class TestTCM02269BloqueoDeEscrituraDirecta:

    @pytest.mark.parametrize('correo', [h.ADMIN, h.PRODUCTOR, h.CONTADOR], ids=['admin', 'productor', 'contador'])
    def test_ningun_rol_puede_insertar_en_la_bitacora_por_api(self, correo):
        token = h.login(correo)
        r = h.request(token, 'POST', h.RUTA_AUDITORIA, json={'rf_origen': 'RF42', 'tipo_evento': 'EVENTO_FALSO', 'resultado': 'EXITOSO'})
        assert r.status_code >= 400, f'POST como {correo} respondio {r.status_code}'

    def test_la_bd_restringe_la_escritura_directa_a_los_componentes_internos(self):
        assert h.hay_bloqueo_de_escritura_en_bd(), (
            'Sin trigger ni REVOKE sobre modulo2.bitacora_auditoria_m02: una conexion con permisos de escritura '
            'puede insertar registros fuera del flujo interno de M02.'
        )
