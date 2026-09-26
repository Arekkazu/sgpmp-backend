"""INC-M02-43-G52 / #413: GET /activos-biologicos/{id}/eventos exponia el
historial sanitario completo (diagnostico, medicamento, dosis) a cualquier
rol con el permiso generico de RF39, sin distinguir autorizacion clinica.
`_redactar_datos_clinicos` es la funcion pura que aplica el recorte cuando
el rol no tiene el permiso dedicado sobre `_RECURSO_DATOS_CLINICOS`.
"""
from __future__ import annotations

from src.biological_assets.infrastructure.routers.activo_biologico_router import (
    _redactar_datos_clinicos,
)
from src.biological_assets.infrastructure.schema.activo_biologico_schema import (
    EventoActivoResponse,
    EventoSanitarioResponse,
)
from datetime import datetime, timezone


def _evento_sanitario() -> EventoActivoResponse:
    return EventoActivoResponse(
        id_eventos=1,
        id_activo_biologico=10,
        fecha=datetime(2026, 1, 1, tzinfo=timezone.utc),
        descripcion=None,
        id_usuario=1,
        sanitario=EventoSanitarioResponse(
            tipo='DIAGNOSTICO',
            diagnostico='Mastitis clínica',
            medicamento='Penicilina',
            dosis=5,
            unidad_dosis='ml',
            frecuencia=2,
            duracion=7,
            observaciones='Aislar del resto del lote',
        ),
    )


def _evento_no_sanitario() -> EventoActivoResponse:
    return EventoActivoResponse(
        id_eventos=2,
        id_activo_biologico=10,
        fecha=datetime(2026, 1, 1, tzinfo=timezone.utc),
        descripcion=None,
        id_usuario=1,
    )


def test_redacta_campos_clinicos_de_evento_sanitario() -> None:
    respuestas = _redactar_datos_clinicos([_evento_sanitario()])

    sanitario = respuestas[0].sanitario
    assert sanitario is not None
    assert sanitario.diagnostico is None
    assert sanitario.medicamento is None
    assert sanitario.dosis is None
    assert sanitario.unidad_dosis is None
    assert sanitario.frecuencia is None
    assert sanitario.duracion is None
    assert sanitario.observaciones is None
    # `tipo` es la categoria del evento (RF-46), no el detalle clinico -- se conserva.
    assert sanitario.tipo == 'DIAGNOSTICO'


def test_no_toca_eventos_sin_sub_objeto_sanitario() -> None:
    original = _evento_no_sanitario()
    respuestas = _redactar_datos_clinicos([original])

    assert respuestas[0].sanitario is None
