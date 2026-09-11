"""Caso de uso: Editar finca existente (PATCH RF-19). Concurrencia optimista (FA-14)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.configuration.domain.entities.finca import Finca
from src.configuration.domain.repositories.auditoria_finca_repository import AuditoriaFincaRepository
from src.configuration.domain.repositories.finca_repository import FincaRepository
from src.configuration.domain.value_objects.nombre_finca import NombreFinca
from src.configuration.domain.value_objects.tamano_h import TamanoH
from src.configuration.domain.value_objects.ubicacion_finca import UbicacionFinca
from src.configuration.infrastructure.dto.editar_finca_dto import EditarFincaDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import ConflictError, NotFoundError, PreconditionFailedError


class EditarFincaUseCase:

    def __init__(
        self,
        db: Session,
        finca_repo: FincaRepository,
        auditoria_repo: AuditoriaFincaRepository,
    ) -> None:
        self.db = db
        self.finca_repo = finca_repo
        self.auditoria_repo = auditoria_repo

    def execute(self, id_finca: int, dto: EditarFincaDTO, usuario_actual: UsuarioActual) -> Finca:
        finca = self.finca_repo.obtener_por_id(id_finca)
        if finca is None:
            raise NotFoundError(code="FINCA_NO_ENCONTRADA", message=f"No existe una finca con ID {id_finca}.")

        ts_actual = finca.fecha_actualizacion
        ts_dto = dto.fecha_actualizacion
        if ts_actual is not None and ts_dto is not None:
            if ts_actual.astimezone(timezone.utc) != ts_dto.astimezone(timezone.utc):
                raise PreconditionFailedError(
                    code="CONFLICTO_CONCURRENCIA",
                    message="El registro fue modificado por otro usuario. Recarga y reintenta.",
                )
        elif ts_actual != ts_dto:
            raise PreconditionFailedError(
                code="CONFLICTO_CONCURRENCIA",
                message="El registro fue modificado por otro usuario. Recarga y reintenta.",
            )

        nombre = NombreFinca(dto.nombre)
        if nombre.normalizado() != finca.nombre.normalizado():
            existente = self.finca_repo.obtener_por_nombre(nombre)
            if existente is not None and existente.id_finca != id_finca:
                raise ConflictError(
                    code="FINCA_DUPLICADA",
                    message=f"Ya existe una finca con el nombre '{nombre.valor}' en el sistema.",
                    field="nombre",
                )

        snapshot_anterior = finca._snapshot()

        ubicacion = UbicacionFinca(
            departamento=dto.ubicacion.departamento,
            municipio=dto.ubicacion.municipio,
            vereda=dto.ubicacion.vereda,
            latitud=dto.ubicacion.latitud,
            longitud=dto.ubicacion.longitud,
        )
        tamano = TamanoH(dto.tamano_h)

        finca.actualizar(
            nombre=nombre,
            ubicacion=ubicacion,
            tamano_h=tamano,
            fecha_actualizacion=datetime.now(timezone.utc),
        )

        try:
            finca_actualizada = self.finca_repo.actualizar(finca)
            self.auditoria_repo.registrar(
                id_finca=finca_actualizada.id_finca,
                id_usuario=usuario_actual.id_usuario,
                tipo_operacion="UPDATE",
                valores_nuevos=finca_actualizada._snapshot(),
                valores_anteriores=snapshot_anterior,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return finca_actualizada
