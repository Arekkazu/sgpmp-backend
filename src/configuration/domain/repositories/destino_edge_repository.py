"""Puerto (ABC): a qué Gateway Edge le corresponde un umbral ambiental (RF-17).

INC-M09-104-G29: un umbral se define por (especie, variable ambiental). Llega a
los Gateway Edge de las áreas activas de esa especie (por su ``id_especie`` o
por tener activos biológicos vivos de ella) -- los instalados en el área o los
que atienden un dispositivo activo del área. El Gateway Edge es
quien evalúa las lecturas en campo y lo único que habla MQTT con el broker.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class DestinoEdgeRepository(ABC):

    @abstractmethod
    def listar_seriales_gateway_por_especie(self, id_especie: int) -> list[str]:
        """Seriales de los Gateway Edge activos de las áreas activas de la especie.

        No depende de la identidad de quien llama: la propagación de un umbral
        no puede cambiar según el rol que lo editó.
        """
        ...
