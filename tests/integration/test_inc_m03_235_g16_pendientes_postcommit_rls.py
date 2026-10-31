# | Fecha      | Nombre | Que se hizo |
# |------------|--------|-------------|
# | 2026-10-31 | Claude | INC-M03-235-G16 RF-62: pendientes del postcommit en tiempo acotado bajo RLS |
"""INC-M03-235-G16 (#875): la evaluación de calidad automática (etapa RF62 del
postcommit) dejó de correr en TEST tras desplegar RLS en modulo3.

Con RLS la consulta de pendientes se volvía un anti-join cuadrático contra la
bitácora: con ~100 k lecturas evaluadas pasaba de 60 s y el worker la cancelaba a
los 10 s en cada ciclo. Esta prueba siembra 20 k lecturas ya evaluadas y exige que
la consulta, con el rol de la API y la identidad de servicio, termine bajo el mismo
``statement_timeout`` del worker y encuentre la lectura nueva.
"""
import pytest
from sqlalchemy import text

from src.shared.database import declarar_identidad_sistema
from src.telemetry.domain.repositories.postcommit_port import EtapaPostcommit
from src.telemetry.infrastructure.repositories.postcommit_repository import SqlAlchemyPostcommitRepository
from tests.integration.test_dev05_ingesta_bplus_postcommit import equipo, sql_ingesta  # noqa: F401

pytestmark = pytest.mark.integration

_LECTURAS_EVALUADAS = 20000


def test_pendientes_rf62_con_historial_grande_bajo_rls(db_session, equipo):
    if not db_session.execute(text('SELECT rolsuper FROM pg_roles WHERE rolname = current_user')).scalar_one():
        pytest.skip('La siembra masiva desactiva triggers (session_replication_role): requiere superusuario.')
    nueva = sql_ingesta(db_session, equipo).id_telemetria
    db_session.execute(text('SET LOCAL session_replication_role = replica'))
    db_session.execute(text('''INSERT INTO modulo3.telemetrias (id_sensor,id_variable,id_dispositivo_iot,valor_crudo,
            valor_ajustado,timestamp_captura,timestamp_procesamiento,origen,estado_calidad,calibrado,categoria_variable,
            unidad_medida,valor_agregado,tipo_dato,metadatos)
        SELECT id_sensor,id_variable,id_dispositivo_iot,valor_crudo,valor_ajustado,
               timestamp_captura - make_interval(secs => g),now(),origen,estado_calidad,calibrado,categoria_variable,
               unidad_medida,false,tipo_dato,'{}'
        FROM modulo3.telemetrias, generate_series(1, :n) g WHERE id_telemetria = :id'''),
        {'n': _LECTURAS_EVALUADAS, 'id': nueva})
    db_session.execute(text('''INSERT INTO modulo3.bitacora_auditoria_iot (tipo_evento,modulo,resultado,fecha_hora,
            severidad_log,hash_integridad,clasificacion_registro,retencion_aplicable,registro_incompleto,timestamp_registro,
            entidad_afectada_tipo,entidad_afectada_id)
        SELECT 'POSTCOMMIT_RF62_COMPLETADO',b.modulo,b.resultado,now(),b.severidad_log,b.hash_integridad,
               b.clasificacion_registro,b.retencion_aplicable,false,now(),'LECTURA',t.id_telemetria::text
        FROM modulo3.telemetrias t CROSS JOIN LATERAL (SELECT * FROM modulo3.bitacora_auditoria_iot LIMIT 1) b
        WHERE t.id_sensor = :s AND t.id_telemetria <> :id'''), {'s': equipo['sensor'], 'id': nueva})
    db_session.execute(text('SET LOCAL session_replication_role = origin'))
    db_session.execute(text('ANALYZE modulo3.telemetrias'))
    db_session.execute(text('ANALYZE modulo3.bitacora_auditoria_iot'))

    db_session.execute(text('SET LOCAL ROLE sgpmp_app'))
    try:
        declarar_identidad_sistema(db_session)
        db_session.execute(text("SELECT set_config('statement_timeout', '10000', true)"))
        repo = SqlAlchemyPostcommitRepository(db_session, None)
        pendientes = repo.pendientes(EtapaPostcommit.RF62, 50, 60, 86400)
    finally:
        db_session.execute(text("SELECT set_config('statement_timeout', '0', true)"))
        db_session.execute(text('RESET ROLE'))

    assert nueva in pendientes
