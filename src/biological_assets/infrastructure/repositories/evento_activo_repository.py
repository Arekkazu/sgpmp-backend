from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import func

from sqlalchemy import text
from sqlalchemy.orm import Session

import src.biological_assets.infrastructure.models  # noqa: F401

from src.biological_assets.domain.entities.activo_biologico import (
    EventoActivo,
    EventoBaja,
    EventoCrecimiento,
    EventoProductivo,
    EventoReproductivo,
    EventoSanitario,
)
from src.biological_assets.domain.repositories.evento_activo_repository import EventoActivoRepository
from src.biological_assets.infrastructure.models.evento_activo_model import EventoActivoModel
from src.biological_assets.infrastructure.models.evento_baja_model import EventoBajaModel
from src.biological_assets.infrastructure.models.evento_crecimiento_model import EventoCrecimientoModel
from src.biological_assets.infrastructure.models.evento_productivo_model import EventoProductivoModel
from src.biological_assets.infrastructure.models.evento_reproductivo_model import EventoReproductivoModel
from src.biological_assets.infrastructure.models.evento_sanitario_model import EventoSanitarioModel
from src.shared.db_error_translator import raise_from_db_error


class SqlAlchemyEventoActivoRepository(EventoActivoRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Mapeo ORM ↔ dominio ─────────────────────────────────────────────────

    @staticmethod
    def _a_entidad(orm: EventoActivoModel) -> EventoActivo:
        crecimiento: Optional[EventoCrecimiento] = None
        baja: Optional[EventoBaja] = None
        sanitario: Optional[EventoSanitario] = None
        productivo: Optional[EventoProductivo] = None

        if orm.evento_crecimiento:
            c = orm.evento_crecimiento
            crecimiento = EventoCrecimiento(
                tipo_medicion=c.tipo_medicion,
                valor_medicion=c.valor_medicion,
                unidad_medida=c.unidad_medida,
                tipo_agregacion=c.tipo_agregacion,
                frecuencia=c.frecuencia,
                nuevo_peso_promedio=c.nuevo_peso_promedio,
                cantidad_medida=c.cantidad_medida,
            )

        if orm.evento_baja:
            b = orm.evento_baja
            baja = EventoBaja(
                cantidad_afectada=b.cantidad_afectada,
                tipo=b.tipo,
                detalles=b.detalles,
            )

        if orm.evento_sanitario:
            s = orm.evento_sanitario
            sanitario = EventoSanitario(
                tipo=s.tipo,
                diagnostico=s.diagnostico,
                medicamento=s.medicamento,
                dosis=s.dosis,
                unidad_dosis=s.unidad_dosis,
                frecuencia=s.frecuencia,
                duracion=s.duracion,
                observaciones=s.observaciones,
            )

        if orm.evento_productivo:
            p = orm.evento_productivo
            productivo = EventoProductivo(
                cantidad=p.cantidad,
                id_metrica_produccion=p.id_metrica_produccion,
                id_ciclo_productivo=p.id_ciclo_productivo,
                condiciones=p.condiciones,
            )

        reproductivo: Optional[EventoReproductivo] = None
        if orm.evento_reproductivo:
            r = orm.evento_reproductivo
            reproductivo = EventoReproductivo(
                categoria=r.categoria,
                resultado=r.resultado,
                numero_cria=r.numero_cria,
                id_padre=r.id_padre,
                id_madre=r.id_madre,
            )

        return EventoActivo(
            id_eventos=orm.id_eventos,
            id_activo_biologico=orm.id_activo_biologico,
            fecha=orm.fecha,
            descripcion=orm.descripcion,
            id_usuario=orm.id_usuario,
            crecimiento=crecimiento,
            baja=baja,
            sanitario=sanitario,
            productivo=productivo,
            reproductivo=reproductivo,
        )

    # ── Operaciones del puerto ───────────────────────────────────────────────

    def guardar(self, evento: EventoActivo) -> EventoActivo:
        ahora = evento.fecha or datetime.now(timezone.utc)
        try:
            self.db.execute(text('SET LOCAL app.usuario_id = :uid'), {'uid': evento.id_usuario})
            orm = EventoActivoModel(
                id_activo_biologico=evento.id_activo_biologico,
                fecha=ahora,
                descripcion=evento.descripcion,
                id_usuario=evento.id_usuario,
            )
            self.db.add(orm)
            self.db.flush()

            if evento.crecimiento:
                c = evento.crecimiento
                self.db.add(EventoCrecimientoModel(
                    id_evento=orm.id_eventos,
                    tipo_medicion=c.tipo_medicion,
                    valor_medicion=c.valor_medicion,
                    unidad_medida=c.unidad_medida,
                    tipo_agregacion=c.tipo_agregacion,
                    frecuencia=c.frecuencia,
                    nuevo_peso_promedio=c.nuevo_peso_promedio,
                    cantidad_medida=c.cantidad_medida,
                ))
            elif evento.baja:
                b = evento.baja
                self.db.add(EventoBajaModel(
                    id_evento=orm.id_eventos,
                    cantidad_afectada=b.cantidad_afectada,
                    tipo=b.tipo,
                    detalles=b.detalles,
                ))
            elif evento.sanitario:
                s = evento.sanitario
                self.db.add(EventoSanitarioModel(
                    id_evento=orm.id_eventos,
                    tipo=s.tipo,
                    diagnostico=s.diagnostico,
                    medicamento=s.medicamento,
                    dosis=s.dosis,
                    unidad_dosis=s.unidad_dosis,
                    frecuencia=s.frecuencia,
                    duracion=s.duracion,
                    observaciones=s.observaciones,
                ))
            elif evento.productivo:
                p = evento.productivo
                self.db.add(EventoProductivoModel(
                    id_evento=orm.id_eventos,
                    cantidad=p.cantidad,
                    id_metrica_produccion=p.id_metrica_produccion,
                    id_ciclo_productivo=p.id_ciclo_productivo,
                    condiciones=p.condiciones,
                ))
            elif evento.reproductivo:
                r = evento.reproductivo
                self.db.add(EventoReproductivoModel(
                    id_evento_reproductivo=orm.id_eventos,
                    categoria=r.categoria,
                    resultado=r.resultado,
                    numero_cria=r.numero_cria,
                    id_padre=r.id_padre,
                    id_madre=r.id_madre,
                ))

            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc, {})
        return self._a_entidad(orm)

    def listar_por_activo(self, id_activo: int) -> list[EventoActivo]:
        rows = (
            self.db.query(EventoActivoModel)
            .filter(EventoActivoModel.id_activo_biologico == id_activo)
            .order_by(EventoActivoModel.fecha.desc())
            .all()
        )
        return [self._a_entidad(orm) for orm in rows]

    def obtener_ultima_fecha(self, id_activo: int) -> Optional[datetime]:
        return (
            self.db.query(func.max(EventoActivoModel.fecha))
            .filter(EventoActivoModel.id_activo_biologico == id_activo)
            .scalar()
        )

    def tiene_diagnostico_previo(self, id_activo: int) -> bool:
        return (
            self.db.query(EventoActivoModel)
            .join(EventoSanitarioModel, EventoSanitarioModel.id_evento == EventoActivoModel.id_eventos)
            .filter(
                EventoActivoModel.id_activo_biologico == id_activo,
                EventoSanitarioModel.tipo == 'DIAGNOSTICO',
            )
            .first()
        ) is not None

    def tiene_servicio_o_inseminacion_previa(self, id_activo: int) -> bool:
        return (
            self.db.query(EventoActivoModel)
            .join(EventoReproductivoModel, EventoReproductivoModel.id_evento_reproductivo == EventoActivoModel.id_eventos)
            .filter(
                EventoActivoModel.id_activo_biologico == id_activo,
                EventoReproductivoModel.categoria.in_(['servicio', 'inseminacion']),
            )
            .first()
        ) is not None

    def tiene_diagnostico_positivo_previo(self, id_activo: int) -> bool:
        return (
            self.db.query(EventoActivoModel)
            .join(EventoReproductivoModel, EventoReproductivoModel.id_evento_reproductivo == EventoActivoModel.id_eventos)
            .filter(
                EventoActivoModel.id_activo_biologico == id_activo,
                EventoReproductivoModel.categoria == 'diagnostico',
                EventoReproductivoModel.resultado == 'exitoso',
            )
            .first()
        ) is not None

    def existe_productivo_duplicado(self, id_activo: int, id_metrica_produccion: int, fecha: date) -> bool:
        return (
            self.db.query(EventoActivoModel)
            .join(EventoProductivoModel, EventoProductivoModel.id_evento == EventoActivoModel.id_eventos)
            .filter(
                EventoActivoModel.id_activo_biologico == id_activo,
                EventoProductivoModel.id_metrica_produccion == id_metrica_produccion,
                func.date(EventoActivoModel.fecha) == fecha,
            )
            .first()
        ) is not None
