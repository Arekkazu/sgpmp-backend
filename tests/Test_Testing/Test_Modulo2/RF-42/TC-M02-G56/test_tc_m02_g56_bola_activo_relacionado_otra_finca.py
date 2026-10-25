"""
TC-M02-G56 (TC-M02-105) - Control de acceso a datos genealogicos de activos
de otra finca (Seguridad - OWASP API1 BOLA).

RF relacionado: RF-42, CU08 Gestionar eventos reproductivos
Categoria: Pruebas de seguridad (OWASP API1 - Broken Object Level Authorization)

Criterio de aceptacion (segun la ficha):
    "Manipular activo_relacionado_id en el payload para referenciar un activo
    fuera del alcance del usuario." Precondicion: "activo_relacionado_id
    pertenece a un activo de otra finca." Resultado esperado: "El sistema
    valida la finca/permiso del usuario y rechaza el evento con HTTP
    403/404, sin exponer datos del activo ajeno."

Por que Pytest con dobles de prueba y no un Newman contra el backend en vivo
(a diferencia de TC-M09-G125/G126, que si golpean el backend real): el unico
punto de la ficha que se puede probar con id_padre (servicio/inseminacion)
es tambien el unico camino de escritura de RF-42 que ya esta roto en
produccion por un bug no relacionado (ver TC-M02-G53/TC-M02-G55: cualquier
insert en modulo2.eventos_reproductivos hoy responde 500 ERROR_INTERNO por
un ERRCODE de trigger no traducido). Un Newman contra el backend real solo
podria observar 500 en ambos casos (padre valido de otra finca vs. padre
invalido), sin poder distinguir "la finca se valido y fue rechazada
correctamente antes de tocar la BD" de "el insert exploto por el bug ya
conocido" -- resultado ambiguo. Aislando el use case (y el endpoint completo
via TestClient, con el repositorio de escritura reemplazado por un doble que
SI completa con exito) se puede verificar, sin ese ruido, si el codigo
siquiera intenta comparar la finca del padre contra el alcance del usuario
antes de llegar al insert.

Hallazgo (leido en registrar_evento_reproductivo_use_case.py, lineas 62-79):
la validacion FA-05 de id_padre solo comprueba (a) que el activo exista
(activo_repo.obtener_por_id) y (b) que su id_estado sea 1 (ACTIVO) -- nunca
compara id_infraestructura/finca del padre contra la del activo que recibe
el evento ni contra la finca del usuario autenticado. El fix de RF-25
("restringir activos biologicos a la finca del usuario", commit 6ca29b5,
2026-09-08) solo toco endpoints de LECTURA (listar/consultar/historial/
eventos/ficha integral/indicadores/datos consolidados/asociacion) segun su
propio mensaje de commit -- no toco este use case de escritura ni
SqlAlchemyActivoBiologicoRepository.obtener_por_id (que sigue haciendo
`self.db.get(ActivoBiologicoModel, id_activo)` sin ningun filtro).

Se prueba en dos niveles, mismo criterio que TC-M09-G67:
  1. El use case en aislamiento, con dobles de prueba.
  2. El endpoint completo via TestClient, con los repositorios reales
     parcheados (el repositorio de escritura se reemplaza por un doble que
     completa con exito, para aislar la pregunta de autorizacion del bug de
     TC-M02-G53/G55).

Ambas pruebas se dejan afirmando el comportamiento CORRECTO esperado por el
RF (excepcion / HTTP 403 o 404) en vez de ajustarse al comportamiento actual:
un Pytest en rojo aqui es la evidencia documentada de este BOLA, mismo
criterio aplicado en TC-M09-G125/G126 y TC-M02-G53/G55.

Como correrlo (desde la raiz del repo, con las env vars seteadas):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m02_g56_bola_activo_relacionado_otra_finca.py -v \
        --html=Resultados/reporte-TC-M02-G56.html --self-contained-html
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
)
from src.biological_assets.infrastructure.dto.registrar_evento_reproductivo_dto import (
    RegistrarEventoReproductivoDTO,
)
from src.identity_access.infrastructure.dependencies import UsuarioActual

ID_ACTIVO_MADRE = 200          # activo de la finca del usuario (id_infraestructura=3, finca 1)
ID_INFRAESTRUCTURA_PROPIA = 3
ID_ACTIVO_PADRE_AJENO = 900    # activo de OTRA finca, fuera del alcance del usuario
ID_INFRAESTRUCTURA_AJENA = 4   # id_infraestructura de una finca distinta (finca 2)


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


class TestTCM02G56BolaActivoRelacionadoOtraFinca:
    """Suite de pruebas para TC-M02-G56 / TC-M02-105."""

    def test_use_case_no_rechaza_padre_de_otra_finca(self):
        """
        OWASP API1 (BOLA): RegistrarEventoReproductivoUseCase.execute() debe
        rechazar un id_padre que pertenece a un activo de otra finca (fuera
        del alcance del usuario), sin exponer datos del activo ajeno.
        """
        madre = _activo(ID_ACTIVO_MADRE, ID_INFRAESTRUCTURA_PROPIA)
        padre_ajeno = _activo(ID_ACTIVO_PADRE_AJENO, ID_INFRAESTRUCTURA_AJENA)

        def _obtener_por_id(id_activo):
            if id_activo == ID_ACTIVO_MADRE:
                return madre
            if id_activo == ID_ACTIVO_PADRE_AJENO:
                return padre_ajeno
            return None

        activo_repo = MagicMock()
        activo_repo.obtener_por_id.side_effect = _obtener_por_id

        evento_guardado = EventoActivo(
            id_activo_biologico=ID_ACTIVO_MADRE,
            fecha=datetime(2026, 9, 9, tzinfo=timezone.utc),
            id_usuario=1,
            id_eventos=555,
            reproductivo=EventoReproductivo(
                categoria='servicio', resultado='exitoso', id_padre=ID_ACTIVO_PADRE_AJENO,
            ),
        )
        evento_repo = MagicMock()
        evento_repo.obtener_ultima_fecha.return_value = None
        evento_repo.guardar.return_value = evento_guardado

        db = MagicMock()

        use_case = RegistrarEventoReproductivoUseCase(
            db=db,
            activo_repo=activo_repo,
            evento_repo=evento_repo,
            bitacora_repo=MagicMock(),
        )
        dto = RegistrarEventoReproductivoDTO(
            categoria='servicio', resultado='exitoso', id_padre=ID_ACTIVO_PADRE_AJENO,
        )
        usuario_actual = UsuarioActual(id_usuario=1, id_token=1, id_rol=2, id_estado_cuenta=2)

        excepcion_lanzada = None
        try:
            use_case.execute(ID_ACTIVO_MADRE, dto, usuario_actual)
        except Exception as exc:
            excepcion_lanzada = exc

        assert excepcion_lanzada is not None, (
            "OWASP API1 (BOLA): se esperaba que el use case rechazara un "
            "id_padre perteneciente a un activo de otra finca (HTTP 403/404). "
            "No se lanzo ninguna excepcion -- la FA-05 solo valida existencia "
            "y estado ACTIVO del padre (lineas 69-79 del use case), nunca su "
            "finca/id_infraestructura frente al alcance del usuario o del "
            "activo que recibe el evento."
        )

        # Evidencia adicional de que la ejecucion llego hasta el guardado:
        # confirma que, de no ser por este assert, el evento se habria
        # persistido con la referencia cruzada intacta.
        evento_repo.guardar.assert_called_once()

    def test_endpoint_acepta_padre_de_otra_finca_sin_validar_pertenencia(self):
        """
        OWASP API1 (BOLA): POST /activos-biologicos/{id}/eventos/reproductivo
        debe responder 403/404 cuando id_padre pertenece a un activo de otra
        finca, sin exponer datos del activo ajeno en el cuerpo de la
        respuesta. El repositorio de escritura se reemplaza por un doble que
        SI completa con exito, para aislar esta pregunta de autorizacion del
        bug de db_error_translator ya documentado en TC-M02-G53/G55 (que
        haria fallar CUALQUIER escritura en esta tabla con 500, sin importar
        la finca del padre).
        """
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
            id_eventos=556,
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
                json={
                    "categoria": "servicio",
                    "resultado": "exitoso",
                    "id_padre": ID_ACTIVO_PADRE_AJENO,
                },
            )

        assert response.status_code in (403, 404), (
            "OWASP API1 (BOLA): se esperaba HTTP 403 o 404 al referenciar un "
            f"id_padre de otra finca; el endpoint respondio {response.status_code} "
            f"y acepto la relacion genealogica cruzada sin validar pertenencia. "
            f"Cuerpo: {response.text}"
        )

        app.dependency_overrides.clear()
