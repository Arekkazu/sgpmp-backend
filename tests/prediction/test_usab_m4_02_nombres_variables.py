# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-25 | Arekkazu | USAB-M04 M4-02 RF-64: la patología trae nombre de variables y especie |
"""M4-02: las patologías base mostraban "Variable 13 / 14 / 15 / 16" y la especie "221"."""
from src.prediction.domain.entities.patologia_m04 import PatologiaM04
from src.prediction.domain.entities.patologia_variable import PatologiaVariable
from src.prediction.infrastructure.repositories.patologia_m04_repository import SqlAlchemyPatologiaM04Repository


class _Filas:
    def __init__(self, filas):
        self.filas = filas

    def all(self):
        return self.filas


class _Db:
    def execute(self, sql, params):
        if 'variables_ambientales' in str(sql):
            return _Filas([(13, 'Temperatura Corporal', '°C'), (14, 'Frecuencia Cardiaca', 'bpm')])
        return _Filas([(221, 'Bovino QA')])


def _patologia(especie, *ids):
    return PatologiaM04(nombre='x', especie_aplicable=especie, descripcion_clinica='x', es_base=True,
                        es_activo=True, version_catalogo=1, variables=[PatologiaVariable(i) for i in ids])


def test_nombres_de_variables_y_especie():
    de_especie, todas = SqlAlchemyPatologiaM04Repository(_Db())._con_nombres(
        [_patologia('221', 13, 14), _patologia('TODAS', 99)])

    assert [(v.nombre, v.unidad) for v in de_especie.variables] == [
        ('Temperatura Corporal', '°C'), ('Frecuencia Cardiaca', 'bpm')]
    assert de_especie.nombre_especie == 'Bovino QA'
    # TODAS no es una especie; una variable fuera del catálogo queda sin nombre.
    assert todas.nombre_especie is None
    assert (todas.variables[0].nombre, todas.variables[0].unidad) == (None, None)
