"""
TC-M02-G101 (RF-52, CU13, OWASP API5 / ASVS V8) - REINTENTO 1 (2026-09-26, TEST, tras el merge de origin/test).

    TC-M02-175  insercion directa fuera del flujo interno -> rechazada
    TC-M02-176  retencion: 5 anios (TRANSFORMACION_BIOLOGICA/SANITARIO), 2 anios (resto), configurable

El archivo original queda intacto como evidencia historica.

CAMBIO POR EL MERGE: RF-52 E5 agrego `POST /activos-biologicos/auditoria/registros-correctivos`
(registrar_correctivo_auditoria). El test original "el router no expone rutas de escritura" fallaba ahora
por esa ruta, pero NO es una escritura externa arbitraria: verificado en vivo contra TEST (2026-09-26)
  * solo Administrador la puede usar (Productor y Contador -> 403 ACCESO_DENEGADO);
  * el cuerpo solo admite {tabla, id_registro, motivo}: no se puede forjar rf_origen/tipo_evento/clasificacion
    (un cuerpo de evento falso -> 400 VAL_ENTRADA);
  * un id_registro inexistente en el historial RF-46 -> 404 REGISTRO_RF46_NO_ENCONTRADO.
Este reintento reemplaza la aserción "ninguna ruta de escritura" por "la unica ruta de escritura es esa, protegida
y sin contenido libre". Los sub-casos que siguen fallando (BD sin trigger/REVOKE; sin retencion 5/2 anios) NO
cambiaron: el merge no los toco (verificado por grep en src/ y alembic/).

Como correrlo (desde la raiz del repo; en Windows, stub de fcntl no versionado):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"; $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m02_g101_escritura_externa_y_retencion_reintento1.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M02-G101_reintento1.html --self-contained-html
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bitacora_helpers as h  # noqa: E402

RUTA_CORRECTIVO = f'{h.RUTA_AUDITORIA}/registros-correctivos'


class TestSubcaso175BloqueoDeEscrituraExterna:

    @pytest.mark.parametrize('correo', [h.ADMIN, h.PRODUCTOR, h.CONTADOR], ids=['admin', 'productor', 'contador'])
    def test_ningun_rol_puede_insertar_en_la_bitacora_por_api(self, correo):
        token = h.login(correo)
        cuerpo = {'rf_origen': 'RF42', 'tipo_evento': 'EVENTO_FALSO', 'clasificacion_biologica': 'SANITARIO', 'resultado': 'EXITOSO'}
        for ruta in (h.RUTA_AUDITORIA, f'{h.RUTA_AUDITORIA}/1'):
            r = h.request(token, 'POST', ruta, json=cuerpo)
            assert r.status_code >= 400, f'POST {ruta} como {correo} respondio {r.status_code}: {r.text}'

    def test_la_unica_ruta_de_escritura_es_el_correctivo_e5(self):
        from src.biological_assets.infrastructure.routers.activo_biologico_router import router

        escritura = [
            (sorted(r.methods), r.path) for r in router.routes
            if 'auditoria' in getattr(r, 'path', '') and (r.methods or set()) - {'GET', 'HEAD', 'OPTIONS'}
        ]
        assert escritura == [(['POST'], RUTA_CORRECTIVO)], f'rutas de escritura sobre la bitacora: {escritura}'

    @pytest.mark.parametrize('correo', [h.PRODUCTOR, h.CONTADOR], ids=['productor', 'contador'])
    def test_el_correctivo_e5_esta_prohibido_para_roles_no_administradores(self, correo):
        token = h.login(correo)
        r = h.request(token, 'POST', RUTA_CORRECTIVO, json={'tabla': 'eventos_activos', 'id_registro': 1, 'motivo': 'QA'})
        assert r.status_code == 403, f'{correo}: {r.status_code} {r.text}'

    def test_el_correctivo_e5_no_permite_forjar_contenido_de_eventos(self):
        token = h.login(h.ADMIN)
        cuerpo = {'rf_origen': 'RF42', 'tipo_evento': 'EVENTO_FALSO', 'clasificacion_biologica': 'SANITARIO', 'resultado': 'EXITOSO'}
        r = h.request(token, 'POST', RUTA_CORRECTIVO, json=cuerpo)
        assert r.status_code == 400, f'{r.status_code} {r.text}'
        assert {f['field'] for f in r.json()['fields']} == {'tabla', 'id_registro', 'motivo'}

    def test_el_correctivo_e5_rechaza_un_registro_inexistente_en_el_historial_rf46(self):
        token = h.login(h.ADMIN)
        total_antes = h.total_bitacora(token)
        r = h.request(token, 'POST', RUTA_CORRECTIVO, json={'tabla': 'eventos_activos', 'id_registro': 999999999, 'motivo': 'QA'})
        assert r.status_code == 404 and r.json()['error_code'] == 'REGISTRO_RF46_NO_ENCONTRADO', r.text
        assert h.total_bitacora(token) == total_antes, 'un correctivo rechazado no debe crear filas en la bitacora'

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
