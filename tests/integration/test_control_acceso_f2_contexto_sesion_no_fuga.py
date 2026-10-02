"""F2 del control de acceso por BD: el contexto de sesión no sobrevive al COMMIT.

Todo el diseño de RLS (migraciones `8d80fb56a30b`/`5243bbbb28de`) descansa en
que `set_config('app.current_user_id', ..., true)` (equivalente parametrizado
de `SET LOCAL`) muere con la transacción, no con la conexión física. Si eso
fallara -- por ejemplo, porque algo en `src/shared/database.py` reutiliza la
conexión sin que el `COMMIT`/`ROLLBACK` del request anterior la haya limpiado
de verdad -- una identidad quedaría filtrada al siguiente uso de esa conexión
en el pool, y un usuario vería el contexto de otro.

Se prueba contra una conexión real (no contra `db_session`, que envuelve cada
test en una transacción exterior con savepoints -- eso ocultaría justamente el
COMMIT/ROLLBACK real que este test necesita observar), siguiendo el mismo
patrón crudo de `test_rf10_retencion_auditoria_integration.py`.
"""
from __future__ import annotations

import pytest
from sqlalchemy import Engine, text

pytestmark = pytest.mark.integration


def test_set_config_local_no_sobrevive_al_commit(integration_engine: Engine) -> None:
    conexion = integration_engine.connect()
    try:
        conexion.execute(
            text("SELECT set_config('app.current_user_id', '4242', true)")
        )
        valor_dentro = conexion.execute(
            text("SELECT current_setting('app.current_user_id', true)")
        ).scalar_one()
        assert valor_dentro == "4242"

        conexion.commit()

        valor_despues = conexion.execute(
            text("SELECT current_setting('app.current_user_id', true)")
        ).scalar_one()
        assert valor_despues in (None, "")
    finally:
        conexion.close()


def test_set_config_local_no_sobrevive_al_rollback(integration_engine: Engine) -> None:
    conexion = integration_engine.connect()
    try:
        conexion.execute(
            text("SELECT set_config('app.current_role', 'Administrador', true)")
        )
        conexion.rollback()

        valor_despues = conexion.execute(
            text("SELECT current_setting('app.current_role', true)")
        ).scalar_one()
        assert valor_despues in (None, "")
    finally:
        conexion.close()
