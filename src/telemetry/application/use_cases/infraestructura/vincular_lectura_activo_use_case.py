# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-44 RF-61: estados, causas, snapshot e idempotencia |
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session
from src.shared.errors import ServiceUnavailableError
from src.telemetry.application.use_cases.infraestructura.evidencia_vinculacion import registrar_evidencia

from src.telemetry.domain.entities.vinculacion_lectura import VinculacionLectura
from src.telemetry.domain.repositories.activo_biologico_dependency_port import ActivoBiologicoDependencyPort
from src.telemetry.domain.repositories.vinculacion_lectura_repository import VinculacionLecturaRepository


class VincularLecturaActivoUseCase:
    """RF-61-A+B: Vinculación automática de una lectura telemétrica a su activo biológico.
    Se llama desde IngerirTelemetriaUseCase después del commit de la telemetría.
    Tiene su propia transacción.
    """

    def __init__(
        self,
        db: Session,
        vinculacion_repo: VinculacionLecturaRepository,
        activo_port: ActivoBiologicoDependencyPort,
        auditoria_repo=None,
    ) -> None:
        self.db = db
        self.vinculacion_repo = vinculacion_repo
        self.activo_port = activo_port
        self.auditoria_repo=auditoria_repo

    def execute(
        self,
        id_telemetria: int,
        id_infraestructura: int,
        timestamp_captura: datetime,
    ) -> VinculacionLectura:
        ahora = datetime.now(timezone.utc)

        try:
            self.vinculacion_repo.bloquear_lectura(id_telemetria)
            existente=self.vinculacion_repo.ultima(id_telemetria)
            if existente is not None:
                self.db.commit()
                return existente
            origen=self.vinculacion_repo.contexto_lectura(id_telemetria,timestamp_captura)
            completa=len(origen['areas'])==1
            area=origen['areas'][0] if completa else id_infraestructura
            if area is None:
                raise ServiceUnavailableError('VINCULACION_SIN_ESTRUCTURA_PENDIENTE',
                    'DB-13 requiere infraestructura para persistir el vinculo; no se asigna una estructura ficticia.')
            activos=self.activo_port.obtener_activos_en_momento(area,timestamp_captura) if completa else []
            if activos:
                self.activo_port.bloquear_activos([a.id_activo_biologico for a in activos])
                # Snapshot posterior al lock: un traslado pudo confirmar mientras se esperaba.
                activos=self.activo_port.obtener_activos_en_momento(area,timestamp_captura)
            directos=[a for a in activos if a.id_activo_biologico in origen['activos_directos']]
            if len(directos)==1:
                activos=directos
            causa=None
            contexto={'timestamp_captura':timestamp_captura.isoformat(),
                'id_sensor':origen['id_sensor'],'id_dispositivo_iot':origen['id_dispositivo_iot'],
                'candidatos':[a.id_activo_biologico for a in activos]}
            inconsistente=completa and not directos and self.activo_port.historial_inconsistente(area,timestamp_captura)

            if inconsistente:
                estado='PENDIENTE_REVISION'
                id_activo=None
                modelo_manejo='INDIVIDUAL'
                contexto['historial_consistente']=False
            elif len(activos) == 0:
                estado = 'SIN_VINCULAR'
                causa='SIN_ACTIVOS_EN_ESTRUCTURA' if completa else 'CONFIGURACION_INCOMPLETA'
                id_activo = None
                modelo_manejo = 'INDIVIDUAL'
            elif len(activos) == 1:
                estado = 'CONFIRMADA'
                id_activo = activos[0].id_activo_biologico
                modelo_manejo = activos[0].modelo_manejo
                contexto.update(self.activo_port.obtener_contexto(id_activo,timestamp_captura))
            else:
                estado = 'PENDIENTE_REVISION'
                id_activo = None
                modelos={a.modelo_manejo for a in activos}
                if len(modelos)!=1:
                    raise ServiceUnavailableError('MODELO_MANEJO_AMBIGUO',
                        'Los candidatos tienen modelos de manejo diferentes; no se selecciona el primer modelo.')
                modelo_manejo = modelos.pop()

            fin=None
            if estado=='CONFIRMADA':
                valor=(contexto.get('ubicacion') or {}).get('fecha_fin')
                if valor:
                    fin=datetime.fromisoformat(valor)
                    estado='SUPERADA'
            vinculacion = self.vinculacion_repo.guardar(VinculacionLectura(
                id_vinculacion_lectura=None,
                id_telemetria=id_telemetria,
                modelo_manejo=modelo_manejo,
                id_activo_biologico=id_activo,
                id_infraestructura=area,
                fecha_inicio_vinculacion=timestamp_captura,
                fecha_fin_vinculacion=fin,
                mecanismo_vinculacion='AUTOMATICA',
                estado_vinculacion=estado,
                id_usuario=None,
                motivo_correccion=None,
                id_vinculacion_reemplazada=None,
                fecha_creacion=ahora,
                causa=causa,
                contexto_activo=contexto,
            ))

            if self.auditoria_repo is not None:
                tipo='VINCULACION_AUTOMATICA' if estado in ('CONFIRMADA','SUPERADA') else 'SIN_VINCULAR' if estado=='SIN_VINCULAR' else 'VINCULACION_AMBIGUA'
                registrar_evidencia(self.auditoria_repo,tipo,vinculacion.id_vinculacion_lectura,
                    {'id_telemetria':id_telemetria,'estado':estado,'causa':causa,'contexto_activo':contexto})
            self.db.commit()
            return vinculacion

        except Exception:
            self.db.rollback()
            raise
