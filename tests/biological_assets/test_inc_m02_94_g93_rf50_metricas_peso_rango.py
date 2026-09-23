"""[INC-M02-94-G93][RF-50][TC-M02-157] El endpoint `datos-consolidados`
respondía HTTP 200 con `historial_eventos: []` y `metricas_actuales` mostrando
una métrica de peso *fuera* del rango solicitado, sin ninguna validación de
suficiencia de datos — el flujo alterno "Datos insuficientes para proceso
crítico (NIC 41)" de RF-50 (HTTP 422) no estaba implementado.

Se implementa la regla contractual literal de RF-50: si se solicita un rango
de fechas explícito y el `tipo_dato` incluye métricas, el activo debe tener
al menos un evento de crecimiento de tipo PESO dentro de ese rango; si no,
`422 METRICAS_PESO_INSUFICIENTES`. Sin rango explícito, el comportamiento no
cambia (se sigue devolviendo la última métrica conocida) — la ambigüedad de
si `metricas_actuales` debería respetar siempre el filtro temporal queda
documentada como pregunta abierta para Análisis en
`anotaciones/modulo_2/inc_m02_94_g93_rf50_metricas_peso_rango.md`, no resuelta
unilateralmente aquí.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from src.biological_assets.application.use_cases.gestion.consultar_datos_consolidados_use_case import (
    ConsultarDatosConsolidadosUseCase,
)
from src.biological_assets.domain.entities.activo_biologico import ActivoBiologico, DatosConsolidados
from src.biological_assets.infrastructure.dto.datos_consolidados_dto import DatosConsolidadosDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError


class ActivoRepoFake:
    def __init__(self, activo: ActivoBiologico) -> None:
        self.activo = activo

    def obtener_por_id(self, _id: int, *, ids_fincas_permitidas=None):
        return self.activo

    def obtener_asociacion_activa(self, _id: int):
        return None


class IndicadoresRepoFake:
    def __init__(self, *, hay_peso_en_rango: bool) -> None:
        self.hay_peso_en_rango = hay_peso_en_rango
        self.llamado_obtener_datos = False
        self.rango_consultado: tuple | None = None

    def existen_metricas_peso_en_rango(self, id_activo, fecha_inicio, fecha_fin) -> bool:
        self.rango_consultado = (fecha_inicio, fecha_fin)
        return self.hay_peso_en_rango

    def obtener_datos_consolidados(self, **kwargs) -> DatosConsolidados:
        self.llamado_obtener_datos = True
        return DatosConsolidados(
            id_activo_biologico=kwargs['id_activo'],
            identificador='QAJE-CREC-OK',
            tipo_activo='INDIVIDUAL',
            especie='bovino',
            estado_actual='ACTIVO',
            infraestructura_asociada='Corral 1',
            fase_productiva_activa=None,
            fecha_generacion=datetime.now(timezone.utc),
        )


def _usuario() -> UsuarioActual:
    return UsuarioActual(id_usuario=7, id_token=1, id_rol=2)


def _activo(id_activo=279) -> ActivoBiologico:
    return ActivoBiologico(
        id_especie=1, tipo='INDIVIDUAL', origen_financiero='compra',
        id_infraestructura=49, id_estado=1, id_usuario=1, id_activo_biologico=id_activo,
    )


def _uc(indicadores_repo: IndicadoresRepoFake) -> ConsultarDatosConsolidadosUseCase:
    return ConsultarDatosConsolidadosUseCase(
        db=None, activo_repo=ActivoRepoFake(_activo()), indicadores_repo=indicadores_repo, bitacora_repo=None,
    )


def test_sin_peso_en_rango_y_metricas_solicitadas_responde_422():
    repo = IndicadoresRepoFake(hay_peso_en_rango=False)
    dto = DatosConsolidadosDTO(tipo_dato='metricas', fecha_inicio=date(2026, 6, 1), fecha_fin=date(2026, 8, 31))

    with pytest.raises(BusinessRuleError) as exc:
        _uc(repo).execute(279, dto, _usuario())

    assert exc.value.code == 'METRICAS_PESO_INSUFICIENTES'
    assert '279' in exc.value.message
    assert repo.llamado_obtener_datos is False


def test_sin_peso_en_rango_pero_tipo_dato_eventos_no_valida_suficiencia():
    """La regla de suficiencia es específica de métricas/NIC-41; pedir solo
    'eventos' no depende de que haya mediciones de peso en el rango."""
    repo = IndicadoresRepoFake(hay_peso_en_rango=False)
    dto = DatosConsolidadosDTO(tipo_dato='eventos', fecha_inicio=date(2026, 6, 1), fecha_fin=date(2026, 8, 31))

    resultado = _uc(repo).execute(279, dto, _usuario())

    assert resultado.id_activo_biologico == 279


def test_sin_rango_de_fechas_no_valida_suficiencia():
    """Sin fecha_inicio/fecha_fin explícitos, se mantiene el comportamiento
    actual (última métrica conocida, sin importar su antigüedad)."""
    repo = IndicadoresRepoFake(hay_peso_en_rango=False)
    dto = DatosConsolidadosDTO(tipo_dato='metricas')

    resultado = _uc(repo).execute(279, dto, _usuario())

    assert resultado.id_activo_biologico == 279
    assert repo.rango_consultado is None


def test_con_peso_en_rango_se_acepta():
    repo = IndicadoresRepoFake(hay_peso_en_rango=True)
    dto = DatosConsolidadosDTO(tipo_dato='todos', fecha_inicio=date(2026, 6, 1), fecha_fin=date(2026, 8, 31))

    resultado = _uc(repo).execute(279, dto, _usuario())

    assert resultado.id_activo_biologico == 279
    assert repo.llamado_obtener_datos is True
