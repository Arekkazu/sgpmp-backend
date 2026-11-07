"""
TC-M02-G70 (RF-45, CU09) - Rechazo de baja sin datos obligatorios, control de
acceso por rol (OWASP API5) y verificacion de rollback ante fallo
transaccional.

Sub-casos:
    TC-M02-254  tipo_baja / motivo_baja obligatorios -> 400
    TC-M02-255  funcion de baja restringida por rol  -> 403
    TC-M02-256  rollback ante fallo transaccional en la baja

Un solo archivo y un solo reporte para todo el TC (regla del scanner: un TC
agrupado = un reporte con todos sus sub-casos). Los sub-casos 254 y 255 se
ejecutan EN VIVO contra TEST (httpx); el 256 usa dobles de prueba porque no
hay forma de forzar un fallo transaccional desde un cliente HTTP de caja
negra (mismo criterio de TC-M02-G65). La coleccion Postman
tc_m02_g70.postman_collection.json cubre los sub-casos 254/255 de forma
independiente; su salida va en evidencias/ para no competir con este reporte.

Discrepancias ficha vs implementacion (no son bugs, ya vistas en TC-M02-G62,
G65 y G68):
  * 254: la ficha cita "El tipo de baja y la justificacion son campos
    obligatorios"; el backend responde 400 VAL_ENTRADA con un mensaje por
    campo ("Este campo es obligatorio.").
  * 255: la ficha cita "Solo el Productor, el Veterinario o el
    Administrador..."; el router usa require_permission sin
    mensaje_denegado, asi que el mensaje es el generico de ACCESO_DENEGADO.
  * 256: la ficha cita "Fallo critico de integridad..."; el fallo cae al
    handler global y responde 500 ERROR_INTERNO con el mensaje generico.

Como correrlo (desde la raiz del repo):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m02_g70_baja_validacion_rbac_rollback.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M02-G70.html --self-contained-html
"""
import os
from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.biological_assets.application.use_cases.gestion.registrar_evento_baja_use_case import (
    RegistrarEventoBajaUseCase,
)
from src.biological_assets.domain.entities.activo_biologico import ActivoBiologico, DetallePoblacional
from src.biological_assets.infrastructure.dto.registrar_evento_baja_dto import RegistrarEventoBajaDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.error_handlers import register_error_handlers

BASE_URL = os.getenv(
    'SGPMP_TEST_BASE_URL',
    'https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test',
)
PASSWORD = 'Test1234!'
ID_ACTIVO_EN_VIVO = 306  # INDIVIDUAL ACTIVO; los sub-casos 254/255 nunca lo modifican (solo rechazos)
FECHA_BAJA = '2026-09-18'
ID_LOTE_MOCK = 900


def _login(correo: str) -> str:
    r = httpx.post(f'{BASE_URL}/sesiones/', json={'correo_electronico': correo, 'contrasena': PASSWORD}, timeout=30)
    assert r.status_code == 200, f'login {correo}: {r.status_code} {r.text}'
    return r.json()['token']


def _post_baja(token: str, body: dict) -> httpx.Response:
    return httpx.post(
        f'{BASE_URL}/activos-biologicos/{ID_ACTIVO_EN_VIVO}/eventos/baja',
        json=body,
        headers={'Authorization': f'Bearer {token}'},
        timeout=30,
    )


class TestSubcaso254DatosObligatorios:

    @pytest.mark.parametrize(
        'body, campo',
        [
            ({'fecha_baja': FECHA_BAJA, 'motivo_baja': 'TC-M02-254 sin tipo_baja'}, 'tipo_baja'),
            ({'tipo_baja': 'venta', 'fecha_baja': FECHA_BAJA}, 'motivo_baja'),
            ({'tipo_baja': 'venta', 'fecha_baja': FECHA_BAJA, 'motivo_baja': ''}, 'motivo_baja'),
            ({'tipo_baja': '', 'fecha_baja': FECHA_BAJA, 'motivo_baja': 'TC-M02-254 tipo vacio'}, 'tipo_baja'),
        ],
        ids=['sin_tipo_baja', 'sin_motivo_baja', 'motivo_vacio', 'tipo_vacio'],
    )
    def test_baja_sin_datos_obligatorios_responde_400_senalando_el_campo(self, body, campo):
        respuesta = _post_baja(_login('admin@pecuaria.co'), body)

        assert respuesta.status_code == 400, respuesta.text
        cuerpo = respuesta.json()
        assert cuerpo['error_code'] == 'VAL_ENTRADA'
        assert campo in [f['field'] for f in cuerpo['fields']]


class TestSubcaso255ControlDeAccesoPorRol:

    @pytest.mark.parametrize(
        'correo',
        ['contador@pecuaria.co', 'gestor.granja.test@pecuaria.co', 'revisor.fiscal.test@pecuaria.co'],
        ids=['contador', 'gestor_granja', 'revisor_fiscal'],
    )
    def test_rol_no_autorizado_recibe_403_acceso_denegado(self, correo):
        respuesta = _post_baja(
            _login(correo),
            {'tipo_baja': 'venta', 'fecha_baja': FECHA_BAJA, 'motivo_baja': 'TC-M02-255 rol no autorizado'},
        )

        assert respuesta.status_code == 403, respuesta.text
        assert respuesta.json()['error_code'] == 'ACCESO_DENEGADO'

    @pytest.mark.parametrize(
        'correo',
        ['admin@pecuaria.co', 'm2m.nuevo@ejemplo.com', 'juan.carlos@email.com'],
        ids=['administrador', 'productor', 'veterinario'],
    )
    def test_roles_autorizados_pasan_el_control_de_acceso(self, correo):
        # Body vacio: si el rol tiene permiso, el request llega a la validacion (400) en vez de 403,
        # sin ejecutar ninguna baja real.
        respuesta = _post_baja(_login(correo), {})

        assert respuesta.status_code == 400, respuesta.text
        assert respuesta.json()['error_code'] == 'VAL_ENTRADA'


def _lote(cantidad: int = 10) -> ActivoBiologico:
    return ActivoBiologico(
        id_especie=4,
        tipo='POBLACIONAL',
        origen_financiero='nacimiento',
        id_infraestructura=6,
        id_estado=1,
        id_usuario=1,
        id_activo_biologico=ID_LOTE_MOCK,
        fecha_inicio_ciclo=date(2026, 8, 1),
        fecha_creacion=datetime(2026, 8, 1, tzinfo=timezone.utc),
        detalle_poblacional=DetallePoblacional(cantidad_inicial=cantidad, cantidad_actual=cantidad),
    )


def _use_case(db, activo_repo, evento_repo, historico_repo, bitacora_repo) -> RegistrarEventoBajaUseCase:
    infra_port = MagicMock()
    infra_port.obtener_activa.return_value = None
    return RegistrarEventoBajaUseCase(
        db=db,
        activo_repo=activo_repo,
        evento_repo=evento_repo,
        infra_port=infra_port,
        historico_repo=historico_repo,
        bitacora_repo=bitacora_repo,
    )


def _dto() -> RegistrarEventoBajaDTO:
    return RegistrarEventoBajaDTO(
        tipo_baja='venta',
        fecha_baja=date(2026, 9, 9),
        motivo_baja='TC-M02-256 baja total con fallo transaccional simulado',
    )


def _primer_commit_o_rollback(db) -> str:
    return next(c[0] for c in db.mock_calls if c[0] in ('commit', 'rollback'))


class TestSubcaso256RollbackAnteFalloTransaccional:

    def test_fallo_al_insertar_el_evento_hace_rollback_y_no_descuenta_la_cantidad(self):
        """Baja TOTAL de un lote (cierra estado + descuenta cantidad) con guardar() fallando."""
        activo_repo = MagicMock()
        activo_repo.obtener_por_id.return_value = _lote()
        activo_repo.obtener_fase_activa.return_value = None
        evento_repo = MagicMock()
        evento_repo.obtener_ultima_fecha.return_value = None
        evento_repo.guardar.side_effect = ConnectionError('simulated: fallo transaccional en la baja')
        historico_repo = MagicMock()
        bitacora_repo = MagicMock()
        db = MagicMock()
        usuario = UsuarioActual(id_usuario=1, id_token=1, id_rol=1, id_estado_cuenta=2)

        with pytest.raises(ConnectionError):
            _use_case(db, activo_repo, evento_repo, historico_repo, bitacora_repo).execute(ID_LOTE_MOCK, _dto(), usuario)

        # el cambio de estado quedo encolado, pero nunca se confirmo: lo primero que ocurre en la sesion es el rollback
        historico_repo.registrar.assert_called_once()
        db.rollback.assert_called_once()
        assert _primer_commit_o_rollback(db) == 'rollback'
        # el descuento de cantidad en BD nunca se intento
        activo_repo.actualizar_detalle_poblacional.assert_not_called()
        # el fallo queda auditado antes de relanzar
        evento = bitacora_repo.registrar.call_args_list[0].args[0]
        assert (evento.rf_origen, evento.tipo_evento, evento.resultado) == ('RF45', 'BAJA_REGISTRO_FALLIDO', 'FALLIDO')

    def test_fallo_al_descontar_la_cantidad_del_lote_hace_rollback(self):
        """El evento se inserta bien, pero falla el UPDATE de cantidad_actual: todo debe revertirse."""
        activo_repo = MagicMock()
        activo_repo.obtener_por_id.return_value = _lote()
        activo_repo.obtener_fase_activa.return_value = None
        activo_repo.actualizar_detalle_poblacional.side_effect = ConnectionError('simulated: fallo al descontar cantidad')
        evento_repo = MagicMock()
        evento_repo.obtener_ultima_fecha.return_value = None
        historico_repo = MagicMock()
        bitacora_repo = MagicMock()
        db = MagicMock()
        usuario = UsuarioActual(id_usuario=1, id_token=1, id_rol=1, id_estado_cuenta=2)

        with pytest.raises(ConnectionError):
            _use_case(db, activo_repo, evento_repo, historico_repo, bitacora_repo).execute(ID_LOTE_MOCK, _dto(), usuario)

        evento_repo.guardar.assert_called_once()
        db.rollback.assert_called_once()
        assert _primer_commit_o_rollback(db) == 'rollback'

    def test_endpoint_responde_500_error_interno_y_hace_rollback(self):
        """A traves del router completo: 500 ERROR_INTERNO (mensaje generico, no el 'Fallo critico' de la ficha)."""
        from src.biological_assets.infrastructure.adapters.infraestructura_m09_adapter import InfraestructuraM09Adapter
        from src.biological_assets.infrastructure.repositories.activo_biologico_repository import (
            SqlAlchemyActivoBiologicoRepository,
        )
        from src.biological_assets.infrastructure.repositories.bitacora_auditoria_repository import (
            SqlAlchemyBitacoraAuditoriaRepository,
        )
        from src.biological_assets.infrastructure.repositories.evento_activo_repository import (
            SqlAlchemyEventoActivoRepository,
        )
        from src.biological_assets.infrastructure.repositories.historico_estado_repository import (
            SqlAlchemyHistoricoEstadoRepository,
        )
        from src.biological_assets.infrastructure.routers.activo_biologico_router import (
            router as activo_biologico_router,
        )

        fake_db = MagicMock()
        app = FastAPI()
        register_error_handlers(app)
        app.include_router(activo_biologico_router)
        def _fake_db():
            yield fake_db

        app.dependency_overrides[get_db] = _fake_db
        app.dependency_overrides[get_current_user] = lambda: UsuarioActual(
            id_usuario=1, id_token=1, id_rol=1, id_estado_cuenta=2,
        )

        with patch.object(SqlAlchemyActivoBiologicoRepository, 'obtener_por_id', return_value=_lote()), \
             patch.object(SqlAlchemyActivoBiologicoRepository, 'obtener_fase_activa', return_value=None), \
             patch.object(SqlAlchemyActivoBiologicoRepository, 'actualizar_detalle_poblacional') as actualizar_mock, \
             patch.object(SqlAlchemyEventoActivoRepository, 'obtener_ultima_fecha', return_value=None), \
             patch.object(SqlAlchemyEventoActivoRepository, 'guardar', side_effect=ConnectionError('simulated')), \
             patch.object(SqlAlchemyHistoricoEstadoRepository, 'registrar'), \
             patch.object(InfraestructuraM09Adapter, 'obtener_activa', return_value=None), \
             patch.object(SqlAlchemyBitacoraAuditoriaRepository, 'registrar'):
            respuesta = TestClient(app, raise_server_exceptions=False).post(
                f'/activos-biologicos/{ID_LOTE_MOCK}/eventos/baja',
                json={'tipo_baja': 'venta', 'fecha_baja': '2026-09-09', 'motivo_baja': 'TC-M02-256 endpoint'},
            )

        assert respuesta.status_code == 500, respuesta.text
        cuerpo = respuesta.json()
        assert cuerpo['error_code'] == 'ERROR_INTERNO'
        assert 'Fallo crítico' not in cuerpo['message']
        fake_db.rollback.assert_called_once()
        actualizar_mock.assert_not_called()
