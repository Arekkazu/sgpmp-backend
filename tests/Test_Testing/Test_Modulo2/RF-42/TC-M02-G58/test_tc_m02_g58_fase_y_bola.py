"""
TC-M02-G58 (parte Pytest) - Fase productiva incompatible (TC-M02-230) y BOLA
sobre datos genealogicos de otra finca (TC-M02-231).

RF relacionado: RF-42, CU08 Gestionar eventos reproductivos
Categoria: Validacion / Seguridad (OWASP API1)

Criterio de aceptacion (segun la ficha, sub-casos 230 y 231):
    TC-M02-230: "La fase productiva debe ser compatible con reproduccion
    (409 si no)." Precondicion: "Activo en fase 'Engorde/Finalizacion' no
    apta para reproduccion." Resultado esperado: "HTTP 409 CONFLICT - 'La
    fase productiva del activo no permite registrar este tipo de evento'."

    TC-M02-231: "Manipulacion de activo_relacionado_id de otra finca ->
    403/404 (BOLA)." Ya se confirmo el mismo hallazgo en TC-M02-G56 con su
    propio archivo dedicado; aqui se reproduce el mismo test (mismos dobles
    de prueba) para que el reporte de TC-M02-G58 quede autocontenido bajo
    su propio TC-M02-231, sin depender de que se haya corrido G56 antes.

Por que Pytest con dobles de prueba y no Newman contra el backend en vivo
(mismo criterio que TC-M02-G56): cualquier escritura real en
modulo2.eventos_reproductivos hoy responde 500 por el bug de
db_error_translator ya documentado en TC-M02-G53/G55/G57, lo que confundiria
la pregunta de autorizacion/validacion bajo prueba aqui. Aislando el use
case (y el endpoint completo via TestClient, con el repositorio de
escritura reemplazado por un doble que SI completa con exito) se puede
verificar si el codigo siquiera intenta las validaciones pedidas, sin ese
ruido.

Hallazgo TC-M02-230 (leido en registrar_evento_reproductivo_use_case.py):
el use case NUNCA llama a `activo_repo.obtener_fase_activa(id_activo)` --
a diferencia de sus hermanos RegistrarEventoProductivoUseCase (RF-43,
E-02: `SIN_FASE_PRODUCTIVA_ACTIVA` si no hay fase activa),
RegistrarEventoCrecimientoUseCase y RegistrarEventoBajaUseCase, que si
consultan la fase antes de proceder. RF-42 no tiene ningun mecanismo de
compatibilidad de fase: un evento reproductivo se acepta sin importar en
que fase productiva (o si tiene alguna) este el activo. No es un bug de
"codigo muerto" como el de TC-M02-G55 (LOTE) -- aqui simplemente no existe
ningun intento de validacion, ni en Python ni en un trigger de BD (no se
encontro ninguna referencia a fase en los triggers de
modulo2.eventos_reproductivos en esquema_baseline.sql).

Hallazgo TC-M02-231: ver TC-M02-G56 (mismo mecanismo, mismo codigo fuente).

Ambas pruebas se dejan afirmando el comportamiento CORRECTO esperado por
el RF (409 en 230, 403/404 en 231) en vez de ajustarse al comportamiento
actual: un Pytest en rojo aqui es la evidencia documentada, mismo criterio
aplicado en TC-M09-G125/G126 y TC-M02-G53/G55/G56.

Como correrlo (desde la raiz del repo, con las env vars seteadas):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m02_g58_fase_y_bola.py -v \
        --html=Resultados/reporte-TC-M02-G58-pytest.html --self-contained-html
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.biological_assets.application.use_cases.gestion.registrar_evento_reproductivo_use_case import (
    RegistrarEventoReproductivoUseCase,
)
from src.biological_assets.domain.entities.activo_biologico import (
    ActivoBiologico,
    EventoActivo,
    EventoReproductivo,
    GestionFase,
)
from src.biological_assets.infrastructure.dto.registrar_evento_reproductivo_dto import (
    RegistrarEventoReproductivoDTO,
)
from src.identity_access.infrastructure.dependencies import UsuarioActual

ID_ACTIVO_MADRE = 300
ID_INFRAESTRUCTURA_PROPIA = 3
ID_ACTIVO_PADRE_AJENO = 901
ID_INFRAESTRUCTURA_AJENA = 4


def _activo(id_activo_biologico: int, id_infraestructura: int) -> ActivoBiologico:
    return ActivoBiologico(
        id_especie=10,
        tipo='INDIVIDUAL',
        origen_financiero='compra',
        id_infraestructura=id_infraestructura,
        id_estado=1,  # ACTIVO
        id_usuario=1,
        id_activo_biologico=id_activo_biologico,
        fecha_creacion=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


class TestTCM02G58FaseProductivaIncompatible:
    """TC-M02-230: la fase productiva debe ser compatible con reproduccion."""

    def test_use_case_no_valida_fase_productiva(self):
        madre = _activo(ID_ACTIVO_MADRE, ID_INFRAESTRUCTURA_PROPIA)

        activo_repo = MagicMock()
        activo_repo.obtener_por_id.return_value = madre
        # Fase activa deliberadamente incompatible con reproduccion, tal
        # como pide la precondicion de la ficha -- se deja disponible para
        # que el use case la consulte, si acaso lo hiciera.
        activo_repo.obtener_fase_activa.return_value = GestionFase(
            id_activo_biologico=ID_ACTIVO_MADRE,
            id_ciclo_productiva=1,
            nombre_ciclo='Ciclo Tilapia 2026-1',
            fecha_inicio=datetime(2026, 1, 1, tzinfo=timezone.utc),
            es_activa=True,
            id_usuario=1,
            nombre_fase_actual='Engorde/Finalizacion',
        )

        evento_guardado = EventoActivo(
            id_activo_biologico=ID_ACTIVO_MADRE,
            fecha=datetime(2026, 9, 9, tzinfo=timezone.utc),
            id_usuario=1,
            id_eventos=601,
            reproductivo=EventoReproductivo(categoria='diagnostico', resultado='exitoso'),
        )
        evento_repo = MagicMock()
        evento_repo.obtener_ultima_fecha.return_value = None
        evento_repo.tiene_servicio_o_inseminacion_previa.return_value = True
        evento_repo.guardar.return_value = evento_guardado

        db = MagicMock()

        use_case = RegistrarEventoReproductivoUseCase(
            db=db, activo_repo=activo_repo, evento_repo=evento_repo, bitacora_repo=MagicMock(),
        )
        dto = RegistrarEventoReproductivoDTO(categoria='diagnostico', resultado='exitoso')
        usuario_actual = UsuarioActual(id_usuario=1, id_token=1, id_rol=2, id_estado_cuenta=2)

        excepcion_lanzada = None
        try:
            use_case.execute(ID_ACTIVO_MADRE, dto, usuario_actual)
        except Exception as exc:
            excepcion_lanzada = exc

        assert excepcion_lanzada is not None, (
            "RF-42 exige que un evento reproductivo sobre un activo en fase "
            "'Engorde/Finalizacion' (incompatible con reproduccion) sea "
            "rechazado con HTTP 409. El use case no lanzo ninguna excepcion "
            "-- de hecho, nunca consulta la fase activa del activo en absoluto."
        )

        activo_repo.obtener_fase_activa.assert_called_once_with(ID_ACTIVO_MADRE)

    def test_endpoint_acepta_evento_sin_verificar_fase(self):
        from src.biological_assets.infrastructure.repositories.activo_biologico_repository import (
            SqlAlchemyActivoBiologicoRepository,
        )
        from src.biological_assets.infrastructure.repositories.bitacora_auditoria_repository import (
            SqlAlchemyBitacoraAuditoriaRepository,
        )
        from src.biological_assets.infrastructure.repositories.evento_activo_repository import (
            SqlAlchemyEventoActivoRepository,
        )
        from src.biological_assets.infrastructure.routers.activo_biologico_router import (
            router as activo_biologico_router,
        )
        from src.identity_access.infrastructure.dependencies import get_current_user
        from src.shared.database import get_db
        from src.shared.error_handlers import register_error_handlers

        madre = _activo(ID_ACTIVO_MADRE, ID_INFRAESTRUCTURA_PROPIA)
        evento_guardado = EventoActivo(
            id_activo_biologico=ID_ACTIVO_MADRE,
            fecha=datetime(2026, 9, 9, tzinfo=timezone.utc),
            id_usuario=1,
            id_eventos=602,
            reproductivo=EventoReproductivo(categoria='diagnostico', resultado='exitoso'),
        )

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

        with (
            patch.object(SqlAlchemyActivoBiologicoRepository, 'obtener_por_id', return_value=madre),
            patch.object(
                SqlAlchemyActivoBiologicoRepository,
                'obtener_fase_activa',
                return_value=GestionFase(
                    id_activo_biologico=ID_ACTIVO_MADRE, id_ciclo_productiva=1,
                    nombre_ciclo='Ciclo Tilapia 2026-1', fecha_inicio=datetime(2026, 1, 1, tzinfo=timezone.utc),
                    es_activa=True, id_usuario=1, nombre_fase_actual='Engorde/Finalizacion',
                ),
            ),
            patch.object(SqlAlchemyEventoActivoRepository, 'obtener_ultima_fecha', return_value=None),
            patch.object(SqlAlchemyEventoActivoRepository, 'tiene_servicio_o_inseminacion_previa', return_value=True),
            patch.object(SqlAlchemyEventoActivoRepository, 'guardar', return_value=evento_guardado),
            patch.object(SqlAlchemyBitacoraAuditoriaRepository, 'registrar', return_value=None),
        ):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.post(
                f"/activos-biologicos/{ID_ACTIVO_MADRE}/eventos/reproductivo",
                json={"categoria": "diagnostico", "resultado": "exitoso"},
            )

        assert response.status_code == 409, (
            "RF-42 exige HTTP 409 al registrar un evento reproductivo sobre "
            f"un activo en fase incompatible; el endpoint respondio "
            f"{response.status_code} y acepto el evento sin verificar la "
            f"fase. Cuerpo: {response.text}"
        )

        app.dependency_overrides.clear()


class TestTCM02G58BolaOtraFinca:
    """TC-M02-231: BOLA sobre datos genealogicos de otra finca (reproduce TC-M02-G56)."""

    def test_endpoint_acepta_padre_de_otra_finca_sin_validar_pertenencia(self):
        from src.biological_assets.infrastructure.repositories.activo_biologico_repository import (
            SqlAlchemyActivoBiologicoRepository,
        )
        from src.biological_assets.infrastructure.repositories.bitacora_auditoria_repository import (
            SqlAlchemyBitacoraAuditoriaRepository,
        )
        from src.biological_assets.infrastructure.repositories.evento_activo_repository import (
            SqlAlchemyEventoActivoRepository,
        )
        from src.biological_assets.infrastructure.routers.activo_biologico_router import (
            router as activo_biologico_router,
        )
        from src.identity_access.infrastructure.dependencies import get_current_user
        from src.shared.database import get_db
        from src.shared.error_handlers import register_error_handlers

        madre = _activo(ID_ACTIVO_MADRE, ID_INFRAESTRUCTURA_PROPIA)
        padre_ajeno = _activo(ID_ACTIVO_PADRE_AJENO, ID_INFRAESTRUCTURA_AJENA)

        def _obtener_por_id(id_activo):
            if id_activo == ID_ACTIVO_MADRE:
                return madre
            if id_activo == ID_ACTIVO_PADRE_AJENO:
                return padre_ajeno
            return None

        evento_guardado = EventoActivo(
            id_activo_biologico=ID_ACTIVO_MADRE,
            fecha=datetime(2026, 9, 9, tzinfo=timezone.utc),
            id_usuario=1,
            id_eventos=603,
            reproductivo=EventoReproductivo(
                categoria='servicio', resultado='exitoso', id_padre=ID_ACTIVO_PADRE_AJENO,
            ),
        )

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

        with (
            patch.object(SqlAlchemyActivoBiologicoRepository, 'obtener_por_id', side_effect=_obtener_por_id),
            patch.object(SqlAlchemyEventoActivoRepository, 'obtener_ultima_fecha', return_value=None),
            patch.object(SqlAlchemyEventoActivoRepository, 'guardar', return_value=evento_guardado),
            patch.object(SqlAlchemyBitacoraAuditoriaRepository, 'registrar', return_value=None),
        ):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.post(
                f"/activos-biologicos/{ID_ACTIVO_MADRE}/eventos/reproductivo",
                json={"categoria": "servicio", "resultado": "exitoso", "id_padre": ID_ACTIVO_PADRE_AJENO},
            )

        assert response.status_code in (403, 404), (
            "OWASP API1 (BOLA): se esperaba HTTP 403 o 404 al referenciar un "
            f"id_padre de otra finca; el endpoint respondio {response.status_code} "
            f"y acepto la relacion genealogica cruzada sin validar pertenencia "
            f"(mismo hallazgo que TC-M02-G56). Cuerpo: {response.text}"
        )

        app.dependency_overrides.clear()
