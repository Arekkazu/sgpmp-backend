from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, text
from sqlalchemy.orm import Session

import src.biological_assets.infrastructure.models  # noqa: F401 — ensures all ORM models register before mapper resolution

from src.biological_assets.domain.entities.activo_biologico import (
    ActivoBiologico,
    DetalleIndividual,
    DetallePoblacional,
    HistorialInfraestructura,
)
from src.biological_assets.domain.repositories.activo_biologico_repository import ActivoBiologicoRepository
from src.biological_assets.infrastructure.models.activo_biologico_model import ActivoBiologicoModel
from src.biological_assets.infrastructure.models.detalle_individual_model import DetalleActivoIndividualModel
from src.biological_assets.infrastructure.models.detalle_poblacional_model import DetalleActivoPoblacionalModel
from src.biological_assets.infrastructure.models.historial_infraestructura_activo_model import (
    HistorialInfraestructuraActivoModel,
)
from src.configuration.infrastructure.models.infraestructura_model import InfraestructuraModel
from src.shared.db_error_translator import raise_from_db_error


class SqlAlchemyActivoBiologicoRepository(ActivoBiologicoRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Mapeo ORM ↔ dominio ─────────────────────────────────────────────────

    @staticmethod
    def _a_entidad(orm: ActivoBiologicoModel) -> ActivoBiologico:
        detalle_ind: Optional[DetalleIndividual] = None
        detalle_pob: Optional[DetallePoblacional] = None

        if orm.detalle_individual:
            d = orm.detalle_individual
            detalle_ind = DetalleIndividual(
                id_detalle=d.id_detalle_activo_individual,
                raza=d.raza,
                sexo=d.sexo,
                fecha_nacimiento=d.fecha_nacimeinto,  # typo en DB
                peso_inicial=d.peso_inicial,
                fecha_creacion=d.fecha_creacion,
            )

        if orm.detalle_poblacional:
            p = orm.detalle_poblacional
            detalle_pob = DetallePoblacional(
                id_detalle=p.id_detalle_activo_biologico_poblacional,
                cantidad_inicial=p.cantidad_inicial,
                cantidad_actual=p.cantidad_actual,
                peso_promedio_inicial=p.peso_promedio_inicial,
                peso_promedio=p.peso_promedio,
                biomasa_total=p.biomasa_total,
                densidad=p.densidad,
            )

        nombre_estado = orm.estado.nombre if orm.estado else None

        return ActivoBiologico(
            id_activo_biologico=orm.id_activo_biologico,
            id_especie=orm.id_especie,
            tipo=orm.tipo,
            identificador=orm.identificador,
            fecha_inicio_ciclo=orm.fecha_inicio_ciclo,
            detalles_procedencia=orm.detalles_procedencia,
            origen_financiero=orm.origen_financiero,
            costo_adquisicion=orm.costo_adquisicion,
            soporte_documental=orm.soporte_documental,
            descripcion=orm.descripcion,
            id_infraestructura=orm.id_infraestructura,
            atributos_dinamicos=orm.atributos_dinamicos,
            id_estado=orm.id_estado,
            id_usuario=orm.id_usuario,
            fecha_creacion=orm.fecha_creacion,
            nombre_estado=nombre_estado,
            detalle_individual=detalle_ind,
            detalle_poblacional=detalle_pob,
        )

    # ── Operaciones del puerto ───────────────────────────────────────────────

    def guardar(self, activo: ActivoBiologico) -> ActivoBiologico:
        ahora = datetime.now(timezone.utc)
        try:
            # El trigger trg_auditar_activo_biologico requiere esta variable de sesión
            self.db.execute(text("SET LOCAL app.usuario_id = :uid"), {"uid": activo.id_usuario})
            orm = ActivoBiologicoModel(
                id_especie=activo.id_especie,
                tipo=activo.tipo,
                identificador=activo.identificador,
                id_infraestructura=activo.id_infraestructura,
                fecha_inicio_ciclo=activo.fecha_inicio_ciclo,
                id_estado=activo.id_estado,
                descripcion=activo.descripcion,
                origen_financiero=activo.origen_financiero,
                costo_adquisicion=activo.costo_adquisicion,
                atributos_dinamicos=activo.atributos_dinamicos,
                id_usuario=activo.id_usuario,
                fecha_creacion=ahora,
                soporte_documental=activo.soporte_documental,
                detalles_procedencia=activo.detalles_procedencia,
            )
            self.db.add(orm)
            self.db.flush()

            if activo.detalle_individual:
                di = activo.detalle_individual
                self.db.add(DetalleActivoIndividualModel(
                    id_activo_biologico=orm.id_activo_biologico,
                    raza=di.raza,
                    sexo=di.sexo,
                    fecha_nacimeinto=di.fecha_nacimiento,  # typo en DB
                    peso_inicial=di.peso_inicial,
                    fecha_creacion=ahora,
                    id_usuario=activo.id_usuario,
                ))

            if activo.detalle_poblacional:
                dp = activo.detalle_poblacional
                self.db.add(DetalleActivoPoblacionalModel(
                    id_activo_biologico=orm.id_activo_biologico,
                    cantidad_inicial=dp.cantidad_inicial,
                    cantidad_actual=dp.cantidad_actual,
                    peso_promedio_inicial=dp.peso_promedio_inicial,
                ))

            self.db.add(HistorialInfraestructuraActivoModel(
                id_activo_biologico=orm.id_activo_biologico,
                id_infraestructura=activo.id_infraestructura,
                fecha_inicio=ahora,
                fecha_fin=None,
                id_usuario_registro=activo.id_usuario,
            ))

            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc, {
                'uq_activo_biologico_identificador': (
                    f"El identificador '{activo.identificador}' ya está registrado en el sistema."
                ),
            })
        return self._a_entidad(orm)

    def obtener_por_id(self, id_activo: int) -> Optional[ActivoBiologico]:
        orm = self.db.get(ActivoBiologicoModel, id_activo)
        return self._a_entidad(orm) if orm else None

    def existe_identificador(self, identificador: str) -> bool:
        return (
            self.db.query(ActivoBiologicoModel)
            .filter(func.lower(ActivoBiologicoModel.identificador) == identificador.lower())
            .first()
        ) is not None

    def obtener_asociacion_activa(self, id_activo: int) -> Optional[HistorialInfraestructura]:
        row = (
            self.db.query(HistorialInfraestructuraActivoModel, InfraestructuraModel)
            .join(
                InfraestructuraModel,
                HistorialInfraestructuraActivoModel.id_infraestructura == InfraestructuraModel.id_infraestructura,
            )
            .filter(
                HistorialInfraestructuraActivoModel.id_activo_biologico == id_activo,
                HistorialInfraestructuraActivoModel.fecha_fin.is_(None),
            )
            .first()
        )
        if not row:
            return None
        hist, infra = row
        return HistorialInfraestructura(
            id_historial=hist.id_historial,
            id_activo_biologico=hist.id_activo_biologico,
            id_infraestructura=hist.id_infraestructura,
            nombre_infraestructura=infra.nombre,
            tipo_infraestructura=infra.tipo,
            fecha_inicio=hist.fecha_inicio,
            fecha_fin=hist.fecha_fin,
        )

    def obtener_historial_infraestructura(self, id_activo: int) -> list[HistorialInfraestructura]:
        rows = (
            self.db.query(HistorialInfraestructuraActivoModel, InfraestructuraModel)
            .join(
                InfraestructuraModel,
                HistorialInfraestructuraActivoModel.id_infraestructura == InfraestructuraModel.id_infraestructura,
            )
            .filter(HistorialInfraestructuraActivoModel.id_activo_biologico == id_activo)
            .order_by(HistorialInfraestructuraActivoModel.fecha_inicio.desc())
            .all()
        )
        return [
            HistorialInfraestructura(
                id_historial=h.id_historial,
                id_activo_biologico=h.id_activo_biologico,
                id_infraestructura=h.id_infraestructura,
                nombre_infraestructura=i.nombre,
                tipo_infraestructura=i.tipo,
                fecha_inicio=h.fecha_inicio,
                fecha_fin=h.fecha_fin,
            )
            for h, i in rows
        ]
