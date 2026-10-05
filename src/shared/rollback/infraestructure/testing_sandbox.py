import logging
import threading
from typing import Dict, Any
from sqlalchemy import event
from sqlalchemy.orm import Session
from src.shared.database import engine, SessionLocal

logger = logging.getLogger(__name__)

active_test_transactions: Dict[str, Dict[str, Any]] = {}

sandbox_lock = threading.Lock()

MAX_CONCURRENT_RUNS = 5
IDLE_TIMEOUT_SECONDS = 180

class SandboxCapacityExceeded(Exception):
    """Excepción lanzada cuando el sandbox alcanza su límite máximo de concurrencia."""
    pass

def _timeout_cleanup(run_id: str):
    """Rollback de emergencia si el test runner falla en llamar al endpoint de cierre."""
    with sandbox_lock:
        entry = active_test_transactions.pop(run_id, None)
        
    if entry:
        try:
            logger.warning(f"[Sandbox] Timeout: Forzando rollback para run_id {run_id}")
            entry['session'].close()
            entry['transaction'].rollback()
            entry['connection'].close()
        except Exception as e:
            logger.error(f"[Sandbox] Error durante limpieza por timeout para {run_id}: {e}")

def get_or_create_test_session(run_id: str) -> Session:
    """Recupera una sesión de prueba existente o inicializa una nueva transacción aislada."""
    
    with sandbox_lock:
        if run_id in active_test_transactions:
            active_test_transactions[run_id]['timer'].cancel()
            session = active_test_transactions[run_id]['session']
        else:
            if len(active_test_transactions) >= MAX_CONCURRENT_RUNS:
                raise SandboxCapacityExceeded(
                    f"Se ha alcanzado el máximo de pruebas concurrentes ({MAX_CONCURRENT_RUNS})."
                )

            # Inicializar la transacción aislada
            connection = engine.connect()
            transaction = connection.begin()
            
            session = SessionLocal(bind=connection)
            session.begin_nested() # SAVEPOINT
            
            @event.listens_for(session, "after_transaction_end")
            def restart_savepoint(sess, trans):
                if trans.nested and not trans._parent.nested:
                    sess.begin_nested()
                    
            active_test_transactions[run_id] = {
                'session': session,
                'connection': connection,
                'transaction': transaction
            }
            
        new_timer = threading.Timer(IDLE_TIMEOUT_SECONDS, _timeout_cleanup, args=[run_id])
        new_timer.start()
        active_test_transactions[run_id]['timer'] = new_timer
        
    return session

def cleanup_test_session(run_id: str) -> bool:
    """Ejecuta el rollback final y cierra las conexiones para la prueba."""
    with sandbox_lock:
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
            logger.error(f"[Sandbox] Error durante limpieza para {run_id}: {e}")
            return False
    return False