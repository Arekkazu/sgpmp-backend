from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from src.biological_assets.application.use_cases._registrar_evento_bitacora import registrar_evento_bitacora
from src.biological_assets.domain.entities.activo_biologico import EventoAuditoria, FichaLote
from src.biological_assets.domain.repositories.activo_biologico_repository import ActivoBiologicoRepository
from src.biological_assets.domain.repositories.bitacora_auditoria_repository import BitacoraAuditoriaRepository
from src.biological_assets.domain.repositories.especie_consulta_port import EspecieConsultaPort
from src.biological_assets.domain.repositories.infraestructura_consulta_port import InfraestructuraConsultaPort
from src.biological_assets.domain.repositories.transferencia_repository import TransferenciaRepository
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import NotFoundError, ValidationError

_ULTIMOS_EVENTOS_FICHA = 10


class ConsultarFichaLoteUseCase:
    """RF-36 (tarea Taiga "Ficha de gestión de lote, densidad máxima,
    ingreso de individuos"): ficha operativa dedicada a un lote POBLACIONAL
    -- cantidad_actual + peso_promedio + biomasa_total + densidad + estado +
    historial en una sola vista, que hoy no existía como endpoint propio (la
    ficha integral de RF-47 es genérica para ambos tipos, sin densidad ni
    densidad_maxima, y con "últimos 5 eventos" en vez de historial real)."""

    def __init__(
        self,
        db: Session,
        activo_repo: ActivoBiologicoRepository,
        infra_port: InfraestructuraConsultaPort,
        especie_port: EspecieConsultaPort,
        transferencia_repo: TransferenciaRepository,
        bitacora_repo: BitacoraAuditoriaRepository | None = None,
    ) -> None:
        self.db = db
        self.activo_repo = activo_repo
        self.infra_port = infra_port
        self.especie_port = especie_port
        self.transferencia_repo = transferencia_repo
        self.bitacora_repo = bitacora_repo

    def execute(
        self,
        id_activo: int,
        usuario: UsuarioActual,
        *,
        ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> FichaLote:
        activo = self.activo_repo.obtener_por_id(id_activo, ids_fincas_permitidas=ids_fincas_permitidas)
        if activo is None:
            raise NotFoundError(
                code='ACTIVO_NO_ENCONTRADO',
                message=f'El activo biológico con id {id_activo} no fue encontrado en el sistema.',
            )

        if activo.tipo != 'POBLACIONAL':
            raise ValidationError(
                code='TIPO_INVALIDO',
                message='La ficha de gestión de lote solo aplica a activos de tipo POBLACIONAL.',
                field='id_activo',
            )

        dp = activo.detalle_poblacional

        infra = self.infra_port.obtener_activa(activo.id_infraestructura)
        densidad_maxima: Optional[Decimal] = None
        if infra and infra.capacidad_maxima and infra.superficie and infra.superficie > 0:
            densidad_maxima = Decimal(infra.capacidad_maxima) / infra.superficie

        especie = self.especie_port.obtener_activa(activo.id_especie)

        historial = self.transferencia_repo.consultar_historial(
            id_activo=id_activo,
            fecha_inicio=None,
            fecha_fin=None,
            categoria=None,
            pagina=1,
            page_size=_ULTIMOS_EVENTOS_FICHA,
        )

        registrar_evento_bitacora(self.bitacora_repo, self.db, EventoAuditoria(
            rf_origen='RF36', tipo_evento='FICHA_LOTE_CONSULTADA',
            clasificacion_biologica='ACCESO_DATOS', resultado='EXITOSO',
            severidad_log='INFO', timestamp_evento=datetime.now(timezone.utc),
            id_activo_biologico=id_activo, tipo_activo=activo.tipo,
            id_usuario_responsable=usuario.id_usuario,
        ))

        return FichaLote(
            id_activo_biologico=id_activo,
            identificador=activo.identificador,
            especie=especie.nombre if especie else None,
            infraestructura_asociada=infra.nombre if infra else None,
            estado_actual=activo.nombre_estado or str(activo.id_estado),
            fecha_registro=activo.fecha_creacion,
            cantidad_inicial=dp.cantidad_inicial if dp else 0,
            cantidad_actual=dp.cantidad_actual if dp else None,
            peso_promedio_inicial=dp.peso_promedio_inicial if dp else None,
            peso_promedio=dp.peso_promedio if dp else None,
            biomasa_total=dp.biomasa_total if dp else None,
            densidad=dp.densidad if dp else None,
            densidad_maxima=densidad_maxima,
            historial=historial.registros,
            total_registros_historial=historial.total_registros,
        )
