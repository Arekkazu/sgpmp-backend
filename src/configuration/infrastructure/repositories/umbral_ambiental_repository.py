# | Fecha      | Nombre | Que se hizo |
# |------------|--------|-------------|
# | 2026-10-31 | Claude | INC-M03-246-G88 RF-58: tolerancia T del semáforo configurable en el umbral |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Implementación SQLAlchemy del puerto UmbralAmbientalRepository."""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.configuration.domain.entities.nivel_alerta_ambiental import NivelAlertaAmbiental
from src.configuration.domain.entities.umbral_ambiental import UmbralAmbiental
from src.configuration.domain.repositories.umbral_ambiental_repository import UmbralAmbientalRepository
from src.configuration.domain.value_objects.nivel_alerta import NivelAlerta
from src.configuration.infrastructure.models.nivel_alerta_ambiental_model import NivelAlertaAmbientalModel
from src.configuration.infrastructure.models.umbral_ambiental_model import UmbralAmbientalModel
from src.shared.db_error_translator import raise_from_db_error


class SqlAlchemyUmbralAmbientalRepository(UmbralAmbientalRepository):
    """Implementación SQLAlchemy de ``UmbralAmbientalRepository``."""
    def __init__(self, db: Session) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Lectura
    # ------------------------------------------------------------------

    def obtener_por_id(self, id_umbral_ambiental: int, *, bloquear: bool = False) -> Optional[UmbralAmbiental]:
        """``bloquear=True`` toma la fila con ``SELECT ... FOR UPDATE`` (#498)."""
        orm = self._db.get(UmbralAmbientalModel, id_umbral_ambiental, with_for_update=bloquear, populate_existing=bloquear)
        return self._a_entidad(orm) if orm else None

    def obtener_por_especie_y_variable(
        self, id_especie: int, id_variable_ambiental: int
    ) -> Optional[UmbralAmbiental]:
        """Umbral de la especie para la variable, o ``None`` si no existe."""
        stmt = select(UmbralAmbientalModel).where(
            UmbralAmbientalModel.id_especie == id_especie,
            UmbralAmbientalModel.id_variable_ambiental == id_variable_ambiental,
        )
        orm = self._db.scalars(stmt).first()
        return self._a_entidad(orm) if orm else None

    def listar_por_especie(
        self, id_especie: int, *, solo_activas: bool = False
    ) -> list[UmbralAmbiental]:
        """Umbrales de la especie, opcionalmente solo los activos."""
        stmt = select(UmbralAmbientalModel).where(
            UmbralAmbientalModel.id_especie == id_especie
        )
        if solo_activas:
            stmt = stmt.where(UmbralAmbientalModel.es_activo.is_(True))
        stmt = stmt.order_by(UmbralAmbientalModel.id_variable_ambiental)
        rows = self._db.scalars(stmt).all()
        return [self._a_entidad(r) for r in rows]

    # ------------------------------------------------------------------
    # Escritura
    # ------------------------------------------------------------------

    def guardar(self, umbral: UmbralAmbiental) -> UmbralAmbiental:
        """Inserta el umbral y devuelve la entidad con su id asignado."""
        try:
            orm = UmbralAmbientalModel(
                id_especie=umbral.id_especie,
                id_variable_ambiental=umbral.id_variable_ambiental,
                id_usuario=umbral.id_usuario,
                unidad_medida=umbral.unidad_medida,
                valor_min=umbral.valor_min,
                valor_max=umbral.valor_max,
                tolerancia_semaforo=umbral.tolerancia_semaforo,
                es_activo=umbral.es_activo,
                fecha_actualizacion=umbral.fecha_actualizacion,
                estado_sincronizacion=umbral.estado_sincronizacion,
                fecha_ultima_sincronizacion=umbral.fecha_ultima_sincronizacion,
                motivo_fallo_sincronizacion=umbral.motivo_fallo_sincronizacion,
            )
            self._db.add(orm)
            self._db.flush()

            for n in umbral.niveles:
                nivel_orm = NivelAlertaAmbientalModel(
                    id_umbral_ambiental=orm.id_umbral_ambiental,
                    nivel=n.nivel.value,
                    limite_inferior=n.limite_inferior,
                    limite_superior=n.limite_superior,
                )
                self._db.add(nivel_orm)

            self._db.flush()
            self._db.refresh(orm)
            return self._a_entidad(orm)
        except Exception as exc:
            raise_from_db_error(exc)

    def actualizar(self, umbral: UmbralAmbiental) -> UmbralAmbiental:
        """Persiste los cambios del umbral y devuelve la entidad actualizada."""
        try:
            orm = self._db.get(UmbralAmbientalModel, umbral.id_umbral_ambiental)
            orm.valor_min = umbral.valor_min
            orm.valor_max = umbral.valor_max
            orm.tolerancia_semaforo = umbral.tolerancia_semaforo
            orm.es_activo = umbral.es_activo
            orm.fecha_actualizacion = umbral.fecha_actualizacion
            orm.id_usuario = umbral.id_usuario
            orm.estado_sincronizacion = umbral.estado_sincronizacion
            orm.fecha_ultima_sincronizacion = umbral.fecha_ultima_sincronizacion
            orm.motivo_fallo_sincronizacion = umbral.motivo_fallo_sincronizacion

            # Reemplazar niveles (delete-then-insert via cascade)
            for nivel_orm in list(orm.niveles):
                self._db.delete(nivel_orm)
            self._db.flush()

            for n in umbral.niveles:
                nivel_orm = NivelAlertaAmbientalModel(
                    id_umbral_ambiental=orm.id_umbral_ambiental,
                    nivel=n.nivel.value,
                    limite_inferior=n.limite_inferior,
                    limite_superior=n.limite_superior,
                )
                self._db.add(nivel_orm)

            self._db.flush()
            self._db.refresh(orm)
            return self._a_entidad(orm)
        except Exception as exc:
            raise_from_db_error(exc)

    def actualizar_estado_sincronizacion(self, umbral: UmbralAmbiental) -> UmbralAmbiental:
        """Persiste solo estado_sincronizacion/fecha_ultima_sincronizacion/motivo_fallo_sincronizacion.

        No toca valor_min/valor_max/niveles -- se usa después del intento de
        propagación al Nodo Edge (INC-M09-104-G29), en un segundo commit
        separado del guardado del umbral en sí.
        """
        try:
            orm = self._db.get(UmbralAmbientalModel, umbral.id_umbral_ambiental)
            orm.estado_sincronizacion = umbral.estado_sincronizacion
            orm.fecha_ultima_sincronizacion = umbral.fecha_ultima_sincronizacion
            orm.motivo_fallo_sincronizacion = umbral.motivo_fallo_sincronizacion
            self._db.flush()
            self._db.refresh(orm)
            return self._a_entidad(orm)
        except Exception as exc:
            raise_from_db_error(exc)

    def desactivar_todos_por_especie(self, id_especie: int) -> None:
        """Marca como inactivos todos los umbrales activos de una especie. Hace ``flush``."""
        try:
            self._db.query(UmbralAmbientalModel).filter(
                UmbralAmbientalModel.id_especie == id_especie,
                UmbralAmbientalModel.es_activo.is_(True),
            ).update({'es_activo': False}, synchronize_session='fetch')
            self._db.flush()
        except Exception as exc:
            raise_from_db_error(exc)

    def guardar_desde_snapshot(self, datos: dict, id_especie: int, id_usuario: int) -> None:
        """Inserta un umbral + niveles a partir de un dict del params_snapshot. Hace ``flush``."""
        from decimal import Decimal
        try:
            orm = UmbralAmbientalModel(
                id_especie=id_especie,
                id_variable_ambiental=int(datos['id_variable_ambiental']),
                id_usuario=id_usuario,
                unidad_medida=datos['unidad_medida'],
                valor_min=Decimal(datos['valor_min']),
                valor_max=Decimal(datos['valor_max']),
                tolerancia_semaforo=(
                    Decimal(datos['tolerancia_semaforo']) if datos.get('tolerancia_semaforo') is not None else None
                ),
                es_activo=True,
            )
            self._db.add(orm)
            self._db.flush()
            for n in datos.get('niveles', []):
                nivel_orm = NivelAlertaAmbientalModel(
                    id_umbral_ambiental=orm.id_umbral_ambiental,
                    nivel=n['nivel'],
                    limite_inferior=Decimal(n['limite_inferior']),
                    limite_superior=Decimal(n['limite_superior']),
                )
                self._db.add(nivel_orm)
            self._db.flush()
        except Exception as exc:
            raise_from_db_error(exc)

    @staticmethod
    def _a_entidad(orm: UmbralAmbientalModel) -> UmbralAmbiental:
        niveles = [
            NivelAlertaAmbiental(
                nivel=NivelAlerta(n.nivel),
                limite_inferior=n.limite_inferior,
                limite_superior=n.limite_superior,
            )
            for n in orm.niveles
        ]
        return UmbralAmbiental(
            id_umbral_ambiental=orm.id_umbral_ambiental,
            id_especie=orm.id_especie,
            id_variable_ambiental=orm.id_variable_ambiental,
            unidad_medida=orm.unidad_medida,
            valor_min=orm.valor_min,
            valor_max=orm.valor_max,
            tolerancia_semaforo=orm.tolerancia_semaforo,
            es_activo=orm.es_activo,
            niveles=niveles,
            fecha_actualizacion=orm.fecha_actualizacion,
            id_usuario=orm.id_usuario,
            estado_sincronizacion=orm.estado_sincronizacion,
            fecha_ultima_sincronizacion=orm.fecha_ultima_sincronizacion,
            motivo_fallo_sincronizacion=orm.motivo_fallo_sincronizacion,
        )
