# | Fecha       | Nombre | Que se hizo |
# |-------------|--------|-------------|
# | 2026-11-10  | —      | TC-M06-G109: procedimiento de dos sesiones para el candado del aviso |
"""Dos sesiones PostgreSQL para el mismo par precio + aviso.

Queda omitida hasta tener una base local cuyo nombre contenga ``g109`` y cuya URL
esté en ``G109_PG_AISLADO_URL``. El host tiene que ser localhost. No usa TEST ni
``modulo1``.
"""
from __future__ import annotations

import os
import threading
from urllib.parse import urlparse

import pytest

_URL = os.getenv("G109_PG_AISLADO_URL", "").strip()


def _destino_aislado(url: str) -> bool:
    if not url:
        return False
    partes = urlparse(url)
    host = (partes.hostname or "").lower()
    nombre = (partes.path or "").lstrip("/").lower()
    return host in {"localhost", "127.0.0.1"} and "g109" in nombre


pytestmark = pytest.mark.skipif(
    not _destino_aislado(_URL),
    reason="No hay un PostgreSQL local aislado en G109_PG_AISLADO_URL. No se usa TEST.",
)


def test_dos_sesiones_reclaman_el_mismo_aviso_una_sola_vez():
    import psycopg2

    with psycopg2.connect(_URL) as preparacion:
        preparacion.autocommit = True
        with preparacion.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS g109_reclamo_aviso (
                    id_precio_mercado integer NOT NULL,
                    aviso text NOT NULL,
                    PRIMARY KEY (id_precio_mercado, aviso)
                )
                """
            )
            cursor.execute("DELETE FROM g109_reclamo_aviso WHERE id_precio_mercado = 88001")

    barrera = threading.Barrier(2)
    resultados: dict[str, str] = {}

    def reclamar(nombre: str) -> None:
        conexion = psycopg2.connect(_URL)
        try:
            with conexion.cursor() as cursor:
                barrera.wait(timeout=5)
                cursor.execute("SELECT pg_advisory_xact_lock(%s, %s)", (88001, 15))
                cursor.execute(
                    "SELECT 1 FROM g109_reclamo_aviso WHERE id_precio_mercado = %s AND aviso = %s",
                    (88001, "15_DIAS"),
                )
                if cursor.fetchone() is not None:
                    resultados[nombre] = "repetido"
                    conexion.rollback()
                    return
                cursor.execute(
                    "INSERT INTO g109_reclamo_aviso (id_precio_mercado, aviso) VALUES (%s, %s)",
                    (88001, "15_DIAS"),
                )
                conexion.commit()
                resultados[nombre] = "nuevo"
        finally:
            conexion.close()

    hilos = [threading.Thread(target=reclamar, args=(nombre,)) for nombre in ("a", "b")]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join(timeout=10)

    assert sorted(resultados.values()) == ["nuevo", "repetido"]
    with psycopg2.connect(_URL) as verificacion:
        with verificacion.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) FROM g109_reclamo_aviso WHERE id_precio_mercado = %s AND aviso = %s",
                (88001, "15_DIAS"),
            )
            assert cursor.fetchone()[0] == 1
