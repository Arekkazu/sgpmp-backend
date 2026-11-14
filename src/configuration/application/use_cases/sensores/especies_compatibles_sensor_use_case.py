# | Fecha      | Nombre   | Que se hizo                                                      |
# |------------|----------|------------------------------------------------------------------|
# | 2026-10-30 | Arekkazu | INC-M03-135-G01 RF-49: especies compatibles de un sensor desde M09 |
"""RF-49 R3 / FA-04: especies con las que un sensor puede vincularse a un activo biológico.

M02 exige esta lista antes de asociar un sensor a un animal; antes solo se había cargado
una vez (septiembre 2026) y ningún endpoint la alimentaba (INC-M03-135-G01).
"""
from __future__ import annotations

from typing import Optional

from src.configuration.domain.entities.especie import Especie
from src.configuration.domain.repositories.compatibilidad_sensor_especie_repository import (
    CompatibilidadSensorEspecieRepository,
)
from src.configuration.domain.repositories.dispositivo_iot_repository import DispositivoIotRepository
from src.configuration.domain.repositories.especie_repository import EspecieRepository
from src.configuration.domain.repositories.sensor_repository import SensorRepository
from src.shared.errors import NotFoundError, ValidationError


class EspeciesCompatiblesSensorUseCase:
    def __init__(
        self, *, db, sensor_repo: SensorRepository, dispositivo_repo: DispositivoIotRepository,
        especie_repo: EspecieRepository, compatibilidad_repo: CompatibilidadSensorEspecieRepository,
    ) -> None:
        self.db = db
        self.sensor_repo = sensor_repo
        self.dispositivo_repo = dispositivo_repo
        self.especie_repo = especie_repo
        self.compatibilidad_repo = compatibilidad_repo

    def consultar(self, id_sensor: int, ids_fincas_permitidas: Optional[list[int]]) -> list[Especie]:
        self._validar_sensor(id_sensor, ids_fincas_permitidas)
        return [self.especie_repo.obtener_por_id(i) for i in self.compatibilidad_repo.listar_especies(id_sensor)]

    def reemplazar(
        self, id_sensor: int, ids_especies: list[int], ids_fincas_permitidas: Optional[list[int]],
    ) -> list[Especie]:
        self._validar_sensor(id_sensor, ids_fincas_permitidas)
        ids = list(dict.fromkeys(ids_especies))
        especies = []
        for id_especie in ids:
            especie = self.especie_repo.obtener_por_id(id_especie)
            if especie is None or not especie.es_activo:
                raise ValidationError(
                    code="ESPECIE_NO_VALIDA",
                    message=f"La especie {id_especie} no existe o no está activa.",
                    field="ids_especies",
                )
            especies.append(especie)
        try:
            self.compatibilidad_repo.reemplazar(id_sensor, ids)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return especies

    def _validar_sensor(self, id_sensor: int, ids_fincas_permitidas: Optional[list[int]]) -> None:
        # Un sensor de una finca ajena responde 404, igual que uno inexistente (TC-M09-141).
        sensor = self.sensor_repo.obtener_por_id(id_sensor)
        if sensor is None or self.dispositivo_repo.obtener_por_id(
            sensor.id_dispositivo_iot, ids_fincas_permitidas=ids_fincas_permitidas,
        ) is None:
            raise NotFoundError(code="SENSOR_NO_ENCONTRADO", message=f"El sensor {id_sensor} no existe.")
