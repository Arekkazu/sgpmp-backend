# | Fecha      | Nombre   | Que se hizo                                                  |
# |------------|----------|--------------------------------------------------------------|
# | 2026-11-18 | Arekkazu | M08 RF-107: catálogo de mensajes de error sobre modulo9      |
"""Implementación SQLAlchemy de :class:`CatalogoMensajesErrorRepository` sobre ``modulo9.catalogo_mensajes_error``.
La RLS deja leer a cualquiera y escribir a quien tenga el permiso sobre el recurso del catálogo."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.configuration.domain.entities.mensaje_error import MensajeError
from src.configuration.domain.repositories.catalogo_mensajes_error_repository import CatalogoMensajesErrorRepository
from src.shared.db_error_translator import raise_from_db_error

_COLUMNAS = "clave, idioma, mensaje, texto_accion, ruta_accion, es_activo, id_usuario, fecha_actualizacion"
_SQL_LISTAR = text(f"""SELECT {_COLUMNAS} FROM modulo9.catalogo_mensajes_error
                       WHERE CAST(:idioma AS text) IS NULL OR idioma = :idioma ORDER BY clave, idioma""")
_SQL_GUARDAR = text(f"""
    INSERT INTO modulo9.catalogo_mensajes_error (clave, idioma, mensaje, texto_accion, ruta_accion, es_activo, id_usuario)
    VALUES (:clave, :idioma, :mensaje, :texto_accion, :ruta_accion, :es_activo, :id_usuario)
    ON CONFLICT (clave, idioma) DO UPDATE SET mensaje = EXCLUDED.mensaje, texto_accion = EXCLUDED.texto_accion,
        ruta_accion = EXCLUDED.ruta_accion, es_activo = EXCLUDED.es_activo, id_usuario = EXCLUDED.id_usuario,
        fecha_actualizacion = now()
    RETURNING {_COLUMNAS}""")
_SQL_ELIMINAR = text("DELETE FROM modulo9.catalogo_mensajes_error WHERE clave = :clave AND idioma = :idioma")


class SqlAlchemyCatalogoMensajesErrorRepository(CatalogoMensajesErrorRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    def listar(self, idioma: Optional[str]) -> list[MensajeError]:
        return [MensajeError(**dict(f._mapping)) for f in self.db.execute(_SQL_LISTAR, {"idioma": idioma})]

    def guardar(self, mensaje: MensajeError) -> MensajeError:
        try:
            fila = self.db.execute(_SQL_GUARDAR, {
                "clave": mensaje.clave, "idioma": mensaje.idioma, "mensaje": mensaje.mensaje,
                "texto_accion": mensaje.texto_accion, "ruta_accion": mensaje.ruta_accion,
                "es_activo": mensaje.es_activo, "id_usuario": mensaje.id_usuario}).first()
            self.db.flush()
            return MensajeError(**dict(fila._mapping))
        except Exception as exc:
            raise_from_db_error(exc)

    def eliminar(self, clave: str, idioma: str) -> bool:
        try:
            borradas = self.db.execute(_SQL_ELIMINAR, {"clave": clave, "idioma": idioma}).rowcount
            self.db.flush()
            return bool(borradas)
        except Exception as exc:
            raise_from_db_error(exc)
