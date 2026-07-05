from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import model_validator

from src.shared.base_dto import BaseDTO


class RegistrarActivoBiologicoDTO(BaseDTO):
    tipo_activo: str
    id_especie: int
    fecha_inicio_ciclo: date
    detalles_procedencia: Optional[str] = None
    origen_financiero: str
    costo_adquisicion: Optional[Decimal] = None
    soporte_documental: Optional[str] = None
    id_infraestructura: int
    atributos_dinamicos: Optional[dict] = None
    # Solo para INDIVIDUAL
    identificador: Optional[str] = None
    raza: Optional[str] = None
    sexo: Optional[str] = None
    fecha_nacimiento: Optional[datetime] = None
    peso_inicial: Optional[Decimal] = None
    # Solo para POBLACIONAL
    cantidad_inicial: Optional[int] = None
    peso_promedio_inicial: Optional[Decimal] = None

    @model_validator(mode='after')
    def validar_segun_tipo(self) -> RegistrarActivoBiologicoDTO:
        tipo = self.tipo_activo
        if tipo not in ('INDIVIDUAL', 'POBLACIONAL'):
            raise ValueError("tipo_activo debe ser 'INDIVIDUAL' o 'POBLACIONAL'.")

        if tipo == 'INDIVIDUAL':
            # FA-02: identificador, raza, sexo, fecha_nacimiento requeridos para INDIVIDUAL
            if not self.identificador:
                raise ValueError("identificador es requerido para activos de tipo INDIVIDUAL.")
            if not self.raza:
                raise ValueError("raza es requerida para activos de tipo INDIVIDUAL.")
            if not self.sexo:
                raise ValueError("sexo es requerido para activos de tipo INDIVIDUAL.")
            if self.fecha_nacimiento is None:
                raise ValueError("fecha_nacimiento es requerida para activos de tipo INDIVIDUAL.")
            if self.cantidad_inicial is not None:
                raise ValueError("cantidad_inicial no aplica para activos de tipo INDIVIDUAL.")

        elif tipo == 'POBLACIONAL':
            # FA-02: cantidad_inicial requerida para POBLACIONAL
            if self.cantidad_inicial is None:
                raise ValueError("cantidad_inicial es requerida para activos de tipo POBLACIONAL.")
            if self.cantidad_inicial <= 0:
                raise ValueError("cantidad_inicial debe ser mayor a 0.")
            if self.identificador is not None:
                raise ValueError("identificador no aplica para activos de tipo POBLACIONAL.")
            if self.raza is not None or self.sexo is not None or self.fecha_nacimiento is not None:
                raise ValueError("raza, sexo y fecha_nacimiento no aplican para activos de tipo POBLACIONAL.")

        return self

    @model_validator(mode='after')
    def validar_fecha_inicio_ciclo(self) -> RegistrarActivoBiologicoDTO:
        # FA-04
        hoy = date.today()
        limite_inferior = date(1970, 1, 1)
        if self.fecha_inicio_ciclo > hoy:
            raise ValueError("fecha_inicio_ciclo no puede ser futura.")
        if self.fecha_inicio_ciclo < limite_inferior:
            raise ValueError("fecha_inicio_ciclo no puede ser anterior a 1970-01-01.")
        return self

    @model_validator(mode='after')
    def validar_origen_financiero(self) -> RegistrarActivoBiologicoDTO:
        # FA-08
        origen = self.origen_financiero
        if origen not in ('compra', 'nacimiento', 'donacion', 'transferencia_interna'):
            raise ValueError(
                "origen_financiero debe ser 'compra', 'nacimiento', 'donacion' o 'transferencia_interna'."
            )

        if origen in ('compra', 'donacion'):
            if not self.costo_adquisicion or self.costo_adquisicion <= 0:
                raise ValueError(
                    f"costo_adquisicion mayor a 0 es requerido cuando origen_financiero es '{origen}'."
                )
            if not self.soporte_documental:
                raise ValueError(
                    f"soporte_documental es requerido cuando origen_financiero es '{origen}'."
                )

        elif origen == 'nacimiento':
            if self.costo_adquisicion is not None:
                raise ValueError("costo_adquisicion no aplica cuando origen_financiero es 'nacimiento'.")
            if self.soporte_documental is not None:
                raise ValueError("soporte_documental no aplica cuando origen_financiero es 'nacimiento'.")

        return self
