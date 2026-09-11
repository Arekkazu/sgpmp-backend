"""Implementación SQLAlchemy del puerto :class:`MedicamentoRepository` (RF-76).

Usa ``flush()``/``refresh()`` (nunca ``commit()``) y traduce errores de BD con
``raise_from_db_error``. ``costo_total_medicamento`` lo calcula un trigger
BEFORE INSERT; se relee tras ``refresh``.
"""
from __future__ import annotations

from datetime import date, time
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.shared.db_error_translator import raise_from_db_error
from src.supplies.domain.entities.medicamento import Medicamento
from src.supplies.domain.repositories.medicamento_repository import MedicamentoRepository
from src.supplies.domain.value_objects.estado_registro import EstadoRegistro
from src.supplies.infrastructure.models.registro_medicamento_model import RegistroMedicamentoModel

_MEDIANOCHE = time(0, 0, 0)

_CONFLICTO_DUP = {
    "uq_medicamento_validado_dup": (
        "Ya existe un registro de este medicamento VALIDADO para el activo en la misma "
        "fecha y hora de aplicación. No se permiten registros duplicados."
    ),
}


class SqlAlchemyMedicamentoRepository(MedicamentoRepository):
    """Adaptador SQLAlchemy para ``modulo5.registros_medicamentos``."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Mapeo ORM ↔ dominio ─────────────────────────────────────────────────

    @staticmethod
    def _a_entidad(orm: RegistroMedicamentoModel) -> Medicamento:
        return Medicamento(
            id_registro_medicamento=orm.id_registro_medicamento,
            id_activo_biologico=orm.id_activo_biologico,
            nombre_medicamento=orm.nombre_medicamento,
            descripcion_clinica=orm.descripcion_clinica,
            unidad_dosis=orm.unidad_dosis,
            cantidad=orm.cantidad,
            fecha_aplicacion=orm.fecha_aplicacion,
            costo_unitario_medicamento=orm.costo_unitario_medicamento,
            costo_total_medicamento=orm.costo_total_medicamento,
            via_aplicacion=orm.via_aplicacion,
            motivo_aplicacion=orm.motivo_aplicacion,
            nombre_veterinario=orm.nombre_veterinario,
            id_usuario=orm.id_usuario,
            id_usuario_veterinario=orm.id_usuario_veterinario,
            estado_registro=orm.estado_registro,
            hora_aplicacion=orm.hora_aplicacion,
            periodo_retiro_dias=orm.periodo_retiro_dias or 0,
            fecha_fin_retiro=orm.fecha_fin_retiro,
            dosis_por_individuo=orm.dosis_por_individuo,
            id_evento_sanitario=orm.id_evento_sanitario,
            lote_medicameto=orm.lote_medicameto,
            fehca_vencimietno_lote=orm.fehca_vencimietno_lote,
            fecha_registro=orm.fecha_registro,
            justificacion_anulacion=orm.justificacion_anulacion,
            fecha_hora_anulacion=orm.fecha_hora_anulacion,
        )

    # ── Operaciones del puerto ───────────────────────────────────────────────

    def existe_duplicado_validado(
        self,
        *,
        id_activo_biologico: int,
        nombre_medicamento: str,
        fecha_aplicacion: date,
        hora_aplicacion: Optional[time],
    ) -> bool:
        hora = hora_aplicacion or _MEDIANOCHE
        existe = (
            self.db.query(RegistroMedicamentoModel.id_registro_medicamento)
            .filter(
                RegistroMedicamentoModel.estado_registro == EstadoRegistro.VALIDADO.value,
                RegistroMedicamentoModel.id_activo_biologico == id_activo_biologico,
                func.lower(RegistroMedicamentoModel.nombre_medicamento) == nombre_medicamento.lower(),
                RegistroMedicamentoModel.fecha_aplicacion == fecha_aplicacion,
                func.coalesce(RegistroMedicamentoModel.hora_aplicacion, _MEDIANOCHE) == hora,
            )
            .first()
        )
        return existe is not None

    def guardar(self, medicamento: Medicamento) -> Medicamento:
        # costo_total_medicamento lo calcula el trigger BEFORE INSERT — no se asigna.
        orm = RegistroMedicamentoModel(
            id_activo_biologico=medicamento.id_activo_biologico,
            nombre_medicamento=medicamento.nombre_medicamento,
            descripcion_clinica=medicamento.descripcion_clinica,
            unidad_dosis=medicamento.unidad_dosis,
            cantidad=medicamento.cantidad,
            fecha_aplicacion=medicamento.fecha_aplicacion,
            costo_unitario_medicamento=medicamento.costo_unitario_medicamento,
            via_aplicacion=medicamento.via_aplicacion,
            lote_medicameto=medicamento.lote_medicameto,
            fehca_vencimietno_lote=medicamento.fehca_vencimietno_lote,
            id_usuario=medicamento.id_usuario,
            id_usuario_veterinario=medicamento.id_usuario_veterinario,
            estado_registro=medicamento.estado_registro,
            hora_aplicacion=medicamento.hora_aplicacion,
            periodo_retiro_dias=medicamento.periodo_retiro_dias,
            fecha_fin_retiro=medicamento.fecha_fin_retiro,
            dosis_por_individuo=medicamento.dosis_por_individuo,
            motivo_aplicacion=medicamento.motivo_aplicacion,
            id_evento_sanitario=medicamento.id_evento_sanitario,
            nombre_veterinario=medicamento.nombre_veterinario,
        )
        try:
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc, _CONFLICTO_DUP)
        return self._a_entidad(orm)

    def obtener_por_id(self, id_medicamento: int) -> Optional[Medicamento]:
        orm = self.db.get(RegistroMedicamentoModel, id_medicamento)
        return self._a_entidad(orm) if orm else None

    def anular(self, medicamento: Medicamento) -> Medicamento:
        orm = self.db.get(RegistroMedicamentoModel, medicamento.id_registro_medicamento)
        # Solo se tocan estado y campos de anulación (el trigger protege el resto).
        orm.estado_registro = medicamento.estado_registro
        orm.justificacion_anulacion = medicamento.justificacion_anulacion
        orm.fecha_hora_anulacion = medicamento.fecha_hora_anulacion
        try:
            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc, {})
        return self._a_entidad(orm)

    def max_fecha_fin_retiro_vigente(self, id_activo: int) -> Optional[date]:
        return (
            self.db.query(func.max(RegistroMedicamentoModel.fecha_fin_retiro))
            .filter(
                RegistroMedicamentoModel.id_activo_biologico == id_activo,
                RegistroMedicamentoModel.estado_registro == EstadoRegistro.VALIDADO.value,
                RegistroMedicamentoModel.fecha_fin_retiro.isnot(None),
            )
            .scalar()
        )

    def obtener_tratamiento_vigente(self, id_activo: int) -> Optional[Medicamento]:
        orm = (
            self.db.query(RegistroMedicamentoModel)
            .filter(
                RegistroMedicamentoModel.id_activo_biologico == id_activo,
                RegistroMedicamentoModel.estado_registro == EstadoRegistro.VALIDADO.value,
                RegistroMedicamentoModel.fecha_fin_retiro.isnot(None),
            )
            .order_by(RegistroMedicamentoModel.fecha_fin_retiro.desc())
            .first()
        )
        return self._a_entidad(orm) if orm else None

    def listar(
        self,
        *,
        id_activo_biologico: Optional[int] = None,
        fecha_desde: Optional[date] = None,
        fecha_hasta: Optional[date] = None,
        estado_registro: Optional[str] = None,
    ) -> list[Medicamento]:
        query = self.db.query(RegistroMedicamentoModel)
        if id_activo_biologico is not None:
            query = query.filter(RegistroMedicamentoModel.id_activo_biologico == id_activo_biologico)
        if fecha_desde is not None:
            query = query.filter(RegistroMedicamentoModel.fecha_aplicacion >= fecha_desde)
        if fecha_hasta is not None:
            query = query.filter(RegistroMedicamentoModel.fecha_aplicacion <= fecha_hasta)
        if estado_registro is not None:
            query = query.filter(RegistroMedicamentoModel.estado_registro == estado_registro)
        registros = query.order_by(
            RegistroMedicamentoModel.fecha_aplicacion.desc(),
            RegistroMedicamentoModel.id_registro_medicamento.desc(),
        ).all()
        return [self._a_entidad(o) for o in registros]
