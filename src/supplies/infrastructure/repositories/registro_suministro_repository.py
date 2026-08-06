"""Implementación SQLAlchemy del puerto :class:`RegistroSuministroRepository` (RF-78, CU-05).

Usa ``flush()``/``refresh()`` (nunca ``commit()``) y traduce errores de BD con
``raise_from_db_error``. ``id_registro_suministro`` y ``fecha_registro`` los
genera la BD (``gen_random_uuid()``/``now()``); se relee tras ``refresh``.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from src.shared.db_error_translator import raise_from_db_error
from src.supplies.domain.entities.registro_suministro_directo import RegistroSuministroDirecto
from src.supplies.domain.repositories.registro_suministro_repository import RegistroSuministroRepository
from src.supplies.infrastructure.models.registro_suministro_model import RegistroSuministroModel

_ESCALA_CANTIDAD = Decimal("0.0001")
_ESCALA_PRECIO = Decimal("0.01")

_CONFLICTO_DUP = {
    "uq_registro_suministro_dedup_contenido": (
        "Registro de suministro idéntico ya existe. Si es una corrección, use "
        "tipo_operacion=CORRECCION con id_registro_original."
    ),
    "registro_suministro_id_idempotencia_key": (
        "Ya existe un registro procesado con este id_idempotencia."
    ),
}


class SqlAlchemyRegistroSuministroRepository(RegistroSuministroRepository):
    """Adaptador SQLAlchemy para ``modulo5.registro_suministro`` (escritura app-owned)."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Mapeo ORM ↔ dominio ─────────────────────────────────────────────────

    @staticmethod
    def _a_entidad(orm: RegistroSuministroModel) -> RegistroSuministroDirecto:
        return RegistroSuministroDirecto(
            id_registro_suministro=orm.id_registro_suministro,
            id_activo_biologico=orm.id_activo_biologico,
            id_ciclo_productivo=orm.id_ciclo_productivo,
            id_gestion_fases=orm.id_gestion_fases,
            tipo_suministro=orm.tipo_suministro,
            cantidad=orm.cantidad,
            unidad_medida=orm.unidad_medida,
            precio_unitario_resuelto=orm.precio_unitario_resuelto,
            costo_registro=orm.costo_registro,
            origen_precio=orm.origen_precio,
            fecha_aplicacion=orm.fecha_aplicacion,
            naturaleza_costo=orm.naturaleza_costo,
            justificacion_precio=orm.justificacion_precio,
            observacion=orm.observacion,
            tipo_operacion=orm.tipo_operacion or "REGISTRO",
            id_registro_original=orm.id_registro_original,
            motivo_correccion=orm.motivo_correccion,
            id_idempotencia=orm.id_idempotencia,
            fecha_registro=orm.fecha_registro,
        )

    # ── Operaciones del puerto ───────────────────────────────────────────────

    def existe_idempotente(self, id_idempotencia: UUID) -> Optional[RegistroSuministroDirecto]:
        orm = (
            self.db.query(RegistroSuministroModel)
            .filter(RegistroSuministroModel.id_idempotencia == id_idempotencia)
            .first()
        )
        return self._a_entidad(orm) if orm else None

    def existe_duplicado_contenido(
        self,
        *,
        id_activo_biologico: int,
        id_ciclo_productivo: int,
        tipo_suministro: str,
        fecha_aplicacion: date,
        cantidad: Decimal,
        precio_unitario_resuelto: Decimal,
    ) -> bool:
        existe = (
            self.db.query(RegistroSuministroModel.id_registro_suministro)
            .filter(
                RegistroSuministroModel.tipo_operacion == "REGISTRO",
                RegistroSuministroModel.id_activo_biologico == id_activo_biologico,
                RegistroSuministroModel.id_ciclo_productivo == id_ciclo_productivo,
                RegistroSuministroModel.tipo_suministro == tipo_suministro,
                RegistroSuministroModel.fecha_aplicacion == fecha_aplicacion,
                RegistroSuministroModel.cantidad == cantidad.quantize(_ESCALA_CANTIDAD),
                RegistroSuministroModel.precio_unitario_resuelto
                == precio_unitario_resuelto.quantize(_ESCALA_PRECIO),
            )
            .first()
        )
        return existe is not None

    def guardar(self, registro: RegistroSuministroDirecto) -> RegistroSuministroDirecto:
        orm = RegistroSuministroModel(
            id_activo_biologico=registro.id_activo_biologico,
            id_ciclo_productivo=registro.id_ciclo_productivo,
            id_gestion_fases=registro.id_gestion_fases,
            tipo_suministro=registro.tipo_suministro,
            cantidad=registro.cantidad,
            unidad_medida=registro.unidad_medida,
            precio_unitario_resuelto=registro.precio_unitario_resuelto,
            costo_registro=registro.costo_registro,
            origen_precio=registro.origen_precio,
            fecha_aplicacion=registro.fecha_aplicacion,
            naturaleza_costo=registro.naturaleza_costo,
            justificacion_precio=registro.justificacion_precio,
            observacion=registro.observacion,
            tipo_operacion=registro.tipo_operacion,
            id_registro_original=registro.id_registro_original,
            motivo_correccion=registro.motivo_correccion,
            id_idempotencia=registro.id_idempotencia,
        )
        try:
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc, _CONFLICTO_DUP)
        return self._a_entidad(orm)

    def obtener_por_id(self, id_registro_suministro: UUID) -> Optional[RegistroSuministroDirecto]:
        orm = self.db.get(RegistroSuministroModel, id_registro_suministro)
        return self._a_entidad(orm) if orm else None

    def listar_por_gestion_fase(self, id_gestion_fases: int) -> list[RegistroSuministroDirecto]:
        registros = (
            self.db.query(RegistroSuministroModel)
            .filter(RegistroSuministroModel.id_gestion_fases == id_gestion_fases)
            .order_by(RegistroSuministroModel.fecha_registro.asc())
            .all()
        )
        return [self._a_entidad(o) for o in registros]
