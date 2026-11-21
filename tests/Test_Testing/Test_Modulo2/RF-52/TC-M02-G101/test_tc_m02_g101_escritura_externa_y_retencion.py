"""
TC-M02-G101 (RF-52, CU13, OWASP API5 / ASVS V8) - Bloqueo de escritura externa a
la bitacora y retencion minima diferenciada.

    TC-M02-175  insercion directa fuera del flujo interno -> rechazada
    TC-M02-176  retencion: 5 anios (TRANSFORMACION_BIOLOGICA/SANITARIO), 2 anios (resto), configurable

Un solo reporte para todo el TC. Los tests afirman lo que pide la ficha; si el
backend no lo cumple, el test queda en rojo como evidencia del defecto.
La insercion directa en BD no es alcanzable desde caja negra, asi que se
combina evidencia en vivo (API de TEST) con evidencia estructural (router,
esquema y migraciones del repo).

Como correrlo (desde la raiz del repo):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m02_g101_escritura_externa_y_retencion.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M02-G101.html --self-contained-html
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bitacora_helpers as h  # noqa: E402


class TestSubcaso175BloqueoDeEscrituraExterna:

    @pytest.mark.parametrize('correo', [h.ADMIN, h.PRODUCTOR, h.CONTADOR], ids=['admin', 'productor', 'contador'])
    def test_ningun_rol_puede_insertar_en_la_bitacora_por_api(self, correo):
        token = h.login(correo)
        cuerpo = {'rf_origen': 'RF42', 'tipo_evento': 'EVENTO_FALSO', 'clasificacion_biologica': 'SANITARIO', 'resultado': 'EXITOSO'}
        for ruta in (h.RUTA_AUDITORIA, f'{h.RUTA_AUDITORIA}/1'):
            r = h.request(token, 'POST', ruta, json=cuerpo)
            assert r.status_code >= 400, f'POST {ruta} como {correo} respondio {r.status_code}: {r.text}'

    def test_el_router_no_expone_rutas_de_escritura_sobre_la_bitacora(self):
        from src.biological_assets.infrastructure.routers.activo_biologico_router import router

        escritura = [
            (sorted(r.methods), r.path) for r in router.routes
            if 'auditoria' in getattr(r, 'path', '') and (r.methods or set()) - {'GET', 'HEAD', 'OPTIONS'}
        ]
        assert escritura == [], f'rutas de escritura sobre la bitacora: {escritura}'

    def test_la_bd_restringe_la_escritura_directa_a_los_componentes_internos(self):
        """No debe poder insertarse en modulo2.bitacora_auditoria_m02 fuera del flujo interno (trigger o REVOKE)."""
        hallazgos = h.hay_bloqueo_de_escritura_en_bd()
        assert hallazgos, (
            'Ninguna migracion ni el esquema base define un trigger o REVOKE sobre modulo2.bitacora_auditoria_m02: '
            'cualquier conexion con permisos de escritura a la tabla puede insertar registros fuera del flujo interno de M02.'
        )


class TestSubcaso176RetencionMinimaDiferenciada:

    def test_los_registros_de_la_bitacora_exponen_la_politica_de_retencion(self):
        token = h.login(h.ADMIN)
        registro = h.get(token, h.RUTA_AUDITORIA, page_size=1).json()['registros'][0]
        assert 'retencion_aplicable' in registro, (
            f'Los registros de RF-52 no llevan ningun campo de retencion (campos: {sorted(registro)}); '
            'RF-63 (IoT) si expone retencion_aplicable.'
        )

    def test_existe_configuracion_de_retencion_por_clasificacion_en_m02(self):
        archivos = h.archivos_de_m02_que_mencionan(r'retenci|retention')
        assert archivos, (
            'Ningun archivo de src/biological_assets define ni configura una politica de retencion '
            '(5 anios TRANSFORMACION_BIOLOGICA/SANITARIO, 2 anios el resto, configurable sin tocar codigo).'
        )
