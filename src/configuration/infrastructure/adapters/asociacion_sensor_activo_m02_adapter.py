# | Fecha      | Nombre   | Que se hizo                                      |
# |------------|----------|--------------------------------------------------|
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Adaptador de escritura sobre modulo2 para el cierre de asociaciones
sensor→activo al reasignar un sensor de área (RF-22, issue #290).

Reutiliza los modelos ORM de biological_assets directamente (mismo patrón
que `CicloM02Adapter` en supplies) en vez de SQL crudo: al compartir la
misma `Session` que `AsociarSensorAreaUseCase`, el cierre queda en la misma
transacción que la reasignación — un solo `commit()`, un solo `rollback()`.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.biological_assets.infrastructure.models.asociacion_sensor_activo_model import (
    AsociacionSensorActivoModel,
)
from src.biological_assets.infrastructure.models.auditoria_asociacion_sensor_model import (
    AuditoriaAsociacionSensorModel,
)
from src.configuration.domain.repositories.asociacion_sensor_activo_dependency_port import (
    AsociacionActivoSuperada,
    AsociacionSensorActivoDependencyPort,
)


class AsociacionSensorActivoM02Adapter(AsociacionSensorActivoDependencyPort):
    """Gestiona las asociaciones sensor-activo afectadas al cambiar el área de un sensor."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def superar_ambientales_y_poblacionales(
        self,
        id_sensor: int,
        id_usuario: int,
        motivo: str,
    ) -> list[AsociacionActivoSuperada]:
        """Marca SUPERADA toda asociación ACTIVA ambiental/poblacional de
        `id_sensor` y registra la auditoría correspondiente en modulo2.

        Devuelve las asociaciones cerradas (lista vacía si el sensor no tenía
        ninguna vigente de esos tipos).
        """
        activas = (
            self.db.query(AsociacionSensorActivoModel)
            .filter(
                AsociacionSensorActivoModel.id_sensor == id_sensor,
                AsociacionSensorActivoModel.estado_asociacion == 'ACTIVA',
                AsociacionSensorActivoModel.fecha_fin.is_(None),
                AsociacionSensorActivoModel.tipo.in_(('ambiental', 'poblacional')),
            )
            .all()
        )
        if not activas:
            return []

        ahora = datetime.now(timezone.utc)
        cerradas: list[AsociacionActivoSuperada] = []
        for asociacion in activas:
            valores_anteriores = {
                'estado_asociacion': asociacion.estado_asociacion,
                'tipo': asociacion.tipo,
                'id_infraestructura': asociacion.id_infraestructura,
            }
            asociacion.estado_asociacion = 'SUPERADA'
            asociacion.fecha_fin = ahora
            asociacion.motivo = motivo
            self.db.add(AuditoriaAsociacionSensorModel(
                id_asociacion_activo_sensor=asociacion.id_asociacion_activo_sensor,
                id_usuario=id_usuario,
                tipo_operacion='UPDATE',
                valores_anteriores=valores_anteriores,
                valores_nuevos={
                    'estado_asociacion': 'SUPERADA',
                    'fecha_fin': ahora.isoformat(),
                    'motivo': motivo,
                },
            ))
            cerradas.append(AsociacionActivoSuperada(
                id_asociacion_activo_sensor=asociacion.id_asociacion_activo_sensor,
                id_activo_biologico=asociacion.id_activo_biologico,
                tipo=asociacion.tipo,
            ))

        self.db.flush()
        return cerradas
