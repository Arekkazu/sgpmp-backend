"""Caso de uso: Consultar dispositivos IoT (GET RF-21)."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.configuration.domain.entities.dispositivo_iot import DispositivoIot
from src.configuration.domain.repositories.auditoria_dispositivo_iot_repository import AuditoriaDispositivoIotRepository
from src.configuration.domain.repositories.dispositivo_iot_repository import DispositivoIotRepository
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import NotFoundError


class ConsultarDispositivosIotUseCase:

    def __init__(
        self,
        db: Session,
        dispositivo_repo: DispositivoIotRepository,
        auditoria_repo: AuditoriaDispositivoIotRepository,
    ) -> None:
        self.db = db
        self.dispositivo_repo = dispositivo_repo
        self.auditoria_repo = auditoria_repo

    def listar(
        self,
        usuario_actual: UsuarioActual,
        *,
        solo_activos: bool = False,
        ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> list[DispositivoIot]:
        dispositivos = self.dispositivo_repo.listar(
            solo_activos=solo_activos, ids_fincas_permitidas=ids_fincas_permitidas
        )
        for dispositivo in dispositivos:
            try:
                self.auditoria_repo.registrar(
                    id_dispositivo_iot=dispositivo.id_dispositivo_iot,
                    id_usuario=usuario_actual.id_usuario,
                    tipo_operacion="GET",
                    valores_nuevos=dispositivo._snapshot(),
                )
                self.db.commit()
            except Exception:
                self.db.rollback()
        return dispositivos

    def obtener(
        self,
        id_dispositivo_iot: int,
        usuario_actual: UsuarioActual,
        *,
        ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> DispositivoIot:
        dispositivo = self.dispositivo_repo.obtener_por_id(
            id_dispositivo_iot, ids_fincas_permitidas=ids_fincas_permitidas
        )
        if dispositivo is None:
            raise NotFoundError(
                code="DISPOSITIVO_NO_ENCONTRADO",
                message=f"No existe un dispositivo IoT con ID {id_dispositivo_iot}.",
            )
        try:
            self.auditoria_repo.registrar(
                id_dispositivo_iot=dispositivo.id_dispositivo_iot,
                id_usuario=usuario_actual.id_usuario,
                tipo_operacion="GET",
                valores_nuevos=dispositivo._snapshot(),
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
        return dispositivo
