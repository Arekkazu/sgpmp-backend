# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-11-15 | Arekkazu         | INC-M05-367/368-G02 RF-74: el aviso de CA crítica llega a las dos bandejas bajo RLS |
"""INC-M05-367-G02 (#1147) e INC-M05-368-G02 (#1146), TC-M05-007b.

367: el cálculo manual escribía el aviso con la sesión del Administrador; la RLS de
las notificaciones lo rechazaba y no le llegaba a nadie. 368: un solo evento a nombre
del Productor para todos los destinatarios; la bandeja une con el evento bajo RLS y el
Veterinario no lo veía, tampoco desde el batch.

Fuerza ``TEST_ROL_APP=sgpmp_app``: con superusuario RLS no aplica y el defecto no se ve.
"""
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.shared.database import declarar_identidad, declarar_identidad_sistema
from src.supplies.infrastructure.adapters import notificacion_suministros_m01_adapter
from src.supplies.infrastructure.adapters.notificacion_suministros_m01_adapter import (
    NotificacionSuministrosM01Adapter,
)
from tests.integration.test_m05_flujo_completo_integration import _catalogos, _escenario  # noqa: F401

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _rol_api(monkeypatch):
    monkeypatch.setenv("TEST_ROL_APP", "sgpmp_app")


@pytest.mark.parametrize("origen", ["calculo_manual_admin", "batch_sistema"])
def test_aviso_ca_critica_llega_al_productor_y_al_veterinario(
    origen, client, db_session, crear_usuario_db, crear_auth_headers, monkeypatch,
):
    def sesion_notificaciones():
        sesion = Session(bind=db_session.connection(), join_transaction_mode="create_savepoint")
        declarar_identidad_sistema(sesion)
        return sesion

    monkeypatch.setattr(notificacion_suministros_m01_adapter, "sesion_sistema", sesion_notificaciones)
    admin = crear_usuario_db(id_rol=1)
    productor = crear_usuario_db(id_rol=2)
    veterinario = crear_usuario_db(id_rol=3)
    esc = _escenario(db_session, productor["id_usuario"])
    db_session.execute(text("INSERT INTO modulo9.usuarios_fincas (id_usuario, id_finca) VALUES (:u, :f)"),
                       {"u": veterinario["id_usuario"], "f": esc["finca"]})
    db_session.commit()
    mensaje = f"Urgencia ALTA: la conversión alimenticia del activo M05-{esc['activo']} es crítica (CA 9,0000)."

    # La sesión con la que llega el aviso: la del request del Administrador o la del batch.
    if origen == "calculo_manual_admin":
        declarar_identidad(db_session, admin["id_usuario"], "Administrador")
    else:
        declarar_identidad_sistema(db_session)
    db_session.execute(text("SET LOCAL ROLE sgpmp_app"))
    try:
        NotificacionSuministrosM01Adapter(db_session).a_responsables_activo(
            esc["activo"], "ALERTA_CONVERSION_ALIMENTICIA", mensaje, {"id_activo_biologico": esc["activo"]},
        )
    finally:
        db_session.execute(text("RESET ROLE"))
    db_session.commit()

    for rol, usuario in (("Productor", productor), ("Veterinario", veterinario)):
        bandeja = client.get("/notificaciones", headers=crear_auth_headers(usuario))
        assert bandeja.status_code == 200, bandeja.text
        assert mensaje in [aviso["mensaje"] for aviso in bandeja.json()["items"]], rol
