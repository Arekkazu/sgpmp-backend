# | Fecha      | Nombre  | Que se hizo                                      |
# |------------|---------|--------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-43 RF-62: integra calidad temporal y alertas tecnicas |
# | 2026-10-22 | Leandro | DEV-44 RF-61: clasifica capturas con su contexto historico cerrado |
# | 2026-10-27 | Leandro | INC-M03-132-G30 RF-53/54/62: propagar snapshot inmutable de reloj a la evaluacion postcommit. |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Caso de uso que completa el procesamiento postcommit de una lectura (RF-53/54/61/62).

Tras confirmarse la ingesta, vincula la lectura si falta, evalúa su calidad y la
reclasifica con el semáforo del activo al que pertenece.
"""
from src.shared.errors import ServiceUnavailableError


class ProcesarLecturaConfirmadaUseCase:
    """Encadena vinculación, evaluación de calidad y reclasificación de una lectura."""

    def __init__(self, lecturas, vincular, evaluar, reclasificar):
        self.lecturas = lecturas
        self.vincular = vincular
        self.evaluar = evaluar
        self.reclasificar = reclasificar

    def vincular_lectura(self, identificador):
        """Vincula la lectura si aún no tiene vinculación RF-61."""
        lectura = self.lecturas.obtener_por_id(identificador)
        if self.lecturas.vinculacion(identificador) is None:
            self.vincular.execute(identificador, self.lecturas.infraestructura(lectura.id_dispositivo_iot), lectura.timestamp_captura)

    def evaluar_lectura(self, identificador):
        """Evalúa la calidad de la lectura si no tiene evaluación vigente.

        Raises:
            RuntimeError: Si la evaluación no queda persistida como vigente.
        """
        if self.lecturas.evaluacion_vigente(identificador) is not None:
            return
        lectura = self.lecturas.obtener_por_id(identificador)
        resultado = self.evaluar.execute(
            id_telemetria=identificador, id_sensor=lectura.id_sensor,
            id_variable=lectura.id_variable, valor=lectura.valor_crudo,
            valor_ajustado=lectura.valor_ajustado, timestamp_captura=lectura.timestamp_captura,
            estado_calidad_rf53=lectura.estado_calidad, parametros_calibracion=lectura.parametros_calibracion,
            reloj_desincronizado=lectura.reloj_desincronizado,
            evidencia_reloj=(lectura.metadatos or {}).get('rf53_reloj'),
        )
        if resultado is None and self.lecturas.evaluacion_omitida(identificador):
            return
        if self.lecturas.evaluacion_vigente(identificador) is None:
            raise RuntimeError('RF-62 no persistió una evaluación vigente.')

    def clasificar_lectura(self, identificador):
        """Reclasifica la última lectura válida con el semáforo del activo vinculado.

        Raises:
            ServiceUnavailableError: Si la lectura no tiene vinculación disponible.
        """
        fuente = self.lecturas.obtener_por_id(identificador)
        lectura = self.lecturas.ultima_lectura_valida(fuente.id_sensor)
        if lectura is None:
            return  # RF-58 no proyecta estas lecturas; RF-62 conserva su rechazo/calidad.
        vinculo = self.lecturas.vinculacion(lectura.id_telemetria)
        if vinculo is None:
            vinculo = self.lecturas.vinculacion_historica(lectura.id_telemetria)
        if vinculo is None:
            raise ServiceUnavailableError('VINCULACION_PENDIENTE', 'La lectura actual aún no tiene vinculación RF-61.')
        self.lecturas.restaurar_cache(lectura)
        color = self.reclasificar.execute(lectura.id_telemetria, vinculo['id_activo_biologico'])
        self.lecturas.aplicar_prioridades(lectura, color)
