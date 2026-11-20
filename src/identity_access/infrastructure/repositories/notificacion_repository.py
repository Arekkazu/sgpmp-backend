# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-11-14 | Arekkazu | M08 RF-105: nivel, agrupación, filtros de bandeja, entrega y purga  |
# | 2026-11-18 | Arekkazu | M08 RF-105: escalamiento, auditoría de cada notificación, preferencias y ventana de M09 |
"""Implementación SQLAlchemy del puerto de dominio :class:`NotificacionRepository`.

Traduce el estado de envío de texto al enum ``EnumEstadoEnvio`` de la columna y
gestiona el registro de notificaciones, el control anti-spam por ventana
temporal y la consulta/registro de dispositivos FCM.

RF-105: el nivel definitivo sale del tipo de evento (nunca más bajo que el sugerido), la bandeja se
ordena por nivel y luego por fecha, y ``es_leido`` se mantiene sincronizada con ``estado`` mientras
el front anterior la siga leyendo.

Fase 5: cada notificación interna creada, cada cambio de estado (LEÍDA, ATENDIDA, DESCARTADA) y cada entrega
por push o correo deja un evento inmutable ``AUDITORIA_NOTIFICACION`` (tipo 46). Se registra en un savepoint:
si la auditoría falla, la notificación no se pierde (queda en el log técnico).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import case, func, text
from sqlalchemy.orm import Session

from src.identity_access.domain.entities.notificacion import Notificacion
from src.identity_access.domain.repositories.notificacion_repository import (
    EntregaPendiente,
    FiltroBandeja,
    NotificacionRepository,
)
from src.identity_access.domain.value_objects.nivel_notificacion import (
    CRITICA,
    INFORMATIVA,
    LEIDA,
    NUEVA,
    NUMERO_POR_MODULO,
    VENTANA_AGRUPACION_POR_DEFECTO,
    canal_por_defecto,
    destino_por_defecto,
    modulo_desde,
    nivel_para,
)
from src.identity_access.infrastructure.models.cuenta_usuarios_model import CuentasUsuarios
from src.identity_access.infrastructure.models.dispositivos_fcm_model import DispositivosFcm
from src.identity_access.infrastructure.models.enums_models import EnumEstadoEnvio
from src.identity_access.infrastructure.models.eventos_model import Eventos
from src.identity_access.infrastructure.models.notificaciones_model import Notificaciones
from src.identity_access.infrastructure.models.usuarios_model import Usuarios
from src.identity_access.infrastructure.repositories.evento_repository import SqlAlchemyEventoRepository
from src.shared.db_error_translator import raise_from_db_error

logger = logging.getLogger(__name__)


ID_CANAL_INTERNO = 2
_INTENTOS_PUSH_MAX = 4  # el primero y tres reintentos (RF-105 restricción 5)
# Un push que no salió en un día ya no avisa de nada útil: queda solo en la bandeja.
_VENTANA_ENTREGA = timedelta(days=1)
_ORDEN_NIVEL = case((Notificaciones.nivel == CRITICA, 0), (Notificaciones.nivel == "ADVERTENCIA", 1), else_=2)
_NUMERO_MODULO = func.regexp_replace(Eventos.modulo, "[^0-9]", "", "g")

TIPO_AUDITORIA_NOTIFICACION = 46
_CANALES = {1: "EMAIL", 2: "IN_APP"}
# RF-105 Fase 1: un aviso sanitario sobre un animal con 3+ alertas críticas en 7 días sube a CRÍTICA.
_MODULOS_SANITARIOS = ("telemetria", "prediccion")
_DIAS_ESCALAMIENTO, _CRITICAS_ESCALAMIENTO = 7, 3
_SQL_PREFERENCIAS = text("""
    SELECT nivel::text AS nivel, canal::text AS canal, es_habilitado
    FROM modulo9.preferencias_notificaciones WHERE id_usuario = :u""")
_SQL_GUARDAR_PREFERENCIA = text("""
    INSERT INTO modulo9.preferencias_notificaciones (id_usuario, nivel, canal, es_habilitado)
    VALUES (:u, CAST(:nivel AS modulo1.enum_notificacion_nivel),
            CAST(:canal AS modulo9.enum_preferencia_notificacion_canal), :habilitado)
    ON CONFLICT (id_usuario, nivel, canal)
    DO UPDATE SET es_habilitado = EXCLUDED.es_habilitado, fecha_actualizacion = now()""")
_SQL_VENTANA = text("""SELECT COALESCE(valor_actual, valor_por_defecto) FROM modulo4.parametros_mlops
                       WHERE nombre_parametro = 'ventana_agrupacion_notificaciones_min'""")
_SQL_ORIGEN_EVENTO = text("""
    SELECT te.nombre AS tipo, e.modulo
    FROM modulo1.eventos e
    LEFT JOIN modulo1.tipos_eventos te ON te.id_tipo_evento = e.tipo_evento
    WHERE e.id_evento = :id""")


class SqlAlchemyNotificacionRepository(NotificacionRepository):
    """Adaptador SQLAlchemy para ``Notificaciones`` y ``DispositivosFcm``."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _a_entidad(orm: Notificaciones, tipo_evento: int, modulo: Optional[str] = None) -> Notificacion:
        return Notificacion(
            id_notificacion=orm.id_notificacion,
            id_evento=orm.id_evento,
            tipo_evento=tipo_evento,
            id_usuario=orm.id_usuario,
            mensaje=orm.mensaje,
            fecha_envio=orm.fecha_envio,
            es_leido=orm.es_leido,
            estado_envio=getattr(orm.estado_envio, "value", orm.estado_envio),
            nivel=orm.nivel or INFORMATIVA,
            estado=orm.estado or NUEVA,
            modulo=modulo_desde(modulo),
            accion_documentada=orm.accion_documentada,
            fecha_lectura=orm.fecha_lectura,
            fecha_atencion=orm.fecha_atencion,
            fecha_descarte=orm.fecha_descarte,
            ocurrencias=orm.ocurrencias or 1,
            fecha_ultima_ocurrencia=orm.fecha_ultima_ocurrencia,
            contexto=dict(orm.json_contexto or {}),
        )

    def registrar(
        self,
        id_evento: int,
        id_usuario: int,
        id_canal: int,
        mensaje: str,
        estado: str,
        *,
        nivel: Optional[str] = None,
        id_activo_biologico: Optional[int] = None,
        contexto: Optional[dict[str, Any]] = None,
        entrega_inmediata: bool = False,
    ) -> int:
        origen = self.db.execute(_SQL_ORIGEN_EVENTO, {"id": id_evento}).first()
        modulo = modulo_desde(origen.modulo if origen else None)
        ahora = datetime.now(timezone.utc)
        nivel_final = nivel_para(origen.tipo if origen else None, nivel)
        if (nivel_final != CRITICA and id_activo_biologico is not None and modulo in _MODULOS_SANITARIOS
                and self._criticas_recientes(id_usuario, id_activo_biologico, ahora) >= _CRITICAS_ESCALAMIENTO):
            nivel_final = CRITICA
        notificacion = Notificaciones(
            id_evento=id_evento,
            id_usuario=id_usuario,
            id_notificacion_canal=id_canal,
            mensaje=mensaje,
            fecha_envio=ahora,
            es_leido=False,
            estado_envio=EnumEstadoEnvio(estado),
            nivel=nivel_final,
            estado=NUEVA,
            id_activo_biologico=id_activo_biologico,
            json_contexto={"url": destino_por_defecto(modulo), **(contexto or {})},
            ocurrencias=1,
            # Quien registra ya intenta el push; el entregador espera al primer reintento.
            intentos_push=1 if entrega_inmediata else 0,
            fecha_proximo_intento=ahora + timedelta(minutes=1) if entrega_inmediata else None,
        )
        self.db.add(notificacion)
        self.db.flush()
        self.db.refresh(notificacion)
        if id_canal == ID_CANAL_INTERNO:
            self._auditar(id_usuario, {"accion": "CREADA", "id_notificacion": notificacion.id_notificacion,
                                       "nivel": nivel_final, "canal": "IN_APP", "modulo": modulo, "estado": NUEVA})
        return notificacion.id_notificacion

    def _criticas_recientes(self, id_usuario: int, id_activo: int, ahora: datetime) -> int:
        return (self.db.query(func.count(Notificaciones.id_notificacion))
                .filter(Notificaciones.id_usuario == id_usuario,
                        Notificaciones.id_notificacion_canal == ID_CANAL_INTERNO,
                        Notificaciones.id_activo_biologico == id_activo, Notificaciones.nivel == CRITICA,
                        Notificaciones.fecha_envio >= ahora - timedelta(days=_DIAS_ESCALAMIENTO))
                .scalar() or 0)

    def _auditar(self, id_usuario: int, detalle: dict[str, Any]) -> None:
        """Evento inmutable de la notificación (RF-105 Fase 5) en un savepoint: si falla, la notificación sigue."""
        try:
            with self.db.begin_nested():
                SqlAlchemyEventoRepository(self.db).registrar(
                    tipo_evento=TIPO_AUDITORIA_NOTIFICACION, exitoso=True, id_usuario=id_usuario, detalle=detalle,
                    descripcion=f"Notificación {detalle.get('accion', '').lower()}", modulo="MODULO8")
        except Exception:
            logger.exception("RF-105: no se pudo auditar la notificación %s", detalle.get("id_notificacion"))

    # --- Preferencias (R6) y ventana de agrupación (Fase 2.1) ---

    def preferencias(self, id_usuario: int) -> dict[tuple[str, str], bool]:
        return {(f.nivel, f.canal): f.es_habilitado for f in self.db.execute(_SQL_PREFERENCIAS, {"u": id_usuario})}

    def canal_habilitado(self, id_usuario: int, nivel: str, canal: str) -> bool:
        try:
            with self.db.begin_nested():
                guardada = self.preferencias(id_usuario).get((nivel, canal))
        except Exception:
            logger.exception("RF-105: no se pudieron leer las preferencias del usuario %s", id_usuario)
            guardada = None
        return canal_por_defecto(nivel, canal) if guardada is None else guardada

    def guardar_preferencias(self, id_usuario: int, preferencias: dict[tuple[str, str], bool]) -> None:
        try:
            for (nivel, canal), habilitado in preferencias.items():
                self.db.execute(_SQL_GUARDAR_PREFERENCIA, {"u": id_usuario, "nivel": nivel, "canal": canal,
                                                           "habilitado": habilitado})
            self.db.flush()
        except Exception as exc:
            raise_from_db_error(exc)

    def ventana_agrupacion_minutos(self) -> int:
        try:
            with self.db.begin_nested():
                valor = self.db.execute(_SQL_VENTANA).scalar()
            return int(valor) if valor is not None else VENTANA_AGRUPACION_POR_DEFECTO
        except Exception:
            return VENTANA_AGRUPACION_POR_DEFECTO

    def sumar_ocurrencia(
        self, id_usuario: int, tipo_evento: int, id_activo_biologico: int, ventana_minutos: int
    ) -> bool:
        desde = datetime.now(timezone.utc) - timedelta(minutes=ventana_minutos)
        existente = (
            self.db.query(Notificaciones)
            .join(Eventos, Notificaciones.id_evento == Eventos.id_evento)
            .filter(
                Notificaciones.id_usuario == id_usuario,
                Notificaciones.id_notificacion_canal == ID_CANAL_INTERNO,
                Notificaciones.id_activo_biologico == id_activo_biologico,
                Notificaciones.estado.in_((NUEVA, LEIDA)),
                Notificaciones.fecha_envio >= desde,
                Eventos.tipo_evento == tipo_evento,
            )
            .order_by(Notificaciones.fecha_envio.desc())
            .with_for_update()
            .first()
        )
        if existente is None:
            return False
        try:
            existente.ocurrencias = (existente.ocurrencias or 1) + 1
            existente.fecha_ultima_ocurrencia = datetime.now(timezone.utc)
            self.db.flush()
        except Exception as exc:
            raise_from_db_error(exc)
        return True

    def pendientes_de_entrega(self, limite: int) -> list[EntregaPendiente]:
        ahora = datetime.now(timezone.utc)
        filas = (
            self.db.query(Notificaciones, Eventos.modulo)
            .join(Eventos, Notificaciones.id_evento == Eventos.id_evento)
            .filter(
                Notificaciones.id_notificacion_canal == ID_CANAL_INTERNO,
                Notificaciones.nivel != INFORMATIVA,
                Notificaciones.estado == NUEVA,
                Notificaciones.estado_envio.in_((EnumEstadoEnvio("en_cola"), EnumEstadoEnvio("fallido"))),
                Notificaciones.intentos_push < _INTENTOS_PUSH_MAX,
                func.coalesce(Notificaciones.fecha_proximo_intento, Notificaciones.fecha_envio) <= ahora,
                Notificaciones.fecha_envio >= ahora - _VENTANA_ENTREGA,
            )
            .order_by(_ORDEN_NIVEL, Notificaciones.fecha_envio)
            .limit(limite)
            .with_for_update(of=Notificaciones, skip_locked=True)
            .all()
        )
        return [EntregaPendiente(
            id_notificacion=orm.id_notificacion, id_evento=orm.id_evento, id_usuario=orm.id_usuario,
            mensaje=orm.mensaje, nivel=orm.nivel, intentos_push=orm.intentos_push or 0,
            modulo=modulo_desde(modulo), contexto=dict(orm.json_contexto or {}),
        ) for orm, modulo in filas]

    def registrar_intento_push(
        self, id_notificacion: int, entregada: bool, proximo_intento: Optional[datetime]
    ) -> None:
        orm = self.db.get(Notificaciones, id_notificacion)
        if orm is None:
            return
        try:
            orm.intentos_push = (orm.intentos_push or 0) + 1
            orm.estado_envio = EnumEstadoEnvio("enviado" if entregada else "fallido")
            orm.fecha_proximo_intento = None if entregada else proximo_intento
            self.db.flush()
        except Exception as exc:
            raise_from_db_error(exc)
        if entregada:
            self._auditar(orm.id_usuario, {"accion": "ENTREGADA", "id_notificacion": id_notificacion,
                                           "nivel": orm.nivel, "canal": "PUSH"})

    def purgar_informativas(self, antes_de: datetime) -> int:
        try:
            borradas = (
                self.db.query(Notificaciones)
                .filter(
                    Notificaciones.id_notificacion_canal == ID_CANAL_INTERNO,
                    Notificaciones.nivel == INFORMATIVA,
                    Notificaciones.estado.in_((LEIDA, "DESCARTADA")),
                    Notificaciones.fecha_envio < antes_de,
                )
                .delete(synchronize_session=False)
            )
            self.db.flush()
            return borradas
        except Exception as exc:
            raise_from_db_error(exc)

    def actualizar_estado(self, id_notificacion: int, estado: str) -> None:
        notificacion = self.db.get(Notificaciones, id_notificacion)
        notificacion.estado_envio = EnumEstadoEnvio(estado)
        self.db.flush()
        if estado == "enviado" and notificacion is not None and notificacion.id_notificacion_canal != ID_CANAL_INTERNO:
            self._auditar(notificacion.id_usuario, {
                "accion": "ENTREGADA", "id_notificacion": id_notificacion, "nivel": notificacion.nivel,
                "canal": _CANALES.get(notificacion.id_notificacion_canal, "EMAIL")})

    def verificar_anti_spam(
        self, id_usuario: int, tipo_evento: int, id_canal: int, ventana_minutos: int
    ) -> bool:
        desde = datetime.now(timezone.utc) - timedelta(minutes=ventana_minutos)
        existe = (
            self.db.query(Notificaciones)
            .join(Eventos, Notificaciones.id_evento == Eventos.id_evento)
            .filter(
                Notificaciones.id_usuario == id_usuario,
                Eventos.tipo_evento == tipo_evento,
                Notificaciones.id_notificacion_canal == id_canal,
                Notificaciones.fecha_envio >= desde,
            )
            .first()
        )
        return existe is not None

    def buscar_ultimo_evento_id(self, id_usuario: int, tipo_evento: int) -> Optional[int]:
        evento = (
            self.db.query(Eventos)
            .filter(
                Eventos.id_usuario == id_usuario,
                Eventos.tipo_evento == tipo_evento,
            )
            .order_by(Eventos.id_evento.desc())
            .first()
        )
        return evento.id_evento if evento else None

    def buscar_estado_cuenta(self, id_usuario: int) -> Optional[int]:
        cuenta = (
            self.db.query(CuentasUsuarios)
            .filter(CuentasUsuarios.id_usuario == id_usuario)
            .first()
        )
        return cuenta.id_estado_cuenta if cuenta else None

    def buscar_correo_usuario(self, id_usuario: int) -> Optional[str]:
        fila = (
            self.db.query(Usuarios.correo_electronico)
            .filter(Usuarios.id_usuario == id_usuario)
            .first()
        )
        return fila.correo_electronico if fila else None

    def buscar_fcm_tokens(self, id_usuario: int) -> list[str]:
        rows = (
            self.db.query(DispositivosFcm.fcm_token)
            .filter(DispositivosFcm.id_usuario == id_usuario)
            .all()
        )
        return [row.fcm_token for row in rows]

    def guardar_fcm_token(self, id_usuario: int, token: str, user_agent: Optional[str] = None) -> None:
        """Registra el token del dispositivo del usuario.

        No lleva UPSERT a proposito: `uq_dispositivos_fcm_token` la resuelve el
        trigger `trg_fcm_2_revocar_token_previo`, que borra la fila previa con
        ese token antes del INSERT. Un token FCM es por navegador, no por
        usuario, asi que al entrar un segundo usuario en el mismo equipo el
        dispositivo se reasigna en vez de chocar. Ver
        `anotaciones/modulo_1/fcm_tokens.md`.
        """
        dispositivo = DispositivosFcm(
            id_usuario=id_usuario,
            fcm_token=token,
            user_agent=user_agent,
        )
        self.db.add(dispositivo)
        self.db.flush()

    def _query_internas(self, id_usuario: int, filtro: Optional[FiltroBandeja] = None):
        query = (
            self.db.query(Notificaciones, Eventos.tipo_evento, Eventos.modulo)
            .join(Eventos, Notificaciones.id_evento == Eventos.id_evento)
            .filter(
                Notificaciones.id_usuario == id_usuario,
                Notificaciones.id_notificacion_canal == ID_CANAL_INTERNO,
            )
        )
        if filtro is None:
            return query
        if filtro.solo_no_leidas:
            # Mientras ``es_leido`` siga en la tabla, una marcada solo por esa columna también cuenta como leída.
            query = query.filter(Notificaciones.estado == NUEVA, Notificaciones.es_leido.is_(False))
        query = query.filter(Notificaciones.estado == filtro.estado if filtro.estado
                             else Notificaciones.estado.in_((NUEVA, LEIDA)))
        if filtro.nivel:
            query = query.filter(Notificaciones.nivel == filtro.nivel)
        if filtro.modulo:
            query = query.filter(_NUMERO_MODULO == NUMERO_POR_MODULO[filtro.modulo])
        if filtro.desde is not None:
            query = query.filter(Notificaciones.fecha_envio >= filtro.desde)
        return query

    def listar_internas(
        self,
        id_usuario: int,
        filtro: FiltroBandeja,
        offset: int,
        limit: int,
    ) -> list[Notificacion]:
        filas = (
            self._query_internas(id_usuario, filtro)
            .order_by(
                _ORDEN_NIVEL,
                Notificaciones.fecha_envio.desc(),
                Notificaciones.id_notificacion.desc(),
            )
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [self._a_entidad(orm, tipo_evento, modulo) for orm, tipo_evento, modulo in filas]

    def contar_internas(self, id_usuario: int, filtro: FiltroBandeja) -> int:
        return self._query_internas(id_usuario, filtro).count()

    def obtener_interna(
        self,
        id_notificacion: int,
        id_usuario: int,
    ) -> Optional[Notificacion]:
        fila = (
            self._query_internas(id_usuario)
            .filter(Notificaciones.id_notificacion == id_notificacion)
            .first()
        )
        if fila is None:
            return None
        orm, tipo_evento, modulo = fila
        return self._a_entidad(orm, tipo_evento, modulo)

    def guardar(self, notificacion: Notificacion) -> None:
        orm = (
            self.db.query(Notificaciones)
            .filter(
                Notificaciones.id_notificacion == notificacion.id_notificacion,
                Notificaciones.id_usuario == notificacion.id_usuario,
                Notificaciones.id_notificacion_canal == ID_CANAL_INTERNO,
            )
            .first()
        )
        if orm is None:
            return
        anterior = orm.estado
        orm.es_leido = notificacion.es_leido
        orm.estado = notificacion.estado
        orm.accion_documentada = notificacion.accion_documentada
        orm.fecha_lectura = notificacion.fecha_lectura
        orm.fecha_atencion = notificacion.fecha_atencion
        orm.fecha_descarte = notificacion.fecha_descarte
        try:
            self.db.flush()
        except Exception as exc:
            raise_from_db_error(exc)
        if anterior != notificacion.estado:
            self._auditar(notificacion.id_usuario, {
                "accion": notificacion.estado, "id_notificacion": notificacion.id_notificacion,
                "nivel": notificacion.nivel, "estado_anterior": anterior,
                "accion_documentada": notificacion.accion_documentada})

    def marcar_todas_leidas(self, id_usuario: int) -> int:
        filtro = (Notificaciones.id_usuario == id_usuario, Notificaciones.id_notificacion_canal == ID_CANAL_INTERNO,
                  Notificaciones.estado == NUEVA)
        try:
            ids = [i for (i,) in self.db.query(Notificaciones.id_notificacion).filter(*filtro).all()]
            cambiadas = (
                self.db.query(Notificaciones)
                .filter(*filtro)
                .update({Notificaciones.es_leido: True, Notificaciones.estado: LEIDA,
                         Notificaciones.fecha_lectura: datetime.now(timezone.utc)},
                        synchronize_session=False)
            )
            self.db.flush()
        except Exception as exc:
            raise_from_db_error(exc)
        for id_notificacion in ids:
            self._auditar(id_usuario, {"accion": LEIDA, "id_notificacion": id_notificacion, "estado_anterior": NUEVA})
        return cambiadas
