"""RF-28: los datos de los widgets del tablero se filtran por las fincas del usuario."""
from src.configuration.infrastructure.repositories.widget_datos_repository import (
    _FUENTES_PERMITIDAS,
    SqlAlchemyWidgetDatosRepository,
)


class _Resultado:
    def mappings(self):
        return self

    def all(self):
        return []


class _Sesion:
    def __init__(self):
        self.consultas = []

    def execute(self, sql, parametros):
        self.consultas.append((str(sql), parametros))
        return _Resultado()


def test_todas_las_vistas_se_filtran_por_las_fincas_del_usuario():
    for fuente in _FUENTES_PERMITIDAS:
        sesion = _Sesion()
        SqlAlchemyWidgetDatosRepository(sesion).obtener(fuente, 42)
        sql, parametros = sesion.consultas[0]
        assert "fn_fincas_del_usuario(:usuario)" in sql and "WHERE id_finca IN" in sql
        assert parametros["usuario"] == 42


def test_fuente_desconocida_no_consulta():
    sesion = _Sesion()
    assert SqlAlchemyWidgetDatosRepository(sesion).obtener("modulo1.usuarios", 42) == []
    assert sesion.consultas == []
