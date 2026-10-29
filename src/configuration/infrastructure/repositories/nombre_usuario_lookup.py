"""Nombre visible de los usuarios que M09 referencia por id (RF-18, RF-19).

Las pantallas de parámetros operativos y de fincas mostraban "usuario #29" y
"#12" porque las respuestas solo traían ``id_usuario``. Es una lectura simple
para armar la respuesta; bajo RLS un usuario sin permiso de lectura sobre
``usuarios`` solo ve su propio nombre, y para los demás queda ``None``.
"""
from __future__ import annotations

from typing import Iterable

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

_SQL = text(
    "SELECT id_usuario, trim(concat_ws(' ', nombre, apellidos)) AS nombre "
    "FROM modulo1.usuarios WHERE id_usuario IN :ids"
).bindparams(bindparam('ids', expanding=True))


def nombres_usuarios(db: Session, ids: Iterable[int | None]) -> dict[int, str]:
    """``{id_usuario: "Nombre Apellidos"}`` de los ids dados que el usuario actual puede leer."""
    unicos = sorted({i for i in ids if i is not None})
    if not unicos:
        return {}
    return {fila.id_usuario: fila.nombre for fila in db.execute(_SQL, {'ids': unicos}) if fila.nombre}
