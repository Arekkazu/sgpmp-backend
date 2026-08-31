"""Integración de la exportación CSV del historial de auditoría (RF-10).

Lo que estas pruebas defienden es el motivo por el que el endpoint existe: antes,
exportar el log completo costaba una petición por página y cada una dejaba su
propio evento ``CONSULTA_AUDITORIA``, así que una sola descarga podía ensuciar la
auditoría con doscientos registros de haberla leído.
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

TIPO_EXPORTACION_AUDITORIA = 26
TIPO_CONSULTA_AUDITORIA = 16


def _contar_eventos(db_session: Session, id_usuario: int, tipo_evento: int) -> int:
    return db_session.execute(
        text(
            """
            SELECT count(*) FROM modulo1.eventos
            WHERE tipo_evento = :tipo AND id_usuario = :usuario
            """
        ),
        {"tipo": tipo_evento, "usuario": id_usuario},
    ).scalar_one()


def test_exportar_deja_un_unico_evento_en_vez_de_uno_por_pagina(
    client: TestClient,
    db_session: Session,
    crear_usuario_db: Callable[..., dict[str, Any]],
    crear_auth_headers: Callable[[dict[str, Any]], dict[str, str]],
    crear_evento_db: Callable[..., int],
) -> None:
    admin = crear_usuario_db(id_rol=1)
    headers = crear_auth_headers(admin)
    for _ in range(5):
        crear_evento_db(
            id_usuario=admin["id_usuario"],
            tipo_evento=3,
            categoria="AUTENTICACION",
        )

    respuesta = client.get("/auditoria/exportar", headers=headers)

    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"].startswith("text/csv")
    assert "attachment" in respuesta.headers["content-disposition"]
    # El corazón del RF: una descarga, un evento. No uno por página.
    assert _contar_eventos(db_session, admin["id_usuario"], TIPO_EXPORTACION_AUDITORIA) == 1
    assert _contar_eventos(db_session, admin["id_usuario"], TIPO_CONSULTA_AUDITORIA) == 0


def test_el_csv_abre_en_excel_y_trae_las_etiquetas_del_catalogo(
    client: TestClient,
    crear_usuario_db: Callable[..., dict[str, Any]],
    crear_auth_headers: Callable[[dict[str, Any]], dict[str, str]],
    crear_evento_db: Callable[..., int],
) -> None:
    admin = crear_usuario_db(id_rol=1)
    headers = crear_auth_headers(admin)
    crear_evento_db(
        id_usuario=admin["id_usuario"],
        tipo_evento=3,
        categoria="AUTENTICACION",
    )

    cuerpo = client.get("/auditoria/exportar", headers=headers).text

    # Sin el BOM, Excel abre "Módulo" y "Descripción" con los acentos rotos.
    assert cuerpo.startswith("﻿")
    assert "Módulo" in cuerpo and "Integridad" in cuerpo
    # La etiqueta sale de modulo1.tipos_eventos, no de una copia en el cliente.
    assert "LOGIN_EXITOSO" in cuerpo


def test_las_cabeceras_de_conteo_permiten_avisar_de_una_exportacion_truncada(
    client: TestClient,
    crear_usuario_db: Callable[..., dict[str, Any]],
    crear_auth_headers: Callable[[dict[str, Any]], dict[str, str]],
    crear_evento_db: Callable[..., int],
) -> None:
    admin = crear_usuario_db(id_rol=1)
    headers = crear_auth_headers(admin)
    for _ in range(3):
        crear_evento_db(
            id_usuario=admin["id_usuario"],
            tipo_evento=3,
            categoria="AUTENTICACION",
        )

    respuesta = client.get(
        "/auditoria/exportar",
        params={"id_usuario": admin["id_usuario"], "tipo_evento": 3},
        headers=headers,
    )

    assert int(respuesta.headers["X-Total-Registros"]) == 3
    assert int(respuesta.headers["X-Registros-Exportados"]) == 3


def test_respeta_los_filtros_recibidos(
    client: TestClient,
    crear_usuario_db: Callable[..., dict[str, Any]],
    crear_auth_headers: Callable[[dict[str, Any]], dict[str, str]],
    crear_evento_db: Callable[..., int],
) -> None:
    admin = crear_usuario_db(id_rol=1)
    headers = crear_auth_headers(admin)
    antiguo = datetime.now(timezone.utc) - timedelta(days=30)
    crear_evento_db(
        id_usuario=admin["id_usuario"],
        tipo_evento=3,
        categoria="AUTENTICACION",
        fecha=antiguo,
    )
    crear_evento_db(
        id_usuario=admin["id_usuario"],
        tipo_evento=3,
        categoria="AUTENTICACION",
    )

    corte = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    respuesta = client.get(
        "/auditoria/exportar",
        params={"id_usuario": admin["id_usuario"], "tipo_evento": 3, "fecha_desde": corte},
        headers=headers,
    )

    assert int(respuesta.headers["X-Registros-Exportados"]) == 1


def test_un_rango_de_fechas_invertido_se_rechaza_antes_de_generar_nada(
    client: TestClient,
    crear_usuario_db: Callable[..., dict[str, Any]],
    crear_auth_headers: Callable[[dict[str, Any]], dict[str, str]],
) -> None:
    admin = crear_usuario_db(id_rol=1)
    headers = crear_auth_headers(admin)

    respuesta = client.get(
        "/auditoria/exportar",
        params={"fecha_desde": "2026-06-01T00:00:00Z", "fecha_hasta": "2026-01-01T00:00:00Z"},
        headers=headers,
    )

    assert respuesta.status_code == 400
    assert respuesta.json()["error_code"] == "FILTROS_INCONSISTENTES"


def test_sin_permiso_de_auditoria_no_se_puede_exportar(
    client: TestClient,
    crear_usuario_db: Callable[..., dict[str, Any]],
    crear_auth_headers: Callable[[dict[str, Any]], dict[str, str]],
) -> None:
    productor = crear_usuario_db(id_rol=2)
    headers = crear_auth_headers(productor)

    respuesta = client.get("/auditoria/exportar", headers=headers)

    assert respuesta.status_code == 403
    assert respuesta.json()["error_code"] == "ACCESO_DENEGADO"


def test_el_catalogo_de_tipos_evita_que_el_cliente_mantenga_su_propia_copia(
    client: TestClient,
    db_session: Session,
    crear_usuario_db: Callable[..., dict[str, Any]],
    crear_auth_headers: Callable[[dict[str, Any]], dict[str, str]],
) -> None:
    admin = crear_usuario_db(id_rol=1)
    headers = crear_auth_headers(admin)

    respuesta = client.get("/auditoria/catalogo/tipos-evento", headers=headers)

    assert respuesta.status_code == 200
    catalogo = respuesta.json()
    en_db = dict(
        db_session.execute(
            text("SELECT id_tipo_evento, nombre FROM modulo1.tipos_eventos")
        ).all()
    )
    assert {t["id_tipo_evento"]: t["nombre"] for t in catalogo} == en_db
    # La categoría permite colorear por 3 valores en vez de un mapa de 25 ids.
    assert {t["categoria"] for t in catalogo} <= {
        "AUTENTICACION",
        "MODIFICACION",
        "CONSULTA",
        None,
    }


def test_consultar_el_catalogo_no_ensucia_la_auditoria(
    client: TestClient,
    db_session: Session,
    crear_usuario_db: Callable[..., dict[str, Any]],
    crear_auth_headers: Callable[[dict[str, Any]], dict[str, str]],
) -> None:
    """Se pinta en cada carga del filtro: no puede dejar un evento cada vez."""
    admin = crear_usuario_db(id_rol=1)
    headers = crear_auth_headers(admin)

    client.get("/auditoria/catalogo/tipos-evento", headers=headers)

    assert _contar_eventos(db_session, admin["id_usuario"], TIPO_CONSULTA_AUDITORIA) == 0


# ── Cola asíncrona ───────────────────────────────────────────────────────────

def _fijar_umbral(db_session: Session, valor: int) -> None:
    db_session.execute(
        text(
            "UPDATE modulo1.configuracion_batch_exportacion_auditoria "
            "SET umbral_exportacion_async = :v"
        ),
        {"v": valor},
    )


def test_por_encima_del_umbral_el_export_sincrono_redirige_a_la_cola(
    client: TestClient,
    db_session: Session,
    crear_usuario_db: Callable[..., dict[str, Any]],
    crear_auth_headers: Callable[[dict[str, Any]], dict[str, str]],
    crear_evento_db: Callable[..., int],
) -> None:
    admin = crear_usuario_db(id_rol=1)
    headers = crear_auth_headers(admin)
    for _ in range(3):
        crear_evento_db(
            id_usuario=admin["id_usuario"], tipo_evento=3, categoria="AUTENTICACION"
        )
    _fijar_umbral(db_session, 1)

    respuesta = client.get(
        "/auditoria/exportar",
        params={"id_usuario": admin["id_usuario"], "tipo_evento": 3},
        headers=headers,
    )

    assert respuesta.status_code == 422
    assert respuesta.json()["error_code"] == "EXPORTACION_REQUIERE_MODO_ASINCRONO"


def test_el_ciclo_encolar_procesar_descargar(
    client: TestClient,
    db_session: Session,
    crear_usuario_db: Callable[..., dict[str, Any]],
    crear_auth_headers: Callable[[dict[str, Any]], dict[str, str]],
    crear_evento_db: Callable[..., int],
) -> None:
    from src.identity_access.application.use_cases.auditoria.exportacion_async_use_cases import (
        ProcesarColaExportacionesUseCase,
    )
    from src.identity_access.application.use_cases.auditoria.exportar_auditoria_use_case import (
        ExportarAuditoriaUseCase,
    )
    from src.identity_access.infrastructure.repositories.evento_repository import (
        SqlAlchemyEventoRepository,
    )
    from src.identity_access.infrastructure.repositories.exportacion_auditoria_repository import (
        SqlAlchemyExportacionAuditoriaRepository,
    )

    admin = crear_usuario_db(id_rol=1)
    headers = crear_auth_headers(admin)
    crear_evento_db(
        id_usuario=admin["id_usuario"], tipo_evento=3, categoria="AUTENTICACION"
    )

    encolada = client.post(
        "/auditoria/exportaciones",
        params={"id_usuario": admin["id_usuario"], "tipo_evento": 3},
        headers=headers,
    )
    assert encolada.status_code == 202
    id_cola = encolada.json()["id_cola"]

    # Mientras no se procese, el archivo no existe todavía.
    pendiente = client.get(f"/auditoria/exportaciones/{id_cola}/descargar", headers=headers)
    assert pendiente.status_code == 422
    assert pendiente.json()["error_code"] == "EXPORTACION_NO_DISPONIBLE"

    ProcesarColaExportacionesUseCase(
        db=db_session,
        cola_repo=SqlAlchemyExportacionAuditoriaRepository(db_session),
        exportar_use_case=ExportarAuditoriaUseCase(
            eventos_repo=SqlAlchemyEventoRepository(db_session), db=db_session
        ),
    ).ejecutar()

    estado = client.get(f"/auditoria/exportaciones/{id_cola}", headers=headers).json()
    assert estado["estado"] == "COMPLETADO"
    assert estado["descargable"] is True

    descarga = client.get(f"/auditoria/exportaciones/{id_cola}/descargar", headers=headers)
    assert descarga.status_code == 200
    assert descarga.text.startswith("﻿")
    assert "LOGIN_EXITOSO" in descarga.text


def test_una_exportacion_inexistente_es_404(
    client: TestClient,
    crear_usuario_db: Callable[..., dict[str, Any]],
    crear_auth_headers: Callable[[dict[str, Any]], dict[str, str]],
) -> None:
    admin = crear_usuario_db(id_rol=1)
    headers = crear_auth_headers(admin)

    respuesta = client.get("/auditoria/exportaciones/999999", headers=headers)

    assert respuesta.status_code == 404
    assert respuesta.json()["error_code"] == "EXPORTACION_NO_ENCONTRADA"
