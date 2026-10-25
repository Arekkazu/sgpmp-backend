# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-20 | Arekkazu | DEV-25 RF-17: marcar o desmarcar una variable como crítica, con auditoría (RFC-016) |
"""Caso de uso: marcar una variable ambiental como crítica (RFC-016 B.7, RF-17).

El permiso (solo Administrador, DB-08) lo exige el router. El cambio queda en la
bitácora central de auditoría (``modulo1.eventos``) con los valores anterior y nuevo.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.configuration.domain.entities.variable_ambiental import VariableAmbiental
from src.configuration.domain.repositories.variable_ambiental_repository import VariableAmbientalRepository
from src.identity_access.domain.repositories.evento_repository import EventoRepository
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import NotFoundError

TIPO_EVENTO_CAMBIO_VARIABLE_CRITICA = 31  # modulo1.tipos_eventos 'CAMBIO_VARIABLE_CRITICA' (DBA)


class ActualizarVariableCriticaUseCase:

    def __init__(self, db: Session, variable_repo: VariableAmbientalRepository, eventos_repo: EventoRepository) -> None:
        self.db = db
        self.variable_repo = variable_repo
        self.eventos_repo = eventos_repo

    def execute(self, id_variable_ambiental: int, es_critica: bool, usuario_actual: UsuarioActual) -> VariableAmbiental:
        variable = self.variable_repo.obtener_por_id(id_variable_ambiental)
        if variable is None:
            raise NotFoundError(
                code="VARIABLE_AMBIENTAL_NO_ENCONTRADA",
                message=f"No existe una variable ambiental con ID {id_variable_ambiental}.",
            )
        if variable.es_critica == es_critica:
            return variable

        anterior = variable._snapshot()
        variable.es_critica = es_critica
        try:
            actualizada = self.variable_repo.actualizar(variable)
            self.eventos_repo.registrar(
                tipo_evento=TIPO_EVENTO_CAMBIO_VARIABLE_CRITICA,
                exitoso=True,
                id_usuario=usuario_actual.id_usuario,
                detalle={"valores_anteriores": anterior, "valores_nuevos": actualizada._snapshot()},
                descripcion=f"Variable ambiental '{actualizada.nombre}' {'marcada' if es_critica else 'desmarcada'} como crítica",
                modulo="MODULO9",
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return actualizada
