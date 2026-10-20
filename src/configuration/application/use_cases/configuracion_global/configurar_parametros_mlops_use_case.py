"""Carga administrativa explícita; ninguna inicialización ocurre en un request."""
from decimal import Decimal

from src.configuration.domain.entities.parametro_mlops import (
    PARAMETROS_CALIDAD, RF57_CONFIANZA, RF62_DRIFT, RF62_K, RF62_M, RF62_N, RF62_P,
    RF72_VENTANA, ParametroMLOps, calidad_configurada, numero_configurado,
)
from src.shared.errors import ServiceUnavailableError, ValidationError

_LIMITES = {
    RF62_K: (0, None), RF62_M: (1, None), RF62_N: (2, None),
    RF62_DRIFT: (0, None), RF62_P: (1, None),
    RF57_CONFIANZA: (Decimal('0.70'), Decimal('0.95')),
    RF72_VENTANA: (7, 365),
}


class ConfigurarParametrosMLOpsUseCase:
    def __init__(self, db, parametros_repo):
        self.db = db
        self.parametros_repo = parametros_repo

    def validar(self, cambios):
        if not isinstance(cambios, dict) or not cambios or set(cambios) - _LIMITES.keys():
            raise ValidationError('PARAMETRO_MLOPS_INVALIDO', 'El archivo contiene parámetros vacíos o ajenos a DEV-14.')
        nombres = set(cambios)
        if nombres.intersection(PARAMETROS_CALIDAD):
            nombres.update(PARAMETROS_CALIDAD)
        actuales = self.parametros_repo.obtener(sorted(nombres))
        nuevos = {}
        for nombre, valor in cambios.items():
            previo = actuales.get(nombre)
            minimo, maximo = (previo.minimo, previo.maximo) if previo else _LIMITES[nombre]
            nuevos[nombre] = ParametroMLOps(nombre, valor, minimo, maximo)
        try:
            if set(nuevos).intersection(PARAMETROS_CALIDAD):
                calidad_configurada(actuales | nuevos)
            if RF57_CONFIANZA in nuevos:
                numero_configurado(nuevos, RF57_CONFIANZA, minimo='0.70', maximo='0.95')
            if RF72_VENTANA in nuevos:
                numero_configurado(nuevos, RF72_VENTANA, minimo=7, maximo=365, entero=True)
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
