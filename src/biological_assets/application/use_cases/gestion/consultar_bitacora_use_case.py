from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.biological_assets.domain.entities.activo_biologico import EventoAuditoria
from src.biological_assets.domain.repositories.bitacora_auditoria_repository import BitacoraAuditoriaRepository
from src.biological_assets.infrastructure.dto.consultar_bitacora_dto import ConsultarBitacoraDTO
from src.identity_access.domain.repositories.rol_repository import RolRepository
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import AuthorizationError


_CLASIFICACIONES_CONTADOR = {'TRANSFORMACION_BIOLOGICA', 'SANITARIO'}
_ACCESO_DATOS = 'ACCESO_DATOS'


class ConsultarBitacoraUseCase:

    def __init__(
        self,
        db: Session,
        bitacora_repo: BitacoraAuditoriaRepository,
        rol_repo: RolRepository,
    ) -> None:
        self.db = db
        self.bitacora_repo = bitacora_repo
        self.rol_repo = rol_repo

    def execute(
        self,
        dto: ConsultarBitacoraDTO,
        usuario_actual: UsuarioActual,
    ) -> tuple[list[EventoAuditoria], int]:
        rol = self.rol_repo.obtener_por_id(usuario_actual.id_rol)
        nombre_rol = rol.nombre_rol.strip().casefold() if rol else ''
        clasificacion = (
            dto.clasificacion_biologica.strip().upper()
            if dto.clasificacion_biologica
            else None
        )

        clasificaciones_permitidas = None
        id_propietario_acceso_datos = None

        if nombre_rol == 'contador':
            if clasificacion is not None and clasificacion not in _CLASIFICACIONES_CONTADOR:
                self._denegar(
                    usuario_actual,
                    dto,
                    nombre_rol='Contador',
                    motivo=(
                        'El rol Contador solo puede consultar eventos de clasificación '
                        'TRANSFORMACION_BIOLOGICA o SANITARIO.'
                    ),
                )
            clasificaciones_permitidas = _CLASIFICACIONES_CONTADOR

        elif nombre_rol == 'productor':
            if (
                clasificacion == _ACCESO_DATOS
                and dto.id_activo_biologico is not None
                and not self.bitacora_repo.activo_pertenece_a_usuario(
                    dto.id_activo_biologico,
                    usuario_actual.id_usuario,
                )
            ):
                self._denegar(
                    usuario_actual,
                    dto,
                    nombre_rol='Productor',
                    motivo=(
                        'El Productor no puede consultar eventos ACCESO_DATOS '
                        'de activos que no le pertenecen.'
                    ),
                )
            # También cubre consultas sin clasificación: los ACCESO_DATOS de
            # activos ajenos se excluyen aunque compartan página con otras clases.
            if clasificacion in {None, _ACCESO_DATOS}:
                id_propietario_acceso_datos = usuario_actual.id_usuario

        return self.bitacora_repo.consultar(
            rf_origen=dto.rf_origen,
            tipo_evento=dto.tipo_evento,
            id_activo_biologico=dto.id_activo_biologico,
            clasificacion_biologica=clasificacion,
            resultado=dto.resultado,
            severidad_log=dto.severidad_log,
            fecha_inicio=dto.fecha_inicio,
            fecha_fin=dto.fecha_fin,
            pagina=dto.pagina,
            page_size=dto.page_size,
            clasificaciones_permitidas=clasificaciones_permitidas,
            id_propietario_acceso_datos=id_propietario_acceso_datos,
        )

    def _denegar(
        self,
        usuario_actual: UsuarioActual,
        dto: ConsultarBitacoraDTO,
        *,
        nombre_rol: str,
        motivo: str,
    ) -> None:
        try:
            self.bitacora_repo.registrar(
                EventoAuditoria(
                    rf_origen='RF52',
                    tipo_evento='ACCESO_NO_AUTORIZADO',
                    clasificacion_biologica='ACCESO_DATOS',
                    timestamp_evento=datetime.now(timezone.utc),
                    resultado='RECHAZADO',
                    severidad_log='WARNING',
                    id_activo_biologico=dto.id_activo_biologico,
                    descripcion=motivo,
                    detalle_tecnico={
                        'rol': nombre_rol,
                        'clasificacion_solicitada': dto.clasificacion_biologica,
                    },
                    id_usuario_responsable=usuario_actual.id_usuario,
                )
            )
            self.db.commit()
        except Exception:
            self.db.rollback()

        raise AuthorizationError(
            code='ALCANCE_BITACORA_DENEGADO',
            message=motivo,
        )
