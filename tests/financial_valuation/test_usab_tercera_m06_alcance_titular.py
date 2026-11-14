# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-12 | Arekkazu | USAB-M05-M06 N-04 RF-92/93: el Productor solo ve los titulares de sus fincas |
"""N-04 (tercera evaluación de usabilidad, 12-11): el selector de Finanzas del Productor ofrecía la razón
social, el NIT y los períodos de otras empresas. Quien no lee el cierre queda acotado a los NIT de sus
fincas en titulares, períodos, estados de resultados e informes de revelaciones. Se verificó contra la BD
de DEV con RLS (rol sgpmp_app): el Productor 105 pasa de ver el período «Sin titular» a ver solo su NIT y
el Administrador conserva los 6 períodos."""
from __future__ import annotations

from src.financial_valuation.infrastructure.repositories import periodo_repository, reporte_repository
from src.financial_valuation.infrastructure.repositories.sql import alcance_periodo, alcance_titular


class _Db:
    """Guarda el SQL de cada consulta; no devuelve filas."""

    def __init__(self):
        self.sql: list[str] = []

    def execute(self, sql, _params=None):
        self.sql.append(str(sql))
        return _Resultado()


class _Resultado:
    def mappings(self):
        return self

    def first(self):
        return None

    def all(self):
        return []

    def __iter__(self):
        return iter([])


def test_el_alcance_exige_leer_el_cierre_o_ser_de_las_fincas_propias():
    sql = alcance_titular("pc.numero_id_tributaria")
    assert "fn_tiene_permiso('cierre_periodo', 'R')" in sql
    assert "pc.numero_id_tributaria IN (SELECT f.numero_id_tributaria FROM modulo9.fincas f)" in sql
    assert alcance_titular("pa.numero_id_tributaria") in alcance_periodo("i.id_periodo_contable")


def test_titulares_periodos_estados_e_informes_aplican_el_alcance():
    db = _Db()
    periodos = periodo_repository.SqlAlchemyPeriodoRepository(db)
    periodos.titulares()
    periodos.listar(None)
    periodos.obtener(7)
    reportes = reporte_repository.SqlAlchemyReporteRepository(db)
    reportes.obtener_estado(1)
    reportes.listar_estados(7)
    reportes.obtener_informe(1)
    reportes.listar_informes(7)
    assert len(db.sql) == 7 and all("fn_tiene_permiso('cierre_periodo', 'R')" in s for s in db.sql)
    # La subconsulta compara con la columna de la tabla externa, no consigo misma (sería siempre verdadera).
    assert all("pa.id_periodo_contable = id_periodo_contable" not in s for s in db.sql)


def test_el_cierre_bloquea_el_periodo_sin_el_alcance():
    db = _Db()
    periodo_repository.SqlAlchemyPeriodoRepository(db).obtener(7, bloquear=True)
    assert "FOR UPDATE NOWAIT" in db.sql[0] and "fn_tiene_permiso" not in db.sql[0]
