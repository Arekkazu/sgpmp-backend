# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-82..94: puerto del módulo financiero |
# | 2026-11-05 | Arekkazu | M06 RF-83..86: listados del período para las vistas del prototipo |
# | 2026-11-08 | Arekkazu | INC-M06-314-G15 RF-83: mediciones del período filtrables por evento y estimación, con id_evento e id_periodo_contable |
# | 2026-11-09 | destroyerban | INC-M06-317-G17 RF-84: cálculo en revisión y validación del valor neto ≤ 0 |
# | 2026-11-09 | destroyerban | INC-M06-325-G30 RF-85 RNF-85-05: historial de productos con filtros, evento y usuario |
# | 2026-11-10 | Arekkazu | INC-M06-297-G34 RF-86: eventos del período con medición pendiente |
# | 2026-11-11 | Arekkazu | USAB-M06 M6-03 RF-82/87: razón social del período y listas filtradas por el titular del período |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Puerto de la valoración NIC 41: cálculos (RF-84), reconocimientos (RF-82), mediciones y
variaciones (RF-83/86), productos agrícolas (RF-85) y valoración por costo (RF-88)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from decimal import Decimal
from typing import Optional

from src.financial_valuation.domain.entities.valoracion import (
    CalculoValor,
    Medicion,
    Reconocimiento,
    ValoracionCosto,
    VariacionRegistro,
)


class ValoracionRepository(ABC):
    """Puerto de persistencia de valoraciones, reconocimientos y deterioros."""
    @abstractmethod
    def agregar_calculo(self, calculo: CalculoValor) -> int:
        """Registra un cálculo de valor razonable y devuelve su id."""
        ...

    @abstractmethod
    def obtener_calculo(self, id_calculo_valor_razonable: int) -> Optional[CalculoValor]:
        """Devuelve el cálculo, o ``None``."""
        ...

    @abstractmethod
    def validar_calculo(self, id_calculo_valor_razonable: int, validacion: dict) -> None:
        """Pasa un cálculo en REVISION_REQUERIDA a CALCULADO y guarda la validación en ``json_metodo_costo``."""

    @abstractmethod
    def ultimo_calculo(self, id_activo_biologico: int, hasta: Optional[date] = None) -> Optional[CalculoValor]:
        """Devuelve el último cálculo del activo hasta la fecha, o ``None``."""
        ...

    @abstractmethod
    def agregar_medicion(self, medicion: Medicion) -> int:
        """Registra una medición y devuelve su id."""
        ...

    @abstractmethod
    def agregar_variacion(self, variacion: VariacionRegistro) -> int:
        """Registra una variación y devuelve su id."""
        ...

    @abstractmethod
    def reconocimiento_confirmado(self, id_activo_biologico: int) -> Optional[Reconocimiento]:
        """Devuelve el reconocimiento confirmado del activo, o ``None``."""
        ...

    @abstractmethod
    def agregar_reconocimiento(self, datos: dict) -> int:
        """Registra un reconocimiento y devuelve su id."""
        ...

    @abstractmethod
    def revertir_reconocimiento(self, id_reconocimiento: int, motivo: str, id_usuario: int,
                                monto: Decimal, cuenta_debito: str, cuenta_credito: str) -> int:
        """Revierte el reconocimiento con su asiento."""
        ...

    @abstractmethod
    def dependientes_reconocimiento(self, reconocimiento: Reconocimiento) -> list[dict]:
        """Mediciones, variaciones y cierres que impiden revertir (RF-82 R2 b)."""

    @abstractmethod
    def reconocimientos_del_activo(self, id_activo_biologico: int) -> list[dict]:
        """Lista los reconocimientos del activo."""
        ...

    @abstractmethod
    def agregar_valoracion_costo(self, valoracion: ValoracionCosto) -> int:
        """Registra una valoración al costo y devuelve su id."""
        ...

    @abstractmethod
    def valoracion_costo_activa(self, id_activo_biologico: int) -> Optional[ValoracionCosto]:
        """Devuelve la valoración al costo activa, o ``None``."""
        ...

    @abstractmethod
    def actualizar_valoracion_costo(self, valoracion: ValoracionCosto) -> None:
        """Actualiza la valoración al costo."""
        ...

    @abstractmethod
    def agregar_deterioro(self, id_valoracion: int, id_evento_sanitario: int, monto: Decimal, justificacion: str,
                          id_usuario: int) -> int:
        """Registra un deterioro y devuelve su id."""
        ...

    @abstractmethod
    def agregar_producto(self, datos: dict) -> int:
        """Registra un producto agrícola y devuelve su id."""
        ...

    @abstractmethod
    def activos_valorados(self, numero_id_tributaria: Optional[str] = None) -> list[dict]:
        """Lista los activos valorados, opcionalmente de un titular."""
        ...

    @abstractmethod
    def historial_activo(self, id_activo_biologico: int) -> dict:
        """Devuelve el historial de valoración del activo."""
        ...

    @abstractmethod
    def mediciones_del_periodo(self, id_periodo_contable: int, id_evento: Optional[int] = None,
                               tiene_valor_estimado: Optional[bool] = None) -> list[dict]:
        """RF-83: mediciones posteriores del período con el activo que midieron."""

    @abstractmethod
    def eventos_pendientes_del_periodo(self, id_periodo_contable: int) -> list[dict]:
        """RF-86: eventos del período cuya medición quedó suspendida (MEDICION_PENDIENTE). No dejan
        medición, así que sin esto el panel tomaría como vigente una medición anterior del activo."""

    @abstractmethod
    def variaciones_del_periodo(self, id_periodo_contable: int) -> list[dict]:
        """RF-86: variaciones del período con la evidencia y la trazabilidad de su línea de asiento."""

    @abstractmethod
    def calculos_del_periodo(self, id_periodo_contable: int) -> list[dict]:
        """RF-84: cálculos del valor razonable menos costos de venta registrados en el período."""

    @abstractmethod
    def productos_agricolas(self, filtros: dict) -> list[dict]:
        """RF-85 RNF-85-05: productos agrícolas reconocidos, filtrables por período, activo, tipo de producto,
        especie, producto y rango de valores, con su evento productivo y el usuario que lo registró."""
