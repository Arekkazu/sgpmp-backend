# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-28 | destroyerban | INC-M03-168-G76 RF-57: consulta y actualización de los parámetros de alertas por el administrador |
# | 2026-10-28 | destroyerban | INC-M03-176-G57A RF-57: ventana de deduplicación y SLA en los parámetros de alertas |
# | 2026-10-29 | Arekkazu | INC-M03-82-G192 RF-62: catálogo por subclase para reutilizarlo en la política de visión |
"""Parámetros de RF-57 que el administrador configura (E12/E13, CA-2, E16, E8).

Viven en el almacén de DEV-14 (``modulo4.parametros_mlops``). La escritura reutiliza
``ConfigurarParametrosMLOpsUseCase``: mismo lock, misma validación y el autor queda en
``id_usuario_modificador``. Antes solo se cargaban con el script offline de DEV-14.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Optional

from src.configuration.application.use_cases.configuracion_global.configurar_parametros_mlops_use_case import (
    _LIMITES,
    ConfigurarParametrosMLOpsUseCase,
)
from src.configuration.domain.entities.parametro_mlops import (
    RF57_CONFIANZA,
    RF57_CONFIANZA_BASE,
    RF57_CONFIANZA_MINIMA,
    RF57_CONFIANZA_MINIMA_BASE,
    RF57_SLA_BASE,
    RF57_SLA_CRITICO,
    RF57_SLA_LEVE,
    RF57_SLA_MODERADO,
    RF57_VENTANA_DEDUPLICACION,
    RF57_VENTANA_DEDUPLICACION_BASE,
    RF57_TORMENTA_SISTEMA,
    RF57_TORMENTA_UNIDAD,
    RF57_VENTANA_REEVALUACION,
    RF57_VENTANA_REEVALUACION_BASE,
)
from src.shared.errors import ValidationError

#: nombre → (valor base publicado por el RF o None, descripción).
PARAMETROS_ALERTAS: dict[str, tuple[Any, str]] = {
    RF57_CONFIANZA: (RF57_CONFIANZA_BASE, "E12/E13: confianza de la IA para resolver conflictos de tipo y severidad"),
    RF57_CONFIANZA_MINIMA: (RF57_CONFIANZA_MINIMA_BASE, "CA-2: probabilidad mínima para generar PREDICCION_PATOLOGIA"),
    RF57_VENTANA_REEVALUACION: (RF57_VENTANA_REEVALUACION_BASE, "E16: minutos para reevaluar una alerta generada sin IA"),
    RF57_TORMENTA_SISTEMA: (None, "E8: alertas por minuto del sistema que activan la tormenta (sin valor: no agrupa)"),
    RF57_TORMENTA_UNIDAD: (None, "E8: alertas por minuto por unidad productiva que activan la tormenta"),
    RF57_VENTANA_DEDUPLICACION: (RF57_VENTANA_DEDUPLICACION_BASE,
                                 "E4: minutos en los que un evento de la misma condición se consolida"),
    RF57_SLA_CRITICO: (RF57_SLA_BASE[RF57_SLA_CRITICO], "SLA de atención de una alerta CRITICO (minutos)"),
    RF57_SLA_MODERADO: (RF57_SLA_BASE[RF57_SLA_MODERADO], "SLA de atención de una alerta MODERADO (minutos)"),
    RF57_SLA_LEVE: (RF57_SLA_BASE[RF57_SLA_LEVE], "SLA de atención de una alerta LEVE (minutos)"),
}


@dataclass
class ParametroAlerta:
    nombre: str
    descripcion: str
    valor: Optional[Any]             # valor efectivo que usa RF-57
    valor_configurado: Optional[Any]
    valor_base: Optional[Any]
    fuente: str                      # CONFIGURADO | VALOR_BASE | SIN_CONFIGURAR
    rango_minimo: Optional[Decimal]
    rango_maximo: Optional[Decimal]


class ParametrosAlertasUseCase:
    catalogo = PARAMETROS_ALERTAS
    codigo_invalido, rf = "PARAMETRO_ALERTAS_INVALIDO", "RF-57"

    def __init__(self, db, parametros_repo) -> None:
        self.db = db
        self.parametros_repo = parametros_repo

    def consultar(self) -> list[ParametroAlerta]:
        configurados = self.parametros_repo.obtener(list(self.catalogo))
        resultado = []
        for nombre, (base, descripcion) in self.catalogo.items():
            actual = configurados.get(nombre)
            minimo, maximo = (actual.minimo, actual.maximo) if actual else _LIMITES[nombre]
            valor = actual.valor if actual else base
            fuente = "CONFIGURADO" if actual else "VALOR_BASE" if base is not None else "SIN_CONFIGURAR"
            resultado.append(ParametroAlerta(nombre, descripcion, valor, actual.valor if actual else None, base,
                                             fuente, minimo, maximo))
        return resultado

    def actualizar(self, cambios: dict[str, Any], id_usuario: int) -> list[ParametroAlerta]:
        ajenos = sorted(set(cambios) - set(self.catalogo))
        if not cambios or ajenos:
            raise ValidationError(
                self.codigo_invalido,
                f"Solo se admiten los parámetros de {self.rf}: {', '.join(self.catalogo)}."
                + (f" No pertenecen: {', '.join(ajenos)}." if ajenos else ""),
                field="parametros",
            )
        ConfigurarParametrosMLOpsUseCase(self.db, self.parametros_repo).execute(cambios, id_usuario)
        return self.consultar()
