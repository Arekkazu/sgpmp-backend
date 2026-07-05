from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.biological_assets.domain.entities.activo_biologico import EventoAuditoria, Transferencia
from src.biological_assets.domain.repositories.activo_biologico_repository import ActivoBiologicoRepository
from src.biological_assets.domain.repositories.bitacora_auditoria_repository import BitacoraAuditoriaRepository
from src.biological_assets.domain.repositories.infraestructura_consulta_port import InfraestructuraConsultaPort
from src.biological_assets.domain.repositories.transferencia_repository import TransferenciaRepository
from src.biological_assets.domain.value_objects.estado_activo import EstadoActivo
from src.biological_assets.infrastructure.dto.registrar_transferencia_dto import RegistrarTransferenciaDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, ConflictError, NotFoundError, ValidationError


class RegistrarTransferenciaUseCase:

    def __init__(
        self,
        db: Session,
        activo_repo: ActivoBiologicoRepository,
        transferencia_repo: TransferenciaRepository,
        infra_port: InfraestructuraConsultaPort,
        bitacora_repo: BitacoraAuditoriaRepository | None = None,
    ) -> None:
        self.db = db
        self.activo_repo = activo_repo
        self.transferencia_repo = transferencia_repo
        self.infra_port = infra_port
        self.bitacora_repo = bitacora_repo

    def execute(self, id_activo: int, dto: RegistrarTransferenciaDTO, usuario: UsuarioActual) -> Transferencia:
        # E-01: control de concurrencia — bloquea el registro para evitar transferencias simultáneas
        hay_concurrencia = self.transferencia_repo.hay_transferencia_en_progreso(id_activo)
        if hay_concurrencia:
            raise ConflictError(
                code='TRANSFERENCIA_CONCURRENTE',
                message=(
                    f'Existe una operación de transferencia en progreso para el activo {id_activo}. '
                    'Espere a que finalice e intente nuevamente.'
                ),
            )

        # E-02: el activo debe existir
        activo = self.activo_repo.obtener_por_id(id_activo)
        if activo is None:
            raise NotFoundError(
                code='ACTIVO_NO_ENCONTRADO',
                message=f'El activo biológico con id {id_activo} no fue encontrado en el sistema.',
            )

        # E-03: el activo debe estar en estado ACTIVO
        if activo.id_estado != EstadoActivo.ACTIVO:
            raise ConflictError(
                code='ACTIVO_NO_ACTIVO',
                message=(
                    f'El activo {activo.identificador} se encuentra en estado {activo.nombre_estado}. '
                    'Solo se pueden transferir activos en estado ACTIVO.'
                ),
            )

        # E-04: el activo debe tener infraestructura origen activa
        asociacion_actual = self.activo_repo.obtener_asociacion_activa(id_activo)
        if asociacion_actual is None:
            raise ValidationError(
                code='SIN_INFRAESTRUCTURA_ORIGEN',
                message=(
                    f'El activo {activo.identificador} no tiene una infraestructura origen registrada. '
                    'Asocie el activo a una infraestructura antes de realizar la transferencia.'
                ),
            )

        # Verificar que la infra origen del activo coincide con la del DTO
        if asociacion_actual.id_infraestructura != dto.infraestructura_origen_id:
            raise ValidationError(
                code='INFRAESTRUCTURA_ORIGEN_INCORRECTA',
                message=(
                    f'La infraestructura origen indicada no coincide con la asociación activa del activo. '
                    f'La infraestructura actual es: {asociacion_actual.nombre_infraestructura}.'
                ),
                field='infraestructura_origen_id',
            )

        # E-05: infraestructura destino debe existir y estar activa
        infra_destino = self.infra_port.obtener_activa(dto.infraestructura_destino_id)
        if infra_destino is None:
            raise ValidationError(
                code='INFRAESTRUCTURA_DESTINO_INVALIDA',
                message=f'La infraestructura con id {dto.infraestructura_destino_id} no existe o no está activa.',
                field='infraestructura_destino_id',
            )

        # E-06: destino distinto al origen
        if dto.infraestructura_destino_id == dto.infraestructura_origen_id:
            raise ValidationError(
                code='DESTINO_IGUAL_ORIGEN',
                message='La infraestructura destino debe ser diferente a la infraestructura origen del activo.',
                field='infraestructura_destino_id',
            )

        # E-07: compatibilidad C1 — especie
        if infra_destino.id_especie is not None and infra_destino.id_especie != activo.id_especie:
            raise BusinessRuleError(
                code='INCOMPATIBILIDAD_ESPECIE',
                message=(
                    f'La infraestructura {infra_destino.nombre} no está habilitada para la especie del activo. '
                    'Seleccione una infraestructura compatible con la especie.'
                ),
                field='infraestructura_destino_id',
            )

        # E-09: capacidad C3
        if infra_destino.capacidad_maxima is not None:
            cantidad_activo = 1
            if activo.tipo == 'POBLACIONAL' and activo.detalle_poblacional:
                cantidad_activo = activo.detalle_poblacional.cantidad_actual or 1
            ocupacion_actual = self.infra_port.calcular_ocupacion(dto.infraestructura_destino_id)
            if ocupacion_actual + cantidad_activo > infra_destino.capacidad_maxima:
                raise BusinessRuleError(
                    code='CAPACIDAD_EXCEDIDA',
                    message=(
                        f'La infraestructura {infra_destino.nombre} no tiene capacidad disponible. '
                        f'Capacidad máxima: {infra_destino.capacidad_maxima}, '
                        f'ocupación actual: {ocupacion_actual}.'
                    ),
                    field='infraestructura_destino_id',
                )

        fecha_dt = datetime(
            dto.fecha_transferencia.year,
            dto.fecha_transferencia.month,
            dto.fecha_transferencia.day,
            tzinfo=timezone.utc,
        )
        # Use actual current timestamp for historial operations to satisfy
        # chk_historial_fechas (fecha_fin must be > fecha_inicio of the row being closed)
        ahora = datetime.now(tz=timezone.utc)

        transferencia = Transferencia(
            id_activo_biologico=id_activo,
            id_infraestructura_origen=dto.infraestructura_origen_id,
            id_infraestructura_destino=dto.infraestructura_destino_id,
            nombre_infra_origen=asociacion_actual.nombre_infraestructura,
            nombre_infra_destino=infra_destino.nombre,
            fecha_transferencia=fecha_dt,
            motivo_transferencia=dto.motivo_transferencia,
            id_usuario=usuario.id_usuario,
        )

        try:
            # a) Cerrar asociación origen en historial_infraestructura_activo
            self.db.execute(
                text(
                    'UPDATE modulo2.historial_infraestructura_activo '
                    'SET fecha_fin = :ahora '
                    'WHERE id_activo_biologico = :id AND fecha_fin IS NULL'
                ),
                {'id': id_activo, 'ahora': ahora},
            )

            # b) Abrir nueva asociación con destino
            self.db.execute(
                text(
                    'INSERT INTO modulo2.historial_infraestructura_activo '
                    '(id_activo_biologico, id_infraestructura, fecha_inicio, fecha_fin, id_usuario_registro) '
                    'VALUES (:id_activo, :id_infra, :fecha, NULL, :id_usuario)'
                ),
                {
                    'id_activo': id_activo,
                    'id_infra': dto.infraestructura_destino_id,
                    'fecha': ahora,
                    'id_usuario': usuario.id_usuario,
                },
            )

            # c) Actualizar id_infraestructura en activos_biologicos (trigger requiere app.usuario_id)
            self.db.execute(text('SET LOCAL app.usuario_id = :uid'), {'uid': usuario.id_usuario})
            self.db.execute(
                text(
                    'UPDATE modulo2.activos_biologicos '
                    'SET id_infraestructura = :id_infra '
                    'WHERE id_activo_biologico = :id'
                ),
                {'id': id_activo, 'id_infra': dto.infraestructura_destino_id},
            )

            # d) Registrar evento en movimientos
            resultado = self.transferencia_repo.guardar(transferencia)

            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            if self.bitacora_repo:
                try:
                    self.bitacora_repo.registrar(EventoAuditoria(
                        rf_origen='RF48', tipo_evento='TRANSFERENCIA_FALLIDA',
                        clasificacion_biologica='GESTION_OPERATIVA', resultado='FALLIDO',
                        severidad_log='ERROR', timestamp_evento=datetime.now(timezone.utc),
                        id_activo_biologico=id_activo, tipo_activo=activo.tipo,
                        detalle_tecnico={'error': str(exc), 'destino': dto.infraestructura_destino_id},
                        id_usuario_responsable=usuario.id_usuario,
                    ))
                    self.db.commit()
                except Exception:
                    pass
            raise

        if self.bitacora_repo:
            try:
                self.bitacora_repo.registrar(EventoAuditoria(
                    rf_origen='RF48', tipo_evento='TRANSFERENCIA_REGISTRADA',
                    clasificacion_biologica='GESTION_OPERATIVA', resultado='EXITOSO',
                    severidad_log='INFO', timestamp_evento=datetime.now(timezone.utc),
                    id_activo_biologico=id_activo, tipo_activo=activo.tipo,
                    descripcion=f'Transferencia: {transferencia.nombre_infra_origen} → {transferencia.nombre_infra_destino}',
                    detalle_tecnico={
                        'origen': dto.infraestructura_origen_id,
                        'destino': dto.infraestructura_destino_id,
                        'motivo': dto.motivo_transferencia,
                    },
                    id_usuario_responsable=usuario.id_usuario,
                ))
                self.db.commit()
            except Exception:
                pass

        return resultado

    def listar_infraestructuras_disponibles(
        self, id_activo: int, usuario: UsuarioActual
    ) -> list[dict]:
        """Retorna infraestructuras activas distintas a la actual del activo."""
        activo = self.activo_repo.obtener_por_id(id_activo)
        if activo is None:
            raise NotFoundError(
                code='ACTIVO_NO_ENCONTRADO',
                message=f'El activo biológico con id {id_activo} no fue encontrado en el sistema.',
            )
        infras = self.infra_port.listar_activas(excluir_id=activo.id_infraestructura)
        return [
            {
                'id_infraestructura': i.id_infraestructura,
                'nombre': i.nombre,
                'tipo': i.tipo,
                'capacidad_maxima': i.capacidad_maxima,
                'id_especie': i.id_especie,
            }
            for i in infras
        ]
