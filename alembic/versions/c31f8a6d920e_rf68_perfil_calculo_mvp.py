# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-30 | Leandro | INC-M04-221-G032 RF-68: persistir perfil de contagio y su historial sin alterar modos de despliegue ni RLS. |
# | 2026-10-31 | Arekkazu | INC-M04-221-G032 RF-68: encadena tras c3f1a9d27e48 para no dejar dos heads |
"""RF-65/RF-68: perfil ESTANDAR/MVP con historial append-only.

Revision ID: c31f8a6d920e
Revises: c3f1a9d27e48
Aplicar antes de desplegar el backend que mapea la nueva columna.
"""
from alembic import op

revision = 'c31f8a6d920e'
down_revision = 'c3f1a9d27e48'
branch_labels = None
depends_on = None

_TABLAS = (('configuraciones_motor_ia', 'ck_config_motor_perfil_contagio'),
           ('configuracion_ia_log', 'ck_config_log_perfil_contagio'))

_FUNCION_ANTERIOR = r"""
CREATE OR REPLACE FUNCTION modulo4.fn_rf65_log_configuracion_motor()
    RETURNS trigger
    LANGUAGE 'plpgsql'
    COST 100
    VOLATILE NOT LEAKPROOF
    SECURITY DEFINER
    SET search_path = pg_catalog, pg_temp
AS $BODY$
BEGIN
    INSERT INTO modulo4.configuracion_ia_log (
        id_configuracion_motor, operacion,
        tipo_modelo, umbral_riesgo_alto, umbral_alerta_critica,
        ventana_temporal_min, id_version_modelo_activa, modo_ejecucion,
        config_version,
        w_factor_sanitario, w_factor_ambiental, w_factor_densidad,
        temp_min_config, temp_max_config, hr_min_config, hr_max_config,
        densidad_maxima_config, es_activa,
        id_usuario_responsable, fecha_creacion_config,
        umbral_score_anomalia, versiones_activas_por_componente,
        id_usuario_cambio, fecha_cambio
    ) VALUES (
        OLD.id_configuracion_motor, TG_OP,
        OLD.tipo_modelo, OLD.umbral_riesgo_alto, OLD.umbral_alerta_critica,
        OLD.ventana_temporal_min, OLD.id_version_modelo_activa, OLD.modo_ejecucion,
        OLD.config_version,
        OLD.w_factor_sanitario, OLD.w_factor_ambiental, OLD.w_factor_densidad,
        OLD.temp_min_config, OLD.temp_max_config, OLD.hr_min_config, OLD.hr_max_config,
        OLD.densidad_maxima_config, OLD.es_activa,
        OLD.id_usuario_responsable, OLD.fecha_creacion,
        OLD.umbral_score_anomalia, OLD.versiones_activas_por_componente,
        CASE WHEN TG_OP = 'UPDATE' THEN NEW.id_usuario_responsable END,
        now()
    );

    RETURN NULL;  -- trigger AFTER: el valor de retorno se ignora
END;
$BODY$;
"""


def _funcion_historial(con_perfil: bool) -> str:
    """CREATE OR REPLACE conserva owner, privilegios, OID y los triggers existentes."""
    sql = _FUNCION_ANTERIOR
    if con_perfil:
        sql = sql.replace('        config_version,', '        config_version, perfil_calculo_contagio,')
        sql = sql.replace('        OLD.config_version,', '        OLD.config_version, OLD.perfil_calculo_contagio,')
    return sql


def upgrade() -> None:
    for tabla, constraint in _TABLAS:
        op.execute(f"ALTER TABLE modulo4.{tabla} ADD COLUMN perfil_calculo_contagio varchar(20) NOT NULL DEFAULT 'ESTANDAR'")
        op.execute(f"""ALTER TABLE modulo4.{tabla} ADD CONSTRAINT {constraint}
            CHECK (perfil_calculo_contagio IN ('ESTANDAR','MVP') AND
                (tipo_modelo::text = 'MODELO_RIESGO_CONTAGIO' OR perfil_calculo_contagio = 'ESTANDAR'))""")
    op.execute(_funcion_historial(True))
    op.execute("COMMENT ON COLUMN modulo4.configuraciones_motor_ia.perfil_calculo_contagio IS 'RF-68: ESTANDAR o MVP; perfil independiente de EDGE/HIBRIDO/SERVIDOR. MVP usa pesos por defecto y no usa cache.'")


def downgrade() -> None:
    op.execute(_funcion_historial(False))
    for tabla, constraint in reversed(_TABLAS):
        op.execute(f'ALTER TABLE modulo4.{tabla} DROP CONSTRAINT {constraint}')
        op.execute(f'ALTER TABLE modulo4.{tabla} DROP COLUMN perfil_calculo_contagio')
