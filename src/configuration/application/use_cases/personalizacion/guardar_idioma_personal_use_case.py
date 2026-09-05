"""Caso de uso: Guardar preferencia de idioma personal del usuario (PATCH RF-29)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.configuration.domain.entities.preferencia_idioma import PreferenciaIdioma
from src.configuration.domain.repositories.preferencia_idioma_repository import PreferenciaIdiomaRepository
from src.configuration.infrastructure.dto.guardar_idioma_dto import GuardarIdiomaDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import AppError, ConflictError, InfrastructureError


class GuardarIdiomaPersonalUseCase:

    def __init__(self, db: Session, idioma_repo: PreferenciaIdiomaRepository) -> None:
        self.db = db
        self.idioma_repo = idioma_repo

    def execute(self, dto: GuardarIdiomaDTO, usuario_actual: UsuarioActual) -> PreferenciaIdioma:
        self._verificar_perfil_vigente(dto, usuario_actual)

        existente = self.idioma_repo.obtener_por_usuario(usuario_actual.id_usuario)

        try:
            if existente is not None:
                existente.actualizar(locale_code=dto.locale_code)
                resultado = self.idioma_repo.actualizar(existente)
            else:
                nuevo = PreferenciaIdioma.crear_personal(
                    id_usuario=usuario_actual.id_usuario,
                    locale_code=dto.locale_code,
                )
                resultado = self.idioma_repo.guardar(nuevo)
            self.db.commit()
        except AppError:
            self.db.rollback()
            raise
        except Exception as exc:
            self.db.rollback()
            raise InfrastructureError(
                code="ERROR_PERSISTENCIA_IDIOMA",
                message=(
                    "Error de persistencia: No se pudo guardar su preferencia de idioma. "
                    "El cambio se aplicará temporalmente en esta sesión, pero se "
                    "perderá al cerrar el navegador."
                ),
                original_error=exc,
                field="locale_code",
            ) from exc

        return resultado

    def _verificar_perfil_vigente(
        self,
        dto: GuardarIdiomaDTO,
        usuario_actual: UsuarioActual,
    ) -> None:
        """FA del RF-29: el perfil del usuario cambió mientras editaba su idioma.

        Mismo mecanismo que RF-28 (``guardar_dashboard_use_case``): el cliente
        devuelve la ``version_perfil`` que recibió en el GET y se compara contra
        ``modulo1.usuarios.version``. Es opcional para no romper a los clientes
        que todavía no la envían.
        """
        if dto.version_perfil is None:
            return
        version_actual = self.idioma_repo.version_perfil(usuario_actual.id_usuario)
        if version_actual is not None and version_actual != dto.version_perfil:
            raise ConflictError(
                code="CONFLICTO_PERFIL_MODIFICADO",
                message=(
                    "Conflicto de datos: No se pudo actualizar el idioma porque su "
                    "perfil está siendo modificado en este momento. Intente de nuevo "
                    "en unos segundos."
                ),
                field="version_perfil",
            )

