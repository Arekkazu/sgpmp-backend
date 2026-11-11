# | Fecha       | Nombre | Que se hizo |
# |-------------|--------|-------------|
# | 2026-11-10  | —      | TC-M06-G109: reclamo del aviso antes de persistir la marca |
"""Serialización del aviso de vencimiento sin cambiar el esquema.

La consulta previa y el alta viven en sesiones distintas. Para que dos procesos no
registren la misma marca, la transacción que escribe toma ``pg_advisory_xact_lock``
y vuelve a consultar antes de insertar. El candado se libera si la transacción no
se confirma, así que un fallo deja el aviso libre para un reintento.

Esto no es una restricción única. Otra vía que inserte el evento sin pasar por aquí
puede duplicarlo. La prueba de dos sesiones PostgreSQL queda pendiente.
"""
from __future__ import annotations

import zlib


def es_marca_vencimiento(detalle) -> bool:
    """La marca del vencimiento es el par precio + aviso. Otros avisos no entran aquí."""
    if not isinstance(detalle, dict):
        return False
    precio = detalle.get("id_precio_mercado")
    aviso = detalle.get("aviso")
    return type(precio) is int and precio > 0 and isinstance(aviso, str) and bool(aviso)


def claves_candado(id_precio: int, aviso: str) -> tuple[int, int]:
    """Dos enteros para ``pg_advisory_xact_lock``. El segundo resume el tipo de aviso."""
    firma = zlib.crc32(aviso.encode("utf-8")) & 0x7FFFFFFF
    return id_precio, firma or 1


class BitacoraAvisos:
    """Visibilidad que se puede probar sin base de datos.

    Una reserva no confirmada bloquea a la otra ejecución. Al revertir, la marca
    desaparece. Al confirmar, las siguientes reservas la ven.
    """

    def __init__(self) -> None:
        self.confirmadas: set[tuple[int, str]] = set()
        self.pendientes: set[tuple[int, str]] = set()

    def reservar(self, marca: tuple[int, str]) -> bool:
        if marca in self.confirmadas or marca in self.pendientes:
            return False
        self.pendientes.add(marca)
        return True

    def confirmar(self, marca: tuple[int, str]) -> None:
        self.pendientes.discard(marca)
        self.confirmadas.add(marca)

    def revertir(self, marca: tuple[int, str]) -> None:
        self.pendientes.discard(marca)
