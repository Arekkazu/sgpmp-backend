"""Caso de uso: consulta del detalle completo de un usuario por un administrador.

El número de identificación se muestra completo solo si el actor tiene el permiso
E (Ejecutar) sobre el recurso Usuarios; en caso contrario se enmascara.

RF-12 pide además tres protecciones sobre esta vista, por tratarse de datos
personales: si la verificación del permiso falla se enmascara en vez de
reventar; si un mismo actor consulta fichas a un ritmo impropio de la
navegación manual se corta con 429; y si no se puede dejar rastro del acceso
en auditoría, la visualización se bloquea.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.identity_access.domain.repositories.evento_repository import EventoRepository
from src.identity_access.domain.repositories.permiso_repository import PermisoRepository
from src.identity_access.domain.repositories.usuario_repository import UsuarioRepository
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import InfrastructureError, NotFoundError, TooManyRequestsError

TIPO_CONSULTA_DETALLE_USUARIO = 18
ID_RECURSO_USUARIOS = 1
ID_ACCION_EJECUTAR = 5

# Umbral de extracción masiva. Un administrador abriendo fichas a mano no se
# acerca; un scraper lo cruza de inmediato. Son la perilla de calibración:
# subirlos o bajarlos no toca la lógica.
MAX_CONSULTAS_DETALLE_POR_VENTANA = 20
VENTANA_CONSULTAS_MINUTOS = 1


class ConsultarDetalleUsuarioUseCase:
    """Orquesta la consulta del detalle de un usuario con enmascarado condicional de ID."""

    def __init__(
        self,
        usuarios_repo: UsuarioRepository,
        permisos_repo: PermisoRepository,
        eventos_repo: EventoRepository,
        db: Session,
    ):
        """Inicializa el use case.

        Args:
            usuarios_repo: Repositorio de dominio del agregado Usuario (proyección de lectura).
            permisos_repo: Repositorio de dominio de permisos (verificación del permiso E).
            eventos_repo: Repositorio de dominio de eventos (registro de auditoría).
            db: Sesión SQLAlchemy activa del request.
        """
        self.usuarios_repo = usuarios_repo
        self.permisos_repo = permisos_repo
        self.eventos_repo = eventos_repo
        self.db = db

    def execute(self, id_usuario: int, usuario_actual: UsuarioActual) -> dict:
        """Retorna el detalle del usuario con enmascarado según permisos del actor.

        Args:
            id_usuario: ID del usuario a consultar.
            usuario_actual: Administrador que realiza la consulta.

        Returns:
            Diccionario con los datos del usuario. El `numero_identificacion`
            aparece completo si el actor tiene el permiso Ejecutar sobre
            el recurso Usuarios; de lo contrario se enmascara.

        Raises:
            NotFoundError: Si el usuario no existe. HTTP 404.
            TooManyRequestsError: Si el actor superó el umbral de consultas de
                detalle en la ventana vigente. HTTP 429.
            InfrastructureError: Si no se pudo registrar la auditoría obligatoria
                del acceso. HTTP 500.
        """
        self._verificar_ritmo_de_consulta(usuario_actual)

        detalle = self.usuarios_repo.obtener_detalle(id_usuario)
        if detalle is None:
            raise NotFoundError(
                code="USUARIO_NO_ENCONTRADO",
                message="Consulta fallida: El usuario solicitado no existe o ha sido retirado del sistema.",
            )

        tiene_id_completo = self._puede_ver_identificacion_completa(usuario_actual)

        numero_identificacion = (
            detalle.numero_identificacion
            if tiene_id_completo
            else self._enmascarar(detalle.numero_identificacion)
        )

        # La auditoría es condición para entregar los datos, no un efecto
        # secundario: si no se puede dejar rastro, RF-12 exige bloquear la
        # visualización en vez de servirla sin trazabilidad.
        try:
            self.eventos_repo.registrar(
                tipo_evento=TIPO_CONSULTA_DETALLE_USUARIO,
                exitoso=True,
                id_usuario=usuario_actual.id_usuario,
                detalle={
                    "id_usuario_consultado": id_usuario,
                    "tiene_id_completo": tiene_id_completo,
                },
            )
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            raise InfrastructureError(
                code="AUDITORIA_NO_DISPONIBLE",
                message=(
                    "Error de seguridad: No se pudo garantizar la trazabilidad de la "
                    "consulta. La visualización de datos sensibles ha sido bloqueada "
                    "preventivamente."
                ),
                original_error=exc,
            ) from exc

        return {
            "id_usuario": detalle.id_usuario,
            "nombre": detalle.nombre,
            "apellidos": detalle.apellidos,
            "correo_electronico": detalle.correo_electronico,
            "tipo_identificacion": detalle.tipo_identificacion,
            "numero_identificacion": numero_identificacion,
            "fecha_nacimiento": detalle.fecha_nacimiento,
            "fecha_registro": detalle.fecha_registro,
            "nombre_rol": detalle.nombre_rol,
            "estado_cuenta": detalle.estado_cuenta,
            "version": detalle.version,
        }

    def _puede_ver_identificacion_completa(self, usuario_actual: UsuarioActual) -> bool:
        """Indica si el actor tiene activo el permiso E sobre el recurso Usuarios.

        Ante cualquier fallo al resolver el permiso retorna ``False``: RF-12
        exige priorizar la privacidad sobre la visualización, así que un
        servicio de permisos caído enmascara en vez de tumbar la consulta.

        Se exige ``es_activo`` porque ``PermisoRepository.buscar`` no lo filtra
        —``AsignarPermisoUseCase`` lo usa para detectar duplicados y necesita
        ver también los inactivos—, mientras que ``require_permission`` sí lo
        hace. Sin esta condición un permiso desactivado seguiría concediendo el
        número completo.
        """
        try:
            permiso = self.permisos_repo.buscar(
                id_rol=usuario_actual.id_rol,
                id_recurso=ID_RECURSO_USUARIOS,
                id_accion=ID_ACCION_EJECUTAR,
            )
        except Exception:
            return False
        return permiso is not None and bool(permiso.es_activo)

    def _verificar_ritmo_de_consulta(self, usuario_actual: UsuarioActual) -> None:
        """Corta la consulta si el actor está extrayendo fichas de forma masiva.

        La ventana se calcula sobre los eventos de auditoría que esta misma
        vista ya registra (tipo 18), así que no hace falta ningún contador
        aparte. El intento bloqueado se registra como evento fallido —es la
        alerta de seguridad que pide RF-12— y se hace ``commit`` antes de
        lanzar, porque de lo contrario la alerta se perdería al cerrar la
        sesión sin confirmar.

        Raises:
            TooManyRequestsError: Si se alcanzó el umbral de la ventana. HTTP 429.
        """
        desde = datetime.now(timezone.utc) - timedelta(minutes=VENTANA_CONSULTAS_MINUTOS)
        consultas = self.eventos_repo.contar_consultas_detalle_usuario(
            id_usuario=usuario_actual.id_usuario,
            desde=desde,
        )
        if consultas < MAX_CONSULTAS_DETALLE_POR_VENTANA:
            return

        try:
            self.eventos_repo.registrar(
                tipo_evento=TIPO_CONSULTA_DETALLE_USUARIO,
                exitoso=False,
                id_usuario=usuario_actual.id_usuario,
                detalle={
                    "motivo": "PATRON_CONSULTA_INUSUAL",
                    "consultas_en_ventana": consultas,
                    "umbral": MAX_CONSULTAS_DETALLE_POR_VENTANA,
                    "ventana_minutos": VENTANA_CONSULTAS_MINUTOS,
                },
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        raise TooManyRequestsError(
            code="PATRON_CONSULTA_INUSUAL",
            message=(
                "Alerta de seguridad: Patrón de consulta inusual detectado. Su acceso a "
                "vistas detalladas ha sido restringido temporalmente por protección de datos."
            ),
        )

    def _enmascarar(self, numero: Optional[str]) -> Optional[str]:
        """Enmascara el número de identificación dejando visibles los 4 primeros dígitos.

        Args:
            numero: Número de identificación completo, o ``None`` en una cuenta
                SSO mínima (``Pendiente Datos``) que aún no lo tiene.

        Returns:
            Número con los últimos caracteres reemplazados por asteriscos, o
            ``None`` si no había número que enmascarar.
        """
        if numero is None:
            return None
        if len(numero) <= 4:
            return "*" * len(numero)
        return numero[:4] + "*" * (len(numero) - 4)
