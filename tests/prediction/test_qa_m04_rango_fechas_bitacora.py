# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-03 | Arekkazu | QA-M04 RF-73: rango de fechas invertido en la bitácora responde 400 RANGO_FECHAS_INVALIDO |
"""QA-M04 RF-73: "hasta" anterior a "desde" filtraba y devolvía vacío sin avisar."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.prediction.application.use_cases.auditoria.consultar_auditoria_m04_use_case import (
    ConsultarAuditoriaM04UseCase,
)
from src.prediction.application.use_cases.auditoria.exportar_auditoria_m04_use_case import (
    ExportarAuditoriaM04UseCase,
)
from src.shared.errors import ValidationError

_DESDE = datetime(2026, 11, 3, tzinfo=timezone.utc)
_HASTA = datetime(2026, 11, 2, tzinfo=timezone.utc)
_FILTROS = dict(tipo_evento=None, id_usuario=None, id_sistema=None, id_referencia=None, severidad_evento=None)


class _Repo:
    def consultar(self, **kw):
        return [], 0


def test_listar_con_rango_invertido_es_400() -> None:
    with pytest.raises(ValidationError) as error:
        ConsultarAuditoriaM04UseCase(_Repo()).listar(
            fecha_desde=_DESDE, fecha_hasta=_HASTA, pagina=1, por_pagina=50, **_FILTROS
        )
    assert error.value.code == "RANGO_FECHAS_INVALIDO"


def test_exportar_con_rango_invertido_es_400() -> None:
    with pytest.raises(ValidationError) as error:
        ExportarAuditoriaM04UseCase(db=None, repo=_Repo()).exportar(
            fecha_desde=_DESDE, fecha_hasta=_HASTA, formato="json", id_usuario_exportador=1, **_FILTROS
        )
    assert error.value.code == "RANGO_FECHAS_INVALIDO"


def test_mismo_dia_se_acepta() -> None:
    items, total = ConsultarAuditoriaM04UseCase(_Repo()).listar(
        fecha_desde=_HASTA, fecha_hasta=_HASTA, pagina=1, por_pagina=50, **_FILTROS
    )
    assert (items, total) == ([], 0)
