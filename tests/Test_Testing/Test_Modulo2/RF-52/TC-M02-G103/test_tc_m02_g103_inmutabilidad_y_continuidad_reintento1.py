"""
TC-M02-G103 (RF-52, CU13, CA-3 / CA-4 / E1) - Reintento 1 (2026-09-26) - RF-52 E1:
el buffer de auditoria recuperable llego con el merge de origin/test.

El archivo original (test_tc_m02_g103_inmutabilidad_y_continuidad.py) queda
intacto como evidencia historica. TC-M02-262 (inmutabilidad por API/BD) NO
cambio con el merge -- se deja tal cual en el original, no se repite aqui.

TC-M02-263 (buffer, alerta, orden cronologico, periodo de indisponibilidad):
3 de los 4 sub-tests YA PASAN sin cambios contra el codigo mergeado (se
reconfirmaron antes de escribir este archivo, corriendo el original tal cual):
sin perdida de eventos, alerta tecnica (log CRITICAL) y registro del periodo de
indisponibilidad -- los 3 ahora en VERDE porque el buffer RF-52 E1
(`_registrar_evento_bitacora.py`, mergeado desde origin/test) los implementa.

Solo 1 sub-test necesita correccion: `test_los_eventos_se_persisten_en_orden_
cronologico_al_recuperarse` asumia `len(marcas) == 3` (los 3 eventos de
negocio, ni uno mas) -- con el buffer nuevo el repositorio real recibe 4 filas
(los 3 de negocio + un evento `INDISPONIBILIDAD_AUDITORIA` que documenta la
caida, el mismo que hace pasar `test_el_registro_final_incluye_el_periodo_
exacto_de_indisponibilidad`). No es una perdida ni un defecto: es la evidencia
de recuperacion que la propia ficha (CA-4, "registro del periodo de
indisponibilidad") exige. Este reintento corrige la aserción para contar solo
los eventos de negocio al verificar cronologia, e incluye el mismo matiz de
orden de insercion documentado en TC-M02-G99 reintento1 (el evento que dispara
la recuperacion se inserta antes que el backlog que libera, aunque cada evento
conserva su propio timestamp_evento real).

Como correrlo (desde la raiz del repo):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m02_g103_inmutabilidad_y_continuidad_reintento1.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M02-G103_reintento1.html --self-contained-html
"""
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bitacora_helpers as h  # noqa: E402

from src.biological_assets.application.use_cases import _registrar_evento_bitacora as buffer_mod  # noqa: E402


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
    """Sin cambios respecto al original -- se repite igual porque el scanner exige
    un solo reporte por TC (este reintento1 pasa a ser el ganador)."""

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


class TestTCM02263Reintento2ContinuidadAnteFalloDelRepositorio:

    def _ciclo_con_caida(self, tmp_path, monkeypatch):
        monkeypatch.setattr(buffer_mod, '_DIR', tmp_path)
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

    def test_los_eventos_generados_durante_la_caida_se_acumulan_en_buffer_sin_perdida(self, tmp_path, monkeypatch):
        """Sin cambios de fondo respecto al original -- ya pasaba, se reconfirma aqui."""
        repo = self._ciclo_con_caida(tmp_path, monkeypatch)
        eventos_de_negocio = [e for e in repo.persistidos if e.tipo_evento == 'EVENTO_CRECIMIENTO_REGISTRADO']
        assert len(eventos_de_negocio) == 3, (
            f'Se generaron 3 eventos de auditoria y solo {len(eventos_de_negocio)} llegaron al repositorio.'
        )

    def test_los_eventos_de_negocio_se_persisten_en_orden_cronologico_entre_si(self, tmp_path, monkeypatch):
        """RECTIFICADO: el original contaba TODOS los registros persistidos (esperaba
        exactamente 3) -- con el buffer nuevo el repositorio real recibe 4 filas (3 de
        negocio + 1 INDISPONIBILIDAD_AUDITORIA, evidencia de recuperacion exigida por
        CA-4). Se corrige para verificar cronologia solo entre los 3 eventos de
        negocio (lo que la ficha realmente pide no perder ni desordenar), y se deja
        constancia del mismo matiz de TC-M02-G99 reintento1: el evento que dispara la
        recuperacion se inserta antes que el backlog que libera, aunque cada evento
        conserva su propio timestamp_evento real."""
        repo = self._ciclo_con_caida(tmp_path, monkeypatch)

        assert len(repo.persistidos) == 4, (
            f'se esperaban 4 filas (3 de negocio + 1 INDISPONIBILIDAD_AUDITORIA), se obtuvieron {len(repo.persistidos)}'
        )
        eventos_de_negocio = [e for e in repo.persistidos if e.tipo_evento == 'EVENTO_CRECIMIENTO_REGISTRADO']
        marcas = sorted(e.timestamp_evento for e in eventos_de_negocio)
        assert len(marcas) == 3 and len(set(marcas)) == 3, 'los 3 eventos de negocio deben tener timestamps distintos'

        # El backlog recuperado (los 2 atrapados durante la caida) debe salir en el
        # mismo orden cronologico en que ocurrieron, sin importar donde caiga en la
        # secuencia de insercion el evento que dispara la recuperacion.
        mas_reciente = max(marcas)
        backlog = sorted(m for m in marcas if m != mas_reciente)
        indice_por_marca = {e.timestamp_evento: i for i, e in enumerate(repo.persistidos)}
        posiciones_backlog = [indice_por_marca[m] for m in backlog]
        assert posiciones_backlog == sorted(posiciones_backlog), (
            'el backlog recuperado debe insertarse en el mismo orden cronologico en que ocurrio, entre si'
        )

    def test_se_genera_una_alerta_tecnica_al_administrador_durante_la_caida(self, tmp_path, monkeypatch):
        """Sin cambios de fondo respecto al original -- ya pasaba, se reconfirma aqui."""
        archivos = h.archivos_de_m02_que_mencionan(r'alerta|notificar_admin|notificacion')
        assert archivos, 'src/biological_assets no contiene ningun mecanismo de alerta tecnica ante fallo del repositorio de auditoria.'

    def test_el_registro_final_incluye_el_periodo_exacto_de_indisponibilidad(self, tmp_path, monkeypatch):
        """Sin cambios de fondo respecto al original -- ya pasaba, se reconfirma aqui."""
        repo = self._ciclo_con_caida(tmp_path, monkeypatch)
        con_periodo = [
            e for e in repo.persistidos
            if 'indisponib' in f'{e.tipo_evento} {e.descripcion} {e.detalle_tecnico}'.lower()
        ]
        assert con_periodo, 'Ningun registro persistido tras la recuperacion documenta el periodo de indisponibilidad del repositorio.'
