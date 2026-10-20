"""DB-04 (RF-70/RF-73): distribuciones OTA, fases de rollout y firma del artefacto (DEV-15)

Revision ID: c41f8e2d7a96
Revises: ad5cb8644adb
Create Date: 2026-10-19 23:00:00

Segunda parte de DB-04 (tarea Taiga #3556): el esquema que el orquestador OTA
de DEV-15 (#604) ya lee y escribe. La primera parte (b3d4f69e9303) dejó el
índice único del despliegue en curso.

- `modulo4.distribuciones_ota`: una fila por `POST /prediccion/ota/distribuciones`
  (versión, nodos, modo, ventana, batería mínima, fragmento, reintentos) con su
  fase de rollout (`CANARY` → `PARCIAL` → `TOTAL`) y su estado (`EN_CURSO`,
  `COMPLETADA`, `DETENIDA`). `tipo_modelo` y `modo_distribucion` reutilizan los
  ENUM que ya usa `despliegues_ota`; `componente`, la fase y el estado van como
  VARCHAR con CHECK, igual que `componente` en RFC-009 y como los mapea el ORM.
  `ventana_inicio`/`ventana_fin` conservan el nombre de las columnas homónimas
  de `despliegues_ota` en vez del prefijo `fecha_`.
- `despliegues_ota`: `id_distribucion_ota` (FK, nullable: las filas anteriores
  no tienen distribución), `fase_rollout`, `fecha_expiracion_url` (vencimiento
  de la URL firmada) e `id_mensaje_notify` (id del aviso `ota/notify` de BRK-08).
- `versiones_modelos.firma_artefacto`: la firma que viaja en el aviso. No entra
  en la lista de `trg_fn_versiones_modelos_inmutabilidad` (que solo protege
  las columnas que enumera), así que se puede completar después de registrar
  la versión.
- Permiso `admin_ejecutar_ota_status` (Administrador, recurso 44, Ejecutar)
  para lanzar la distribución. El downgrade no lo puede borrar
  (`trg_fn_proteger_permisos_admin_delete`): queda, y un upgrade posterior lo
  reutiliza (`ON CONFLICT DO NOTHING`).

Sin RLS, como el resto de `modulo4`.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'c41f8e2d7a96'
down_revision: Union[str, Sequence[str], None] = 'ad5cb8644adb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Mismos roles de BD que en e3b8c1d9f702; solo los que existan.
_ROLES_APP = "('sgpmp_app', 'rol_app', 'rol_dev', 'rol_impl', 'rol_migracion')"
_COMPONENTES = "('DETECTOR', 'SEGUIMIENTO', 'METRICAS', 'ANOMALIAS')"
_FASES = "('CANARY', 'PARCIAL', 'TOTAL')"


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE modulo4.distribuciones_ota (
            id_distribucion_ota SERIAL,
            id_version_modelo INTEGER NOT NULL,
            tipo_modelo modulo4.enum_tipo_modelo NOT NULL,
            componente VARCHAR(20),
            modo_distribucion modulo4.enum_modo_distribucion_ota NOT NULL,
            ventana_inicio TIMESTAMPTZ,
            ventana_fin TIMESTAMPTZ,
            nivel_bateria_minimo NUMERIC(5,2),
            tamano_fragmento_bytes INTEGER NOT NULL,
            max_reintentos_descarga INTEGER NOT NULL,
            fase_rollout VARCHAR(10) NOT NULL DEFAULT 'CANARY',
            porcentaje_parcial SMALLINT,
            estado_distribucion VARCHAR(15) NOT NULL DEFAULT 'EN_CURSO',
            id_usuario INTEGER NOT NULL,
            fecha_creacion TIMESTAMPTZ NOT NULL DEFAULT now(),
            fecha_actualizacion TIMESTAMPTZ,
            CONSTRAINT distribuciones_ota_pkey PRIMARY KEY (id_distribucion_ota),
            CONSTRAINT distribuciones_ota_id_version_modelo_fkey
                FOREIGN KEY (id_version_modelo) REFERENCES modulo4.versiones_modelos (id_version_modelo)
                ON DELETE RESTRICT ON UPDATE CASCADE,
            CONSTRAINT distribuciones_ota_id_usuario_fkey
                FOREIGN KEY (id_usuario) REFERENCES modulo1.usuarios (id_usuario)
                ON DELETE RESTRICT ON UPDATE CASCADE,
            CONSTRAINT ck_distribucion_ota_componente CHECK (componente IN {_COMPONENTES}),
            CONSTRAINT ck_distribucion_ota_fase_rollout CHECK (fase_rollout IN {_FASES}),
            CONSTRAINT ck_distribucion_ota_estado_distribucion
                CHECK (estado_distribucion IN ('EN_CURSO', 'COMPLETADA', 'DETENIDA')),
            CONSTRAINT ck_distribucion_ota_nivel_bateria_minimo
                CHECK (nivel_bateria_minimo BETWEEN 0 AND 100),
            CONSTRAINT ck_distribucion_ota_tamano_fragmento_bytes CHECK (tamano_fragmento_bytes > 0),
            CONSTRAINT ck_distribucion_ota_max_reintentos_descarga CHECK (max_reintentos_descarga >= 0),
            CONSTRAINT ck_distribucion_ota_porcentaje_parcial CHECK (porcentaje_parcial BETWEEN 20 AND 30),
            CONSTRAINT ck_distribucion_ota_ventana CHECK (ventana_fin IS NULL OR ventana_inicio IS NULL
                                                          OR ventana_fin > ventana_inicio)
        )
    """)
    op.execute("""
        COMMENT ON TABLE modulo4.distribuciones_ota IS
        'DEV-15 (RF-70/RF-73, D6): una distribución OTA de un (tipo_modelo, componente) a varios nodos '
        'y su rollout por fases. Cada nodo es una fila de despliegues_ota.'
    """)

    op.execute(f"""
        ALTER TABLE modulo4.despliegues_ota
            ADD COLUMN id_distribucion_ota INTEGER,
            ADD COLUMN fase_rollout VARCHAR(10),
            ADD COLUMN fecha_expiracion_url TIMESTAMPTZ,
            ADD COLUMN id_mensaje_notify VARCHAR(32),
            ADD CONSTRAINT despliegues_ota_id_distribucion_ota_fkey
                FOREIGN KEY (id_distribucion_ota) REFERENCES modulo4.distribuciones_ota (id_distribucion_ota)
                ON DELETE RESTRICT ON UPDATE CASCADE,
            ADD CONSTRAINT ck_despliegue_ota_fase_rollout CHECK (fase_rollout IN {_FASES})
    """)
    # El avance de fase lista los despliegues de una distribución en cada reporte.
    op.execute("CREATE INDEX idx_despliegue_ota_id_distribucion_ota ON modulo4.despliegues_ota (id_distribucion_ota)")

    op.execute("ALTER TABLE modulo4.versiones_modelos ADD COLUMN firma_artefacto TEXT")

    op.execute(f"""
        DO $$
        DECLARE r text;
        BEGIN
            FOR r IN SELECT rolname FROM pg_roles WHERE rolname IN {_ROLES_APP} LOOP
                EXECUTE format('GRANT INSERT, SELECT, UPDATE ON modulo4.distribuciones_ota TO %I', r);
                EXECUTE format(
                    'GRANT USAGE, SELECT ON SEQUENCE modulo4.distribuciones_ota_id_distribucion_ota_seq TO %I', r
                );
            END LOOP;
        END $$;
    """)

    op.execute("""
        DO $$
        BEGIN
            PERFORM set_config('app.current_role', 'Administrador', true);
            PERFORM set_config('app.current_user_id', '1', true);
            INSERT INTO modulo1.permisos (nombre, descripcion, id_rol, id_recurso, id_accion, es_activo)
            VALUES ('admin_ejecutar_ota_status',
                    'Administrador lanza una distribución OTA de un modelo a los nodos Edge (RF-70).',
                    1, 44, 5, TRUE)
            ON CONFLICT (id_rol, id_recurso, id_accion) DO NOTHING;
        END
        $$;
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE modulo4.versiones_modelos DROP COLUMN firma_artefacto")
    op.execute("DROP INDEX modulo4.idx_despliegue_ota_id_distribucion_ota")
    op.execute("""
        ALTER TABLE modulo4.despliegues_ota
            DROP CONSTRAINT ck_despliegue_ota_fase_rollout,
            DROP CONSTRAINT despliegues_ota_id_distribucion_ota_fkey,
            DROP COLUMN id_mensaje_notify,
            DROP COLUMN fecha_expiracion_url,
            DROP COLUMN fase_rollout,
            DROP COLUMN id_distribucion_ota
    """)
    op.execute("DROP TABLE modulo4.distribuciones_ota")
