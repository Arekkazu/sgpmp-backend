# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-06 | Arekkazu | RFC-019 D-19.6: token de activación de las cuentas creadas por AgroFusion |
"""Funciones de dominio para proteger tokens de un solo uso.

Los tokens de activación y recuperación tienen suficiente entropía para usar
un hash SHA-256 determinista. El valor en texto plano solo se entrega al
usuario; la aplicación persiste y consulta exclusivamente su representación
hexadecimal.
"""
from __future__ import annotations

import hashlib


def calcular_hash_token(token: str) -> str:
    """Devuelve el hash SHA-256 hexadecimal de un token de un solo uso."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# RFC-019 D-19.6: las cuentas que crea AgroFusion (CREATE_USER) nacen activas y reciben un token
# de activación que AgroFusion usa después (ACTIVATE_ACCOUNT). El prefijo lo distingue de los
# tokens de recuperación, que comparten columna, para responder 200 idempotente solo a estos.
PREFIJO_TOKEN_M2M = "m2m-"


def es_token_m2m(token: str) -> bool:
    return token.startswith(PREFIJO_TOKEN_M2M)
