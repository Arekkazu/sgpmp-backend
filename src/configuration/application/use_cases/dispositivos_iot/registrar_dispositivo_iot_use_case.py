"""Caso de uso: Registrar dispositivo IoT (POST RF-21)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.configuration.domain.entities.dispositivo_iot import DispositivoIot
from src.configuration.domain.repositories.auditoria_dispositivo_iot_repository import AuditoriaDispositivoIotRepository
from src.configuration.domain.repositories.dispositivo_iot_repository import DispositivoIotRepository
from src.configuration.domain.repositories.infraestructura_repository import InfraestructuraRepository
from src.configuration.domain.value_objects.serial_dispositivo import SerialDispositivo
from src.configuration.infrastructure.dto.registrar_dispositivo_iot_dto import RegistrarDispositivoIotDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, ConflictError, NotFoundError


class RegistrarDispositivoIotUseCase:

    def __init__(
        self,
        db: Session,
        dispositivo_repo: DispositivoIotRepository,
        infra_repo: InfraestructuraRepository,
        auditoria_repo: AuditoriaDispositivoIotRepository,
    ) -> None:
        self.db = db
        self.dispositivo_repo = dispositivo_repo
        self.infra_repo = infra_repo
        self.auditoria_repo = auditoria_repo

    def execute(self, dto: RegistrarDispositivoIotDTO, usuario_actual: UsuarioActual) -> DispositivoIot:
        area = self.infra_repo.obtener_por_id(dto.id_infraestructura)
        if area is None:
            raise NotFoundError(
                code="AREA_NO_ENCONTRADA",
                message=f"No existe un área productiva con ID {dto.id_infraestructura}.",
            )
        if not area.es_activo:
            raise BusinessRuleError(
                code="AREA_NO_DISPONIBLE",
                message="No se puede registrar el dispositivo porque el área productiva seleccionada está desactivada.",
            )

        serial = SerialDispositivo(dto.serial)

        existente = self.dispositivo_repo.obtener_por_serial(serial.valor)
        if existente is not None:
            raise ConflictError(
                code="SERIAL_DUPLICADO",
                message=f"El serial '{serial.valor}' ya está registrado en el sistema.",
                field="serial",
            )

        dispositivo = DispositivoIot.crear(
            serial=serial,
            descripcion=dto.descripcion,
            id_infraestructura=dto.id_infraestructura,
            es_activo=dto.es_activo,
        )

        try:
            dispositivo_guardado = self.dispositivo_repo.guardar(dispositivo)
            self.auditoria_repo.registrar(
                id_dispositivo_iot=dispositivo_guardado.id_dispositivo_iot,
                id_usuario=usuario_actual.id_usuario,
                tipo_operacion="CREATE",
                valores_nuevos=dispositivo_guardado._snapshot(),
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return dispositivo_guardado
