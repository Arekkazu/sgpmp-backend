"""Prueba de Integración: Reversión Transaccional (Rollback) ante Fallo de Auditoría Obligatoria.

Módulo: M02 - Activos Biológicos
Requisito Funcional: RF-49 (CU11 - Asociación de sensores IoT a activos biológicos)
Caso de Prueba: TC-M02-151 (Caso Agrupado TC-M02-G86)
Entorno: TEST
Estrategia: In-process Monkeypatch sobre el repositorio de auditoría (sin modificación estructural de BD).
"""
import os
import sys

# Asegurar que la raíz del proyecto esté en sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import pytest
import psycopg2

os.environ["DATABASE_URL"] = os.getenv(
    "TEST_DB_URL",
    "postgresql://member_qa:qaSGP2026@158.69.200.27:5448/sgpmp_test"
)

from src.shared.database import get_db
from src.biological_assets.infrastructure.repositories.asociacion_sensor_activo_repository import (
    SqlAlchemyAsociacionSensorActivoRepository,
)
from src.biological_assets.infrastructure.repositories.activo_biologico_repository import (
    SqlAlchemyActivoBiologicoRepository,
)
from src.biological_assets.infrastructure.adapters.sensor_m09_adapter import SensorM09Adapter
from src.biological_assets.infrastructure.adapters.infraestructura_m09_adapter import InfraestructuraM09Adapter
from src.biological_assets.application.use_cases.gestion.asociar_sensor_activo_use_case import (
    AsociarSensorActivoUseCase,
)
from src.biological_assets.infrastructure.dto.asociar_sensor_activo_dto import AsociarSensorActivoDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual

ID_ACTIVO = 108
ID_SENSOR = 22
ID_DISPOSITIVO = 38
ID_INFRA = 3


def test_tc_m02_151_reversion_asociacion_fallo_auditoria(monkeypatch):
    """TC-M02-151: Revertir asociación completa si falla el registro de auditoría obligatoria.
    
    Verifica que:
    1. La operación captura la falla de auditoría obligatoria.
    2. La sesión ejecuta un rollback transaccional estricto.
    3. Ninguna fila queda persistida en modulo2.asociaciones_activos_sensores.
    4. NO se altera la estructura de la base de datos TEST (verificación pura por SELECT).
    """
    db = next(get_db())
    repo = SqlAlchemyAsociacionSensorActivoRepository(db)
    activo_repo = SqlAlchemyActivoBiologicoRepository(db)
    sensor_port = SensorM09Adapter(db)
    infra_port = InfraestructuraM09Adapter(db)

    # 1. Verificar estado inicial en la base de datos (solo lectura)
    conn_raw = db.connection().connection
    cur = conn_raw.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM modulo2.asociaciones_activos_sensores "
        "WHERE id_sensor = %s AND id_activo_biologico = %s AND estado_asociacion = 'ACTIVA';",
        (ID_SENSOR, ID_ACTIVO)
    )
    count_inicial = cur.fetchone()[0]
    assert count_inicial == 0, f"Precondición falló: sensor {ID_SENSOR} ya tiene asociación previa con activo {ID_ACTIVO}"

    # 2. Inyectar fallo simulado mediante monkeypatch in-process sobre registrar_auditoria
    def mock_registrar_auditoria_falla(*args, **kwargs):
        raise RuntimeError("SIMULATED_AUDIT_FAILURE_FOR_ROLLBACK_TEST: Servicio de auditoría no disponible.")

    monkeypatch.setattr(repo, "registrar_auditoria", mock_registrar_auditoria_falla)

    use_case = AsociarSensorActivoUseCase(
        db=db,
        repo=repo,
        activo_repo=activo_repo,
        sensor_port=sensor_port,
        infra_port=infra_port,
    )

    dto = AsociarSensorActivoDTO(
        tipo_activo="INDIVIDUAL",
        tipo_asociacion="DIRECTA",
        dispositivo_iot_id=ID_DISPOSITIVO,
        sensor_id=ID_SENSOR,
        id_infraestructura=ID_INFRA,
        motivo="Verificación de rollback ante fallo de auditoría TC-M02-151",
    )

    usuario = UsuarioActual(id_usuario=1, id_token=1, id_rol=1, id_estado_cuenta=1)

    # 3. Ejecutar y validar que el caso de uso captura y propaga el fallo
    with pytest.raises(RuntimeError) as exc_info:
        use_case.execute(ID_ACTIVO, dto, usuario)

    assert "SIMULATED_AUDIT_FAILURE_FOR_ROLLBACK_TEST" in str(exc_info.value), (
        "La excepción capturada no coincide con la falla de auditoría inyectada."
    )

    # 4. Verificación en la base de datos TEST mediante SELECT (sin DDL ni alteraciones)
    cur.execute(
        "SELECT COUNT(*) FROM modulo2.asociaciones_activos_sensores "
        "WHERE id_sensor = %s AND id_activo_biologico = %s;",
        (ID_SENSOR, ID_ACTIVO)
    )
    count_final = cur.fetchone()[0]

    # Aserción crítica de atomicidad / rollback
    assert count_final == 0, (
        f"FALLA DE ROLLBACK: Se encontró {count_final} asociación persistida en modulo2.asociaciones_activos_sensores "
        "a pesar de que el registro de auditoría obligatoria falló."
    )

    db.close()
