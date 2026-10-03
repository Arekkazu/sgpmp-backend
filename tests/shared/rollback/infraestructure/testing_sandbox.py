import logging
import threading
from typing import Dict, Any
from sqlalchemy import event
from sqlalchemy.orm import Session
from src.shared.database import engine, SessionLocal

logger = logging.getLogger(__name__)

# Almacén en memoria para las transacciones activas de Newman
active_test_transactions: Dict[str, Dict[str, Any]] = {}
IDLE_TIMEOUT_SECONDS = 180

def _timeout_cleanup(run_id: str):
    """Rollback de emergencia si Newman falla y abandona la conexión."""
    entry = active_test_transactions.pop(run_id, None)
    if entry:
        try:
            logger.warning(f"[Sandbox] Timeout: Rollback forzado del run_id {run_id}")
            entry['session'].close()
            entry['transaction'].rollback()
            entry['connection'].close()
        except Exception as e:
            logger.error(f"[Sandbox] Error limpiando run_id {run_id}: {e}")

def get_or_create_test_session(run_id: str) -> Session:
    """Recupera la sesión del run-id actual o crea una nueva aislada."""
    if run_id in active_test_transactions:
        # La prueba sigue viva, cancelamos el timer de timeout
        active_test_transactions[run_id]['timer'].cancel()
        session = active_test_transactions[run_id]['session']
    else:
        # Nueva corrida de Newman: abrimos el SAVEPOINT global
        connection = engine.connect()
        transaction = connection.begin()
        
        session = SessionLocal(bind=connection)
        session.begin_nested() # SAVEPOINT inicial
        
        # Restaurar SAVEPOINT después de cada commit interno
        @event.listens_for(session, "after_transaction_end")
        def restart_savepoint(sess, trans):
            if trans.nested and not trans._parent.nested:
                sess.begin_nested()
                
        active_test_transactions[run_id] = {
            'session': session,
            'connection': connection,
            'transaction': transaction
        }
        
    # Arrancamos un timer nuevo para contar la inactividad desde cero
    new_timer = threading.Timer(IDLE_TIMEOUT_SECONDS, _timeout_cleanup, args=[run_id])
    new_timer.start()
    active_test_transactions[run_id]['timer'] = new_timer
    
    return session

def cleanup_test_session(run_id: str) -> bool:
    """Ejecuta el rollback final de Newman."""
    entry = active_test_transactions.pop(run_id, None)
    if entry:
        entry['timer'].cancel()
        try:
            entry['session'].close()
            entry['transaction'].rollback()
            entry['connection'].close()
            logger.info(f"[Sandbox] Rollback exitoso para run_id {run_id}")
            return True
        except Exception as e:
            logger.error(f"[Sandbox] Error en rollback para {run_id}: {e}")
            return False
    return False