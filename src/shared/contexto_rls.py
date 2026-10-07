"""Contexto de sesión para RLS que sobrevive a los ``commit()`` del request.

F2 del control de acceso por BD: las políticas de modulo1/modulo9 leen la
identidad con ``modulo1.fn_id_usuario_actual()`` / ``modulo1.fn_rol_actual()``,
que a su vez leen variables declaradas con ``set_config(..., true)`` (el
equivalente parametrizado de ``SET LOCAL``). Ese ``true`` es deliberado: la
variable muere con la transacción y nunca se filtra al siguiente uso de la
conexión en el pool (``tests/integration/test_control_acceso_f2_contexto_sesion_no_fuga.py``).

El costo es que un use case que hace dos ``commit()`` en el mismo request
perdía la identidad en el segundo. Es el patrón documentado de "persistir,
notificar fuera de la transacción, persistir el resultado" -- p. ej. RF-17
(INC-M09-104-G29): guarda el umbral, lo propaga al Nodo Edge y después guarda
``estado_sincronizacion``. Sin identidad, la política UPDATE de
``modulo9.umbrales_ambientales`` filtra la fila y el UPDATE afecta 0 filas en
silencio (verificado contra ``sgpmp_dev`` con ``member_dev``, sin
``BYPASSRLS``).

``declarar_contexto_rls`` guarda las variables en ``Session.info`` -- que vive
lo que vive la sesión del request, no la conexión -- y el listener
``after_begin`` las vuelve a declarar al inicio de cada transacción nueva de
esa misma sesión. Siguen siendo locales a la transacción: cuando la sesión se
cierra y la conexión vuelve al pool, no queda nada.
"""
from __future__ import annotations

from sqlalchemy import event, text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

_CLAVE_CONTEXTO_RLS = "contexto_rls"


def _aplicar(conexion: Connection, variables: dict[str, str]) -> None:
    for nombre, valor in variables.items():
        conexion.execute(
            text("SELECT set_config(:nombre, :valor, true)"),
            {"nombre": nombre, "valor": valor},
        )


def declarar_contexto_rls(db: Session, variables: dict[str, str]) -> None:
    """Declara ``variables`` (GUC → valor) en la transacción actual de ``db`` y
    en cada transacción que ``db`` abra después."""
    db.info[_CLAVE_CONTEXTO_RLS] = dict(variables)
    _aplicar(db.connection(), variables)


@event.listens_for(Session, "after_begin")
def _redeclarar_contexto_rls(session: Session, _transaccion, conexion: Connection) -> None:
    variables = session.info.get(_CLAVE_CONTEXTO_RLS)
    if variables:
        _aplicar(conexion, variables)
