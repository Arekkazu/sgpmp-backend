"""Implementación SQLAlchemy del puerto :class:`ConsumoAlimentoRepository` (RF-75).

Único punto donde se cruza la frontera ORM ↔ dominio para el consumo de
alimento. Usa ``flush()``/``refresh()`` (nunca ``commit()``) y traduce errores
de BD con ``raise_from_db_error``. ``costo_total`` lo calcula un trigger BEFORE
INSERT; se relee tras ``refresh``.
"""
from __future__ import annotations

from datetime import date, time
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.shared.db_error_translator import raise_from_db_error
from src.supplies.domain.entities.consumo_alimento import ConsumoAlimento
from src.supplies.domain.repositories.consumo_alimento_repository import (
    ConsumoAlimentoRepository,
    TipoAlimentoRef,
)
from src.supplies.domain.value_objects.estado_registro import EstadoRegistro
from src.supplies.infrastructure.models.registro_consumo_alimento_model import RegistroConsumoAlimentoModel
from src.supplies.infrastructure.models.tipo_alimento_model import TipoAlimentoModel

_MEDIANOCHE = time(0, 0, 0)

_CONFLICTO_DUP = {
    "uq_consumo_validado_dup": (
        "Ya existe un registro de consumo VALIDADO para este activo en la misma fecha, "
        "hora y tipo de alimento. No se permiten registros duplicados."
    ),
}


class SqlAlchemyConsumoAlimentoRepository(ConsumoAlimentoRepository):
    """Adaptador SQLAlchemy para ``modulo5.registros_consumo_alimentos``."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Mapeo ORM ↔ dominio ─────────────────────────────────────────────────

    @staticmethod
    def _a_entidad(orm: RegistroConsumoAlimentoModel) -> ConsumoAlimento:
        return ConsumoAlimento(
            id_consumo_alimeto=orm.id_consumo_alimeto,
            id_activo_biologico=orm.id_activo_biologico,
            id_tipo_alimento=orm.id_tipo_alimento,
            tipo_alimento=orm.tipo_alimento,
            tipo_unidad=orm.tipo_unidad,
            cantidad_suministrada=orm.cantidad_suministrada,
            costo_unitario=orm.costo_unitario,
            costo_total=orm.costo_total,
            consumo_por_individuo_kg=orm.consumo_por_individuo_kg,
            observacion=orm.observacion,
            fecha_consumo=orm.fecha_consumo,
            hora_suministro=orm.hora_suministro,
            estado_registro=orm.estado_registro,
            id_usuario=orm.id_usuario,
            fecha_registro=orm.fecha_registro,
            justificacion_anulacion=orm.justificacion_anulacion,
            fecha_hora_anulacion=orm.fecha_hora_anulacion,
        )

    # ── Operaciones del puerto ───────────────────────────────────────────────

    def obtener_tipo_alimento(self, id_tipo_alimento: int) -> Optional[TipoAlimentoRef]:
        orm = self.db.get(TipoAlimentoModel, id_tipo_alimento)
        if orm is None:
            return None
        return TipoAlimentoRef(
            id_tipo_elemento=orm.id_tipo_elemento,
            nombre=orm.nombre,
            unidad_medida=orm.unidad_medida,
            costo_unitario=orm.costo_unitario,
            estado=orm.estado,
        )

    def existe_duplicado_validado(
        self,
        *,
        id_activo_biologico: int,
        fecha_consumo: date,
        hora_suministro: Optional[time],
        tipo_alimento: str,
    ) -> bool:
        hora = hora_suministro or _MEDIANOCHE
        existe = (
            self.db.query(RegistroConsumoAlimentoModel.id_consumo_alimeto)
            .filter(
                RegistroConsumoAlimentoModel.estado_registro == EstadoRegistro.VALIDADO.value,
                RegistroConsumoAlimentoModel.id_activo_biologico == id_activo_biologico,
                RegistroConsumoAlimentoModel.fecha_consumo == fecha_consumo,
                func.coalesce(RegistroConsumoAlimentoModel.hora_suministro, _MEDIANOCHE) == hora,
                func.lower(RegistroConsumoAlimentoModel.tipo_alimento) == tipo_alimento.lower(),
            )
            .first()
        )
        return existe is not None

    def guardar(self, consumo: ConsumoAlimento) -> ConsumoAlimento:
        # costo_total lo calcula el trigger BEFORE INSERT — no se asigna aquí.
        orm = RegistroConsumoAlimentoModel(
            id_activo_biologico=consumo.id_activo_biologico,
            id_tipo_alimento=consumo.id_tipo_alimento,
            tipo_alimento=consumo.tipo_alimento,
            tipo_unidad=consumo.tipo_unidad,
            cantidad_suministrada=consumo.cantidad_suministrada,
            observacion=consumo.observacion,
            fecha_consumo=consumo.fecha_consumo,
            hora_suministro=consumo.hora_suministro,
            costo_unitario=consumo.costo_unitario,
            consumo_por_individuo_kg=consumo.consumo_por_individuo_kg,
            estado_registro=consumo.estado_registro,
            id_usuario=consumo.id_usuario,
        )
        try:
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc, _CONFLICTO_DUP)
        return self._a_entidad(orm)

    def obtener_por_id(self, id_consumo: int) -> Optional[ConsumoAlimento]:
        orm = self.db.get(RegistroConsumoAlimentoModel, id_consumo)
        return self._a_entidad(orm) if orm else None

    def anular(self, consumo: ConsumoAlimento) -> ConsumoAlimento:
        orm = self.db.get(RegistroConsumoAlimentoModel, consumo.id_consumo_alimeto)
        # Solo se tocan estado y campos de anulación (el trigger protege el resto).
        orm.estado_registro = consumo.estado_registro
        orm.justificacion_anulacion = consumo.justificacion_anulacion
        orm.fecha_hora_anulacion = consumo.fecha_hora_anulacion
        try:
            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc, {})
        return self._a_entidad(orm)

    def listar(
        self,
        *,
        id_activo_biologico: Optional[int] = None,
        fecha_desde: Optional[date] = None,
        fecha_hasta: Optional[date] = None,
        tipo_alimento: Optional[str] = None,
        estado_registro: Optional[str] = None,
    ) -> list[ConsumoAlimento]:
        query = self.db.query(RegistroConsumoAlimentoModel)
        if id_activo_biologico is not None:
            query = query.filter(RegistroConsumoAlimentoModel.id_activo_biologico == id_activo_biologico)
        if fecha_desde is not None:
            query = query.filter(RegistroConsumoAlimentoModel.fecha_consumo >= fecha_desde)
        if fecha_hasta is not None:
            query = query.filter(RegistroConsumoAlimentoModel.fecha_consumo <= fecha_hasta)
        if tipo_alimento is not None:
            query = query.filter(func.lower(RegistroConsumoAlimentoModel.tipo_alimento) == tipo_alimento.lower())
        if estado_registro is not None:
            query = query.filter(RegistroConsumoAlimentoModel.estado_registro == estado_registro)
        registros = query.order_by(
            RegistroConsumoAlimentoModel.fecha_consumo.desc(),
            RegistroConsumoAlimentoModel.id_consumo_alimeto.desc(),
        ).all()
        return [self._a_entidad(o) for o in registros]
