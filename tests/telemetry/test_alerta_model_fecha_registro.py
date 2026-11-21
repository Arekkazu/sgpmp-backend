"""modulo3.alertas.fecha_registro es NOT NULL DEFAULT now(). Sin server_default en el
modelo, SQLAlchemy inserta NULL explícito y toda alerta de SqlAlchemyAlertaRepository
(heartbeat, evaluación periódica, eventos de buffer) falla con NotNullViolation."""
from sqlalchemy.dialects import postgresql

from src.telemetry.infrastructure.models.alerta_model import AlertaModel


def test_el_insert_del_orm_no_manda_fecha_registro_nula():
    columnas_none = AlertaModel.__mapper__._insert_cols_as_none[AlertaModel.__table__]
    assert "fecha_registro" not in columnas_none
    assert AlertaModel.__table__.c.fecha_registro.server_default is not None
    assert "now()" in str(AlertaModel.__table__.c.fecha_registro.server_default.arg.compile(dialect=postgresql.dialect()))
