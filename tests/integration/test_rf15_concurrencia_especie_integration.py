"""Prueba de integración con PostgreSQL para TC-M09-G06 (RF-15 / CU-01): Edición concurrente de una misma especie.

Aclaración Metodológica:
La presente prueba simula la condición de carrera de edición concurrente evaluando las solicitudes de forma secuencial
con timestamps declarados desfasados. Esto es metodológicamente equivalente a solicitudes concurrentes en tiempo real,
ya que el control de concurrencia optimista implementado en SGPMP no se basa en bloqueos (locks) de fila a nivel de BD,
sino en la comparación estricta del timestamp `fecha_actualizacion` provisto en el DTO cliente contra la versión vigente en BD.

Flujo de la Prueba:
1. Lectura inicial del registro `id_especie = 5` ("Mojarra Plateada") guardando dinámicamente sus valores originales de restauración.
2. Simulación de lectura simultánea por Usuario A y Usuario B capturando el timestamp inicial `ts_v0`.
3. Usuario A envía la edición primero usando `ts_v0`. La actualización se persiste exitosamente y genera `ts_v1`.
4. Usuario B intenta aplicar su edición usando el timestamp desactualizado `ts_v0`. Se verifica el rechazo HTTP 412 (`PreconditionFailedError` / `code == "CONFLICTO_CONCURRENCIA"`).
5. Se verifica que prevalecen los datos guardados por Usuario A.
6. Teardown Bloqueante: Se restaura exactamente el nombre y descripción originales en BD de la especie `id_especie = 5`.
"""
from __future__ import annotations

from datetime import datetime, timezone
import pytest

from src.configuration.application.use_cases.especies.editar_especie_use_case import EditarEspecieUseCase
from src.configuration.infrastructure.dto.editar_especie_dto import EditarEspecieDTO
from src.configuration.infrastructure.repositories.auditoria_especie_repository import SqlAlchemyAuditoriaEspecieRepository
from src.configuration.infrastructure.repositories.especie_repository import SqlAlchemyEspecieRepository
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import PreconditionFailedError

USUARIO_A = UsuarioActual(id_usuario=1, id_token=10, id_rol=1)
USUARIO_B = UsuarioActual(id_usuario=2, id_token=11, id_rol=1)


@pytest.mark.integration
def test_concurrencia_optimista_edicion_especie_integration(db_session):
    especies_repo = SqlAlchemyEspecieRepository(db_session)
    auditoria_repo = SqlAlchemyAuditoriaEspecieRepository(db_session)
    uc = EditarEspecieUseCase(db=db_session, especies_repo=especies_repo, auditoria_repo=auditoria_repo)

    # 1. Lectura del estado original exacto para garantía de restauración (Punto 2)
    especie_original = especies_repo.obtener_por_id(5)
    assert especie_original is not None, "La especie id_especie=5 debe existir en la base de datos."
    
    nombre_original = especie_original.nombre.valor
    descripcion_original = especie_original.descripcion
    ts_v0 = especie_original.fecha_actualizacion

    assert ts_v0 is not None, "La especie id_especie=5 debe tener fecha_actualizacion poblada."

    try:
        # 2. Usuario A edita primero enviando ts_v0
        dto_a = EditarEspecieDTO(
            nombre="Mojarra Plateada Edit A Integration",
            descripcion="Modificacion por Usuario A",
            fecha_actualizacion=ts_v0,
        )
        especie_a = uc.execute(5, dto_a, USUARIO_A)
        assert especie_a.nombre.valor == "Mojarra Plateada Edit A Integration"
        
        ts_v1 = especie_a.fecha_actualizacion
        assert ts_v1 != ts_v0, "fecha_actualizacion debió actualizarse al guardar la edición A."

        # 3. Usuario B intenta editar usando el timestamp desactualizado ts_v0
        dto_b = EditarEspecieDTO(
            nombre="Mojarra Plateada Edit B Integration",
            descripcion="Modificacion por Usuario B",
            fecha_actualizacion=ts_v0,  # Obsoleto
        )

        with pytest.raises(PreconditionFailedError) as exc_info:
            uc.execute(5, dto_b, USUARIO_B)

        assert exc_info.value.code == "CONFLICTO_CONCURRENCIA"
        assert exc_info.value.status_code == 412

        # 4. Verificar que la versión A prevalece
        especie_actual = especies_repo.obtener_por_id(5)
        assert especie_actual.nombre.valor == "Mojarra Plateada Edit A Integration"
        assert especie_actual.descripcion == "Modificacion por Usuario A"

    finally:
        # 5. Teardown / Restauración Bloqueante (Punto 3)
        try:
            especie_post = especies_repo.obtener_por_id(5)
            if especie_post is not None and especie_post.nombre.valor != nombre_original:
                ts_restauracion = especie_post.fecha_actualizacion
                dto_restauracion = EditarEspecieDTO(
                    nombre=nombre_original,
                    descripcion=descripcion_original,
                    fecha_actualizacion=ts_restauracion,
                )
                especie_restaurada = uc.execute(5, dto_restauracion, USUARIO_A)
                assert especie_restaurada.nombre.valor == nombre_original, (
                    f"El nombre de la especie id=5 no se restauró a '{nombre_original}'"
                )
        except Exception as e_teardown:
            import sys
            import logging
            mensaje_error = f"[FALLO CRÍTICO DE RESTAURACIÓN] No se pudo restaurar la especie id=5 a '{nombre_original}': {e_teardown}"
            logging.critical(mensaje_error)
            print(f"\n{mensaje_error}", file=sys.stderr)
            raise RuntimeError(mensaje_error) from e_teardown

