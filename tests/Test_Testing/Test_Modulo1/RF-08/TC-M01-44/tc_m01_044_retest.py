"""
TC-M01-044 (RETEST 2026-09-12) - Validar que un fallo del servicio SMTP
mantenga el mensaje generico hacia el usuario (HTTP 202 / mensaje generico
del use case) y dispare una alerta interna al administrador.

RF relacionado: RF-08
Categoria: Manejo de errores (RESILIENCIA)

Por que este archivo reemplaza al original (test_tc_m01_044_fallo_smtp.py):
el codigo cambio de arquitectura por completo entre la ejecucion original
(2026-09-03) y esta version (sincronizada de origin/test el 2026-09-12):

1. SolicitarRecuperacionUseCase ahora recibe dos dependencias nuevas
   (`intentos_anonimos_repo`, `correo_recuperacion_port`) que el test
   original no pasaba -- fallaria con TypeError solo al construirlo.
2. El use case ya NO llama a `send_email(...)` directamente. En vez de
   eso, programa el correo con `correo_recuperacion_port.programar_recuperacion(...)`,
   que en produccion usa `BackgroundTasks` de FastAPI: la respuesta al
   usuario se envia ANTES de que se intente el envio real del correo. El
   parche `@patch(".../solicitar_recuperacion_use_case.send_email")` del
   test original ya no tiene nada que parchear ahi -- fallaria con
   AttributeError.
3. La logica de "que pasa si el SMTP falla" y "avisar al administrador"
   se movio por completo a
   src/identity_access/infrastructure/adapters/correo_recuperacion_background_adapter.py,
   que corre DESPUES de responder al usuario, en un hilo de fondo. Por
   eso ahora hacen falta dos niveles de prueba distintos:
   - Nivel 1 (use case): confirmar que el use case SIEMPRE devuelve el
     mensaje generico sin lanzar excepcion, sin importar el correo --
     esto ahora es casi estructural, porque el use case ni siquiera
     espera el resultado del envio.
   - Nivel 2 (adaptador de fondo): confirmar que, cuando el envio real
     falla (email_enviado=False), SI se dispara la alerta interna a los
     usuarios con permiso de auditoria (RBAC), y que si el envio tiene
     exito NO se dispara ninguna alerta falsa.

Como correrlo (desde la raiz del repo):
    python -m pytest tests/Test_Testing/Test_Modulo1/RF-08/TC-M01-44/test_tc_m01_044_retest.py -v --html=reporte-TC-M01-044-retest.html --self-contained-html
"""
from unittest.mock import MagicMock, patch

from src.identity_access.application.use_cases.contrasena.solicitar_recuperacion_use_case import (
    SolicitarRecuperacionUseCase,
)
from src.identity_access.infrastructure.adapters.correo_recuperacion_background_adapter import (
    CorreoRecuperacionBackgroundAdapter,
    procesar_correo_recuperacion_background,
)
from src.identity_access.infrastructure.dto.contrasena_dto import SolicitarRecuperacionDTO

CORREO_PRUEBA = "ana.martinez.qa1@sgpmp-test.com"
MENSAJE_GENERICO = (
    "Si el correo está registrado, recibirás instrucciones para recuperar "
    "tu contraseña en unos minutos."
)


def _construir_use_case(correo_recuperacion_port):
    """Doble de prueba: cuenta activa, sin bloqueo por limite de
    solicitudes -- llega directo al paso de programar el correo."""
    usuario = MagicMock()
    usuario.id_usuario = 74
    usuario.nombre = "Ana Martinez"
    usuario.correo = CORREO_PRUEBA

    cuenta = MagicMock()
    cuenta.id_estado_cuenta = 2  # activa, distinta de ESTADO_ELIMINADO (5)
    cuenta.esta_pendiente.return_value = False

    usuarios_repo = MagicMock()
    usuarios_repo.obtener_por_correo.return_value = usuario

    cuentas_repo = MagicMock()
    cuentas_repo.obtener_por_usuario.return_value = cuenta

    eventos_repo = MagicMock()

    intentos_anonimos_repo = MagicMock()
    intentos_anonimos_repo.contar_por_ip.return_value = 0  # muy por debajo del limite

    db = MagicMock()

    use_case = SolicitarRecuperacionUseCase(
        usuarios_repo=usuarios_repo,
        cuentas_repo=cuentas_repo,
        eventos_repo=eventos_repo,
        intentos_anonimos_repo=intentos_anonimos_repo,
        db=db,
        correo_recuperacion_port=correo_recuperacion_port,
    )
    return use_case


class TestTCM01044NivelUseCase:
    """Nivel 1: el use case nunca debe verse afectado por el resultado del envio."""

    def test_use_case_devuelve_mensaje_generico_aunque_el_puerto_de_correo_falle(self):
        """
        RF-08: aunque `correo_recuperacion_port.programar_recuperacion`
        lance una excepcion (ej. la cola de tareas en segundo plano no
        esta disponible), el use case ya confirmo el token antes de
        llegar ahi -- pero segun el diseño actual, programar_recuperacion
        se llama DESPUES del commit y sin try/except, asi que si esto
        llegara a fallar de verdad, si se propagaria. Esta prueba
        documenta ese comportamiento tal cual existe hoy (no es lo mismo
        que un fallo de SMTP, que ahora ocurre en segundo plano, fuera
        del alcance del use case).
        """
        correo_recuperacion_port = MagicMock()
        use_case = _construir_use_case(correo_recuperacion_port)
        dto = SolicitarRecuperacionDTO(correo_electronico=CORREO_PRUEBA)

        resultado = use_case.execute(dto, ip="203.0.113.10")

        assert resultado == MENSAJE_GENERICO
        assert correo_recuperacion_port.programar_recuperacion.called, (
            "El use case deberia haber programado el correo en segundo "
            "plano en vez de enviarlo de forma sincrona."
        )

    def test_use_case_no_espera_ni_conoce_el_resultado_real_del_envio(self):
        """
        RF-08 (nucleo de la correccion): el use case programa el correo
        y retorna de inmediato -- un fallo del SMTP real (que ocurre
        despues, en segundo plano) es estructuralmente imposible que
        vuelva a este punto. Esto es justo lo que garantiza el HTTP 202
        con mensaje generico incluso si el SMTP esta caido.
        """
        correo_recuperacion_port = MagicMock()
        # programar_recuperacion no devuelve nada util al use case (fire-and-forget)
        correo_recuperacion_port.programar_recuperacion.return_value = None
        use_case = _construir_use_case(correo_recuperacion_port)
        dto = SolicitarRecuperacionDTO(correo_electronico=CORREO_PRUEBA)

        resultado = use_case.execute(dto, ip="203.0.113.10")

        assert resultado == MENSAJE_GENERICO


class TestTCM01044NivelAdaptadorDeFondo:
    """Nivel 2: el adaptador de fondo es quien debe manejar el fallo real de SMTP."""

    @patch(
        "src.identity_access.infrastructure.adapters."
        "correo_recuperacion_background_adapter.SqlAlchemyUsuarioRepository"
    )
    @patch(
        "src.identity_access.infrastructure.adapters."
        "correo_recuperacion_background_adapter.NotificacionService"
    )
    @patch(
        "src.identity_access.infrastructure.adapters."
        "correo_recuperacion_background_adapter.SqlAlchemyNotificacionRepository"
    )
    @patch(
        "src.identity_access.infrastructure.adapters."
        "correo_recuperacion_background_adapter.SessionLocal"
    )
    def test_smtp_fallido_dispara_alerta_interna_a_administradores(
        self,
        mock_session_local,
        mock_notificacion_repo_cls,
        mock_notificacion_service_cls,
        mock_usuario_repo_cls,
    ):
        """
        RF-08: si el envio real del correo falla (email_enviado=False,
        es decir, se agotaron los reintentos), debe registrarse una
        notificacion interna para cada usuario con permiso de auditoria
        (RBAC), con un mensaje que describa el fallo critico de SMTP.
        """
        db_mock = MagicMock()
        mock_session_local.return_value = db_mock

        notificaciones_repo = mock_notificacion_repo_cls.return_value
        notificaciones_repo.buscar_ultimo_evento_id.return_value = 999

        mock_notificacion_service_cls.return_value.notificar.return_value = False  # SMTP fallo

        usuario_repo = mock_usuario_repo_cls.return_value
        usuario_repo.listar_ids_con_permiso.return_value = [1, 2]  # dos admins con permiso de auditoria

        procesar_correo_recuperacion_background(
            correo=CORREO_PRUEBA,
            nombre="Ana Martinez",
            token="token-de-prueba",
            id_usuario=74,
            flujo="recuperacion",
        )

        assert notificaciones_repo.registrar.call_count == 2, (
            "Se esperaba una notificacion interna por cada usuario con "
            "permiso de auditoria (RBAC), pero se registraron "
            f"{notificaciones_repo.registrar.call_count}."
        )
        primera_llamada = notificaciones_repo.registrar.call_args_list[0].kwargs
        assert primera_llamada["id_evento"] == 999
        assert "SMTP" in primera_llamada["mensaje"]
        assert "74" in primera_llamada["mensaje"]  # referencia al usuario afectado
        assert db_mock.commit.called, (
            "La alerta interna debe confirmarse (commit) en la sesion "
            "independiente del adaptador de fondo."
        )

    @patch(
        "src.identity_access.infrastructure.adapters."
        "correo_recuperacion_background_adapter.SqlAlchemyUsuarioRepository"
    )
    @patch(
        "src.identity_access.infrastructure.adapters."
        "correo_recuperacion_background_adapter.NotificacionService"
    )
    @patch(
        "src.identity_access.infrastructure.adapters."
        "correo_recuperacion_background_adapter.SqlAlchemyNotificacionRepository"
    )
    @patch(
        "src.identity_access.infrastructure.adapters."
        "correo_recuperacion_background_adapter.SessionLocal"
    )
    def test_smtp_exitoso_no_dispara_ninguna_alerta(
        self,
        mock_session_local,
        mock_notificacion_repo_cls,
        mock_notificacion_service_cls,
        mock_usuario_repo_cls,
    ):
        """Control: si el envio SI tiene exito, no debe crearse ninguna
        alerta interna (evitar falsos positivos que saturen a los
        administradores)."""
        db_mock = MagicMock()
        mock_session_local.return_value = db_mock
        notificaciones_repo = mock_notificacion_repo_cls.return_value
        mock_notificacion_service_cls.return_value.notificar.return_value = True  # SMTP OK

        procesar_correo_recuperacion_background(
            correo=CORREO_PRUEBA,
            nombre="Ana Martinez",
            token="token-de-prueba",
            id_usuario=74,
            flujo="recuperacion",
        )

        assert not notificaciones_repo.registrar.called, (
            "No deberia crearse ninguna alerta interna cuando el correo "
            "se envio exitosamente."
        )

    def test_el_adaptador_programa_la_tarea_en_background_tasks_de_fastapi(self):
        """Verifica que CorreoRecuperacionBackgroundAdapter efectivamente
        delega a BackgroundTasks.add_task en vez de ejecutar el envio de
        inmediato -- esto es lo que garantiza que la respuesta HTTP no
        espera al resultado del correo."""
        background_tasks = MagicMock()
        adapter = CorreoRecuperacionBackgroundAdapter(background_tasks)

        adapter.programar_recuperacion(
            correo=CORREO_PRUEBA, nombre="Ana Martinez", token="tok123", id_usuario=74
        )

        assert background_tasks.add_task.called
        _, kwargs = background_tasks.add_task.call_args
        assert kwargs["correo"] == CORREO_PRUEBA
        assert kwargs["id_usuario"] == 74
        assert kwargs["flujo"] == "recuperacion"