# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-11-02 | Arekkazu | RF-66/RF-69: catálogo del motor IA armado desde la BD            |
"""Animales que atiende el motor IA (M02 + M09) y su versión de RF-69 (RFC-010).

Un animal entra al catálogo si es INDIVIDUAL, sigue vivo (ACTIVO, EN_TRATAMIENTO o AISLADO),
está en un área con modelo individual asignado (RF-20) y tiene un sensor en asociación
``directa`` vigente: sin eso el backend nunca le arma paquetes (RF-56).
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.prediction.domain.entities.animal_motor import AnimalMotor
from src.prediction.domain.repositories.catalogo_motor_port import CatalogoMotorPort
from src.shared.db_error_translator import raise_from_db_error
from src.telemetry.infrastructure.adapters.ventana_inferencia_m02_adapter import lecturas_activo

TIPOS_INDIVIDUALES = ("MODELO_ESPECIES_GRANDES", "MODELO_ESPECIES_MEDIANAS")
ESTADOS_ATENDIDOS = ("ACTIVO", "EN_TRATAMIENTO", "AISLADO")

_SQL_ANIMALES = text("""
    SELECT ab.id_activo_biologico, i.tipo_modelo_asignado::text AS tipo_modelo,
           v.id_version_modelo, v.nombre_version, v.hash_artefacto_sha256, v.fuente_datos::text
    FROM modulo2.activos_biologicos ab
    JOIN modulo2.estados_activos_biologicos ea ON ea.id_estado_activo_biologico = ab.id_estado
    JOIN modulo9.infraestructuras i ON i.id_infraestructura = ab.id_infraestructura
    LEFT JOIN LATERAL (
        SELECT v.id_version_modelo, v.nombre_version, v.hash_artefacto_sha256, v.fuente_datos
        FROM modulo4.versiones_modelos v
        WHERE v.id_activo_biologico = ab.id_activo_biologico
          AND v.tipo_modelo::text = i.tipo_modelo_asignado::text
          AND v.estado_version::text IN ('ACTIVO', 'SOMBRA')
        ORDER BY (v.estado_version::text = 'ACTIVO') DESC, v.id_version_modelo DESC
        LIMIT 1
    ) v ON true
    WHERE ab.tipo::text = 'INDIVIDUAL'
      AND ea.nombre = ANY(CAST(:estados AS text[]))
      AND i.tipo_modelo_asignado::text = ANY(CAST(:tipos AS text[]))
      AND (CAST(:activo AS int) IS NULL OR ab.id_activo_biologico = :activo)
      AND EXISTS (
          SELECT 1 FROM modulo2.asociaciones_activos_sensores a
          WHERE a.id_activo_biologico = ab.id_activo_biologico AND a.tipo::text = 'directa'
            AND a.estado_asociacion = 'ACTIVA' AND (a.fecha_fin IS NULL OR a.fecha_fin > now())
      )
    ORDER BY ab.id_activo_biologico
""")

# La activa primero; entre iguales, la más reciente. Una copia comparte artefacto con su
# original, así que da lo mismo cuál de las dos se tome.
_SQL_REFERENCIA = text("""
    SELECT id_version_modelo FROM modulo4.versiones_modelos
    WHERE tipo_modelo::text = :tipo AND estado_version::text IN ('ACTIVO', 'SOMBRA')
      AND id_activo_biologico IS NOT NULL
    ORDER BY (estado_version::text = 'ACTIVO') DESC, fecha_entrenamiento DESC, id_version_modelo
    LIMIT 1
""")


class CatalogoMotorM02Adapter(CatalogoMotorPort):
    def __init__(self, db: Session) -> None:
        self._db = db

    def animales(self, id_activo: Optional[int] = None) -> list[AnimalMotor]:
        try:
            filas = self._db.execute(_SQL_ANIMALES, {
                "estados": list(ESTADOS_ATENDIDOS), "tipos": list(TIPOS_INDIVIDUALES), "activo": id_activo,
            }).all()
        except Exception as exc:
            raise_from_db_error(exc)
        return [AnimalMotor(*f) for f in filas]

    def version_referencia(self, tipo_modelo: str) -> Optional[int]:
        try:
            return self._db.execute(_SQL_REFERENCIA, {"tipo": tipo_modelo}).scalar()
        except Exception as exc:
            raise_from_db_error(exc)

    def lecturas(self, id_activo: int, desde: datetime, hasta: datetime) -> list[dict]:
        try:
            return lecturas_activo(self._db, id_activo, desde, hasta)
        except Exception as exc:
            raise_from_db_error(exc)
