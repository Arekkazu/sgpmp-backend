"""TC-M03-G60 — RF-56 / CU-02.

Subcasos: TC-M03-119 (idempotencia), TC-M03-120 (duplicado distinto / parcial).

Tres capas distintas:
- identity autonumérica del repositorio en memoria (no es clave de negocio);
- validación temporal de recepción (TIMESTAMP_FUTURO);
- idempotencia / duplicado con contenido distinto: sin contrato en src/.

El Δt≤5 s de consolidación (FA-03) está en G55, no sustituye detección de duplicados.
"""
from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

import pytest

from src.shared.errors import ValidationError
from src.telemetry.domain.entities.telemetria import TipoEventoEdge

_MODULO3 = Path(__file__).resolve().parents[2]
if str(_MODULO3) not in sys.path:
    sys.path.insert(0, str(_MODULO3))
from rf56_dobles import ahora_utc, dto_evento_edge, recibir_use_case  # noqa: E402


def test_tc_m03_119_repositorio_asigna_identity_autonumerica() -> None:
    """Dos execute() crean dos filas locales. No demuestra idempotencia ni su ausencia en M04."""
    use_case, eventos, paquetes, motor, _ = recibir_use_case()
    use_case.execute(
        dto_evento_edge(
            clasificacion_rf55=TipoEventoEdge.DESVIACION_SIMPLE,
            severidad="LEVE",
        )
    )
    use_case.execute(
        dto_evento_edge(
            clasificacion_rf55=TipoEventoEdge.DESVIACION_SIMPLE,
            severidad="LEVE",
        )
    )
    assert len(eventos.guardados) == 2
    assert eventos.guardados[0].id_evento_edge_computing != eventos.guardados[1].id_evento_edge_computing
    assert paquetes.guardados[0].id_paquetes_inferencia != paquetes.guardados[1].id_paquetes_inferencia
    assert len(motor.paquetes) == 2
    assert motor.exito is False


def test_tc_m03_119_idempotencia_en_m04() -> None:
    pytest.skip(
        "BLOQUEADO TC-M03-119: no hay id_paquete de negocio ni cliente M04 que "
        "conserve un único registro ante reenvíos. Dos identities locales no "
        "prueban idempotencia (test_tc_m03_119_repositorio_asigna_identity_autonumerica).",
    )


def test_tc_m03_120_captura_futura_es_validacion_temporal_de_recepcion() -> None:
    """TIMESTAMP_FUTURO rechaza antes de persistir. No es detección de solicitud duplicada."""
    dto = dto_evento_edge(clasificacion_rf55=TipoEventoEdge.NORMAL)
    dto.timestamp_captura = ahora_utc() + timedelta(seconds=31)
    dto.timestamp_procesamiento_edge = dto.timestamp_captura
    use_case, eventos, paquetes, motor, _ = recibir_use_case()
    with pytest.raises(ValidationError) as exc:
        use_case.execute(dto)
    assert exc.value.code == "TIMESTAMP_FUTURO"
    assert eventos.guardados == []
    assert paquetes.guardados == []
    assert motor.paquetes == []


def test_tc_m03_120_duplicado_contenido_distinto_y_reconstruccion() -> None:
    pytest.skip(
        "BLOQUEADO TC-M03-120: no hay detección de id_paquete repetido con "
        "contenido distinto ni reconstrucción parcial. TIMESTAMP_FUTURO es "
        "validación temporal de recepción, no idempotencia. FA-03 Δt>5 s está en G55."
    )
