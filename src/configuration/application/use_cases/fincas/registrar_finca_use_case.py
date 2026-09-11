"""Caso de uso: Registrar nueva finca (POST RF-19)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.configuration.domain.entities.finca import Finca
from src.configuration.domain.repositories.auditoria_finca_repository import AuditoriaFincaRepository
from src.configuration.domain.repositories.finca_repository import FincaRepository
from src.configuration.domain.value_objects.nombre_finca import NombreFinca
from src.configuration.domain.value_objects.tamano_h import TamanoH
from src.configuration.domain.value_objects.ubicacion_finca import UbicacionFinca
from src.configuration.infrastructure.dto.registrar_finca_dto import RegistrarFincaDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import ConflictError


class RegistrarFincaUseCase:

    def __init__(
        self,
        db: Session,
        finca_repo: FincaRepository,
        auditoria_repo: AuditoriaFincaRepository,
    ) -> None:
        self.db = db
        self.finca_repo = finca_repo
        self.auditoria_repo = auditoria_repo

    def execute(self, dto: RegistrarFincaDTO, usuario_actual: UsuarioActual) -> Finca:
        nombre = NombreFinca(dto.nombre)

        existente = self.finca_repo.obtener_por_nombre(nombre)
        if existente is not None:
            raise ConflictError(
                code="FINCA_DUPLICADA",
                message=f"Ya existe una finca con el nombre '{nombre.valor}' en el sistema.",
                field="nombre",
            )

        ubicacion = UbicacionFinca(
            departamento=dto.ubicacion.departamento,
            municipio=dto.ubicacion.municipio,
            vereda=dto.ubicacion.vereda,
            latitud=dto.ubicacion.latitud,
            longitud=dto.ubicacion.longitud,
        )
        tamano = TamanoH(dto.tamano_h)
        ahora = datetime.now(timezone.utc)

        finca = Finca.crear(
            nombre=nombre,
            ubicacion=ubicacion,
            tamano_h=tamano,
            id_usuario=dto.id_usuario,
            fecha_creacion=ahora,
            fecha_actualizacion=ahora,
        )

        try:
            finca_guardada = self.finca_repo.guardar(finca)
            self.auditoria_repo.registrar(
                id_finca=finca_guardada.id_finca,
                id_usuario=usuario_actual.id_usuario,
                tipo_operacion="CREATE",
                valores_nuevos=finca_guardada._snapshot(),
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return finca_guardada
