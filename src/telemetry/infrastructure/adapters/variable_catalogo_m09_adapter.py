from decimal import Decimal
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.telemetry.domain.entities.telemetria import CATALOGO_I3P1, ReglaVariableI3P1
from src.telemetry.domain.repositories.variable_catalogo_port import VariableCatalogoPort

# Factores de conversión de unidades a la unidad estándar
_CONVERSIONES: dict[tuple[str, str], tuple[str, callable]] = {
    ('°F', '°C'): ('°C', lambda v: (v - 32) * 5 / 9),
    ('K', '°C'): ('°C', lambda v: v - Decimal('273.15')),
    ('mS/cm', 'µS/cm'): ('µS/cm', lambda v: v * 1000),
    ('g', 'm/s²'): ('m/s²', lambda v: v * Decimal('9.80665')),
}


class VariableCatalogoM09Adapter(VariableCatalogoPort):
    """Implementación del catálogo I3P-1 con datos de modulo9.variables_ambientales.

    Usa el catálogo en memoria (CATALOGO_I3P1) para la clasificación por tipo y
    consulta M09 para obtener los rangos físicos actualizados.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def obtener_regla(self, tipo_variable: str, unidad: str) -> Optional[ReglaVariableI3P1]:
        catalogo_entry = CATALOGO_I3P1.get(tipo_variable.upper())
        if catalogo_entry is None:
            return None

        id_variable = catalogo_entry['id_variable']

        row = self.db.execute(
            text(
                'SELECT valor_fisico_min, valor_fisico_max '
                'FROM modulo9.variables_ambientales '
                'WHERE id_variable_ambiental = :id AND es_activo = true'
            ),
            {'id': id_variable},
        ).fetchone()

        if row is None:
            return None

        unidades_aceptadas = catalogo_entry['unidades']
        unidad_estandar = catalogo_entry['unidad_estandar']

        # Validar unidad: debe estar en la lista de aceptadas o tener conversión
        unidad_normalizada = unidad
        if unidad not in unidades_aceptadas:
            # Intentar conversión
            clave = (unidad, unidad_estandar)
            if clave not in _CONVERSIONES:
                raise ValueError(
                    f"Unidad '{unidad}' inválida para {tipo_variable}. "
                    f"Unidades aceptadas: {', '.join(unidades_aceptadas)}"
                )
            unidad_normalizada = unidad_estandar

        return ReglaVariableI3P1(
            id_variable=id_variable,
            tipo_variable=tipo_variable.upper(),
            categoria=catalogo_entry['categoria'].value,
            unidad_estandar=unidad_estandar,
            unidades_aceptadas=unidades_aceptadas,
            valor_fisico_min=Decimal(str(row.valor_fisico_min)),
            valor_fisico_max=Decimal(str(row.valor_fisico_max)),
        )

    @staticmethod
    def convertir_valor(valor: Decimal, unidad_origen: str, unidad_destino: str) -> Decimal:
        clave = (unidad_origen, unidad_destino)
        if clave in _CONVERSIONES:
            _, fn = _CONVERSIONES[clave]
            return Decimal(str(fn(valor)))
        return valor
