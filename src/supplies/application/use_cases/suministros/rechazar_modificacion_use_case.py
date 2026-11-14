# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-75 E5 / RF-76 R5: edición → 405        |
"""Caso de uso: rechazar la modificación de un consumo o medicamento (RF-75 E5, RF-76 R5).

Los registros son inmutables: un VALIDADO solo se anula y un ANULADO no se
reactiva. Cualquier PUT/PATCH/DELETE sobre un registro existente responde 405
con el mensaje del RF; si el registro no existe, 404.
"""
from __future__ import annotations

from src.shared.errors import MethodNotAllowedError, NotFoundError
from src.supplies.domain.repositories.consumo_alimento_repository import ConsumoAlimentoRepository
from src.supplies.domain.repositories.medicamento_repository import MedicamentoRepository
from src.supplies.domain.value_objects.estado_registro import EstadoRegistro


class RechazarModificacionUseCase:
    def __init__(
        self,
        consumo_repo: ConsumoAlimentoRepository,
        medicamento_repo: MedicamentoRepository,
    ) -> None:
        self.consumo_repo = consumo_repo
        self.medicamento_repo = medicamento_repo

    def consumo(self, id_consumo: int) -> None:
        registro = self.consumo_repo.obtener_por_id(id_consumo)
        if registro is None:
            raise NotFoundError(
                code="CONSUMO_NO_ENCONTRADO",
                message=f"El registro de consumo con ID {id_consumo} no existe.",
            )
        self._rechazar("El registro de consumo", id_consumo, registro.estado_registro)

    def medicamento(self, id_medicamento: int) -> None:
        registro = self.medicamento_repo.obtener_por_id(id_medicamento)
        if registro is None:
            raise NotFoundError(
                code="MEDICAMENTO_NO_ENCONTRADO",
                message=f"El registro de aplicación de medicamento con ID {id_medicamento} no existe.",
            )
        self._rechazar("El registro de aplicación de medicamento", id_medicamento, registro.estado_registro)

    @staticmethod
    def _rechazar(sujeto: str, id_registro: int, estado: str) -> None:
        if estado == EstadoRegistro.ANULADO.value:
            mensaje = (
                f"{sujeto} {id_registro} está en estado ANULADO y no puede ser modificado ni reactivado. "
                "Si necesita reemplazarlo, cree un nuevo registro."
            )
        else:
            mensaje = (
                f"{sujeto} {id_registro} está en estado VALIDADO y no puede ser modificado. Para corregirlo, "
                "debe anularlo y crear un nuevo registro."
            )
        raise MethodNotAllowedError(code="REGISTRO_INMUTABLE", message=mensaje)
