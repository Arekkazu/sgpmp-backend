"""Caso de uso: cierre de sesión voluntario."""
from sqlalchemy.orm import Session

from src.identity_access.domain.repositories.evento_repository import EventoRepository
from src.identity_access.domain.repositories.sesion_repository import SesionRepository

TIPO_CIERRE_SESION = 5


class LogoutUseCase:
    """Invalida la sesión activa del usuario y registra el evento de cierre."""

    def __init__(self, sesiones_repo: SesionRepository, eventos_repo: EventoRepository, db: Session):
        """Inicializa el use case.

        Args:
            sesiones_repo: Repositorio de dominio del agregado Sesion.
            eventos_repo: Repositorio de dominio de eventos (registro de auditoría).
            db: Sesión SQLAlchemy activa del request.
        """
        self.sesiones_repo = sesiones_repo
        self.eventos_repo = eventos_repo
        self.db = db

    def execute(self, id_token: int, id_usuario: int) -> None:
        """Cierra la sesión asociada al token del request actual.

        Si el token no tiene sesión asociada (ej: ya fue invalidada), registra
        el evento de cierre igualmente y retorna sin error.

        Args:
            id_token: ID del token JWT extraído del payload del request.
            id_usuario: ID del usuario autenticado que realiza el logout.
        """
        try:
            sesion = self.sesiones_repo.buscar_sesion_por_token(id_token)
            if sesion is not None:
                self.sesiones_repo.invalidar_sesion(sesion)

            self.eventos_repo.registrar(
                tipo_evento=TIPO_CIERRE_SESION,
                exitoso=True,
                id_usuario=id_usuario,
                detalle={"motivo": "cierre_voluntario"},
                id_sesion=sesion.id_sesion if sesion is not None else None,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
