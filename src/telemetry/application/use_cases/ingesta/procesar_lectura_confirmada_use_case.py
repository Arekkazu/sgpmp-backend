from src.shared.errors import ServiceUnavailableError
from src.telemetry.domain.repositories.telemetria_repository import TelemetriaRepository


class ProcesarLecturaConfirmadaUseCase:
    def __init__(self, lecturas, vincular, evaluar, reclasificar):
        self.lecturas = lecturas
        self.vincular = vincular
        self.evaluar = evaluar
        self.reclasificar = reclasificar

    def vincular_lectura(self, identificador):
        lectura = self.lecturas.obtener_por_id(identificador)
        if self.lecturas.vinculacion(identificador) is None:
            self.vincular.execute(identificador, self.lecturas.infraestructura(lectura.id_dispositivo_iot), lectura.timestamp_captura)

    def evaluar_lectura(self, identificador):
        if self.lecturas.evaluacion_vigente(identificador) is not None:
            return
        # Dependencia explícita de la eliminación del puerto obsoleto en DEV-02.
        # No se copia esa solución ni se ejecuta el RF-62 anterior contra RF-53.
        if hasattr(TelemetriaRepository, 'actualizar_flags_aptitud'):
            raise ServiceUnavailableError('RF62_DEV02_PENDIENTE', 'Se requiere integrar DEV-02 para evaluar telemetría inmutable.')
        lectura = self.lecturas.obtener_por_id(identificador)
        self.evaluar.execute(
            id_telemetria=identificador, id_sensor=lectura.id_sensor,
            id_variable=lectura.id_variable, valor=lectura.valor_crudo,
            valor_ajustado=lectura.valor_ajustado, timestamp_captura=lectura.timestamp_captura,
            estado_calidad_rf53=lectura.estado_calidad, parametros_calibracion=lectura.parametros_calibracion,
        )
        if self.lecturas.evaluacion_vigente(identificador) is None:
            raise RuntimeError('RF-62 no persistió una evaluación vigente.')

    def clasificar_lectura(self, identificador):
        fuente = self.lecturas.obtener_por_id(identificador)
        lectura = self.lecturas.ultima_lectura_valida(fuente.id_sensor)
        if lectura is None:
            return  # RF-58 no proyecta estas lecturas; RF-62 conserva su rechazo/calidad.
        vinculo = self.lecturas.vinculacion(lectura.id_telemetria)
        if vinculo is None:
            raise ServiceUnavailableError('VINCULACION_PENDIENTE', 'La lectura actual aún no tiene vinculación RF-61.')
        self.lecturas.restaurar_cache(lectura)
        color = self.reclasificar.execute(lectura.id_telemetria, vinculo['id_activo_biologico'])
        self.lecturas.aplicar_prioridades(lectura, color)
