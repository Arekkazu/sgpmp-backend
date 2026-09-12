from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.biological_assets.domain.entities.activo_biologico import ActivoBiologico, EventoAuditoria, ResultadoIndicadores
from src.biological_assets.domain.repositories.activo_biologico_repository import ActivoBiologicoRepository
from src.biological_assets.domain.repositories.bitacora_auditoria_repository import BitacoraAuditoriaRepository
from src.biological_assets.domain.repositories.historico_estado_repository import HistoricoEstadoRepository
from src.biological_assets.domain.repositories.indicadores_repository import IndicadoresRepository
from src.biological_assets.domain.value_objects.estado_activo import EstadoActivo
from src.biological_assets.infrastructure.dto.consultar_indicadores_dto import ConsultarIndicadoresDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import NotFoundError, ValidationError

_ESTADOS_TERMINALES = {EstadoActivo.BAJA: 'baja', EstadoActivo.CERRADO: 'cierre'}


class ConsultarIndicadoresUseCase:

    def __init__(
        self,
        db: Session,
        activo_repo: ActivoBiologicoRepository,
        indicadores_repo: IndicadoresRepository,
        historico_repo: HistoricoEstadoRepository,
        bitacora_repo: BitacoraAuditoriaRepository | None = None,
    ) -> None:
        self.db = db
        self.activo_repo = activo_repo
        self.indicadores_repo = indicadores_repo
        self.historico_repo = historico_repo
        self.bitacora_repo = bitacora_repo

    def execute(
        self,
        id_activo: int,
        dto: ConsultarIndicadoresDTO,
        usuario: UsuarioActual,
        *,
        ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> ResultadoIndicadores:
        activo = self.activo_repo.obtener_por_id(id_activo, ids_fincas_permitidas=ids_fincas_permitidas)
        if activo is None:
            raise NotFoundError(
                code='ACTIVO_NO_ENCONTRADO',
                message=f'El activo biológico con ID {id_activo} no existe en los registros del sistema.',
            )

        self._validar_rango_dentro_del_ciclo_de_vida(activo, dto.fecha_inicio, dto.fecha_fin)

        resultado = self.indicadores_repo.calcular_indicadores(
            id_activo=id_activo,
            tipo_activo=activo.tipo,
            fecha_inicio=dto.fecha_inicio,
            fecha_fin=dto.fecha_fin,
            tipo_indicador=dto.tipo_indicador,
        )

        if self.bitacora_repo:
            try:
                self.bitacora_repo.registrar(EventoAuditoria(
                    rf_origen='RF51', tipo_evento='INDICADOR_CALCULADO',
                    clasificacion_biologica='GESTION_OPERATIVA', resultado='EXITOSO',
                    severidad_log='INFO', timestamp_evento=datetime.now(timezone.utc),
                    id_activo_biologico=id_activo, tipo_activo=activo.tipo,
                    detalle_tecnico={'tipo_indicador': dto.tipo_indicador},
                    id_usuario_responsable=usuario.id_usuario,
                ))
                self.db.commit()
            except Exception:
                pass

        return resultado

    def _validar_rango_dentro_del_ciclo_de_vida(
        self,
        activo: ActivoBiologico,
        fecha_inicio: Optional[date],
        fecha_fin: Optional[date],
    ) -> None:
        if fecha_inicio is not None:
            if activo.detalle_individual is not None:
                nacimiento = activo.detalle_individual.fecha_nacimiento
                nacimiento_fecha = nacimiento.date() if isinstance(nacimiento, datetime) else nacimiento
                if nacimiento_fecha is not None and fecha_inicio < nacimiento_fecha:
                    raise ValidationError(
                        code='RANGO_FUERA_DE_CICLO_VIDA',
                        message=(
                            f'La fecha de inicio ({fecha_inicio.isoformat()}) es anterior a la fecha de '
                            f'nacimiento del activo ({nacimiento_fecha.isoformat()}).'
                        ),
                        field='fecha_inicio',
                    )
            if activo.fecha_inicio_ciclo is not None and fecha_inicio < activo.fecha_inicio_ciclo:
                raise ValidationError(
                    code='RANGO_FUERA_DE_CICLO_VIDA',
                    message=(
                        f'La fecha de inicio ({fecha_inicio.isoformat()}) es anterior al inicio de '
                        f'ciclo del activo ({activo.fecha_inicio_ciclo.isoformat()}).'
                    ),
                    field='fecha_inicio',
                )

        etiqueta_estado = _ESTADOS_TERMINALES.get(activo.id_estado)
        if fecha_fin is not None and etiqueta_estado is not None:
            ultimo_cambio = self.historico_repo.obtener_ultimo_cambio(activo.id_activo_biologico)
            if ultimo_cambio is not None:
                fecha_limite = ultimo_cambio.fecha_cambio
                fecha_limite_fecha = fecha_limite.date() if isinstance(fecha_limite, datetime) else fecha_limite
                if fecha_fin > fecha_limite_fecha:
                    raise ValidationError(
                        code='RANGO_FUERA_DE_CICLO_VIDA',
                        message=(
                            f'La fecha de fin ({fecha_fin.isoformat()}) es posterior a la fecha de '
                            f'{etiqueta_estado} del activo ({fecha_limite_fecha.isoformat()}).'
                        ),
                        field='fecha_fin',
                    )
