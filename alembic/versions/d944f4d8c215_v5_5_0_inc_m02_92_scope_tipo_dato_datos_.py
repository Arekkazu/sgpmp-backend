"""v5.5.0_inc_m02_92_scope_tipo_dato_datos_consolidados

Revision ID: d944f4d8c215
Revises: c8d4f1a9b7e2
Create Date: 2026-09-22 22:48:25.020786

INC-M02-92-G93 / issue #390: RF-50 exige "permisos y scopes definidos" por
``tipo_dato`` sobre GET /activos-biologicos/{id}/datos-consolidados, y su
flujo alterno #4 documenta un 403 específico para "el módulo solicitante no
tiene autorización para consumir datos de tipo [TIPO_DATO]". La RBAC vigente
solo evaluaba (recurso=29, accion=R) a nivel de endpoint completo, sin
granularidad por tipo_dato -- no existía forma de construir la precondición
que exige TC-M02-155 (credencial válida + scope general + scope de un
tipo_dato específico ausente).

Se agregan 4 recursos nuevos (uno por tipo_dato: eventos, fases, estado,
metricas) y se siembran los permisos correspondientes:

- Los 4 roles humanos que hoy ya leen el endpoint completo vía recurso 29/R
  (Administrador, Productor, Veterinario, Ingeniero de Campo) reciben los 4
  scopes, para no regresionar el acceso que ya tienen.
- Se reaplica el bloque de INC-M02-90-G92 (identidad técnica 'Integración
  M04'), documentado pero nunca ejecutado contra esta base -- confirmado
  vía MCP postgres que el rol no existe en sgpmp_dev (roles van 1-11 y 14).
- 'Integración M04' recibe scope en 3 de los 4 tipo_dato (eventos, fases,
  estado). 'metricas' queda deliberadamente SIN scope: es la precondición
  real que TC-M02-155 necesita para verificar el 403 sin que QA tenga que
  fabricar nada.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'd944f4d8c215'
down_revision: Union[str, Sequence[str], None] = 'c8d4f1a9b7e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE
            v_rec_eventos    INT;
            v_rec_fases      INT;
            v_rec_estado     INT;
            v_rec_metricas   INT;
            v_id_rol_m04     INT;
            v_id_usuario_m04 INT;
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM modulo1.recursos
                WHERE id_recurso = 29 AND lower(btrim(nombre_recurso)) = 'activos_biologicos'
            ) THEN
                RAISE EXCEPTION 'INC-M02-92-G93: id_recurso=29 no corresponde a activos_biologicos';
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM modulo1.acciones
                WHERE id_accion = 2 AND upper(btrim(codigo)) = 'R'
            ) THEN
                RAISE EXCEPTION 'INC-M02-92-G93: id_accion=2 no corresponde a Leer (R)';
            END IF;

            -- Guarda de seguridad: en sgpmp_dev la secuencia de id_recurso
            -- quedó desincronizada por debajo del máximo real ya sembrado
            -- (confirmado en vivo: last_value=54 con filas hasta id_recurso=58,
            -- sin huecos -- probablemente datos de baseline insertados con ID
            -- explícito, sin `setval` posterior). Sin este resync, el primer
            -- INSERT de abajo fallaría por violación de PK. Es seguro e
            -- idempotente: solo avanza la secuencia a la realidad de la tabla.
            PERFORM setval(
                'modulo1.recursos_id_recurso_seq',
                (SELECT MAX(id_recurso) FROM modulo1.recursos),
                true
            );

            -- 1) Recursos de scope por tipo_dato (RF-50, entrada `tipo_dato`:
            -- eventos | fases | estado | metricas).
            INSERT INTO modulo1.recursos (nombre_recurso, descripcion, es_proceso_especial)
            VALUES ('datos_analiticos_eventos', 'RF-50: scope de lectura del historial de eventos biológicos en datos-consolidados.', FALSE)
            ON CONFLICT (nombre_recurso) DO NOTHING;
            SELECT id_recurso INTO v_rec_eventos FROM modulo1.recursos WHERE nombre_recurso = 'datos_analiticos_eventos';

            INSERT INTO modulo1.recursos (nombre_recurso, descripcion, es_proceso_especial)
            VALUES ('datos_analiticos_fases', 'RF-50: scope de lectura del historial de fases productivas en datos-consolidados.', FALSE)
            ON CONFLICT (nombre_recurso) DO NOTHING;
            SELECT id_recurso INTO v_rec_fases FROM modulo1.recursos WHERE nombre_recurso = 'datos_analiticos_fases';

            INSERT INTO modulo1.recursos (nombre_recurso, descripcion, es_proceso_especial)
            VALUES ('datos_analiticos_estado', 'RF-50: scope de lectura del estado operativo y su fecha de cambio en datos-consolidados.', FALSE)
            ON CONFLICT (nombre_recurso) DO NOTHING;
            SELECT id_recurso INTO v_rec_estado FROM modulo1.recursos WHERE nombre_recurso = 'datos_analiticos_estado';

            INSERT INTO modulo1.recursos (nombre_recurso, descripcion, es_proceso_especial)
            VALUES ('datos_analiticos_metricas', 'RF-50: scope de lectura de métricas derivadas (peso, biomasa, indicadores) en datos-consolidados.', FALSE)
            ON CONFLICT (nombre_recurso) DO NOTHING;
            SELECT id_recurso INTO v_rec_metricas FROM modulo1.recursos WHERE nombre_recurso = 'datos_analiticos_metricas';

            -- 2) Preservar el acceso de facto de los 4 roles humanos que hoy ya
            -- leen datos-consolidados completo vía recurso 29/R. Sin este paso,
            -- activar el scope los dejaría con 403 en un endpoint que hoy
            -- funciona para ellos. Los permisos 'admin_*' son inmutables una
            -- vez insertados (trg_fn_proteger_permisos_admin_update/_delete),
            -- por eso usan DO NOTHING en vez de DO UPDATE -- igual que el
            -- precedente de f2c84d91a6e7 (RF-12).
            INSERT INTO modulo1.permisos (nombre, descripcion, id_rol, id_recurso, id_accion, es_activo)
            VALUES
                ('admin_leer_datos_analiticos_eventos', 'RF-50: scope eventos de datos-consolidados para Administrador.', 1, v_rec_eventos, 2, TRUE),
                ('admin_leer_datos_analiticos_fases', 'RF-50: scope fases de datos-consolidados para Administrador.', 1, v_rec_fases, 2, TRUE),
                ('admin_leer_datos_analiticos_estado', 'RF-50: scope estado de datos-consolidados para Administrador.', 1, v_rec_estado, 2, TRUE),
                ('admin_leer_datos_analiticos_metricas', 'RF-50: scope metricas de datos-consolidados para Administrador.', 1, v_rec_metricas, 2, TRUE)
            ON CONFLICT (id_rol, id_recurso, id_accion) DO NOTHING;

            INSERT INTO modulo1.permisos (nombre, descripcion, id_rol, id_recurso, id_accion, es_activo)
            VALUES
                ('prod_leer_datos_analiticos_eventos', 'RF-50: scope eventos de datos-consolidados para Productor.', 2, v_rec_eventos, 2, TRUE),
                ('prod_leer_datos_analiticos_fases', 'RF-50: scope fases de datos-consolidados para Productor.', 2, v_rec_fases, 2, TRUE),
                ('prod_leer_datos_analiticos_estado', 'RF-50: scope estado de datos-consolidados para Productor.', 2, v_rec_estado, 2, TRUE),
                ('prod_leer_datos_analiticos_metricas', 'RF-50: scope metricas de datos-consolidados para Productor.', 2, v_rec_metricas, 2, TRUE),
                ('vet_leer_datos_analiticos_eventos', 'RF-50: scope eventos de datos-consolidados para Veterinario.', 3, v_rec_eventos, 2, TRUE),
                ('vet_leer_datos_analiticos_fases', 'RF-50: scope fases de datos-consolidados para Veterinario.', 3, v_rec_fases, 2, TRUE),
                ('vet_leer_datos_analiticos_estado', 'RF-50: scope estado de datos-consolidados para Veterinario.', 3, v_rec_estado, 2, TRUE),
                ('vet_leer_datos_analiticos_metricas', 'RF-50: scope metricas de datos-consolidados para Veterinario.', 3, v_rec_metricas, 2, TRUE),
                ('ing_leer_datos_analiticos_eventos', 'RF-50: scope eventos de datos-consolidados para Ingeniero de Campo.', 4, v_rec_eventos, 2, TRUE),
                ('ing_leer_datos_analiticos_fases', 'RF-50: scope fases de datos-consolidados para Ingeniero de Campo.', 4, v_rec_fases, 2, TRUE),
                ('ing_leer_datos_analiticos_estado', 'RF-50: scope estado de datos-consolidados para Ingeniero de Campo.', 4, v_rec_estado, 2, TRUE),
                ('ing_leer_datos_analiticos_metricas', 'RF-50: scope metricas de datos-consolidados para Ingeniero de Campo.', 4, v_rec_metricas, 2, TRUE)
            ON CONFLICT (id_rol, id_recurso, id_accion) DO UPDATE
                SET nombre = EXCLUDED.nombre, descripcion = EXCLUDED.descripcion, es_activo = TRUE;

            -- 3) Identidad técnica M04 (INC-M02-90-G92): reaplica el bloque que
            -- ese incidente dejó documentado como "pendiente -- no aplicable
            -- desde este entorno". Nunca se ejecutó contra sgpmp_dev. Idempotente:
            -- si ya existe (ej. aplicado manualmente por un DBA), no la toca.
            IF NOT EXISTS (
                SELECT 1 FROM modulo1.roles WHERE lower(btrim(nombre_rol)) = 'integración m04'
            ) THEN
                INSERT INTO modulo1.roles (nombre_rol, descripcion, es_protegido)
                VALUES (
                    'Integración M04',
                    'Identidad técnica de solo lectura para que el módulo 4 (analítica/predicción) consuma los endpoints analíticos de M02 (RF-50 datos-consolidados, RF-51 indicadores). Creado para INC-M02-90-G92, aplicado en INC-M02-92-G93.',
                    FALSE
                )
                RETURNING id_rol INTO v_id_rol_m04;

                INSERT INTO modulo1.permisos (nombre, descripcion, id_rol, id_recurso, id_accion, es_activo)
                VALUES (
                    'm04_leer_activo_biologico',
                    'Lectura de indicadores y datos consolidados de activos biológicos para consumo del módulo 4 (RF-50/RF-51).',
                    v_id_rol_m04, 29, 2, TRUE
                );

                -- Contraseña aleatoria: nunca se hardcodea un secreto en un
                -- script versionado. Quien active esta identidad la rota
                -- después por un canal seguro (ver inc_m02_90_g92_identidad_m04.md).
                INSERT INTO modulo1.usuarios (nombre, apellidos, correo_electronico, contrasena_cifrada, id_rol)
                VALUES (
                    'Integración', 'Módulo Cuatro', 'integracion.m04.test@pecuaria.co',
                    crypt(gen_random_uuid()::text || gen_random_uuid()::text, gen_salt('bf', 12)), v_id_rol_m04
                )
                RETURNING id_usuario INTO v_id_usuario_m04;

                INSERT INTO modulo1.cuentas_usuarios (id_usuario, id_estado_cuenta, tiene_correo_verificado)
                VALUES (v_id_usuario_m04, 2, TRUE);
            ELSE
                SELECT id_rol INTO v_id_rol_m04 FROM modulo1.roles WHERE lower(btrim(nombre_rol)) = 'integración m04';
            END IF;

            -- 4) Fixture de prueba para TC-M02-155 (INC-M02-92-G93): M04 recibe
            -- scope en 3 de los 4 tipo_dato -- 'metricas' queda deliberadamente
            -- SIN scope para que QA tenga una precondición real y ejecutable
            -- ("módulo autenticado = sí, scope general = sí, scope del
            -- tipo_dato solicitado = no") sin fabricar nada manualmente.
            INSERT INTO modulo1.permisos (nombre, descripcion, id_rol, id_recurso, id_accion, es_activo)
            VALUES
                ('m04_leer_datos_analiticos_eventos', 'RF-50: scope eventos de datos-consolidados para Integración M04.', v_id_rol_m04, v_rec_eventos, 2, TRUE),
                ('m04_leer_datos_analiticos_fases', 'RF-50: scope fases de datos-consolidados para Integración M04.', v_id_rol_m04, v_rec_fases, 2, TRUE),
                ('m04_leer_datos_analiticos_estado', 'RF-50: scope estado de datos-consolidados para Integración M04.', v_id_rol_m04, v_rec_estado, 2, TRUE)
            ON CONFLICT (id_rol, id_recurso, id_accion) DO UPDATE
                SET nombre = EXCLUDED.nombre, descripcion = EXCLUDED.descripcion, es_activo = TRUE;
        END
        $$;
        """
    )


def downgrade() -> None:
    """No-op intencional: los permisos ``admin_*`` sembrados en ``upgrade()``

    son inmutables en la BD (``trg_fn_proteger_permisos_admin_delete`` y
    ``trg_fn_proteger_permisos_admin_update`` rechazan cualquier DELETE/UPDATE
    sobre un nombre que empiece con ``admin_``, sin excepción para cascadas de
    FK) -- mismo patrón documentado en el downgrade de f2c84d91a6e7 (RF-12).

    Como esos 4 permisos quedan referenciando los 4 recursos nuevos de forma
    permanente, `fk_recurso_permiso` (sin ON DELETE) tampoco permite borrar
    los recursos. Revertir solo las filas no-admin (prod/vet/ing/m04 y la
    identidad M04) dejaría un estado híbrido inconsistente -- se prefiere
    conservar todo el seed completo. Es idempotente, así que reaplicar
    ``upgrade()`` no duplica datos.
    """
