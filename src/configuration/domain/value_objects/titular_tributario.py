# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | RF-19 v1.1 (RFC-018 D-18.6): titular tributario de la finca |
"""Value object ``TitularTributario``: quién lleva la contabilidad de la finca (RF-19 v1.1).

``tipo_id_tributaria`` ∈ {NIT, CC, CE}; número de 6 a 15 dígitos sin dígito de verificación; ``dv``
obligatorio para NIT y verificado con el algoritmo módulo 11 de la DIAN; razón social de 1 a 120."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.shared.errors import ValidationError

_PESOS_DIAN = (3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71)


def digito_verificacion(numero: str) -> int:
    """DV del NIT: suma ponderada (de derecha a izquierda) módulo 11 (DIAN)."""
    suma = sum(int(d) * p for d, p in zip(reversed(numero), _PESOS_DIAN))
    residuo = suma % 11
    return residuo if residuo < 2 else 11 - residuo


@dataclass(frozen=True)
class TitularTributario:
    tipo_id_tributaria: str
    numero_id_tributaria: str
    razon_social: str
    dv: Optional[str] = None

    def __post_init__(self) -> None:
        if self.tipo_id_tributaria not in ("NIT", "CC", "CE"):
            raise ValidationError(code="TIPO_ID_TRIBUTARIA_INVALIDO", field="tipo_id_tributaria",
                                  message="El tipo de identificación debe ser NIT, CC o CE.")
        if not (self.numero_id_tributaria.isdigit() and 6 <= len(self.numero_id_tributaria) <= 15):
            raise ValidationError(code="NUMERO_ID_TRIBUTARIA_INVALIDO", field="numero_id_tributaria",
                                  message="El número debe tener solo dígitos (6 a 15), sin dígito de verificación.")
        if not (1 <= len(self.razon_social.strip()) <= 120):
            raise ValidationError(code="RAZON_SOCIAL_INVALIDA", field="razon_social",
                                  message="La razón social es obligatoria (máximo 120 caracteres).")
        if self.tipo_id_tributaria == "NIT":
            if self.dv is None or not self.dv.isdigit() or int(self.dv) != digito_verificacion(self.numero_id_tributaria):
                raise ValidationError(code="DV_INVALIDO", field="dv",
                                      message="El dígito de verificación no corresponde al NIT.")
