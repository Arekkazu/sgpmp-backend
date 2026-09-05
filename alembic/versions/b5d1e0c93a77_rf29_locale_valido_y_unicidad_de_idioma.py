"""rf29 lista blanca de locale_code y unicidad de preferencia de idioma

Revision ID: b5d1e0c93a77
Revises: a7f3c92e4d18
Create Date: 2026-09-03 09:00:00.000000

RF-29 — configuracion de idioma. El requerimiento restringe explicitamente el
sistema a espanol e ingles y pide rechazar cualquier otro ``locale_code``, pero
la restriccion solo vivia en la entidad de dominio. Tres huecos en la BD:

1. Sin CHECK sobre ``locale_code``. La aplicacion valida contra
   ``LOCALES_PERMITIDOS`` en los tres caminos de escritura, asi que por HTTP no
   entra basura; pero la columna es ``varchar(5)`` libre y cualquier escritura
   fuera de la aplicacion (script, migracion de datos, consola) persiste un
   locale que el frontend no sabe renderizar. El comentario de la columna
   incluso mencionaba ``pt-BR`` como ejemplo valido, contradiciendo al RF. Es la
   segunda capa de defensa que el resto del modulo 9 si tiene.

2. Sin unicidad de la preferencia personal. Igual que ``dashboard_layouts``
   antes de a7f3c92e4d18: dos PATCH concurrentes de un usuario sin fila previa
   insertan dos filas y ``obtener_por_usuario`` desempata por
   ``fecha_actualizacion DESC``, asi que la preferencia "ganadora" depende de un
   orden de llegada en vez de ser unica. El indice es parcial
   (``WHERE es_por_defecto = false``) porque un administrador puede tener a la
   vez su preferencia personal y ser el dueno de la fila global.

3. Sin unicidad del idioma global. ``obtener_global()`` asume una sola fila con
   ``es_por_defecto = true`` y desempata por fecha si hay varias. Un indice
   unico sobre una expresion constante fuerza esa suposicion en la BD.

El dedup previo conserva la fila mas reciente con el mismo criterio de
desempate que usa el repositorio. En dev es un no-op (4 filas, 0 duplicados,
todos los locale ya validos); va por seguridad ante cualquier otro entorno.

De paso se valida la FK ``id_usuario``, que estaba ``NOT VALID`` desde su
creacion — mismo caso que ``dashboard_layouts`` en RF-28.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b5d1e0c93a77"
down_revision: Union[str, Sequence[str], None] = "a7f3c92e4d18"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_LOCALES = ("es-CO", "en-US")
_LOCALE_DEFAULT = "es-CO"


def upgrade() -> None:
    # Normaliza antes del CHECK: cualquier locale fuera de la lista blanca cae al
    # espanol, que es el idioma por defecto y el fallback que prescribe el RF.
    # Sin esto, un entorno con datos sucios no puede aplicar la migracion.
    op.execute(
        f"""
        UPDATE modulo9.preferencias_idiomas
        SET locale_code = '{_LOCALE_DEFAULT}'
        WHERE locale_code NOT IN {_LOCALES}
        """
    )
    op.create_check_constraint(
        "chk_pref_idioma_locale_code",
        "preferencias_idiomas",
        f"locale_code IN {_LOCALES}",
        schema="modulo9",
    )

    # Dedup defensivo antes de los indices unicos. El criterio de desempate es el
    # mismo que usan obtener_por_usuario y obtener_global en el repositorio:
    # fecha_actualizacion DESC NULLS LAST, id_preferencia_idioma DESC.
    op.execute(
        """
        DELETE FROM modulo9.preferencias_idiomas a
        USING modulo9.preferencias_idiomas b
        WHERE a.es_por_defecto = false
          AND b.es_por_defecto = false
          AND a.id_usuario = b.id_usuario
          AND (
                (a.fecha_actualizacion IS NULL AND b.fecha_actualizacion IS NOT NULL)
             OR a.fecha_actualizacion < b.fecha_actualizacion
             OR (a.fecha_actualizacion IS NOT DISTINCT FROM b.fecha_actualizacion
                 AND a.id_preferencia_idioma < b.id_preferencia_idioma)
          )
        """
    )
    op.execute(
        """
        DELETE FROM modulo9.preferencias_idiomas a
        USING modulo9.preferencias_idiomas b
        WHERE a.es_por_defecto = true
          AND b.es_por_defecto = true
          AND (
                (a.fecha_actualizacion IS NULL AND b.fecha_actualizacion IS NOT NULL)
             OR a.fecha_actualizacion < b.fecha_actualizacion
             OR (a.fecha_actualizacion IS NOT DISTINCT FROM b.fecha_actualizacion
                 AND a.id_preferencia_idioma < b.id_preferencia_idioma)
          )
        """
    )

    # Una preferencia personal por usuario. Parcial: la fila global del admin no
    # compite con su preferencia personal.
    op.create_index(
        "uq_pref_idioma_personal",
        "preferencias_idiomas",
        ["id_usuario"],
        unique=True,
        schema="modulo9",
        postgresql_where="es_por_defecto = false",
    )
    # Una sola fila global en todo el sistema, sin importar de quien sea.
    op.execute(
        "CREATE UNIQUE INDEX uq_pref_idioma_global "
        "ON modulo9.preferencias_idiomas ((true)) "
        "WHERE es_por_defecto = true"
    )

    op.execute(
        "ALTER TABLE modulo9.preferencias_idiomas "
        "VALIDATE CONSTRAINT preferencias_idiomas_id_usuario_fkey"
    )
    op.execute(
        "COMMENT ON COLUMN modulo9.preferencias_idiomas.locale_code IS "
        "'Codigo de idioma y region (IETF BCP 47). RF-29 lo restringe a "
        "es-CO y en-US; agregar un idioma exige tocar el CHECK y los catalogos "
        "de traduccion del frontend.'"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS modulo9.uq_pref_idioma_global")
    op.drop_index("uq_pref_idioma_personal", table_name="preferencias_idiomas", schema="modulo9")
    op.drop_constraint(
        "chk_pref_idioma_locale_code",
        "preferencias_idiomas",
        schema="modulo9",
        type_="check",
    )
    # La FK vuelve a quedar NOT VALID: es el estado exacto previo a esta revision.
    op.drop_constraint(
        "preferencias_idiomas_id_usuario_fkey",
        "preferencias_idiomas",
        schema="modulo9",
        type_="foreignkey",
    )
    op.execute(
        "ALTER TABLE modulo9.preferencias_idiomas "
        "ADD CONSTRAINT preferencias_idiomas_id_usuario_fkey "
        "FOREIGN KEY (id_usuario) REFERENCES modulo1.usuarios(id_usuario) NOT VALID"
    )
    op.execute(
        "COMMENT ON COLUMN modulo9.preferencias_idiomas.locale_code IS "
        "'Codigo de idioma y region segun estandar IETF BCP 47 (ej: \"es-CO\", "
        "\"en-US\", \"pt-BR\").'"
    )
