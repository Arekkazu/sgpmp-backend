# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-20 | Arekkazu | DEV-22 RF-20: áreas de una especie se leen de la tabla puente (RFC-012) |
# | 2026-10-20 | Arekkazu | DEV-19 RF-15: persiste esperanza_vida_dias (RFC-014) |
# | 2026-10-20 | Arekkazu | DEV-21 RF-15: áreas ocupadas de la especie para validar la reducción de densidad |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Implementación SQLAlchemy del puerto :class:`EspecieRepository`.

Único punto donde se cruza la frontera ORM ↔ dominio para el agregado
``Especie``: traduce ``EspecieModel`` → ``Especie`` al leer y
``Especie`` → ``EspecieModel`` al escribir. El resto de la aplicación
trabaja siempre con la entidad pura.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from src.configuration.domain.entities.especie import Especie
from src.configuration.domain.repositories.especie_repository import EspecieRepository
from src.configuration.domain.services.capacidad_area import AreaOcupada
from src.configuration.domain.value_objects.nombre_especie import NombreEspecie
from src.configuration.infrastructure.adapters.infraestructura_dependency_adapter import (
    InfraestructuraDependencyAdapter,
)
from src.configuration.infrastructure.models.especie_model import EspecieModel
from src.configuration.infrastructure.models.infraestructura_model import (
    InfraestructuraEspecieModel,
    InfraestructuraModel,
)
from src.configuration.infrastructure.repositories.infraestructura_repository import (
    SqlAlchemyInfraestructuraRepository,
)
from src.shared.db_error_translator import raise_from_db_error
from src.shared.rehidratar import rehidratar


class SqlAlchemyEspecieRepository(EspecieRepository):
    """Adaptador SQLAlchemy que mapea entre ``modulo9.especies`` y la entidad."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Mapeo ORM ↔ dominio ─────────────────────────────────────────────────

    @staticmethod
    def _a_entidad(orm: EspecieModel) -> Especie:
        return Especie(
            id_especie=orm.id_especie,
            nombre=rehidratar(NombreEspecie, orm.nombre),
            descripcion=orm.descripcion,
            densidad_maxima_por_especie=orm.densidad_maxima_por_especie,
            grupo_manejo=orm.grupo_manejo,
            esperanza_vida_dias=orm.esperanza_vida_dias,
            es_activo=orm.es_activo,
            fecha_creacion=orm.fecha_creacion,
            fecha_actualizacion=orm.fecha_actualizacion,
        )

    @staticmethod
    def _a_orm(especie: Especie) -> EspecieModel:
        return EspecieModel(
            nombre=especie.nombre.valor,
            descripcion=especie.descripcion,
            densidad_maxima_por_especie=especie.densidad_maxima_por_especie,
            grupo_manejo=especie.grupo_manejo,
            esperanza_vida_dias=especie.esperanza_vida_dias,
            es_activo=especie.es_activo,
            fecha_creacion=especie.fecha_creacion or datetime.now(timezone.utc),
        )

    # ── Operaciones del puerto ───────────────────────────────────────────────

    def obtener_por_id(self, id_especie: int, *, bloquear: bool = False) -> Optional[Especie]:
        """Obtiene una especie por su identidad.

        Args:
            id_especie: PK de la especie.
            bloquear: toma la fila con ``SELECT ... FOR UPDATE`` (edición con
                concurrencia optimista, #498).

        Returns:
            La entidad :class:`Especie` o ``None`` si no existe.
        """
        orm = self.db.get(EspecieModel, id_especie, with_for_update=bloquear, populate_existing=bloquear)
        return self._a_entidad(orm) if orm else None

    def obtener_por_nombre(self, nombre: NombreEspecie) -> Optional[Especie]:
        """Busca una especie cuyo nombre normalizado coincida (case-insensitive).

        Usado para validar unicidad antes de insertar o actualizar.

        Args:
            nombre: Value object con el nombre a comparar.

        Returns:
            La entidad :class:`Especie` que coincide o ``None`` si no existe.
        """
        orm = (
            self.db.query(EspecieModel)
            .filter(func.lower(EspecieModel.nombre) == nombre.normalizado())
            .first()
        )
        return self._a_entidad(orm) if orm else None

    def guardar(self, especie: Especie) -> Especie:
        """Inserta una especie nueva y retorna la entidad con ``id_especie`` asignado.

        Hace ``flush`` interno. El ``commit`` lo emite el caso de uso.

        Args:
            especie: Entidad nueva (``id_especie`` es ``None``).

        Returns:
            La entidad re-hidratada con ``id_especie`` y ``fecha_creacion``
            poblados por la base de datos.

        Raises:
            ConflictError: Si el nombre ya existe en el catálogo. HTTP 409.
        """
        orm = self._a_orm(especie)
        try:
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc, {
                "uq_especie_nombre": (
                    f"La especie '{especie.nombre.valor}' ya se encuentra registrada en el catálogo."
                ),
            })
        return self._a_entidad(orm)

    def actualizar(self, especie: Especie) -> Especie:
        """Persiste los cambios de una especie existente.

        Hace ``flush`` interno. El ``commit`` lo emite el caso de uso.

        Args:
            especie: Entidad con los campos ya modificados.

        Returns:
            La entidad re-hidratada desde la base de datos.

        Raises:
            ConflictError: Si el nuevo nombre ya pertenece a otra especie. HTTP 409.
        """
        orm = self.db.get(EspecieModel, especie.id_especie)
        orm.nombre = especie.nombre.valor
        orm.descripcion = especie.descripcion
        orm.densidad_maxima_por_especie = especie.densidad_maxima_por_especie
        orm.grupo_manejo = especie.grupo_manejo
        orm.esperanza_vida_dias = especie.esperanza_vida_dias
        orm.es_activo = especie.es_activo
        orm.fecha_actualizacion = especie.fecha_actualizacion
        try:
            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc, {
                "uq_especie_nombre": (
                    f"El nombre '{especie.nombre.valor}' ya pertenece a otra especie del catálogo."
                ),
            })
        return self._a_entidad(orm)

    def listar(self, *, solo_activas: bool = False) -> list[Especie]:
        """Retorna el catálogo completo de especies.

        Args:
            solo_activas: Si es ``True`` filtra solo las especies con
                ``es_activo=True``.

        Returns:
            Lista de entidades :class:`Especie` ordenadas por nombre.
        """
        query = self.db.query(EspecieModel)
        if solo_activas:
            query = query.filter(EspecieModel.es_activo.is_(True))
        return [
            self._a_entidad(orm)
            for orm in query.order_by(EspecieModel.nombre).all()
        ]

    def contar_areas_con_modelo_distinto(self, id_especie: int, tipo_modelo: Optional[str]) -> int:
        """RF-20 v1.1 (RFC-009): áreas de la especie con un modelo de IA asignado que no es ``tipo_modelo``.

        Con ``tipo_modelo=None`` cuenta todas las que tengan modelo asignado: sin familia,
        ninguno es coherente. Incluye áreas inactivas, que pueden reactivarse.
        """
        # RFC-012: el área tiene la especie si está en la tabla puente.
        consulta = self.db.query(func.count()).select_from(InfraestructuraModel).join(
            InfraestructuraEspecieModel,
            InfraestructuraEspecieModel.id_infraestructura == InfraestructuraModel.id_infraestructura,
        ).filter(
            InfraestructuraEspecieModel.id_especie == id_especie,
            InfraestructuraModel.tipo_modelo_asignado.isnot(None),
        )
        if tipo_modelo is not None:
            consulta = consulta.filter(InfraestructuraModel.tipo_modelo_asignado != tipo_modelo)
        return consulta.scalar()

    def contar_activos_alojados(self, id_especie: int) -> int:
        """RF-15 v1.1: activos biológicos de la especie alojados en un área y operativos."""
        return self.db.execute(
            text(
                "SELECT activos_biologicos_alojados FROM modulo9.vw_rf15_dependencias_especie "
                "WHERE id_especie = :id"
            ),
            {"id": id_especie},
        ).scalar() or 0

    def listar_areas_ocupadas(self, id_especie: int) -> list[AreaOcupada]:
        """RFC-012: áreas activas donde está la especie y que alojan individuos."""
        areas = self.db.query(InfraestructuraModel).join(
            InfraestructuraEspecieModel,
            InfraestructuraEspecieModel.id_infraestructura == InfraestructuraModel.id_infraestructura,
        ).filter(
            InfraestructuraEspecieModel.id_especie == id_especie,
            InfraestructuraModel.es_activo.is_(True),
        ).all()
        infra_repo = SqlAlchemyInfraestructuraRepository(self.db)
        dependencias = InfraestructuraDependencyAdapter(self.db)
        ocupadas = []
        for orm in areas:
            carga = dependencias.calcular_carga(orm.id_infraestructura)
            if carga:
                ocupadas.append(AreaOcupada(
                    nombre=orm.nombre, superficie=Decimal(str(orm.superficie)),
                    especies=infra_repo.especies_del_area(orm), carga=carga,
                ))
        return ocupadas
