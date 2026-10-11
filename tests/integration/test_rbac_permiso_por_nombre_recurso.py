"""`tiene_permiso_sobre` ubica el recurso por nombre, no por un id fijo.

Los recursos sembrados por migraciones recientes toman su id de la secuencia, y
ese id difiere entre bases: con números fijos en el router, `datos_clinicos_activo`
(#417) y el scope `datos_analiticos_eventos` (RF-50) terminaron ambos en 59.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.shared.rbac import tiene_permiso_sobre

pytestmark = pytest.mark.integration

_ROL_VETERINARIO = 3
_LEER = 2


def test_permiso_se_resuelve_por_nombre_con_ids_arbitrarios(db_session: Session) -> None:
    sufijo = uuid.uuid4().hex[:10]
    clinico, eventos = f'prueba_clinico_{sufijo}', f'prueba_eventos_{sufijo}'
    base = db_session.execute(text('SELECT COALESCE(MAX(id_recurso), 0) + 1000 FROM modulo1.recursos')).scalar()
    db_session.execute(
        text(
            'INSERT INTO modulo1.recursos (id_recurso, nombre_recurso, descripcion) '
            "VALUES (:a, :clinico, 'prueba'), (:b, :eventos, 'prueba')"
        ),
        {'a': base, 'b': base + 1, 'clinico': clinico, 'eventos': eventos},
    )
    db_session.execute(
        text(
            'INSERT INTO modulo1.permisos (nombre, descripcion, id_rol, id_recurso, id_accion, es_activo) '
            "VALUES (:nombre, 'prueba', :rol, :recurso, :accion, TRUE)"
        ),
        {'nombre': f'vet_leer_{clinico}', 'rol': _ROL_VETERINARIO, 'recurso': base, 'accion': _LEER},
    )
    db_session.flush()

    assert tiene_permiso_sobre(db_session, _ROL_VETERINARIO, clinico, _LEER)
    assert not tiene_permiso_sobre(db_session, _ROL_VETERINARIO, eventos, _LEER)
    assert not tiene_permiso_sobre(db_session, _ROL_VETERINARIO, f'no_existe_{sufijo}', _LEER)
