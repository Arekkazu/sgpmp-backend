# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-15 | Arekkazu | QA-M06 RF-89: el aviso no espera el bloqueo del Contador que tiene la transacción de quien llama |
"""POST /finanzas/precios no respondía en el sandbox de QA (15-11, Daniela): el run cambia el rol del ingeniero a
Contador (``SELECT … FOR UPDATE`` en el repositorio de usuarios) y nunca confirma. El aviso del precio busca a los
Contadores en la sesión del request (INC-M06-366-G31), los encuentra, y escribe en una sesión aparte que esperaba el
bloqueo de esa fila para su llave foránea; el request esperaba a esa sesión. ``db_session`` es igual al run."""
from __future__ import annotations

import threading

from sqlalchemy import text

from src.financial_valuation.infrastructure.adapters.notificacion_financiera_m01_adapter import (
    NotificacionFinancieraM01Adapter,
)
from src.shared.database import sesion_sistema


def test_el_aviso_no_espera_al_contador_bloqueado_por_quien_llama(db_session):
    db_session.execute(text("SELECT 1 FROM modulo1.usuarios WHERE id_usuario = 1 FOR UPDATE"))
    db_session.execute(text("""UPDATE modulo1.usuarios SET id_rol = (SELECT id_rol FROM modulo1.roles
                               WHERE nombre_rol = 'Contador') WHERE id_usuario = 1"""))
    aviso = threading.Thread(daemon=True, target=lambda: NotificacionFinancieraM01Adapter(sesion_sistema, db_session)
                             .a_contadores("ALERTA_FINANCIERA_NIC41", "Hay un nuevo precio de mercado vigente.", {}))
    aviso.start()
    aviso.join(15)
    assert not aviso.is_alive(), "el aviso quedó esperando el bloqueo del Contador"
