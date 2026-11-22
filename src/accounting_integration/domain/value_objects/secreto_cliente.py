# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-06 | Arekkazu | M07 RF-101: generación, hash y verificación del client_secret |
"""``client_secret`` de un cliente externo (RF-101 5.1, 5.3, RNF-101.1).

Se guarda solo el hash bcrypt (con sal, no reversible) y se compara con ``bcrypt.checkpw``, que no
corta en el primer byte distinto. Un secreto provisto (para migrar el que AgroFusion ya usa) debe
tener al menos 16 caracteres; uno generado tiene 256 bits."""
from __future__ import annotations

import secrets

import bcrypt

from src.shared.errors import ValidationError

LONGITUD_MINIMA = 16
_LONGITUD_MAXIMA = 72  # bcrypt ignora lo que pase de 72 bytes


def generar() -> str:
    return secrets.token_urlsafe(32)


def hashear(secreto: str) -> str:
    if not LONGITUD_MINIMA <= len(secreto.encode("utf-8")) <= _LONGITUD_MAXIMA:
        raise ValidationError(code="SECRETO_INVALIDO", field="client_secret",
                              message=f"El secreto debe tener entre {LONGITUD_MINIMA} y {_LONGITUD_MAXIMA} caracteres.")
    return bcrypt.hashpw(secreto.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def coincide(secreto: str, hash_guardado: str) -> bool:
    try:
        return bcrypt.checkpw(secreto.encode("utf-8")[:_LONGITUD_MAXIMA], hash_guardado.encode("utf-8"))
    except ValueError:
        return False
