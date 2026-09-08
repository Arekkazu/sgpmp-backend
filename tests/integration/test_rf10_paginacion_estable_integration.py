"""Integración RF-10 / INC-M01-17-071: paginación estable ante timestamps iguales.

El listado de auditoría ordenaba solo por ``fecha_evento``; cuando dos o más
eventos compartían el mismo instante, el orden era no determinista y una misma
fila podía repetirse entre páginas (o perderse). El desempate por ``id_evento``
hace el orden total y estable.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

pytestmark = pytest.mark.integration

MISMO_INSTANTE = datetime(2026, 8, 15, 12, 0, 0, tzinfo=timezone.utc)
TOTAL_EVENTOS = 6
TAMANO_PAGINA = 4
TIPO_LOGIN_EXITOSO = 3


def test_paginacion_no_repite_eventos_con_el_mismo_timestamp(
    client,
    crear_usuario_db,
    crear_auth_headers,
    crear_evento_db,
) -> None:
    admin = crear_usuario_db(id_rol=1)
    ids = [
        crear_evento_db(
            id_usuario=admin["id_usuario"],
            tipo_evento=TIPO_LOGIN_EXITOSO,
            categoria="AUTENTICACION",
            fecha=MISMO_INSTANTE,
        )
        for _ in range(TOTAL_EVENTOS)
    ]

    # Se filtra por tipo_evento para aislar los eventos de la prueba: la propia
    # consulta de auditoría registra un evento (tipo 16) del mismo id_usuario,
    # que de otro modo aparecería en la segunda página y desvirtuaría el conteo.
    headers = crear_auth_headers(admin)
    params = {
        "id_usuario": admin["id_usuario"],
        "tipo_evento": TIPO_LOGIN_EXITOSO,
        "tamano": TAMANO_PAGINA,
    }
    pagina_uno = client.get(
        "/auditoria/", params={**params, "pagina": 1}, headers=headers
    ).json()
    pagina_dos = client.get(
        "/auditoria/", params={**params, "pagina": 2}, headers=headers
    ).json()

    ids_uno = {item["id_evento"] for item in pagina_uno["items"]}
    ids_dos = {item["id_evento"] for item in pagina_dos["items"]}

    assert pagina_uno["total"] == TOTAL_EVENTOS
    assert len(ids_uno) == TAMANO_PAGINA
    assert len(ids_dos) == TOTAL_EVENTOS - TAMANO_PAGINA
    # Sin desempate, un evento con el mismo timestamp podía caer en ambas páginas.
    assert ids_uno & ids_dos == set()
    assert (ids_uno | ids_dos) == set(ids)
