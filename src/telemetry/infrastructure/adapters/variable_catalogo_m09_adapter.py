# | Fecha      | Nombre  | Que se hizo                                      |
# |------------|---------|--------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-40 RF-53: consulta variables y metadatos M09   |
"""M09 es la única fuente de códigos, categorías, unidades y rangos escalares."""
from decimal import Decimal
import re
import unicodedata
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.shared.db_error_translator import raise_from_db_error
from src.shared.errors import ServiceUnavailableError
from src.telemetry.domain.entities.telemetria import CategoriaTelemetria, ReglaVariableI3P1
from src.telemetry.domain.repositories.variable_catalogo_port import VariableCatalogoPort


def _normalizar_nombre(nombre: str) -> str:
    texto = unicodedata.normalize('NFKD', nombre).encode('ascii', 'ignore').decode('ascii')
    return re.sub(r'[^A-Z0-9]+', '_', texto.upper()).strip('_')


class VariableCatalogoM09Adapter(VariableCatalogoPort):
    def __init__(self, db: Session) -> None:
        self.db = db

    def obtener_regla(self, tipo_variable: str) -> Optional[ReglaVariableI3P1]:
        try:
            # Consulta de columnas, sin identity-map ni caché que esconda cambios.
            filas = self.db.execute(text("""
                SELECT id_variable_ambiental, nombre, codigo_telemetria,
                       categoria_variable, unidad, valor_fisico_min, valor_fisico_max
                FROM modulo9.variables_ambientales WHERE es_activo = true
            """)).mappings().all()
        except Exception as exc:
            raise_from_db_error(exc)
        codigo = tipo_variable.upper().strip()
        candidatas = [fila for fila in filas if codigo in (
            fila['codigo_telemetria'], _normalizar_nombre(fila['nombre']),
        )]
        if not candidatas:
            return None
        if len(candidatas) != 1:
            raise ServiceUnavailableError('CATALOGO_AMBIGUO', 'El catálogo de variables requiere revisión de configuración.')
        fila = candidatas[0]
        categoria = fila['categoria_variable']
        if categoria not in {item.value for item in CategoriaTelemetria}:
            raise ServiceUnavailableError('CATALOGO_INCOMPLETO', 'La variable no tiene una categoría de telemetría configurada.')
        return ReglaVariableI3P1(
            id_variable=fila['id_variable_ambiental'],
            tipo_variable=fila['codigo_telemetria'] or _normalizar_nombre(fila['nombre']),
            categoria=categoria,
            unidad_estandar=fila['unidad'],
            unidades_aceptadas=[fila['unidad']],
            valor_fisico_min=Decimal(str(fila['valor_fisico_min'])),
            valor_fisico_max=Decimal(str(fila['valor_fisico_max'])),
        )
