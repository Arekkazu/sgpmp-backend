# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-14/RF-87: notificaciones internas al Contador |
# | 2026-11-10 | —        | TC-M06-G109: el aviso QA no consulta a todos los Contadores |
# | 2026-11-10 | —        | TC-M06-G109: la marca de vencimiento se reclama dentro de la transacción |
"""Adaptador de :class:`NotificacionFinancieraPort` sobre M01 (RF-10 + RF-14), mismo patrón que M05:
el aviso cuelga de un evento de ``modulo1.eventos`` y deja una notificación en la bandeja interna.
Hace su propio ``commit`` en una sesión aparte y nunca propaga errores.

El aviso a todos los Contadores conserva su camino. El candado y la revisión del catálogo
solo aplican cuando el detalle es una marca de vencimiento de precio."""
from __future__ import annotations

import json
import logging
from typing import Callable, Optional

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from src.financial_valuation.domain.repositories.notificacion_financiera_port import NotificacionFinancieraPort
from src.financial_valuation.infrastructure.configuracion_alertas import lista_cerrada_valida
from src.financial_valuation.infrastructure.reclamo_aviso import claves_candado, es_marca_vencimiento
from src.identity_access.domain.value_objects.evento_categoria import (
    categoria_para_tipo_evento,
    id_catalogado_para_nombre,
)
from src.identity_access.infrastructure.repositories.evento_repository import SqlAlchemyEventoRepository
from src.identity_access.infrastructure.repositories.notificacion_repository import SqlAlchemyNotificacionRepository
from src.shared.errors import InfrastructureError

logger = logging.getLogger(__name__)

_ID_CANAL_INTERNO = 2
_SQL_CONTADORES = text("""
    SELECT DISTINCT u.id_usuario FROM modulo1.usuarios u JOIN modulo1.roles r ON r.id_rol = u.id_rol
    LEFT JOIN modulo9.usuarios_fincas uf ON uf.id_usuario = u.id_usuario AND uf.es_activo
    WHERE r.nombre_rol = 'Contador' AND (CAST(:finca AS integer) IS NULL OR uf.id_finca = :finca)
""")

_SQL_YA_NOTIFICADO = text("""
    SELECT EXISTS (SELECT 1 FROM modulo1.eventos e JOIN modulo1.tipos_eventos t ON t.id_tipo_evento = e.tipo_evento
                   WHERE t.nombre = :n AND e.modulo = 'MODULO6' AND e.detalle @> CAST(:d AS jsonb))
""")

_SQL_USUARIOS_EXPLICITOS = text("""
    SELECT id_usuario FROM modulo1.usuarios WHERE id_usuario IN :ids
""").bindparams(bindparam("ids", expanding=True))

_SQL_CANDADO = text("SELECT pg_advisory_xact_lock(:precio, :aviso)")


class NotificacionFinancieraM01Adapter(NotificacionFinancieraPort):
    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory

    def a_contadores(self, tipo_evento: str, mensaje: str, detalle: dict, id_finca: Optional[int] = None) -> None:
        db = self.session_factory()
        try:
            destinatarios = sorted({f.id_usuario for f in db.execute(_SQL_CONTADORES, {"finca": id_finca})})
            id_tipo = db.execute(text("SELECT id_tipo_evento FROM modulo1.tipos_eventos WHERE nombre = :n"),
                                 {"n": tipo_evento}).scalar()
            if not destinatarios or id_tipo is None:
                return
            if es_marca_vencimiento(detalle) and not self._reclamar_marca(db, tipo_evento, id_tipo, detalle):
                return
            notificaciones = SqlAlchemyNotificacionRepository(db)
            SqlAlchemyEventoRepository(db).registrar(
                tipo_evento=id_tipo, exitoso=True, id_usuario=destinatarios[0], detalle=detalle,
                descripcion=mensaje[:255], modulo="MODULO6",
            )
            id_evento = notificaciones.buscar_ultimo_evento_id(id_usuario=destinatarios[0], tipo_evento=id_tipo)
            for id_usuario in destinatarios:
                notificaciones.registrar(id_evento=id_evento, id_usuario=id_usuario, id_canal=_ID_CANAL_INTERNO,
                                         mensaje=mensaje, estado="en_cola")
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("No se pudo notificar %s a los contadores.", tipo_evento)
        finally:
            db.close()

    def a_usuarios_autorizados(self, id_usuarios, tipo_evento: str, mensaje: str, detalle: dict) -> bool:
        """Entrega el aviso solo a la lista recibida. No consulta el rol Contador."""
        if not lista_cerrada_valida(id_usuarios):
            logger.error("Alerta de vencimiento M06 no enviada: la lista QA no es válida.")
            return False
        destinatarios = tuple(dict.fromkeys(id_usuarios))
        db = self.session_factory()
        try:
            encontrados = {
                fila.id_usuario
                for fila in db.execute(_SQL_USUARIOS_EXPLICITOS, {"ids": list(destinatarios)})
            }
            if encontrados != set(destinatarios):
                logger.error("Alerta de vencimiento M06 no enviada: la lista QA no pudo confirmarse.")
                return False
            id_tipo = db.execute(text("SELECT id_tipo_evento FROM modulo1.tipos_eventos WHERE nombre = :n"),
                                 {"n": tipo_evento}).scalar()
            if id_tipo is None or not self._reclamar_marca(db, tipo_evento, id_tipo, detalle):
                return False
            notificaciones = SqlAlchemyNotificacionRepository(db)
            SqlAlchemyEventoRepository(db).registrar(
                tipo_evento=id_tipo, exitoso=True, id_usuario=destinatarios[0], detalle=detalle,
                descripcion=mensaje[:255], modulo="MODULO6",
            )
            id_evento = notificaciones.buscar_ultimo_evento_id(id_usuario=destinatarios[0], tipo_evento=id_tipo)
            for id_usuario in destinatarios:
                notificaciones.registrar(id_evento=id_evento, id_usuario=id_usuario, id_canal=_ID_CANAL_INTERNO,
                                         mensaje=mensaje, estado="en_cola")
            db.commit()
            return True
        except InfrastructureError as exc:
            db.rollback()
            if exc.code == "CATEGORIA_EVENTO_NO_DEFINIDA":
                logger.error("Alerta M06 no enviada: el tipo %s no tiene categoría en el código.", tipo_evento)
            else:
                logger.error("No se pudo notificar %s por la vía QA.", tipo_evento)
            return False
        except Exception:
            db.rollback()
            logger.error("No se pudo notificar %s por la vía QA.", tipo_evento)
            return False
        finally:
            db.close()

    def ya_notificado(self, tipo_evento: str, detalle: dict) -> bool:
        db = self.session_factory()
        try:
            return bool(db.execute(_SQL_YA_NOTIFICADO, {"n": tipo_evento, "d": json.dumps(detalle)}).scalar())
        finally:
            db.close()

    def _reclamar_marca(self, db, tipo_evento: str, id_tipo, detalle: dict) -> bool:
        """Reclama la marca de vencimiento. Falso si el catálogo no coincide o la marca ya existe."""
        esperado = id_catalogado_para_nombre(tipo_evento)
        if esperado is not None and int(id_tipo) != esperado:
            logger.error(
                "Alerta M06 no enviada: el tipo %s tiene id %s en la base y el código lo asocia a %s.",
                tipo_evento, id_tipo, esperado,
            )
            return False
        try:
            categoria_para_tipo_evento(int(id_tipo))
        except (TypeError, ValueError):
            logger.error(
                "Alerta M06 no enviada: el tipo %s tiene id %s y no tiene categoría en el código.",
                tipo_evento, id_tipo,
            )
            return False
        if not es_marca_vencimiento(detalle):
            return True
        precio, aviso = claves_candado(detalle["id_precio_mercado"], detalle["aviso"])
        db.execute(_SQL_CANDADO, {"precio": precio, "aviso": aviso})
        marca = {"id_precio_mercado": detalle["id_precio_mercado"], "aviso": detalle["aviso"]}
        if db.execute(_SQL_YA_NOTIFICADO, {"n": tipo_evento, "d": json.dumps(marca)}).scalar():
            return False
        return True
