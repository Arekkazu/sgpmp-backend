"""
TC-M02-G59 (parte Pytest) - Rechazo de evento reproductivo sobre activo
CERRADO o BAJA (TC-M02-234).

RF relacionado: RF-42, CU08 Gestionar eventos reproductivos
Categoria: Pruebas de validacion

Criterio de aceptacion (segun la ficha, sub-caso 3):
    "No se permite registrar eventos reproductivos en activos CERRADO/BAJA
    -> 409." Precondicion: "Activo biologico en estado CERRADO o BAJA."
    Paso: "Intentar registrar un evento reproductivo (cualquier tipo) sobre
    un activo en estado CERRADO o BAJA." Resultado esperado: "HTTP 409
    CONFLICT - 'El activo no se encuentra en estado ACTIVO'."

Por que Pytest con dobles de prueba y no Newman contra el backend en vivo
(a diferencia de TC-M02-232/233, que si se probaron en vivo en
tc_m02_g59.postman_collection.json): reproducir un activo real en estado
CERRADO por API exige antes asignarle una fase productiva
(POST /activos-biologicos/{id}/fases, RF-37), que a su vez requiere un
id_ciclo_productiva de modulo9.ciclos_productivos -- tabla sin ningun
endpoint de catalogo/listado expuesto (se administra por seed o acceso
directo a BD, no hay forma de descubrir un ID valido solo con las rutas
publicas). La ruta alternativa, estado BAJA via POST .../eventos/baja,
esta confirmada rota con 500 ERROR_INTERNO (ver TC-M02-G58) -- tampoco
serviria para preparar esta precondicion. La validacion bajo prueba
(validar_estado_permite_eventos en
src/biological_assets/application/use_cases/gestion/_event_validations.py)
es Python puro sin ninguna dependencia de infraestructura, asi que un
doble de prueba con id_estado=5 (CERRADO) o id_estado=6 (BAJA) la verifica
igual de bien sin necesitar ese montaje.

Se prueba en dos niveles, mismo criterio que TC-M09-G67/TC-M02-G56:
  1. El use case en aislamiento, con un activo CERRADO.
  2. El endpoint completo via TestClient, con un activo BAJA (cubriendo
     ambos estados mencionados en la ficha entre los dos niveles).

Se espera que AMBOS PASEN en verde: a diferencia de TC-M02-G53/G55/G57/G58,
esta es una validacion que si esta implementada correctamente en el codigo
(_ESTADOS_PERMITEN_EVENTOS = {1, 3, 4} -- ACTIVO, EN_TRATAMIENTO, AISLADO
-- deja fuera CERRADO=5 y BAJA=6) y ocurre ANTES de cualquier INSERT, por
lo que no hereda ninguno de los bugs ya documentados en esta familia de TCs.

Como correrlo (desde la raiz del repo, con las env vars seteadas):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m02_234_estado_no_permite_eventos.py -v \
        --html=Resultados/reporte-TC-M02-234.html --self-contained-html
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.biological_assets.application.use_cases.gestion.registrar_evento_reproductivo_use_case import (
    RegistrarEventoReproductivoUseCase,
)
from src.biological_assets.domain.entities.activo_biologico import ActivoBiologico
from src.biological_assets.infrastructure.dto.registrar_evento_reproductivo_dto import (
    RegistrarEventoReproductivoDTO,
)
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import ConflictError

ID_ACTIVO = 400
ID_ESTADO_CERRADO = 5
ID_ESTADO_BAJA = 6


def _activo(id_estado: int) -> ActivoBiologico:
    return ActivoBiologico(
        id_especie=10,
        tipo='INDIVIDUAL',
        origen_financiero='compra',
        id_infraestructura=3,
        id_estado=id_estado,
        id_usuario=1,
        id_activo_biologico=ID_ACTIVO,
        fecha_creacion=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


class TestTCM02234EstadoNoPermiteEventos:

    def test_use_case_rechaza_evento_sobre_activo_cerrado(self):
        activo_cerrado = _activo(ID_ESTADO_CERRADO)

        activo_repo = MagicMock()
        activo_repo.obtener_por_id.return_value = activo_cerrado

        evento_repo = MagicMock()
        db = MagicMock()

        use_case = RegistrarEventoReproductivoUseCase(
            db=db, activo_repo=activo_repo, evento_repo=evento_repo, bitacora_repo=MagicMock(),
        )
        dto = RegistrarEventoReproductivoDTO(categoria='diagnostico', resultado='exitoso')
        usuario_actual = UsuarioActual(id_usuario=1, id_token=1, id_rol=2, id_estado_cuenta=2)

        excepcion_lanzada = None
        try:
            use_case.execute(ID_ACTIVO, dto, usuario_actual)
        except Exception as exc:
            excepcion_lanzada = exc

        assert excepcion_lanzada is not None, (
            "RF-42 exige que un evento reproductivo sobre un activo en "
            "estado CERRADO sea rechazado con HTTP 409."
        )
        assert isinstance(excepcion_lanzada, ConflictError), (
            f"Se esperaba ConflictError (409); se obtuvo {type(excepcion_lanzada).__name__}."
        )
        assert excepcion_lanzada.code == 'ESTADO_NO_PERMITE_EVENTOS'

        # No debe haber llegado a intentar guardar el evento.
        evento_repo.guardar.assert_not_called()
        db.commit.assert_not_called()

    def test_endpoint_rechaza_evento_sobre_activo_en_baja(self):
        from src.biological_assets.infrastructure.repositories.activo_biologico_repository import (
            SqlAlchemyActivoBiologicoRepository,
        )
        from src.biological_assets.infrastructure.routers.activo_biologico_router import (
            router as activo_biologico_router,
        )
        from src.identity_access.infrastructure.dependencies import get_current_user
        from src.shared.database import get_db
        from src.shared.error_handlers import register_error_handlers

        activo_baja = _activo(ID_ESTADO_BAJA)

        fake_db = MagicMock()
        app = FastAPI()
        register_error_handlers(app)
        app.include_router(activo_biologico_router)

        def _fake_db():
            yield fake_db

        def _fake_usuario_actual():
            return UsuarioActual(id_usuario=1, id_token=1, id_rol=2, id_estado_cuenta=2)

        app.dependency_overrides[get_db] = _fake_db
        app.dependency_overrides[get_current_user] = _fake_usuario_actual

        with patch.object(SqlAlchemyActivoBiologicoRepository, 'obtener_por_id', return_value=activo_baja):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.post(
                f"/activos-biologicos/{ID_ACTIVO}/eventos/reproductivo",
                json={"categoria": "diagnostico", "resultado": "exitoso"},
            )

        assert response.status_code == 409, (
            f"Se esperaba HTTP 409 sobre un activo en estado BAJA; el "
            f"endpoint respondio {response.status_code}. Cuerpo: {response.text}"
        )
        assert response.json()["error_code"] == "ESTADO_NO_PERMITE_EVENTOS"

        app.dependency_overrides.clear()
