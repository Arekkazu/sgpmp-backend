from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.biological_assets.domain.entities.activo_biologico import (
    EventoAuditoria,
    HistorialInfraestructura,
    ResultadoConsultaAsociacion,
)
from src.biological_assets.domain.repositories.activo_biologico_repository import ActivoBiologicoRepository
from src.biological_assets.domain.repositories.bitacora_auditoria_repository import BitacoraAuditoriaRepository
from src.biological_assets.domain.repositories.infraestructura_consulta_port import InfraestructuraConsultaPort
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import NotFoundError, ValidationError


def _detectar_solapamiento(historial: list[HistorialInfraestructura]) -> Optional[str]:
    """Detecta si dos o más períodos de asociación a infraestructura del mismo activo se solapan."""
    periodos = sorted(historial, key=lambda h: h.fecha_inicio)
    fin_abierto = datetime.max.replace(tzinfo=timezone.utc)
    for i in range(len(periodos)):
        fin_i = periodos[i].fecha_fin or fin_abierto
        for j in range(i + 1, len(periodos)):
            if periodos[j].fecha_inicio < fin_i:
                return (
                    'Se detectó solapamiento entre los períodos de asociación a infraestructura '
                    f'con id_historial {periodos[i].id_historial} y {periodos[j].id_historial}.'
                )
    return None


class ConsultarAsociacionUseCase:

    def __init__(
        self,
        db: Session,
        repo: ActivoBiologicoRepository,
        infra_port: Optional[InfraestructuraConsultaPort] = None,
        bitacora_repo: BitacoraAuditoriaRepository | None = None,
    ) -> None:
        self.db = db
        self.repo = repo
        self.infra_port = infra_port
        self.bitacora_repo = bitacora_repo

    def execute(
        self,
        id_activo: int,
        tipo_consulta: str,
        fecha_referencia: Optional[datetime] = None,
        usuario: Optional[UsuarioActual] = None,
        *,
        ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> ResultadoConsultaAsociacion:
        if tipo_consulta not in ('ACTIVA', 'HISTORIAL'):
            raise ValidationError(
                code='TIPO_CONSULTA_INVALIDO',
                message="tipo_consulta debe ser 'ACTIVA' o 'HISTORIAL'.",
                field='tipo_consulta',
            )

        if fecha_referencia is not None and tipo_consulta != 'ACTIVA':
            raise ValidationError(
                code='FECHA_REFERENCIA_INVALIDA',
                message="fecha_referencia solo es válida junto a tipo_consulta='ACTIVA'.",
                field='fecha_referencia',
            )

        activo = self.repo.obtener_por_id(id_activo, ids_fincas_permitidas=ids_fincas_permitidas)
        if not activo:
            raise NotFoundError(
                code='ACTIVO_NO_ENCONTRADO',
                message=f"No existe un activo biológico con id {id_activo}.",
            )

        historial_completo = self.repo.obtener_historial_infraestructura(id_activo)
        advertencia_integridad = _detectar_solapamiento(historial_completo)

        asociacion_activa: Optional[HistorialInfraestructura] = None
        historial_resultado: Optional[list[HistorialInfraestructura]] = None
        sensores = []

        if tipo_consulta == 'ACTIVA':
            if fecha_referencia is not None:
                asociacion_activa = self.repo.obtener_asociacion_en_fecha(id_activo, fecha_referencia)
            else:
                asociacion_activa = self.repo.obtener_asociacion_activa(id_activo)

            if asociacion_activa is None:
                if fecha_referencia is not None:
                    mensaje = (
                        f'El activo {id_activo} no tiene una asociación de infraestructura vigente '
                        f'en la fecha {fecha_referencia.isoformat()}. Verifique la integridad del historial.'
                    )
                else:
                    mensaje = (
                        f'El activo {id_activo} no tiene una asociación de infraestructura activa. '
                        'Esto indica una inconsistencia: todo activo biológico debe tener una '
                        'infraestructura vigente asignada.'
                    )
                raise NotFoundError(code='ASOCIACION_INFRAESTRUCTURA_NO_ENCONTRADA', message=mensaje)

            if self.infra_port:
                sensores = self.infra_port.listar_sensores_activos(asociacion_activa.id_infraestructura)
        else:
            historial_resultado = historial_completo

        if self.bitacora_repo:
            try:
                self.bitacora_repo.registrar(EventoAuditoria(
                    rf_origen='RF34', tipo_evento='INFRAESTRUCTURA_CONSULTADA',
                    clasificacion_biologica='ACCESO_DATOS', resultado='EXITOSO',
                    severidad_log='INFO', timestamp_evento=datetime.now(timezone.utc),
                    id_activo_biologico=id_activo,
                    detalle_tecnico={
                        'tipo_consulta': tipo_consulta,
                        'fecha_referencia': fecha_referencia.isoformat() if fecha_referencia else None,
                    },
                    id_usuario_responsable=usuario.id_usuario if usuario else None,
                ))
                self.db.commit()
            except Exception:
                pass

        return ResultadoConsultaAsociacion(
            tipo_consulta=tipo_consulta,
            id_activo_biologico=id_activo,
            asociacion_activa=asociacion_activa,
            historial=historial_resultado,
            sensores_en_infraestructura=sensores,
            advertencia_integridad=advertencia_integridad,
        )
