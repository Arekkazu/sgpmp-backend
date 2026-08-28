"""Implementación SQLAlchemy del puerto de dominio :class:`EventoRepository`.

Mapea filas de la tabla ``eventos`` a la entidad :class:`Evento` y recalcula el
hash SHA-256 de cada registro para devolver el flag de integridad: si el hash
almacenado no coincide con el recalculado, el evento pudo ser alterado
directamente en la tabla.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from src.identity_access.domain.entities.evento import Evento
from src.identity_access.domain.repositories.evento_repository import EventoRepository
from src.identity_access.domain.value_objects.evento_categoria import (
    EventoCategoria,
    categoria_para_tipo_evento,
    nombre_para_tipo_evento,
    tipos_evento_para_categoria,
)
from src.identity_access.infrastructure.models.enums_models import EnumEventoResultado
from src.identity_access.infrastructure.models.eventos_archivados_model import EventosArchivados
from src.identity_access.infrastructure.models.eventos_model import Eventos
from src.identity_access.infrastructure.models.integridad_baseline_model import IntegridadBaseline
from src.identity_access.infrastructure.models.sesiones_model import Sesiones
from src.identity_access.infrastructure.models.usuarios_model import Usuarios
from src.shared.audit_context import LARGO_MAX_IP, LARGO_MAX_USER_AGENT, obtener_origen
from src.shared.errors import InfrastructureError


class SqlAlchemyEventoRepository(EventoRepository):
    """Adaptador SQLAlchemy de lectura para la tabla ``eventos``."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _a_entidad(orm: Eventos | EventosArchivados) -> Evento:
        """Convierte una fila ORM de eventos (activos o archivados) en :class:`Evento`.

        ``EventosArchivados`` replica los nombres de columna de ``Eventos``, así que
        la conversión y la verificación del hash sirven para ambos sin duplicarse.
        """
        try:
            categoria = categoria_para_tipo_evento(orm.tipo_evento).value
        except ValueError:
            # Conserva accesibles los eventos históricos de tipos externos o
            # aún no catalogados. Los eventos nuevos desconocidos se rechazan.
            categoria = orm.categoria

        return Evento(
            id_evento=orm.id_evento,
            tipo_evento=orm.tipo_evento,
            fecha_evento=orm.fecha_evento,
            modulo=orm.modulo,
            resultado=getattr(orm.resultado, "value", orm.resultado),
            detalle=orm.detalle,
            id_usuario=orm.id_usuario,
            categoria=categoria,
            estado=orm.estado,
            id_sesion=orm.id_sesion,
            nombre_usuario=orm.nombre_usuario,
            direccion_ip=orm.direccion_ip,
            user_agent=orm.user_agent,
            descripcion=orm.descripcion,
        )

    def listar_eventos(
        self,
        id_usuario: Optional[int],
        tipo_evento: Optional[int],
        fecha_desde: Optional[datetime],
        fecha_hasta: Optional[datetime],
        offset: int,
        limit: int,
        categoria: Optional[EventoCategoria] = None,
        archivados: bool = False,
    ) -> list[tuple[Evento, str]]:
        modelo = EventosArchivados if archivados else Eventos
        eventos = (
            self._query_con_filtros(
                id_usuario,
                tipo_evento,
                categoria,
                fecha_desde,
                fecha_hasta,
                modelo,
            )
            .order_by(modelo.fecha_evento.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        clasificacion = self.clasificar_integridad(eventos)
        return [(self._a_entidad(e), clasificacion[e.id_evento]) for e in eventos]

    def contar_eventos(
        self,
        id_usuario: Optional[int],
        tipo_evento: Optional[int],
        fecha_desde: Optional[datetime],
        fecha_hasta: Optional[datetime],
        categoria: Optional[EventoCategoria] = None,
        archivados: bool = False,
    ) -> int:
        return self._query_con_filtros(
            id_usuario,
            tipo_evento,
            categoria,
            fecha_desde,
            fecha_hasta,
            EventosArchivados if archivados else Eventos,
        ).count()

    def _query_con_filtros(
        self,
        id_usuario,
        tipo_evento,
        categoria,
        fecha_desde,
        fecha_hasta,
        modelo=Eventos,
    ):
        query = self.db.query(modelo)
        if id_usuario is not None:
            query = query.filter(modelo.id_usuario == id_usuario)
        if tipo_evento is not None:
            query = query.filter(modelo.tipo_evento == tipo_evento)
        if categoria is not None:
            # La columna de los eventos históricos contiene el valor erróneo
            # AUTENTICACION. Filtrar por tipos canónicos permite consultarlos
            # correctamente sin violar la inmutabilidad de la auditoría.
            query = query.filter(
                modelo.tipo_evento.in_(tipos_evento_para_categoria(categoria))
            )
        if fecha_desde is not None:
            query = query.filter(modelo.fecha_evento >= fecha_desde)
        if fecha_hasta is not None:
            query = query.filter(modelo.fecha_evento <= fecha_hasta)
        return query

    @staticmethod
    def _calcular_hash(evento: Eventos | EventosArchivados) -> str:
        """Recalcula el SHA-256 del contenido de un evento ya persistido."""
        contenido = json.dumps({
            "tipo_evento": evento.tipo_evento,
            "fecha_evento": evento.fecha_evento.isoformat() if evento.fecha_evento else None,
            "id_usuario": evento.id_usuario,
            "resultado": evento.resultado.value if hasattr(evento.resultado, "value") else evento.resultado,
            "modulo": evento.modulo,
            "detalle": evento.detalle,
        }, sort_keys=True, default=str)
        return hashlib.sha256(contenido.encode("utf-8")).hexdigest()

    def _verificar_hash(self, evento: Eventos | EventosArchivados) -> bool:
        """Indica si el hash almacenado coincide con el recalculado.

        Un evento sin ``hash_integridad`` cuenta como **no** íntegro: RF-10
        declara el hash obligatorio, así que su ausencia no puede reportarse
        como registro sano.
        """
        if evento.hash_integridad is None:
            return False
        return self._calcular_hash(evento) == evento.hash_integridad

    def clasificar_integridad(
        self,
        eventos: list[Eventos | EventosArchivados],
    ) -> dict[int, str]:
        """Clasifica cada evento en ``INTEGRO``, ``LEGADO`` o ``MANIPULADO``.

        ``LEGADO`` son los registros que ya no eran verificables cuando se adoptó
        la verificación estricta (hash de un esquema anterior, o sin hash) y que
        no han cambiado desde entonces: siguen reportándose como no íntegros,
        pero no son evidencia de manipulación y no escalan a 500. Si el contenido
        de uno de ellos cambia, su recálculo deja de coincidir con la línea base
        y pasa a ``MANIPULADO``.
        """
        sospechosos = {e.id_evento: e for e in eventos if not self._verificar_hash(e)}
        if not sospechosos:
            return {e.id_evento: "INTEGRO" for e in eventos}

        baseline = {
            fila.id_evento: fila.hash_calculado
            for fila in self.db.query(IntegridadBaseline)
            .filter(IntegridadBaseline.id_evento.in_(sospechosos.keys()))
            .all()
        }

        clasificacion: dict[int, str] = {}
        for evento in eventos:
            if evento.id_evento not in sospechosos:
                clasificacion[evento.id_evento] = "INTEGRO"
            elif evento.id_evento not in baseline:
                clasificacion[evento.id_evento] = "MANIPULADO"
            elif baseline[evento.id_evento] == self._calcular_hash(evento):
                clasificacion[evento.id_evento] = "LEGADO"
            else:
                clasificacion[evento.id_evento] = "MANIPULADO"
        return clasificacion

    # ── Escritura de eventos (comando) ──────────────────────────────────────
    def registrar(
        self,
        tipo_evento: int,
        exitoso: bool,
        id_usuario: int,
        detalle: dict,
        id_sesion: Optional[int] = None,
        descripcion: Optional[str] = None,
    ) -> None:
        # El hash SHA-256 cubre los campos clave del evento para detectar
        # modificaciones posteriores en la tabla de auditoría.
        try:
            categoria = categoria_para_tipo_evento(tipo_evento)
        except ValueError as exc:
            raise InfrastructureError(
                code="CATEGORIA_EVENTO_NO_DEFINIDA",
                message=(
                    "No se pudo registrar la auditoría porque el tipo de evento "
                    "no tiene una categoría configurada."
                ),
                original_error=exc,
                field="tipo_evento",
            ) from exc

        # RF-10 exige IP, user-agent y sesión en cada registro. El caso de uso que
        # ya los conoce los pasa explícitamente; el resto los hereda del contexto
        # del request, de modo que ningún punto de registro quede sin ellos.
        origen = obtener_origen()
        detalle_completo = dict(detalle)
        if origen.ip and "ip" not in detalle_completo:
            detalle_completo["ip"] = origen.ip
        if origen.user_agent and "user_agent" not in detalle_completo:
            detalle_completo["user_agent"] = origen.user_agent

        try:
            if id_sesion is None and origen.id_token is not None:
                id_sesion = self._resolver_id_sesion(origen.id_token)
            nombre_usuario = self._resolver_nombre_usuario(id_usuario)

            resultado = EnumEventoResultado.EXITOSO if exitoso else EnumEventoResultado.FALLIDO
            fecha = datetime.now(timezone.utc)
            # La IP y el user-agent viajan dentro de `detalle`, así que el hash ya
            # los cubre sin cambiar la fórmula ni invalidar los eventos previos.
            contenido_hash = json.dumps({
                "tipo_evento": tipo_evento,
                "fecha_evento": fecha.isoformat(),
                "id_usuario": id_usuario,
                "resultado": resultado.value,
                "modulo": "MODULO1",
                "detalle": detalle_completo,
            }, sort_keys=True, default=str)
            hash_integridad = hashlib.sha256(contenido_hash.encode("utf-8")).hexdigest()

            evento = Eventos(
                tipo_evento=tipo_evento,
                fecha_evento=fecha,
                modulo="MODULO1",
                resultado=resultado,
                detalle=detalle_completo,
                id_usuario=id_usuario,
                categoria=categoria.value,
                estado="PROCESADO",
                id_sesion=id_sesion,
                hash_integridad=hash_integridad,
                nombre_usuario=nombre_usuario,
                direccion_ip=(detalle_completo.get("ip") or None) and str(detalle_completo["ip"])[:LARGO_MAX_IP],
                user_agent=(detalle_completo.get("user_agent") or None) and str(detalle_completo["user_agent"])[:LARGO_MAX_USER_AGENT],
                descripcion=descripcion or nombre_para_tipo_evento(tipo_evento),
            )
            self.db.add(evento)
            self.db.flush()
        except Exception as exc:
            # FA "Fallo de persistencia obligatoria": la auditoría es obligatoria,
            # así que el caso de uso revierte la acción principal. Aquí se traduce
            # el fallo técnico al mensaje que exige el RF.
            raise InfrastructureError(
                code="AUDITORIA_OBLIGATORIA_FALLIDA",
                message=(
                    "Fallo crítico de seguridad: No se pudo generar el registro de "
                    "auditoría obligatorio. La operación "
                    f"{nombre_para_tipo_evento(tipo_evento)} ha sido cancelada para "
                    "garantizar la trazabilidad del sistema."
                ),
                original_error=exc,
            ) from exc

    def _resolver_id_sesion(self, id_token: int) -> Optional[int]:
        """Deriva la sesión activa a partir del token del request en curso.

        Es enriquecimiento del registro, no su contenido obligatorio: si no se
        puede resolver, el evento se guarda igual. Lo que no puede fallar es la
        escritura del evento, y de eso se encarga el bloque que llama a esto.
        """
        try:
            return (
                self.db.query(Sesiones.id_sesion)
                .filter(Sesiones.id_token == id_token)
                .order_by(Sesiones.id_sesion.desc())
                .limit(1)
                .scalar()
            )
        except Exception:
            return None

    def _resolver_nombre_usuario(self, id_usuario: int) -> Optional[str]:
        """Congela el nombre del actor al momento del evento.

        Se guarda desnormalizado a propósito: el registro debe seguir
        identificando a quién actuó aunque el usuario cambie de nombre después.
        """
        try:
            fila = (
                self.db.query(Usuarios.nombre, Usuarios.apellidos, Usuarios.correo_electronico)
                .filter(Usuarios.id_usuario == id_usuario)
                .first()
            )
        except Exception:
            return None
        if fila is None:
            return None
        nombre_completo = " ".join(p for p in (fila.nombre, fila.apellidos) if p).strip()
        return (nombre_completo or fila.correo_electronico or "")[:80] or None

    def contar_solicitudes_recuperacion_por_ip(self, ip: str, desde: datetime) -> int:
        # .astext extrae el valor de texto de la columna JSONB sin comillas adicionales.
        return (
            self.db.query(func.count(Eventos.id_evento))
            .filter(
                Eventos.tipo_evento == 7,
                Eventos.fecha_evento >= desde,
                Eventos.detalle["ip"].astext == ip,
            )
            .scalar()
        )

    def adquirir_bloqueo_archivado(self) -> bool:
        """Evita que dos réplicas ejecuten simultáneamente el archivado diario."""
        return bool(
            self.db.execute(
                text("SELECT pg_try_advisory_xact_lock(:lock_id)"),
                {"lock_id": 10101608},
            ).scalar_one()
        )

    def archivar_eventos_anteriores(
        self,
        fecha_corte: datetime,
        limite: int,
    ) -> int:
        """Copia en forma idempotente un lote hacia el histórico inmutable."""
        return int(
            self.db.execute(
                text(
                    """
                    WITH candidatos AS (
                        SELECT
                            e.id_evento,
                            e.tipo_evento,
                            e.fecha_evento,
                            e.modulo,
                            e.resultado,
                            e.detalle,
                            e.id_usuario,
                            e.categoria,
                            e.estado,
                            e.descripcion,
                            e.id_sesion,
                            e.hash_integridad,
                            e.nombre_usuario,
                            e.direccion_ip,
                            e.user_agent
                        FROM modulo1.eventos AS e
                        WHERE e.fecha_evento < :fecha_corte
                          AND NOT EXISTS (
                              SELECT 1
                              FROM modulo1.eventos_archivados AS a
                              WHERE a.id_evento = e.id_evento
                          )
                        ORDER BY e.fecha_evento, e.id_evento
                        LIMIT :limite
                    ),
                    insertados AS (
                        INSERT INTO modulo1.eventos_archivados (
                            id_evento,
                            tipo_evento,
                            fecha_evento,
                            modulo,
                            resultado,
                            detalle,
                            id_usuario,
                            categoria,
                            estado,
                            descripcion,
                            id_sesion,
                            hash_integridad,
                            nombre_usuario,
                            direccion_ip,
                            user_agent
                        )
                        SELECT
                            id_evento,
                            tipo_evento,
                            fecha_evento,
                            modulo,
                            resultado,
                            detalle,
                            id_usuario,
                            categoria,
                            estado,
                            descripcion,
                            id_sesion,
                            hash_integridad,
                            nombre_usuario,
                            direccion_ip,
                            user_agent
                        FROM candidatos
                        ON CONFLICT (id_evento) DO NOTHING
                        RETURNING id_evento
                    )
                    SELECT count(*) FROM insertados
                    """
                ),
                {
                    "fecha_corte": fecha_corte,
                    "limite": limite,
                },
            ).scalar_one()
        )
