"""RFC-006/009/011: auditoría de calibración rechazada, taxonomía de modelos y cámaras

Revision ID: cf12e716a4ec
Revises: e4772c889450
Create Date: 2026-10-05

Una sola revisión para los tres RFC aprobados que tocan backend (la parte de
visión de M03 y la de IA poblacional de M04 quedan fuera, ver
anotaciones/RFC/implementacion_rfc006_rfc009_rfc011.md).

RFC-006 (RF-24 v1.1) — tipo de evento 29 CALIBRACION_RECHAZADA en
modulo1.eventos para auditar los intentos rechazados (mismo patrón que el 28).

RFC-009 (RF-20 v1.1, RF-65/69/70/73 v2.0):
- modulo4.enum_tipo_modelo pasa del eje tamaño al eje tipo de manejo. Los tres
  valores con equivalente directo se renombran (las filas siguen apuntando al
  mismo OID); ESPECIES_PEQUEÑAS -> MODELO_AVES, que es lo que el eje anterior
  agrupaba como "pequeñas". Se agregan MODELO_PORCINOS y MODELO_ACUICULTURA.
  Los CHECK comparan `tipo_modelo::text` para no usar los valores recién
  agregados dentro de la misma transacción (Postgres lo rechaza).
- configuraciones_motor_ia: umbral_riesgo_alto/umbral_alerta_critica solo
  aplican a INDIVIDUAL/META; POBLACIONAL usa umbral_score_anomalia y un mapa
  componente -> id_version (versiones_activas_por_componente).
- versiones_modelos y despliegues_ota: componente, y unicidad de la versión
  ACTIVO por (tipo_modelo, componente).
- modulo9.especies.tipo_modelo (familia de modelo de la especie) y
  modulo9.infraestructuras.tipo_modelo_asignado, base de la coherencia de RF-20.

RFC-011 (RF-21 v2.0) — categoría SENSOR|CAMARA en el catálogo de tipos, un
tipo CAMARA_VISION y los atributos de visión del dispositivo.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'cf12e716a4ec'
down_revision: Union[str, Sequence[str], None] = 'e4772c889450'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ID_TIPO_EVENTO = 29
NOMBRE_TIPO_EVENTO = "CALIBRACION_RECHAZADA"
ACCION_TIPO_EVENTO = "Intento de calibracion de sensor rechazado"  # varchar(50)

_RENOMBRES = (
    ("ESPECIES_PEQUEÑAS", "MODELO_AVES"),
    ("ESPECIES_MEDIANAS", "MODELO_ESPECIES_MEDIANAS"),
    ("ESPECIES_GRANDES", "MODELO_ESPECIES_GRANDES"),
    ("CONTAGIO", "MODELO_RIESGO_CONTAGIO"),
)
_POBLACIONALES = "('MODELO_AVES', 'MODELO_PORCINOS', 'MODELO_ACUICULTURA')"
_ASIGNABLES = (
    "('MODELO_AVES', 'MODELO_PORCINOS', 'MODELO_ACUICULTURA', "
    "'MODELO_ESPECIES_MEDIANAS', 'MODELO_ESPECIES_GRANDES')"
)
_COMPONENTES = "('DETECTOR', 'SEGUIMIENTO', 'METRICAS', 'ANOMALIAS')"


def upgrade() -> None:
    # ── RFC-006 ────────────────────────────────────────────────────────────
    op.execute(
        f"""
        INSERT INTO modulo1.tipos_eventos (id_tipo_evento, nombre, accion)
        SELECT {ID_TIPO_EVENTO}, '{NOMBRE_TIPO_EVENTO}', '{ACCION_TIPO_EVENTO}'
        WHERE NOT EXISTS (
            SELECT 1 FROM modulo1.tipos_eventos
            WHERE id_tipo_evento = {ID_TIPO_EVENTO} OR nombre = '{NOMBRE_TIPO_EVENTO}'
        )
        """
    )
    op.execute(
        "SELECT setval('modulo1.tipos_evento_id_tipo_evento_seq', "
        "(SELECT max(id_tipo_evento) FROM modulo1.tipos_eventos))"
    )

    # ── RFC-009: enum de tipo_modelo ───────────────────────────────────────
    for viejo, nuevo in _RENOMBRES:
        op.execute(f"ALTER TYPE modulo4.enum_tipo_modelo RENAME VALUE '{viejo}' TO '{nuevo}'")
    op.execute("ALTER TYPE modulo4.enum_tipo_modelo ADD VALUE IF NOT EXISTS 'MODELO_PORCINOS'")
    op.execute("ALTER TYPE modulo4.enum_tipo_modelo ADD VALUE IF NOT EXISTS 'MODELO_ACUICULTURA'")

    # ── RF-65: umbrales por paradigma ──────────────────────────────────────
    op.execute(
        f"""
        ALTER TABLE modulo4.configuraciones_motor_ia
            ALTER COLUMN umbral_riesgo_alto DROP NOT NULL,
            ALTER COLUMN umbral_riesgo_alto DROP DEFAULT,
            ALTER COLUMN umbral_alerta_critica DROP NOT NULL,
            ALTER COLUMN umbral_alerta_critica DROP DEFAULT,
            ADD COLUMN umbral_score_anomalia NUMERIC(4, 3),
            ADD COLUMN versiones_activas_por_componente JSONB,
            ADD CONSTRAINT ck_configuracion_motor_umbral_score_anomalia_rango
                CHECK (umbral_score_anomalia BETWEEN 0 AND 1);

        -- Una configuración heredada de ESPECIES_PEQUEÑAS ya es MODELO_AVES
        -- (POBLACIONAL): su umbral de riesgo pasa a ser el de anomalía.
        UPDATE modulo4.configuraciones_motor_ia
           SET umbral_score_anomalia = umbral_riesgo_alto,
               umbral_riesgo_alto = NULL,
               umbral_alerta_critica = NULL
         WHERE tipo_modelo::text IN {_POBLACIONALES};

        ALTER TABLE modulo4.configuraciones_motor_ia
            ADD CONSTRAINT ck_configuracion_motor_umbrales_por_paradigma CHECK (
                CASE WHEN tipo_modelo::text IN {_POBLACIONALES}
                     THEN umbral_score_anomalia IS NOT NULL
                          AND umbral_riesgo_alto IS NULL
                          AND umbral_alerta_critica IS NULL
                          AND id_version_modelo_activa IS NULL
                     ELSE umbral_riesgo_alto IS NOT NULL
                          AND umbral_alerta_critica IS NOT NULL
                          AND umbral_score_anomalia IS NULL
                          AND versiones_activas_por_componente IS NULL
                END
            );
        """
    )

    # ── RF-69 / RF-70: componente y unicidad (tipo_modelo, componente) ─────
    op.execute(
        f"""
        ALTER TABLE modulo4.versiones_modelos
            ADD COLUMN componente VARCHAR(20),
            ADD COLUMN metricas_poblacionales JSONB,
            ADD CONSTRAINT ck_version_modelo_componente CHECK (componente IN {_COMPONENTES});

        CREATE UNIQUE INDEX uq_version_modelo_activa_tipo_componente
            ON modulo4.versiones_modelos (tipo_modelo, COALESCE(componente, ''))
            WHERE estado_version = 'ACTIVO';

        ALTER TABLE modulo4.despliegues_ota
            ADD COLUMN componente VARCHAR(20),
            ADD CONSTRAINT ck_despliegue_ota_componente CHECK (componente IN {_COMPONENTES});
        """
    )

    # ── RF-15 / RF-20: familia de modelo de la especie y modelo del área ───
    op.execute(
        f"""
        ALTER TABLE modulo9.especies
            ADD COLUMN tipo_modelo VARCHAR(30),
            ADD CONSTRAINT ck_especie_tipo_modelo CHECK (tipo_modelo IN {_ASIGNABLES});

        ALTER TABLE modulo9.infraestructuras
            ADD COLUMN tipo_modelo_asignado VARCHAR(30),
            ADD CONSTRAINT ck_infraestructura_tipo_modelo_asignado
                CHECK (tipo_modelo_asignado IN {_ASIGNABLES});
        """
    )

    # ── RFC-011 / RF-21: categoría CAMARA y atributos de visión ────────────
    op.execute(
        """
        ALTER TABLE modulo9.tipos_dispositivo_iot
            ADD COLUMN categoria VARCHAR(10) NOT NULL DEFAULT 'SENSOR',
            ADD CONSTRAINT ck_tipo_dispositivo_iot_categoria CHECK (categoria IN ('SENSOR', 'CAMARA'));

        INSERT INTO modulo9.tipos_dispositivo_iot (
            nombre, categoria,
            frecuencia_captura_min, frecuencia_captura_max,
            intervalo_transmision_min, intervalo_transmision_max
        )
        SELECT 'CAMARA_VISION', 'CAMARA', 1, 1440, 1, 1440
        WHERE NOT EXISTS (SELECT 1 FROM modulo9.tipos_dispositivo_iot WHERE nombre = 'CAMARA_VISION');

        ALTER TABLE modulo9.dispositivos_iot
            ADD COLUMN resolucion VARCHAR(20),
            ADD COLUMN fps SMALLINT,
            ADD COLUMN area_cobertura_m2 NUMERIC(10, 2),
            ADD CONSTRAINT ck_dispositivo_iot_resolucion CHECK (resolucion ~ '^[0-9]+x[0-9]+$'),
            ADD CONSTRAINT ck_dispositivo_iot_fps CHECK (fps BETWEEN 1 AND 60),
            ADD CONSTRAINT ck_dispositivo_iot_area_cobertura CHECK (area_cobertura_m2 > 0);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE modulo9.dispositivos_iot
            DROP COLUMN area_cobertura_m2,
            DROP COLUMN fps,
            DROP COLUMN resolucion;
        DELETE FROM modulo9.tipos_dispositivo_iot t
         WHERE t.nombre = 'CAMARA_VISION'
           AND NOT EXISTS (
               SELECT 1 FROM modulo9.dispositivos_iot d
                WHERE d.id_tipo_dispositivo = t.id_tipo_dispositivo
           );
        ALTER TABLE modulo9.tipos_dispositivo_iot DROP COLUMN categoria;

        ALTER TABLE modulo9.infraestructuras DROP COLUMN tipo_modelo_asignado;
        ALTER TABLE modulo9.especies DROP COLUMN tipo_modelo;

        ALTER TABLE modulo4.despliegues_ota DROP COLUMN componente;
        DROP INDEX modulo4.uq_version_modelo_activa_tipo_componente;
        ALTER TABLE modulo4.versiones_modelos
            DROP COLUMN metricas_poblacionales,
            DROP COLUMN componente;

        ALTER TABLE modulo4.configuraciones_motor_ia
            DROP CONSTRAINT ck_configuracion_motor_umbrales_por_paradigma;
        UPDATE modulo4.configuraciones_motor_ia
           SET umbral_riesgo_alto = umbral_score_anomalia,
               umbral_alerta_critica = umbral_score_anomalia
         WHERE umbral_riesgo_alto IS NULL;
        ALTER TABLE modulo4.configuraciones_motor_ia
            DROP COLUMN versiones_activas_por_componente,
            DROP COLUMN umbral_score_anomalia,
            ALTER COLUMN umbral_riesgo_alto SET DEFAULT 0.700,
            ALTER COLUMN umbral_riesgo_alto SET NOT NULL,
            ALTER COLUMN umbral_alerta_critica SET DEFAULT 0.700,
            ALTER COLUMN umbral_alerta_critica SET NOT NULL;
        """
    )
    # Postgres no permite quitar valores de un enum: MODELO_PORCINOS y
    # MODELO_ACUICULTURA quedan en el tipo. Solo se revierten los nombres.
    for viejo, nuevo in reversed(_RENOMBRES):
        op.execute(f"ALTER TYPE modulo4.enum_tipo_modelo RENAME VALUE '{nuevo}' TO '{viejo}'")

    op.execute(
        f"""
        DELETE FROM modulo1.tipos_eventos
        WHERE id_tipo_evento = {ID_TIPO_EVENTO}
          AND NOT EXISTS (SELECT 1 FROM modulo1.eventos WHERE tipo_evento = {ID_TIPO_EVENTO})
        """
    )
