"""Puerto (ABC) para la auditoría de umbrales ambientales (CU03 RF-17)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.configuration.domain.entities.auditoria_umbral import AuditoriaUmbral


class AuditoriaUmbralRepository(ABC):
    @abstractmethod
    def registrar(
        self,
        id_umbral_ambiental: int,
        id_usuario: Optional[int],
        tipo_operacion: str,
        valores_nuevos: dict,
        valores_anteriores: Optional[dict] = None,
    ) -> None: ...

    @abstractmethod
    def listar_por_umbral(self, id_umbral_ambiental: int) -> list[AuditoriaUmbral]:
        """Historial de auditoría de un umbral, más reciente primero.

        INC-M09-30-G30 (TC-M09-64): la creación, edición y desactivación de un
        umbral ya se persistían en ``modulo9.auditorias_umbrales_ambientales``,
        pero no existía forma de consultarlas por API. Este método expone ese
        historial para poder correlacionar cada operación con el umbral.
        """
        raise NotImplementedError
