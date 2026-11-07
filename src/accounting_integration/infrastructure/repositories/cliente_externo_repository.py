# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-06 | Arekkazu | M07 RF-101: persistencia de clientes externos, credenciales y canales |
"""Clientes externos (``modulo7.clientes_externos``), su credencial (``identificadores_apis``, una sola
ACTIVA por trigger) y sus canales (``canales_clientes_externos``)."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.accounting_integration.domain.entities.cliente_externo import ClienteExterno, Credencial
from src.accounting_integration.domain.repositories.cliente_externo_repository import ClienteExternoRepository
from src.financial_valuation.infrastructure.repositories.sql import escribir, fila, filas

_SELECT = """
    SELECT ce.id_cliente_externo, ce.codigo, ce.nombre, ce.identificador_publico, ce.estado::text AS estado,
           ce.tipo::text AS tipo, host(ce.ip_permitida) || CASE WHEN masklen(ce.ip_permitida) IN (32, 128) THEN ''
               ELSE '/' || masklen(ce.ip_permitida) END AS ip_permitida,
           ce.ttl_token_canal_minutos, ce.fecha_actualizacion,
           COALESCE((SELECT jsonb_object_agg(cc.canal::text, cc.limite_por_minuto)
                     FROM modulo7.canales_clientes_externos cc WHERE cc.id_cliente_externo = ce.id_cliente_externo),
                    '{}'::jsonb) AS canales
    FROM modulo7.clientes_externos ce
"""
_CONFLICTOS = {"uix_cliente_externo_codigo": "Ya existe un cliente externo con ese nombre.",
               "uq_cliente_externo_identificador_publico": "Ya existe un cliente externo con ese identificador."}


class SqlAlchemyClienteExternoRepository(ClienteExternoRepository):
    def __init__(self, db: Session):
        self.db = db

    def obtener(self, id_cliente_externo: int) -> Optional[ClienteExterno]:
        f = fila(self.db, f"{_SELECT} WHERE ce.id_cliente_externo = :id", {"id": id_cliente_externo})
        return ClienteExterno(**f) if f else None

    def obtener_por_identificador(self, identificador_publico: str) -> Optional[ClienteExterno]:
        f = fila(self.db, f"{_SELECT} WHERE ce.identificador_publico = :id", {"id": identificador_publico})
        return ClienteExterno(**f) if f else None

    def listar(self) -> list[ClienteExterno]:
        return [ClienteExterno(**f) for f in filas(self.db, f"{_SELECT} ORDER BY ce.nombre")]

    def guardar(self, cliente: ClienteExterno) -> ClienteExterno:
        params = {"id": cliente.id_cliente_externo, "codigo": cliente.codigo, "nombre": cliente.nombre,
                  "identificador": cliente.identificador_publico, "estado": cliente.estado, "tipo": cliente.tipo,
                  "ip": cliente.ip_permitida, "ttl": cliente.ttl_token_canal_minutos}
        if cliente.id_cliente_externo is None:
            cliente.id_cliente_externo = escribir(self.db, """
                INSERT INTO modulo7.clientes_externos (codigo, nombre, identificador_publico, estado, tipo, ip_permitida,
                    ttl_token_canal_minutos)
                VALUES (:codigo, :nombre, :identificador, CAST(:estado AS modulo7.enum_cliente_externo_estado),
                    CAST(:tipo AS modulo7.enum_cliente_externo_tipo), CAST(:ip AS inet), :ttl)
                RETURNING id_cliente_externo
            """, params, _CONFLICTOS)
        else:
            escribir(self.db, """
                UPDATE modulo7.clientes_externos SET nombre = :nombre,
                    estado = CAST(:estado AS modulo7.enum_cliente_externo_estado), ip_permitida = CAST(:ip AS inet),
                    ttl_token_canal_minutos = :ttl, fecha_actualizacion = now()
                WHERE id_cliente_externo = :id
            """, params, _CONFLICTOS)
            escribir(self.db, "DELETE FROM modulo7.canales_clientes_externos WHERE id_cliente_externo = :id", params)
        for canal, limite in sorted(cliente.canales.items()):
            escribir(self.db, """
                INSERT INTO modulo7.canales_clientes_externos (id_cliente_externo, canal, limite_por_minuto)
                VALUES (:id, CAST(:canal AS modulo7.enum_canal_cliente_externo_canal), :limite)
            """, {"id": cliente.id_cliente_externo, "canal": canal, "limite": limite})
        return self.obtener(cliente.id_cliente_externo)

    def credencial_activa(self, id_cliente_externo: int) -> Optional[Credencial]:
        f = fila(self.db, """
            SELECT id_identificador_api, hash_secreto, fecha_emision, fecha_expiracion, estado::text AS estado
            FROM modulo7.identificadores_apis WHERE id_cliente_externo = :id AND estado = 'ACTIVA'
        """, {"id": id_cliente_externo})
        return Credencial(**f) if f else None

    def reemplazar_credencial(self, id_cliente_externo: int, credencial: Credencial) -> None:
        escribir(self.db, """
            UPDATE modulo7.identificadores_apis SET estado = 'REVOCADA', fecha_revocacion = now()
            WHERE id_cliente_externo = :id AND estado = 'ACTIVA'
        """, {"id": id_cliente_externo})
        escribir(self.db, """
            INSERT INTO modulo7.identificadores_apis (id_cliente_externo, hash_secreto, fecha_emision, fecha_expiracion, estado)
            VALUES (:id, :hash, now(), :expiracion, 'ACTIVA')
        """, {"id": id_cliente_externo, "hash": credencial.hash_secreto, "expiracion": credencial.fecha_expiracion})
