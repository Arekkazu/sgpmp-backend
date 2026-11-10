# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-10 | Arekkazu | INC-M05-339-G08 / 340-G27 / 341-G30 y INC-M06-344-G42: validaciones sin base de datos |
"""Lote QA M05 del 2026-11-10 sin base de datos.

- INC-M05-339-G08 (RF-75): la cantidad admite 3 decimales; 0.0004 kg es 400, no un 500 de la BD.
- INC-M05-340-G27 (RF-78 CA-13): la unidad debe ser la del tipo de suministro.
- INC-M05-341-G30 (RF-78 CA-15): una réplica simultánea que choca con la unicidad responde YA_PROCESADO.
- INC-M06-344-G42 (RF-93): los costos de mantenimiento se desglosan por tipo y suman el total."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal as D
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from src.financial_valuation.domain.services.consolidacion import CostoPeriodo, estado_resultados
from src.shared.errors import BusinessRuleError, ConflictError
from src.shared.fechas import hoy_usuario
from src.supplies.application.use_cases.costeo_suministros import registrar_suministro_directo_use_case as directo
from src.supplies.infrastructure.dto.registrar_consumo_alimento_dto import RegistrarConsumoAlimentoDTO
from src.supplies.infrastructure.dto.registrar_suministro_directo_dto import RegistrarSuministroDirectoDTO


class _Sesion:
    def rollback(self): pass
    def commit(self): pass


def _consumo(cantidad: str) -> RegistrarConsumoAlimentoDTO:
    return RegistrarConsumoAlimentoDTO(id_activo_biologico=1, id_tipo_alimento=1, fecha_consumo=date(2026, 11, 5),
                                       cantidad_alimento=D(cantidad), costo_unitario=D("2000"))


def test_cantidad_de_alimento_con_mas_de_tres_decimales_es_validacion():
    assert _consumo("0.001").cantidad_alimento == D("0.001")
    with pytest.raises(ValidationError, match="3 decimales"):
        _consumo("0.0004")


def test_unidad_distinta_a_la_del_tipo_se_rechaza():
    uc = object.__new__(directo.RegistrarSuministroDirectoUseCase)
    uc.registro_repo = SimpleNamespace(existe_idempotente=lambda _: None)
    uc.ciclo_port = SimpleNamespace(obtener_abierto=lambda _: SimpleNamespace(
        id_gestion_fases=1, id_ciclo_productivo=1, fecha_inicio=None))
    dto = RegistrarSuministroDirectoDTO(
        id_activo_biologico=825, tipo_suministro="SERVICIO_VETERINARIO", id_idempotencia=uuid.uuid4(),
        cantidad=D("7"), unidad_medida="kg", precio_unitario=D("150000"), fecha_aplicacion=hoy_usuario(),
        justificacion_precio="Factura del veterinario sin precio de referencia")
    with pytest.raises(BusinessRuleError) as error:
        uc.execute(dto, SimpleNamespace(id_usuario=1))
    assert (error.value.code, error.value.field) == ("UNIDAD_MEDIDA_NO_COINCIDE", "unidad_medida")
    assert "«servicio»" in error.value.message and "SERVICIO_VETERINARIO" not in error.value.message


def test_replica_simultanea_que_choca_con_la_unicidad_responde_ya_procesado():
    original = SimpleNamespace(id_idempotencia="k")
    uc = object.__new__(directo.RegistrarSuministroDirectoUseCase)
    uc.db = _Sesion()
    uc.registro_repo = SimpleNamespace(
        guardar=lambda e: (_ for _ in ()).throw(ConflictError(code="RECURSO_DUPLICADO", message="duplicado")),
        existe_idempotente=lambda k: original if k == "k" else None)
    resultado = uc._persistir_con_reintentos(SimpleNamespace(id_idempotencia="k"), SimpleNamespace(id_usuario=1))
    assert resultado.ya_procesado and resultado.registro is original
    with pytest.raises(ConflictError):  # otro conflicto (sin registro con esa clave) se propaga
        uc._persistir_con_reintentos(SimpleNamespace(id_idempotencia="otra"), SimpleNamespace(id_usuario=1))


def test_estado_de_resultados_desglosa_el_mantenimiento_por_tipo():
    costos = [CostoPeriodo("MANTENIMIENTO", None, D(v), False, t)
              for t, v in (("ALIMENTO", "101"), ("MEDICAMENTO", "102"), ("MANO_OBRA", "103"), ("VETERINARIO", "104"))]
    er = estado_resultados([], costos + [CostoPeriodo("INVERSION", "CAPITALIZAR", D("999"), False, "INVERSION_DIRECTA")])
    assert er.componentes["costos_mantenimiento"] == D("410")
    assert er.desglose_mantenimiento == {"ALIMENTO": D("101"), "MEDICAMENTO": D("102"), "MANO_OBRA": D("103"),
                                         "VETERINARIO": D("104")}
    assert estado_resultados([], []).desglose_mantenimiento == dict.fromkeys(("ALIMENTO", "MEDICAMENTO", "MANO_OBRA",
                                                                             "VETERINARIO"), D("0"))
