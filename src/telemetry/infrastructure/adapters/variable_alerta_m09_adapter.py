# | Fecha      | Nombre  | Que se hizo                                      |
# |------------|---------|--------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-41 RF-53/57: identidad de variable entre canales |
# | 2026-10-28 | destroyerban | INC-M03-162-G68 RF-57: expone rango físico y es_critica para FALLO_AMBIENTAL |
"""Metadatos M09 para alertas, compatible con el catálogo previo y DEV-40.

No valida ingesta ni define otro catálogo: los alias previos se consultan solo
para compatibilidad mientras DEV-40 no está integrado. Su código persistido,
cuando existe, tiene precedencia. Se conserva el normalizador de nombres de
esa integración sin presuponer columnas nuevas en este esquema.
"""
import re
import unicodedata
from decimal import Decimal

from sqlalchemy import text

from src.shared.db_error_translator import raise_from_db_error
from src.shared.errors import ServiceUnavailableError
from src.telemetry.domain.entities import telemetria as contrato_telemetria
from src.telemetry.domain.repositories.variable_alerta_port import RangoFisicoVariable, VariableAlertaPort


def _normalizar_nombre(nombre):
    texto = unicodedata.normalize('NFKD', nombre).encode('ascii', 'ignore').decode('ascii')
    return re.sub(r'[^A-Z0-9]+', '_', texto.upper()).strip('_')


def variable_para_alerta(db, *, id_variable=None, codigo=None):
    legado = getattr(contrato_telemetria, 'CATALOGO_I3P1', {})
    if codigo is not None:
        codigo = codigo.upper().strip()
        entrada = legado.get(codigo)
        if entrada and id_variable is None:
            id_variable = entrada['id_variable']
    try:
        filas = db.execute(text('''SELECT to_jsonb(v) FROM modulo9.variables_ambientales v
            WHERE (:id IS NULL OR v.id_variable_ambiental=:id)'''), {'id': id_variable}).scalars().all()
    except Exception as exc:
        raise_from_db_error(exc)
    candidatas = []
    for fila in filas:
        aliases = [nombre for nombre, regla in legado.items()
                   if regla['id_variable'] == fila['id_variable_ambiental']]
        canonico = fila.get('codigo_telemetria') or (aliases[0] if aliases else _normalizar_nombre(fila['nombre']))
        equivalentes = list(dict.fromkeys([canonico, _normalizar_nombre(fila['nombre']), *aliases]))
        if codigo is None or codigo in equivalentes:
            candidatas.append({'id_variable': fila['id_variable_ambiental'], 'tipo_variable': canonico,
                    'unidad': fila['unidad'], 'nombre': fila['nombre'], 'aliases': equivalentes,
                    'valor_fisico_min': fila.get('valor_fisico_min'), 'valor_fisico_max': fila.get('valor_fisico_max'),
                    'es_critica': bool(fila.get('es_critica'))})
    if len(candidatas)>1:
        raise ServiceUnavailableError('CATALOGO_AMBIGUO', 'La identidad de la variable requiere revisión de M09.')
    return candidatas[0] if candidatas else None


class VariableAlertaM09Adapter(VariableAlertaPort):
    def __init__(self, db):
        self.db = db

    def obtener_rango_fisico(self, tipo_variable):
        variable = variable_para_alerta(self.db, codigo=tipo_variable)
        if variable is None:
            return None
        decimal = lambda v: None if v is None else Decimal(str(v))
        return RangoFisicoVariable(decimal(variable['valor_fisico_min']), decimal(variable['valor_fisico_max']),
                                   variable['es_critica'])
