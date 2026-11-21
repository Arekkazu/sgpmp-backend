from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert

from src.configuration.domain.entities.parametro_mlops import ParametroMLOps
from src.configuration.domain.repositories.parametros_mlops_port import ParametrosMLOpsPort
from src.prediction.infrastructure.models.parametro_mlops_model import ParametroMLOpsModel
from src.shared.db_error_translator import raise_from_db_error


class SqlAlchemyParametrosMLOpsRepository(ParametrosMLOpsPort):
    def __init__(self, db):
        self.db = db

    def bloquear_configuracion(self):
        try:
            self.db.execute(text('SELECT pg_advisory_xact_lock(3514, 1)'))
        except Exception as exc:
            raise_from_db_error(exc)

    def obtener(self, nombres):
        tabla = ParametroMLOpsModel.__table__
        try:
            # Columnas explícitas: no se devuelve una instancia ORM potencialmente
            # antigua del identity map al reutilizar la misma sesión/consumidor.
            filas = self.db.execute(select(tabla.c.nombre_parametro, tabla.c.valor_actual,
                tabla.c.rango_minimo, tabla.c.rango_maximo).where(tabla.c.nombre_parametro.in_(nombres))).all()
            return {f[0]: ParametroMLOps(*f) for f in filas}
        except Exception as exc:
            raise_from_db_error(exc)

    def guardar(self, parametros, id_usuario):
        tabla = ParametroMLOpsModel.__table__
        try:
            for p in sorted(parametros, key=lambda p: p.nombre):
                sentencia = insert(tabla).values(nombre_parametro=p.nombre, valor_actual=p.valor,
                    valor_por_defecto=p.valor, rango_minimo=p.minimo, rango_maximo=p.maximo,
                    id_usuario_modificador=id_usuario, fecha_modificacion=func.now())
                sentencia = sentencia.on_conflict_do_update(index_elements=[tabla.c.nombre_parametro], set_={
                    'valor_actual': sentencia.excluded.valor_actual,
                    'rango_minimo': sentencia.excluded.rango_minimo,
                    'rango_maximo': sentencia.excluded.rango_maximo,
                    'id_usuario_modificador': id_usuario,
                    'fecha_modificacion': func.now(),
                })
                self.db.execute(sentencia)
            self.db.flush()
        except Exception as exc:
            raise_from_db_error(exc)
