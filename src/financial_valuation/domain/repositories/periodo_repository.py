# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-82..94: puerto del módulo financiero |
# | 2026-11-10 | Arekkazu | INC-M06-345-G43 RF-87: cierre en espera de autorización |
# | 2026-11-11 | Arekkazu | USAB-M06 RF-87/93: titulares con período, filtro sin titular y último cierre de todos los períodos en una consulta |
"""Puerto de los períodos contables, sus cierres y comprobantes (RF-87)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Optional

from src.financial_valuation.domain.entities.contabilidad import Periodo
from src.financial_valuation.domain.services.consolidacion import Comprobante


class PeriodoRepository(ABC):
    @abstractmethod
    def obtener(self, id_periodo_contable: int, bloquear: bool = False) -> Optional[Periodo]:
        """bloquear: SELECT ... FOR UPDATE NOWAIT (un solo cierre a la vez, RF-87)."""

    @abstractmethod
    def que_contiene(self, numero_id_tributaria: str, dia: date) -> Optional[Periodo]: ...

    @abstractmethod
    def primero_abierto_desde(self, numero_id_tributaria: str, dia: date) -> Optional[Periodo]: ...

    @abstractmethod
    def hay_posteriores(self, numero_id_tributaria: str, dia: date) -> bool: ...

    @abstractmethod
    def crear(self, numero_id_tributaria: str, tipo_cierre: str, inicio: date, fin: date, id_usuario: int) -> Periodo: ...

    @abstractmethod
    def cambiar_estado(self, id_periodo_contable: int, estado: str) -> None: ...

    @abstractmethod
    def listar(self, numero_id_tributaria: Optional[str], sin_titular: bool = False) -> list[Periodo]:
        """Del titular dado (todos si es None); con ``sin_titular`` solo los que no tienen titular."""

    @abstractmethod
    def titulares(self) -> list[dict]:
        """NIT y razón social de cada titular con períodos visibles; los períodos sin titular, al final (NIT None)."""

    @abstractmethod
    def abierto_anterior(self, periodo: Periodo) -> Optional[Periodo]: ...

    @abstractmethod
    def iniciar_cierre(self, id_periodo_contable: int, id_usuario: int, incluir_sin_precio: bool) -> int: ...

    @abstractmethod
    def ejecucion_en_proceso(self, id_periodo_contable: int) -> Optional[dict]:
        """Incluye ``esperando_autorizacion`` y ``nombre_usuario_ejecutor``."""

    @abstractmethod
    def esperar_autorizacion(self, id_cierre: int) -> None:
        """El cierre queda EN_PROCESO esperando la decisión del Contador sobre las exclusiones."""

    @abstractmethod
    def reanudar_cierre(self, id_cierre: int, incluir_sin_precio: bool) -> None: ...

    @abstractmethod
    def finalizar_cierre(self, id_cierre: int, estado: str, datos: dict) -> None: ...

    @abstractmethod
    def guardar_comprobante(self, comprobante: Comprobante, id_periodo_contable: int, id_cierre: int) -> int: ...

    @abstractmethod
    def comprobantes(self, id_periodo_contable: int) -> list[dict]: ...

    @abstractmethod
    def ultima_ejecucion(self, id_periodo_contable: int) -> Optional[dict]: ...

    @abstractmethod
    def ultimas_ejecuciones(self, ids_periodos: list[int]) -> dict[int, dict]:
        """La última ejecución de cierre de cada período, en una sola consulta."""
