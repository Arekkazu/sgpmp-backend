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
