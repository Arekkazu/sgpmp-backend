# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-27 | Leandro | INC-M03-133-G170 RF-62: regenerar evaluaciones con causa y auditar el lote antes de un solo commit. |
# | 2026-10-28 | Arekkazu | INC-M03-132-G30 RF-62: la reevaluacion conserva TIME_DESYNC de la lectura |
"""RF-62 FA-08: sustituir evaluaciones y auditar el lote en una transacción."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime,timezone
from src.shared.errors import BusinessRuleError,ServiceUnavailableError
from src.telemetry.application.use_cases.calidad.evaluar_calidad_telemetria_use_case import EvaluarCalidadTelemetriaUseCase
from src.telemetry.application.use_cases.auditoria.registrar_evento_auditoria_iot_use_case import _calcular_hash
from src.telemetry.domain.entities.evento_auditoria_iot import (
    ComponenteOrigen,EntidadAfectadaTipo,SeveridadLog,TipoResultado,EventoAuditoriaIot,clasificar_componente)
from src.telemetry.domain.entities.parametros_reevaluacion import validar_correcciones,corregir_calibracion


@dataclass
class ResultadoReevaluacion:
    evaluaciones_superadas:int
    evaluaciones_creadas:int


class SolicitarReevaluacionUseCase:
    def __init__(self,db,calidad_repo,telemetria_repo,parametros_port,auditoria_repo=None,
                 contexto_port=None,alertas_calidad=None):
        self.db=db
        self.calidad_repo=calidad_repo
        self.telemetria_repo=telemetria_repo
        self.parametros_port=parametros_port
        self.auditoria_repo=auditoria_repo
        self.contexto_port=contexto_port
        self.alertas_calidad=alertas_calidad

    def execute(self,dto,id_usuario:int,nombre_usuario:str)->ResultadoReevaluacion:
        if not dto.causa_documentada or not dto.causa_documentada.strip():
            raise BusinessRuleError('REEVALUACION_SIN_CAUSA',
                'La re-evaluación masiva solo está permitida ante errores documentados de configuración. Debe proporcionar una causa.',
                field='causa_documentada')
        correcciones=validar_correcciones(dto.parametros_correctos)
        try:
            candidatas=self.calidad_repo.listar_vigentes_por_sensor_rango(
                id_sensor=dto.id_sensor,fecha_desde=dto.fecha_desde,fecha_hasta=dto.fecha_hasta)
            if not candidatas:
                raise BusinessRuleError('SIN_EVALUACIONES_EN_RANGO',
                    'No existen evaluaciones vigentes en el rango especificado.')
            if self.contexto_port is None or self.auditoria_repo is None:
                raise ServiceUnavailableError('AUDITORIA_CALIDAD_NO_DISPONIBLE',
                    'La re-evaluación requiere contexto y auditoría disponibles.')
            # Orden común para lotes solapados. Se relee la vigente tras esperar
            # el mismo lock que utiliza la evaluación manual/postcommit.
            ids=sorted({ev.id_telemetria for ev in candidatas})
            for identificador in ids:
                self.contexto_port.bloquear_evaluacion(identificador)
            motor=EvaluarCalidadTelemetriaUseCase(
                self.db,self.telemetria_repo,self.calidad_repo,self.parametros_port,
                self.auditoria_repo,self.contexto_port,self.alertas_calidad)
            anteriores=[]
            nuevas=[]
            for identificador in ids:
                anterior=self.calidad_repo.obtener_por_lectura(identificador)
                lectura=self.telemetria_repo.obtener_por_id(identificador)
                if anterior is None or lectura is None or lectura.id_sensor!=dto.id_sensor:
                    raise BusinessRuleError('REEVALUACION_FUENTE_NO_DISPONIBLE',
                        'Una lectura del rango ya no tiene una fuente o evaluación vigente disponible.')
                calibracion=corregir_calibracion(lectura.parametros_calibracion,correcciones)
                nueva=motor.execute(
                    id_telemetria=identificador,id_sensor=lectura.id_sensor,id_variable=lectura.id_variable,
                    valor=lectura.valor_crudo,valor_ajustado=lectura.valor_ajustado,
                    timestamp_captura=lectura.timestamp_captura,estado_calidad_rf53=lectura.estado_calidad,
                    parametros_calibracion=calibracion,
                    reloj_desincronizado=lectura.reloj_desincronizado,
                    evidencia_reloj=(lectura.metadatos or {}).get('rf53_reloj'),confirmar=False,
                    motivo_reevaluacion=dto.causa_documentada,correcciones=correcciones,
                    version_calibracion=(lectura.version_calibracion if calibracion==lectura.parametros_calibracion else None))
                if nueva is None:
                    raise BusinessRuleError('REEVALUACION_OMITIDA_POR_INACTIVIDAD',
                        'Una lectura del rango no puede reevaluarse por inactividad documentada. Se conserva el lote anterior.')
                anteriores.append(anterior)
                nuevas.append(nueva)
            self._emitir_auditoria(dto,id_usuario,nombre_usuario,anteriores,nuevas)
            self.db.commit()
            return ResultadoReevaluacion(len(anteriores),len(nuevas))
        except Exception:
            self.db.rollback()
            raise

    def _emitir_auditoria(self,dto,id_usuario,nombre_usuario,anteriores,nuevas):
        clasificacion,retencion=clasificar_componente(ComponenteOrigen.RF62)
        cambios=[{
            'id_telemetria':a.id_telemetria,
            'id_evaluacion_anterior':str(a.id_evaluacion),'id_evaluacion_nueva':str(n.id_evaluacion),
            'parametros_anteriores':{'estadisticos':a.parametros_aplicados,'calibracion':a.parametros_calibracion_aplicados},
            'parametros_nuevos':{'estadisticos':n.parametros_aplicados,'calibracion':n.parametros_calibracion_aplicados},
            'version_evaluacion':n.version_evaluacion,
        } for a,n in zip(anteriores,nuevas)]
        evento=EventoAuditoriaIot(
            id_evento=None,tipo_evento='REEVALUACION_CALIDAD_SOLICITADA',fecha_hora=datetime.now(timezone.utc),
            resultado=TipoResultado.PARCIAL,modulo='M03',id_usuario=id_usuario,nombre_usuario=nombre_usuario,
            descripcion='Re-evaluación de calidad completada; avisos a M04/M06 pendientes de integración.',
            entidad_afectada_tipo=EntidadAfectadaTipo.CALIDAD_DATO,
            entidad_afectada_id=str(nuevas[0].id_telemetria),severidad_log=SeveridadLog.WARNING,
            componente_origen=ComponenteOrigen.RF62,clasificacion_registro=clasificacion,
            retencion_aplicable=retencion,hash_integridad='',
            accion_detallada={
                'id_sensor':dto.id_sensor,'fecha_desde':dto.fecha_desde.isoformat(),'fecha_hasta':dto.fecha_hasta.isoformat(),
                'causa':dto.causa_documentada,'parametros_correctos':dto.parametros_correctos,
                'evaluaciones_superadas':len(anteriores),'evaluaciones_generadas':len(nuevas),
                'rango_lecturas_afectadas':[a.id_telemetria for a in anteriores],
                'parametros_anteriores':[{'id_telemetria':c['id_telemetria'],**c['parametros_anteriores']} for c in cambios],
                'parametros_nuevos':[{'id_telemetria':c['id_telemetria'],**c['parametros_nuevos']} for c in cambios],
                'sustituciones':[{k:v for k,v in c.items() if k not in ('parametros_anteriores','parametros_nuevos')} for c in cambios],
                'notificaciones_pendientes':[{'modulo':m,'motivo':'CANAL_REEVALUACION_NO_IMPLEMENTADO',
                    'ids_evaluaciones':[str(n.id_evaluacion) for n in nuevas]} for m in ('M04','M06')],
            })
        evento.hash_integridad=_calcular_hash(evento)
        if self.auditoria_repo.registrar(evento).id_evento is None:
            raise ServiceUnavailableError('AUDITORIA_CALIDAD_NO_DISPONIBLE',
                'No se pudo persistir la evidencia completa de la re-evaluación.')
