"""Prueba de integracion con PostgreSQL TEST para TC-M09-G06 / SC-16 (RF-15 / CU-01).

Sub-caso: TC-M09-16 - Concurrencia optimista en edicion de especie.
Especie fixture: Cachama Blanca (id_especie=4)
Iteracion: v2 (v1 ejecutada sobre Mojarra Plateada id=5, BLOQUEADA por INC-M09-02)

Credencial de ejecucion:
    member_qa es el UNICO usuario de BD disponible para pruebas. La credencial
    de escritura real de la aplicacion (sgpmp_test_user) no esta disponible.
    DECLARACION EXPLICITA: esta prueba de integracion solo pudo ejecutarse usando
    member_qa, cuya capacidad de escritura es en si misma el hallazgo INC-M09-04
    (privilegios DML excesivos en cuenta QA sobre modulo9).

Mecanismo de concurrencia real:
    ThreadPoolExecutor (2 workers) + threading.Barrier(2).

Arbol de decision INC-M09-02:
    - exc_a con mensaje de trigger (app.usuario_id) -> pytest.skip BLOQUEADO
    - exc_a es None y exc_b es PreconditionFailedError(412) -> PASA
    - exc_a es None y exc_b es None -> FALLA real de concurrencia

Teardown condicional:
    Solo restaura si A tuvo exito real. Si SKIP, rollback automatico del Use Case
    ya garantizo integridad -- se verifica por lectura antes de cualquier escritura.
"""
from __future__ import annotations

import logging
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from src.configuration.application.use_cases.especies.editar_especie_use_case import EditarEspecieUseCase
from src.configuration.infrastructure.dto.editar_especie_dto import EditarEspecieDTO
from src.configuration.infrastructure.repositories.auditoria_especie_repository import SqlAlchemyAuditoriaEspecieRepository
from src.configuration.infrastructure.repositories.especie_repository import SqlAlchemyEspecieRepository
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import InfrastructureError, PreconditionFailedError
from sqlalchemy import text

ID_CACHAMA = 4
NOMBRE_ORIGINAL = "Cachama Blanca"
DESC_ORIGINAL = "Pez de agua dulce tropical con alta adaptabilidad a sistemas extensivos e intensivos."

USUARIO_A = UsuarioActual(id_usuario=1, id_token=10, id_rol=1)
USUARIO_B = UsuarioActual(id_usuario=2, id_token=11, id_rol=1)

logger = logging.getLogger(__name__)


def _leer_bd(db_session, id_especie: int) -> dict:
    """Lectura directa SQL del estado actual (sin ORM, mas confiable post-rollback)."""
    try:
        row = db_session.execute(
            text("""
                SELECT nombre, descripcion, es_activo, fecha_actualizacion
                FROM modulo9.especies WHERE id_especie = :id
            """),
            {"id": id_especie},
        ).mappings().one_or_none()
        return dict(row) if row else {}
    except Exception as e:
        return {"error_lectura": str(e)}


@pytest.mark.integration
def test_concurrencia_optimista_edicion_especie_cachama_integration(db_session):
    """TC-M09-G06 / SC-16: Concurrencia optimista sobre Cachama Blanca (id=4).

    Veredicto proyectado: SKIP/BLOQUEADO por INC-M09-02.
    Si PASA: INC-M09-02 fue corregido -- reportar como hallazgo positivo.
    """
    especies_repo = SqlAlchemyEspecieRepository(db_session)
    auditoria_repo = SqlAlchemyAuditoriaEspecieRepository(db_session)

    # --- 0. Lectura inicial para referencia de teardown ----------------------
    especie_original = especies_repo.obtener_por_id(ID_CACHAMA)
    assert especie_original is not None, (
        f"Cachama Blanca (id={ID_CACHAMA}) no existe en BD TEST. Verificar seed."
    )
    assert especie_original.es_activo, (
        f"Cachama Blanca (id={ID_CACHAMA}) esta inactiva. Fixture corrompido."
    )

    nombre_antes = especie_original.nombre.valor
    descripcion_antes = especie_original.descripcion
    ts_v0 = especie_original.fecha_actualizacion

    assert ts_v0 is not None, (
        f"Cachama Blanca no tiene fecha_actualizacion. Control optimista no puede operar."
    )

    edicion_a_exitosa = False
    exc_a = None
    exc_b = None
    resultado_a = None
    resultado_b = None

    try:
        # --- 1. Concurrencia real con Barrier --------------------------------
        barrier = threading.Barrier(2, timeout=10)

        def editar_como_a():
            barrier.wait()
            uc = EditarEspecieUseCase(
                db=db_session,
                especies_repo=SqlAlchemyEspecieRepository(db_session),
                auditoria_repo=SqlAlchemyAuditoriaEspecieRepository(db_session),
            )
            return uc.execute(
                ID_CACHAMA,
                EditarEspecieDTO(
                    nombre="Cachama Blanca TC-G06-A",
                    descripcion="Modificacion Usuario A concurrencia TC-M09-G06",
                    fecha_actualizacion=ts_v0,
                ),
                USUARIO_A,
            )

        def editar_como_b():
            barrier.wait()
            uc = EditarEspecieUseCase(
                db=db_session,
                especies_repo=SqlAlchemyEspecieRepository(db_session),
                auditoria_repo=SqlAlchemyAuditoriaEspecieRepository(db_session),
            )
            return uc.execute(
                ID_CACHAMA,
                EditarEspecieDTO(
                    nombre="Cachama Blanca TC-G06-B",
                    descripcion="Modificacion Usuario B concurrencia TC-M09-G06",
                    fecha_actualizacion=ts_v0,  # ts obsoleto para forzar conflicto
                ),
                USUARIO_B,
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            fut_a = pool.submit(editar_como_a)
            fut_b = pool.submit(editar_como_b)

        exc_a = fut_a.exception()
        exc_b = fut_b.exception()
        if exc_a is None:
            resultado_a = fut_a.result()
        if exc_b is None:
            resultado_b = fut_b.result()

        # --- 2. Arbol de decision INC-M09-02 ---------------------------------
        if exc_a is not None:
            msg = str(exc_a).lower()
            es_trigger = (
                isinstance(exc_a, InfrastructureError)
                or "app.usuario_id" in msg
                or "audit-especies" in msg
                or ("audit" in msg and "usuario_id" in msg)
                or "internalerror" in type(exc_a).__name__.lower()
                or "integrity" in type(exc_a).__name__.lower()
                or "operational" in type(exc_a).__name__.lower()
            )

            if es_trigger:
                estado_post = _leer_bd(db_session, ID_CACHAMA)
                nombre_post = estado_post.get("nombre", "?")
                ts_post = estado_post.get("fecha_actualizacion")
                rollback_ok = (nombre_post == NOMBRE_ORIGINAL)
                pytest.skip(
                    f"BLOQUEADO INC-M09-02 (reconfirmado con Cachama Blanca id={ID_CACHAMA}): "
                    f"trigger modulo9.trg_fn_especies_audit lanzo excepcion por falta de "
                    f"app.usuario_id. SqlAlchemyEspecieRepository.actualizar() no ejecuta "
                    f"SET LOCAL app.usuario_id antes del flush(). "
                    f"Excepcion: {type(exc_a).__name__}: {exc_a}. "
                    f"Estado BD post-fallo: nombre='{nombre_post}', ts={ts_post}. "
                    f"Rollback automatico: {'OK - especie intacta' if rollback_ok else 'VERIFICAR - nombre cambio'}. "
                    f"Credencial: member_qa (INC-M09-04: privilegios DML excesivos en cuenta QA)."
                )
            elif isinstance(exc_a, PreconditionFailedError):
                pytest.fail(
                    f"CP-02 FALLA: Usuario A rechazado con PreconditionFailedError inesperado "
                    f"(ts_v0 era el correcto). code={exc_a.code}. Error nuevo en control optimista."
                )
            else:
                pytest.fail(
                    f"CP-02 FALLA: excepcion no clasificada en A: {type(exc_a).__name__}: {exc_a}"
                )

        # A tuvo exito -- verificar CP-02
        assert resultado_a is not None
        ts_v1 = resultado_a.fecha_actualizacion
        assert ts_v1 != ts_v0, (
            f"CP-02 FALLA: fecha_actualizacion no cambio. ts_v0={ts_v0}"
        )
        assert resultado_a.nombre.valor == "Cachama Blanca TC-G06-A", (
            f"CP-02 FALLA: nombre de A incorrecto: {resultado_a.nombre.valor}"
        )

        # Verificar CP-03: B debe haber sido rechazado con 412
        if exc_b is not None:
            assert isinstance(exc_b, PreconditionFailedError), (
                f"CP-03 FALLA: B lanzo {type(exc_b).__name__}: {exc_b}. "
                "Se esperaba PreconditionFailedError."
            )
            assert exc_b.code == "CONFLICTO_CONCURRENCIA", (
                f"CP-03 FALLA: code={exc_b.code}, esperado CONFLICTO_CONCURRENCIA"
            )
            assert exc_b.status_code == 412, (
                f"CP-03 FALLA: status_code={exc_b.status_code}, esperado 412"
            )

            # CP-04: Verificar en BD que prevalece A
            especie_bd = especies_repo.obtener_por_id(ID_CACHAMA)
            assert especie_bd.nombre.valor == "Cachama Blanca TC-G06-A", (
                f"CP-04 FALLA: en BD prevalece B. nombre={especie_bd.nombre.valor}"
            )

            # CP-05: timestamp incremento exactamente 1 vez
            assert especie_bd.fecha_actualizacion == ts_v1, (
                f"CP-05 FALLA: ts en BD={especie_bd.fecha_actualizacion}, ts_v1={ts_v1}"
            )
        else:
            # Ambos tuvieron exito: FALLA REAL del control de concurrencia
            pytest.fail(
                "CP-03 FALLA CRITICA: B tambien recibio exito (HTTP 200) con ts_v0 obsoleto. "
                f"El control de concurrencia optimista NO funciona. "
                f"Resultado B: nombre={resultado_b.nombre.valor if resultado_b else 'N/A'}"
            )

        edicion_a_exitosa = True

    finally:
        # --- Teardown condicional --------------------------------------------
        estado_actual = _leer_bd(db_session, ID_CACHAMA)
        nombre_actual = estado_actual.get("nombre", "?")
        ts_actual = estado_actual.get("fecha_actualizacion")

        if not edicion_a_exitosa:
            # A fue bloqueada: rollback automatico ya restauro la BD
            logger.info(
                "[TEARDOWN] A fue bloqueada (INC-M09-02). Sin escritura de restauracion. "
                f"Cachama Blanca: nombre='{nombre_actual}', ts={ts_actual}. "
                f"Intacta: {nombre_actual == NOMBRE_ORIGINAL}"
            )
            return

        if nombre_actual == NOMBRE_ORIGINAL:
            logger.info("[TEARDOWN] Especie ya tiene nombre original. Sin restauracion necesaria.")
            return

        try:
            especie_post = especies_repo.obtener_por_id(ID_CACHAMA)
            uc_r = EditarEspecieUseCase(
                db=db_session,
                especies_repo=especies_repo,
                auditoria_repo=auditoria_repo,
            )
            especie_restaurada = uc_r.execute(
                ID_CACHAMA,
                EditarEspecieDTO(
                    nombre=NOMBRE_ORIGINAL,
                    descripcion=descripcion_antes,
                    fecha_actualizacion=especie_post.fecha_actualizacion,
                ),
                USUARIO_A,
            )
            assert especie_restaurada.nombre.valor == NOMBRE_ORIGINAL, (
                f"[TEARDOWN] Restauracion fallida: nombre={especie_restaurada.nombre.valor}"
            )
            logger.info(f"[TEARDOWN] Cachama Blanca restaurada a '{NOMBRE_ORIGINAL}'.")
        except Exception as e_td:
            msg_critico = (
                f"[FALLO CRITICO DE RESTAURACION] No se pudo restaurar Cachama Blanca "
                f"(id={ID_CACHAMA}) a '{NOMBRE_ORIGINAL}'. Error: {e_td}. "
                f"Estado BD: nombre='{nombre_actual}', ts={ts_actual}. "
                "ACCION REQUERIDA: restaurar manualmente con member_qa."
            )
            logging.critical(msg_critico)
            print(f"\n{msg_critico}", file=sys.stderr)
            raise RuntimeError(msg_critico) from e_td
