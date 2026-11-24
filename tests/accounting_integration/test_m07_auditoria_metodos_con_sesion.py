"""RF-102 FA-2: PUT/PATCH/DELETE /integracion/auditoria exige sesión y registra al usuario."""
from types import SimpleNamespace

import pytest

from src.accounting_integration.infrastructure.routers import m07_router
from src.identity_access.infrastructure.dependencies import get_current_user
from src.shared.errors import MethodNotAllowedError


def _ruta():
    return next(r for r in m07_router.router.routes
                if getattr(r, "endpoint", None) is m07_router.bloquear_modificacion_auditoria)


def test_la_ruta_depende_de_la_sesion():
    dependencias = [d.call for d in _ruta().dependant.dependencies]
    assert get_current_user in dependencias


def test_con_sesion_responde_405_y_audita_al_usuario():
    eventos = []
    m07 = SimpleNamespace(auditar_aparte=eventos.append)
    request = SimpleNamespace(method="DELETE", client=SimpleNamespace(host="10.0.0.1"))
    with pytest.raises(MethodNotAllowedError):
        m07_router.bloquear_modificacion_auditoria(request, m07, SimpleNamespace(id_usuario=7, id_rol=1))
    assert len(eventos) == 1
    assert eventos[0].id_usuario == 7
    assert eventos[0].tipo_evento == "INTENTO_MODIFICACION_AUDITORIA"
