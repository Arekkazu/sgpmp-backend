"""Implementación SQLAlchemy del puerto :class:`ProvisionNic41Repository` (RF-79, CU-05).

Usa ``flush()``/``refresh()`` (nunca ``commit()``) y traduce errores de BD con
``raise_from_db_error``. ``hash_integridad`` lo calcula el trigger de BD
(``trg_provision_hash``); se relee tras ``refresh``. Los valores ``Decimal``
de ``desglose_categoria`` se serializan a ``str`` antes de escribir en la
columna ``jsonb`` (mismo criterio que ``resultado_json`` en
``procesar_cola_reportes_gastos_use_case.py``); ``lista_registros`` ya llega
serializada desde ``consolidador_nic41._a_dict``.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from src.shared.db_error_translator import raise_from_db_error
from src.supplies.domain.entities.provision_nic41 import ProvisionNic41
from src.supplies.domain.repositories.provision_nic41_repository import ProvisionNic41Repository
from src.supplies.infrastructure.models.provision_nic41_model import ProvisionNic41Model


class SqlAlchemyProvisionNic41Repository(ProvisionNic41Repository):
    """Adaptador SQLAlchemy para ``modulo5.provision_nic41``."""

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _a_entidad(orm: ProvisionNic41Model) -> ProvisionNic41:
        desglose = {
            categoria: Decimal(str(monto)) for categoria, monto in (orm.desglose_categoria or {}).items()
        }
        return ProvisionNic41(
            id_provision=orm.id_provision,
            id_activo_biologico=orm.id_activo_biologico,
            id_ciclo_productivo=orm.id_ciclo_productivo,
            id_gestion_fases=orm.id_gestion_fases,
            modalidad=orm.modalidad,
            monto_provision=Decimal(str(orm.monto_provision)),
            desglose_categoria=desglose,
            lista_registros=orm.lista_registros or [],
            version_reporte=orm.version_reporte or 1,
            id_reporte_anterior=orm.id_reporte_anterior,
            motivo_correccion=orm.motivo_correccion,
            es_reporte_potencialmente_incompleto=bool(orm.es_reporte_potencialmente_incompleto),
            estado=orm.estado or "GENERADO",
            hash_integridad=orm.hash_integridad,
            fecha_generacion=orm.fecha_generacion,
            fecha_entrega_m06=orm.fecha_entrega_m06,
        )

    def guardar(self, provision: ProvisionNic41) -> ProvisionNic41:
        orm = ProvisionNic41Model(
            id_activo_biologico=provision.id_activo_biologico,
            id_ciclo_productivo=provision.id_ciclo_productivo,
            id_gestion_fases=provision.id_gestion_fases,
            modalidad=provision.modalidad,
            monto_provision=provision.monto_provision,
            desglose_categoria={
                categoria: str(monto) for categoria, monto in provision.desglose_categoria.items()
            },
            lista_registros=provision.lista_registros,
            version_reporte=provision.version_reporte,
            id_reporte_anterior=provision.id_reporte_anterior,
            motivo_correccion=provision.motivo_correccion,
            es_reporte_potencialmente_incompleto=provision.es_reporte_potencialmente_incompleto,
            estado=provision.estado,
        )
        try:
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc)
        return self._a_entidad(orm)

    def obtener(self, id_provision: int) -> Optional[ProvisionNic41]:
        orm = self.db.get(ProvisionNic41Model, id_provision)
        return self._a_entidad(orm) if orm else None

    def obtener_ultima_version(self, id_gestion_fases: int) -> Optional[ProvisionNic41]:
        orm = (
            self.db.query(ProvisionNic41Model)
            .filter(ProvisionNic41Model.id_gestion_fases == id_gestion_fases)
            .order_by(ProvisionNic41Model.version_reporte.desc())
            .first()
        )
        return self._a_entidad(orm) if orm else None

    def listar_versiones(self, id_gestion_fases: int) -> list[ProvisionNic41]:
        registros = (
            self.db.query(ProvisionNic41Model)
            .filter(ProvisionNic41Model.id_gestion_fases == id_gestion_fases)
            .order_by(ProvisionNic41Model.version_reporte.asc())
            .all()
        )
        return [self._a_entidad(o) for o in registros]
