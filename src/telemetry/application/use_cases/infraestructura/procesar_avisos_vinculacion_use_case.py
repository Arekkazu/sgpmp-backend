# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-44 RF-61: avisos recuperables sin confirmar envios ficticios |
from src.shared.errors import ServiceUnavailableError


class ProcesarAvisosVinculacionUseCase:
    """Responsabilidad distinta del vinculo: un aviso pendiente no borra su causa."""
    def __init__(self, vinculaciones, avisos=None, destinatarios=None):
        self.vinculaciones,self.avisos=vinculaciones,avisos
        self.destinatarios=destinatarios

    def execute(self, identificador):
        v=self.vinculaciones.vigente(identificador)
        if v is None:return
        incompleta=v.causa=='CONFIGURACION_INCOMPLETA'
        ambigua=v.estado_vinculacion in ('AMBIGUA','PENDIENTE_REVISION')
        if not incompleta and not ambigua:return
        if self.avisos is None or self.destinatarios is None:
            raise ServiceUnavailableError('AVISO_VINCULACION_NO_DISPONIBLE',
                'Falta integrar la severidad aprobada RF-57 o el contrato de notificacion RF-61; no se confirma el aviso.')
        clave=f'RF61:{v.id_vinculacion_lectura}:'+('CONFIGURACION_INCOMPLETA' if incompleta else 'AMBIGUEDAD')
        destinatarios=self.destinatarios.obtener(v.id_infraestructura,administradores=incompleta)
        if not destinatarios:
            raise ServiceUnavailableError('DESTINATARIOS_VINCULACION_AUSENTES','No hay destinatarios autorizados para atender la vinculacion.')
        metodo=self.avisos.configuracion_incompleta if incompleta else self.avisos.ambiguedad
        if metodo(v,clave=clave,destinatarios=destinatarios) is not True:
            raise ServiceUnavailableError('AVISO_VINCULACION_NO_CONFIRMADO','El canal no confirmo el aviso RF-61.')
