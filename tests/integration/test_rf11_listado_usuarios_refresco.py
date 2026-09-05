"""Pruebas de integración para los gaps de RF-11 cerrados junto al fix de RBAC:
orden descendente por fecha de registro, filtro por estado_cuenta (nombre),
mecanismo de refresco incremental (actualizado_desde) y mensaje informativo
en resultado vacío.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

pytestmark = pytest.mark.integration


def test_listado_admin_ordena_por_fecha_registro_descendente(
    client,
    crear_usuario_db,
    crear_auth_headers,
) -> None:
    """RF-11 pide orden descendente por fecha de registro (más reciente primero)."""
    admin = crear_usuario_db(id_rol=1, estado=2)
    prefijo = f"orden-{uuid.uuid4().hex[:8]}"
    base = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)

    mas_antiguo = crear_usuario_db(
        correo=f"{prefijo}-a@example.com", fecha_registro=base
    )
    intermedio = crear_usuario_db(
        correo=f"{prefijo}-b@example.com", fecha_registro=base + timedelta(minutes=1)
    )
    mas_reciente = crear_usuario_db(
        correo=f"{prefijo}-c@example.com", fecha_registro=base + timedelta(minutes=2)
    )

    respuesta = client.get(
        f"/usuarios/admin?correo={prefijo}&tamano=50",
        headers=crear_auth_headers(admin),
    )

    assert respuesta.status_code == 200
    correos = [item["correo_electronico"] for item in respuesta.json()["items"]]
    assert correos == [
        mas_reciente["correo"],
        intermedio["correo"],
        mas_antiguo["correo"],
    ]


def test_listado_admin_filtra_por_estado_cuenta_case_insensitive(
    client,
    crear_usuario_db,
    crear_auth_headers,
) -> None:
    """Filtro por nombre de estado (enum de catálogo), no por id numérico."""
    admin = crear_usuario_db(id_rol=1, estado=2)
    prefijo = f"estado-{uuid.uuid4().hex[:8]}"
    activo = crear_usuario_db(correo=f"{prefijo}-activo@example.com", estado=2)
    crear_usuario_db(correo=f"{prefijo}-inactivo@example.com", estado=3)

    respuesta = client.get(
        f"/usuarios/admin?correo={prefijo}&estado_cuenta=activo",
        headers=crear_auth_headers(admin),
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["total"] == 1
    assert cuerpo["items"][0]["correo_electronico"] == activo["correo"]


def test_listado_admin_actualizado_desde_detecta_cambios_incrementales(
    client,
    crear_usuario_db,
    crear_auth_headers,
) -> None:
    """El filtro actualizado_desde soporta el polling incremental del refresco.

    Nota: dentro de una misma transacción de prueba, `now()` de PostgreSQL
    (usado por los triggers que mantienen `fecha_actualizacion`/
    `fecha_cambio_estado`) devuelve el mismo valor para todas las sentencias
    — es `transaction_timestamp()`, no `clock_timestamp()` — por lo que no se
    puede provocar un cambio de timestamp real dentro del test. Se verifica
    en cambio la lógica de comparación del filtro contra instantes antes/
    después del `ultima_modificacion` real que devuelve la API.
    """
    admin = crear_usuario_db(id_rol=1, estado=2)
    headers = crear_auth_headers(admin)
    prefijo = f"refresco-{uuid.uuid4().hex[:8]}"
    crear_usuario_db(correo=f"{prefijo}@example.com", estado=2)

    respuesta = client.get(f"/usuarios/admin?correo={prefijo}", headers=headers)
    assert respuesta.status_code == 200
    ultima_modificacion = respuesta.json()["items"][0]["ultima_modificacion"]
    assert ultima_modificacion is not None
    instante = datetime.fromisoformat(ultima_modificacion.replace("Z", "+00:00"))

    respuesta_desde_antes = client.get(
        "/usuarios/admin",
        params={"correo": prefijo, "actualizado_desde": (instante - timedelta(seconds=1)).isoformat()},
        headers=headers,
    )
    assert respuesta_desde_antes.status_code == 200
    assert respuesta_desde_antes.json()["total"] == 1

    respuesta_desde_despues = client.get(
        "/usuarios/admin",
        params={"correo": prefijo, "actualizado_desde": (instante + timedelta(seconds=1)).isoformat()},
        headers=headers,
    )
    assert respuesta_desde_despues.status_code == 200
    cuerpo_vacio = respuesta_desde_despues.json()
    assert cuerpo_vacio["total"] == 0
    assert cuerpo_vacio["items"] == []
    assert cuerpo_vacio["mensaje"] is not None


def test_listado_admin_mensaje_informativo_en_resultado_vacio(
    client,
    crear_usuario_db,
    crear_auth_headers,
) -> None:
    """Un filtro sin coincidencias debe traer un mensaje, no solo items vacíos."""
    admin = crear_usuario_db(id_rol=1, estado=2)

    respuesta = client.get(
        f"/usuarios/admin?nombre=nadie-existe-{uuid.uuid4().hex}",
        headers=crear_auth_headers(admin),
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["total"] == 0
    assert cuerpo["items"] == []
    assert cuerpo["mensaje"]


def test_listado_admin_incluye_id_usuario_por_fila(
    client,
    crear_usuario_db,
    crear_auth_headers,
) -> None:
    """INC-M01-11-87/89: sin id_usuario el frontend no puede construir el link
    de detalle y termina llamando GET /usuarios/undefined/detalle."""
    admin = crear_usuario_db(id_rol=1, estado=2)
    objetivo = crear_usuario_db(correo=f"con-id-{uuid.uuid4().hex[:8]}@example.com")

    respuesta = client.get(
        f"/usuarios/admin?correo={objetivo['correo']}",
        headers=crear_auth_headers(admin),
    )

    assert respuesta.status_code == 200
    items = respuesta.json()["items"]
    assert len(items) == 1
    assert items[0]["id_usuario"] == objetivo["id_usuario"]
