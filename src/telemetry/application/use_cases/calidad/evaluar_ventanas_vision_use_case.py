# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-28 RF-60: evidencia tecnica de ventanas sin alerta |
from src.telemetry.domain.entities.secuencia_vision import ventanas_sin_deteccion
from src.telemetry.domain.entities.evento_auditoria_iot import (
    EventoAuditoriaIot, ComponenteOrigen, EntidadAfectadaTipo, TipoResultado,
    SeveridadLog, clasificar_componente,
)
from src.telemetry.application.use_cases.auditoria.registrar_evento_auditoria_iot_use_case import _calcular_hash


class EvaluarVentanasVisionUseCase:
    """Sin commits: el worker confirma diagnostico y progreso juntos."""
    def __init__(self, ventanas, parametros, auditoria):
        self.ventanas,self.parametros,self.auditoria=ventanas,parametros,auditoria

    def execute(self, identificador):
        p=self.parametros.obtener_ventanas()
        secuencia=ventanas_sin_deteccion(self.ventanas.recientes(identificador,p.cantidad),p)
        if not secuencia:
            return
        ultima=secuencia[-1]
        if self.ventanas.diagnostico_existente(ultima.identificador):
            return
        clasificacion,retencion=clasificar_componente(ComponenteOrigen.RF60)
        evento=EventoAuditoriaIot(
            id_evento=None,tipo_evento='SIN_DETECCION_VALIDA',fecha_hora=ultima.fin,
            resultado=TipoResultado.ADVERTENCIA,componente_origen=ComponenteOrigen.RF60,
            entidad_afectada_tipo=EntidadAfectadaTipo.LECTURA,entidad_afectada_id=str(ultima.identificador),
            descripcion='Ventanas consecutivas con cobertura inferior al minimo configurado.',
            severidad_log=SeveridadLog.WARNING,clasificacion_registro=clasificacion,retencion_aplicable=retencion,
            accion_detallada={'fuente':'observaciones_vision','id_dispositivo_iot':ultima.camara,
                'area_id':ultima.area,'ventanas':[v.identificador for v in secuencia],
                'coberturas':[str(v.cobertura) for v in secuencia],
                'parametros_aplicados':{'ventanas_consecutivas_sin_deteccion':p.cantidad,
                    'cobertura_minima_deteccion_valida':str(p.cobertura_minima),'duracion_ventana_observacion':p.duracion_seg}},
        )
        evento.hash_integridad=_calcular_hash(evento)
        if self.auditoria.registrar(evento).id_evento is None:
            raise RuntimeError('No se confirmo el diagnostico tecnico de vision.')
