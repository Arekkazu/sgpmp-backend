from sqlalchemy import DateTime, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class ParametroMLOpsModel(Base):
    __tablename__ = 'parametros_mlops'
    __table_args__ = {'schema': 'modulo4'}

    id_parametro: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre_parametro: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    valor_actual: Mapped[object] = mapped_column(JSONB, nullable=False)
    valor_por_defecto: Mapped[object] = mapped_column(JSONB, nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text)
    rango_minimo: Mapped[object | None] = mapped_column(Numeric)
    rango_maximo: Mapped[object | None] = mapped_column(Numeric)
    id_usuario_modificador: Mapped[int | None] = mapped_column(Integer)
    fecha_modificacion = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('now()'))
