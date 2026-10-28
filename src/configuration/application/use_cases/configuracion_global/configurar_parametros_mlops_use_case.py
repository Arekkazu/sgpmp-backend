# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-21 | Arekkazu | DEV-32 RF-57: valida los umbrales de tormenta (E8) |
# | 2026-10-21 | Leandro | DEV-27 RF-60: valida parametros y siembra idempotente |
# | 2026-10-22 | Leandro | DEV-28 RF-62: valida snapshot de pesos y tramos de vision |
# | 2026-10-28 | destroyerban | INC-M03-166-G73 RF-57 CA-2: valida el umbral mínimo de confianza de IA |
"""Carga administrativa explícita; ninguna inicialización ocurre en un request."""
from decimal import Decimal

from src.configuration.domain.entities.parametro_mlops import (
    PARAMETROS_CALIDAD, RF57_CONFIANZA, RF57_CONFIANZA_MINIMA, RF57_TORMENTA_SISTEMA, RF57_TORMENTA_UNIDAD, RF62_DRIFT, RF62_K, RF62_M, RF62_N, RF62_P,
    RF72_VENTANA, ParametroMLOps, calidad_configurada, numero_configurado,
)
from src.shared.errors import ServiceUnavailableError, ValidationError
from src.configuration.domain.entities.parametros_heartbeat import (
    LIMITES_HEARTBEAT, TEMPORALES, validar_heartbeat_configurado,
)
from src.configuration.domain.entities.parametros_vision import LIMITES_VISION, vision_configurada

_LIMITES = {
    RF62_K: (0, None), RF62_M: (1, None), RF62_N: (2, None),
    RF62_DRIFT: (0, None), RF62_P: (1, None),
    RF57_CONFIANZA: (Decimal('0.70'), Decimal('0.95')),
    RF57_CONFIANZA_MINIMA: (Decimal('0'), Decimal('1')),
    RF57_TORMENTA_SISTEMA: (1, None), RF57_TORMENTA_UNIDAD: (1, None),
    RF72_VENTANA: (7, 365),
    **LIMITES_HEARTBEAT,
    **LIMITES_VISION,
}


class ConfigurarParametrosMLOpsUseCase:
    def __init__(self, db, parametros_repo, configuracion_repo=None):
        self.db = db
        self.parametros_repo = parametros_repo
        self.configuracion_repo = configuracion_repo

    def validar(self, cambios):
        if not isinstance(cambios, dict) or not cambios or set(cambios) - _LIMITES.keys():
            raise ValidationError('PARAMETRO_MLOPS_INVALIDO', 'El archivo contiene parámetros vacíos o ajenos a DEV-14.')
        nombres = set(cambios)
        if nombres.intersection(PARAMETROS_CALIDAD):
            nombres.update(PARAMETROS_CALIDAD)
        if nombres.intersection(LIMITES_HEARTBEAT):
            nombres.update(LIMITES_HEARTBEAT)
        if nombres.intersection(LIMITES_VISION):
            nombres.update(LIMITES_VISION)
        actuales = self.parametros_repo.obtener(sorted(nombres))
        nuevos = {}
        for nombre, valor in cambios.items():
            previo = actuales.get(nombre)
            minimo, maximo = (previo.minimo, previo.maximo) if previo else _LIMITES[nombre]
            nuevos[nombre] = ParametroMLOps(nombre, valor, minimo, maximo)
        try:
            if set(nuevos).intersection(LIMITES_VISION):
                vision_configurada(actuales | nuevos)
            if set(nuevos).intersection(PARAMETROS_CALIDAD):
                calidad_configurada(actuales | nuevos)
            if RF57_CONFIANZA in nuevos:
                numero_configurado(nuevos, RF57_CONFIANZA, minimo='0.70', maximo='0.95')
            if RF57_CONFIANZA_MINIMA in nuevos:
                numero_configurado(nuevos, RF57_CONFIANZA_MINIMA, minimo=0, maximo=1)
            for nombre in (RF57_TORMENTA_SISTEMA, RF57_TORMENTA_UNIDAD):
                if nombre in nuevos:
                    numero_configurado(nuevos, nombre, minimo=1, entero=True)
            if RF72_VENTANA in nuevos:
                numero_configurado(nuevos, RF72_VENTANA, minimo=7, maximo=365, entero=True)
            if set(nuevos).intersection(LIMITES_HEARTBEAT):
                configuracion = self.configuracion_repo.obtener_activo() if self.configuracion_repo is not None else None
                if set(nuevos).intersection(TEMPORALES) and configuracion is None:
                    raise ServiceUnavailableError('CONFIGURACION_OPERATIVA_AUSENTE',
                        'Configure RF-18 antes de sembrar los parámetros temporales de heartbeat.')
                validar_heartbeat_configurado(
                    actuales | nuevos,
                    configuracion.frecuencia_muestreo.valor if configuracion else None,
                    configuracion.heartbeat.valor if configuracion else None,
                )
        except ServiceUnavailableError as exc:
            raise ValidationError('PARAMETRO_MLOPS_INVALIDO', exc.message) from None
        return list(nuevos.values())

    def execute(self, cambios, id_usuario):
        try:
            self.parametros_repo.bloquear_configuracion()
            parametros = self.validar(cambios)
            self.parametros_repo.guardar(parametros, id_usuario)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def sembrar(self, cambios, id_usuario, *, aplicar=False, actualizar_existentes=False):
        """Reutiliza validación/locks DEV-14, sin sobrescribir por defecto."""
        try:
            self.parametros_repo.bloquear_configuracion()
            existentes = self.parametros_repo.obtener(list(cambios))
            actualizables = set(cambios) if actualizar_existentes is True else set(actualizar_existentes or ())
            efectivos = {nombre: existentes[nombre].valor
                         if nombre in existentes and nombre not in actualizables else valor
                         for nombre, valor in cambios.items()}
            validados = self.validar(efectivos)
            acciones = {nombre: 'creado' if nombre not in existentes else
                        'actualizado' if efectivos[nombre] != existentes[nombre].valor else 'conservado'
                        for nombre in efectivos}
            if aplicar:
                self.parametros_repo.guardar([p for p in validados if acciones[p.nombre] != 'conservado'], id_usuario)
                self.db.commit()
            else:
                self.db.rollback()
            return acciones
        except Exception:
            self.db.rollback()
            raise
