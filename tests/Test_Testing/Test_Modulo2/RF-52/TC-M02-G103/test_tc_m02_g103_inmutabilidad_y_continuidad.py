"""
TC-M02-G103 (RF-52, CU13, CA-3 / CA-4 / E1) - Inmutabilidad de la bitacora y
continuidad ante fallo del repositorio.

    TC-M02-262  la bitacora es append-only (UPDATE/DELETE rechazados y auditados)
    TC-M02-263  fallo del repositorio: buffer sin perdida, alerta tecnica al administrador,
                persistencia en orden cronologico al recuperarse, registro del periodo de indisponibilidad

Un solo reporte para todo el TC. 262 en vivo contra TEST (+ evidencia estructural del esquema);
263 con un repositorio de auditoria falso, porque no se puede tumbar el de TEST desde caja negra.
Los tests afirman lo que pide la ficha; si el backend no lo cumple, quedan en rojo.

Como correrlo (desde la raiz del repo):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m02_g103_inmutabilidad_y_continuidad.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M02-G103.html --self-contained-html
"""
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bitacora_helpers as h  # noqa: E402


def _intentos(id_registro: int):
    return [
        (metodo, ruta)
        for ruta in (h.RUTA_AUDITORIA, f'{h.RUTA_AUDITORIA}/{id_registro}')
        for metodo in ('PUT', 'PATCH', 'DELETE', 'POST')
    ]


def _registro_objetivo(token: str) -> dict:
    registros = h.get(token, h.RUTA_AUDITORIA, id_activo_biologico=h.ID_ACTIVO_CON_HISTORIAL, page_size=50).json()['registros']
    assert registros
    return registros[-1]


class TestTCM02262InmutabilidadDeLaBitacora:

    def test_ningun_intento_de_update_o_delete_por_api_tiene_exito(self):
        token = h.login(h.ADMIN)
        objetivo = _registro_objetivo(token)
        for metodo, ruta in _intentos(objetivo['id_bitacora']):
            r = h.request(token, metodo, ruta, json={'resultado': 'ALTERADO'})
            assert r.status_code >= 400, f'{metodo} {ruta} respondio {r.status_code}'

    def test_el_registro_existente_permanece_intacto_tras_los_intentos(self):
        token = h.login(h.ADMIN)
        antes = _registro_objetivo(token)
        for metodo, ruta in _intentos(antes['id_bitacora']):
            h.request(token, metodo, ruta, json={'resultado': 'ALTERADO'})
        despues = next(
            r for r in h.get(token, h.RUTA_AUDITORIA, id_activo_biologico=h.ID_ACTIVO_CON_HISTORIAL, page_size=50).json()['registros']
            if r['id_bitacora'] == antes['id_bitacora']
        )
        assert despues == antes

    def test_los_intentos_de_alteracion_quedan_registrados_en_la_bitacora(self):
        token = h.login(h.ADMIN)
        intentos = _intentos(_registro_objetivo(token)['id_bitacora'])
        antes = h.total_bitacora(token)
        for metodo, ruta in intentos:
            h.request(token, metodo, ruta, json={'resultado': 'ALTERADO'})
        nuevos = h.total_bitacora(token) - antes
        assert nuevos >= len(intentos), (
            f'{len(intentos)} intentos de alteracion y solo {nuevos} filas nuevas: las respuestas 404/405 del router no dejan rastro.'
        )

    def test_la_bd_bloquea_update_y_delete_sobre_la_tabla_de_bitacora(self):
        assert h.hay_bloqueo_de_escritura_en_bd(), (
            'Sin trigger ni REVOKE sobre modulo2.bitacora_auditoria_m02: la inmutabilidad depende solo de que el router no exponga rutas de escritura.'
        )


class TestTCM02263ContinuidadAnteFalloDelRepositorio:

    def _ciclo_con_caida(self):
        repo = h.RepositorioDeAuditoriaIntermitente()
        uc, _ = h.crecimiento_use_case(repo)
        usuario, dto = h.usuario_actual(), h.dto_crecimiento()
        uc.execute(h.ID_ACTIVO_CON_FASE, dto, usuario)   # evento 1 con el repositorio caido
        time.sleep(0.01)
        uc.execute(h.ID_ACTIVO_CON_FASE, dto, usuario)   # evento 2 con el repositorio caido
        repo.caido = False
        time.sleep(0.01)
        uc.execute(h.ID_ACTIVO_CON_FASE, dto, usuario)   # evento 3, ya recuperado
        return repo

    def test_los_eventos_generados_durante_la_caida_se_acumulan_en_buffer_sin_perdida(self):
        repo = self._ciclo_con_caida()
        eventos_de_negocio = [e for e in repo.persistidos if e.tipo_evento == 'EVENTO_CRECIMIENTO_REGISTRADO']
        assert len(eventos_de_negocio) == 3, (
            f'Se generaron 3 eventos de auditoria y solo {len(eventos_de_negocio)} llegaron al repositorio: '
            'los de la caida se descartan en silencio (except Exception: pass); no hay buffer ni reintento.'
        )

    def test_los_eventos_se_persisten_en_orden_cronologico_al_recuperarse(self):
        repo = self._ciclo_con_caida()
        marcas = [e.timestamp_evento for e in repo.persistidos]
        assert len(marcas) == 3 and marcas == sorted(marcas), f'persistidos: {len(marcas)} de 3'

    def test_se_genera_una_alerta_tecnica_al_administrador_durante_la_caida(self):
        archivos = h.archivos_de_m02_que_mencionan(r'alerta|notificar_admin|notificacion')
        assert archivos, 'src/biological_assets no contiene ningun mecanismo de alerta tecnica ante fallo del repositorio de auditoria.'

    def test_el_registro_final_incluye_el_periodo_exacto_de_indisponibilidad(self):
        repo = self._ciclo_con_caida()
        con_periodo = [
            e for e in repo.persistidos
            if 'indisponib' in f'{e.tipo_evento} {e.descripcion} {e.detalle_tecnico}'.lower()
        ]
        assert con_periodo, 'Ningun registro persistido tras la recuperacion documenta el periodo de indisponibilidad del repositorio.'
