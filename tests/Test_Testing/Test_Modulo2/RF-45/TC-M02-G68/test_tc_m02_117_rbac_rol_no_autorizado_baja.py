"""
TC-M02-G68 (TC-M02-117) - Funcion de baja restringida por rol
(OWASP API5 - Broken Function Level Authorization).

RF relacionado: RF-45, CU09 Gestionar eventos productivos y bajas
Categoria: Pruebas de seguridad

Criterio de aceptacion (segun la ficha):
    Precondicion: "Usuario con rol sin autorizacion para dar de baja
    activos." Paso: "El usuario intenta ejecutar el registro de baja."
    Resultado esperado: "HTTP 403 Forbidden - 'Solo el Productor, el
    Veterinario o el Administrador estan autorizados para retirar
    activos'."

Herramienta pedida por la ficha: Pytest (no Newman) -- se sigue el mismo
patron de dos niveles ya usado en TC-M09-G60/TC-M01-044: (1) la
dependencia RBAC en aislamiento, con un doble de prueba para la sesion
de BD, y (2) el endpoint completo via TestClient, con
app.dependency_overrides para get_db/get_current_user (sin necesitar un
JWT real ni una base de datos real).

POST /activos-biologicos/{id_activo}/eventos/baja usa
`dependencies=[Depends(require_permission(_RECURSO, 1))]` con
`_RECURSO=29` (activos_biologicos), accion 1 (Crear) -- exactamente el
mismo recurso/accion que /eventos/productivo (ver TC-M02-G07). Se usa el
rol Contador (id_rol=5) como "rol no autorizado": segun
anotaciones/modulo_2/cu02_gaps_bd_rf35_rf37.md, Contador no tiene ningun
permiso sobre el recurso 29.

HALLAZGO (discrepancia ficha vs implementacion, no es un bug): la ficha
cita un mensaje de negocio especifico ("Solo el Productor, el
Veterinario o el Administrador..."). El router real
(activo_biologico_router.py:661) usa `require_permission(_RECURSO, 1)`
SIN el parametro opcional `mensaje_denegado` -- por lo tanto el mensaje
real es el generico de src/shared/rbac.py: "Acceso denegado. Su rol no
tiene permisos para realizar esta operacion.", no el texto especifico
que cita la ficha. El codigo de negocio (`ACCESO_DENEGADO`) y el HTTP
403 si son correctos.

Como correrlo (desde la raiz del repo, con las env vars seteadas):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m02_117_rbac_rol_no_autorizado_baja.py -v \
        --html=Resultados/reporte-TC-M02-117.html --self-contained-html
"""
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.errors import AuthorizationError
from src.shared.error_handlers import register_error_handlers
from src.shared.rbac import require_permission

ID_ROL_CONTADOR = 5
RECURSO_ACTIVOS_BIOLOGICOS = 29
ACCION_CREAR = 1


class TestTCM02117RBACRolNoAutorizadoParaBaja:

    def test_require_permission_rechaza_rol_sin_permiso_sobre_el_recurso(self):
        """
        La dependencia RBAC (require_permission) debe lanzar
        AuthorizationError(code=ACCESO_DENEGADO) cuando la tabla
        modulo1.permisos no tiene ninguna fila activa para
        (id_rol=Contador, recurso=activos_biologicos, accion=Crear).
        """
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None  # sin permiso

        usuario_contador = UsuarioActual(
            id_usuario=1, id_token=1, id_rol=ID_ROL_CONTADOR, id_estado_cuenta=2,  # ACTIVO
        )
        dependency = require_permission(RECURSO_ACTIVOS_BIOLOGICOS, ACCION_CREAR)

        with pytest.raises(AuthorizationError) as exc_info:
            dependency(db=db, usuario_actual=usuario_contador)

        assert exc_info.value.code == 'ACCESO_DENEGADO'

    def test_endpoint_baja_responde_403_y_no_persiste_nada_para_rol_no_autorizado(self):
        """
        RF-45/OWASP API5: POST /activos-biologicos/{id}/eventos/baja debe
        responder 403 para un usuario autenticado sin permiso sobre el
        recurso, y el repositorio de eventos NUNCA debe ser invocado --
        sin persistir ningun dato, tal como exige la ficha.
        """
        from src.biological_assets.infrastructure.repositories.evento_activo_repository import (
            SqlAlchemyEventoActivoRepository,
        )
        from src.biological_assets.infrastructure.routers.activo_biologico_router import (
            router as activo_biologico_router,
        )

        fake_db = MagicMock()
        fake_db.query.return_value.filter.return_value.first.return_value = None  # sin permiso

        app = FastAPI()
        register_error_handlers(app)
        app.include_router(activo_biologico_router)

        def _fake_db():
            yield fake_db

        def _fake_usuario_contador():
            return UsuarioActual(id_usuario=1, id_token=1, id_rol=ID_ROL_CONTADOR, id_estado_cuenta=2)

        app.dependency_overrides[get_db] = _fake_db
        app.dependency_overrides[get_current_user] = _fake_usuario_contador

        guardar_mock = MagicMock()
        original_guardar = SqlAlchemyEventoActivoRepository.guardar
        SqlAlchemyEventoActivoRepository.guardar = guardar_mock
        try:
            client = TestClient(app, raise_server_exceptions=False)
            response = client.post(
                '/activos-biologicos/80/eventos/baja',
                json={
                    'tipo_baja': 'venta',
                    'fecha_baja': '2026-09-09',
                    'motivo_baja': 'TC-M02-117 - intento con rol no autorizado (prueba QA)',
                },
            )
        finally:
            SqlAlchemyEventoActivoRepository.guardar = original_guardar

        assert response.status_code == 403, response.text
        cuerpo = response.json()
        assert cuerpo['error_code'] == 'ACCESO_DENEGADO'
        guardar_mock.assert_not_called()
