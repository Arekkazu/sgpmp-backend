"""v5.4.0_rf36_eventos_ingresos_lote

Revision ID: 2848535f94f5
Revises: c8d4f1a9b7e2
Create Date: 2026-09-23 03:00:00.000000

Tarea Taiga "RF-36: Ficha de gestión de lote, densidad máxima, ingreso de
individuos". RF-36 exige un mecanismo de ingreso/alta de individuos al lote
("cantidad_actual se modifica únicamente mediante eventos de tipo BAJA o
mediante registros de ingresos asociados a eventos"), pero solo existía el
flujo de BAJA (`modulo2.eventos_bajas`) — confirmado en vivo vía MCP Postgres
que no existe ninguna tabla `eventos_ingresos` ni enum relacionado en
`sgpmp_dev`.

Se agrega `modulo2.eventos_ingresos`, mismo patrón que `eventos_bajas`
(sub-tabla 1:1 de `modulo2.eventos_activos`, FK como PK). El tipo de ingreso
reutiliza exactamente los 4 valores de `origen_financiero` que ya usa el
registro inicial del activo (`compra`, `nacimiento`, `donacion`,
`transferencia_interna`) — mismas categorías, ahora aplicables también a
altas posteriores sobre un lote ya existente.

No requiere cambios de RBAC: `POST /{id}/eventos/ingreso` reutiliza
`(recurso 29, acción C=1)`, el mismo par que ya usa `POST /{id}/eventos/baja`
— confirmado en vivo que Administrador, Productor, Veterinario e Ingeniero
de Campo ya lo tienen los cuatro.

Segundo gap de BD encontrado al verificar en vivo (bloqueante para que el
ingreso funcione en absoluto): `modulo2.detalles_activos_biologicos_poblacionales`
tiene el CHECK `chk_poblacional_cantidad_actual_coherente = (cantidad_actual
<= cantidad_inicial)` -- una regla escrita bajo el supuesto de que
`cantidad_actual` solo podía DECRECER desde `cantidad_inicial` (vía baja),
nunca crecer. Confirmado en vivo: un ingreso real sobre un lote con
`cantidad_inicial=500` fallaba con `CheckViolation` al intentar dejar
`cantidad_actual=550`. Se elimina ese CHECK -- el piso ya lo garantiza
`chk_poblacional_cantidad_actual_no_negativa` (`cantidad_actual >= 0`,
se conserva), y el techo real (`densidad_maxima_por_especie`) no es una
regla de tabla simple: depende de `capacidad_maxima`/`superficie` de la
infraestructura donde reside el lote, así que se aplica a nivel de
aplicación (`RegistrarEventoIngresoUseCase`), igual que ya hace
INC-M02-38-G25 para eventos de crecimiento.

Tercer gap encontrado al verificar en vivo: la ficha de lote de RF-36 reutiliza
`SqlAlchemyTransferenciaRepository.consultar_historial()` (mismo método que ya
usa RF-46/RF-48) para su campo "historial", y ese método nunca podía mostrar
eventos de tipo INGRESO -- no por la vista, sino porque su set
`categorias_a_consultar` (`src/biological_assets/infrastructure/repositories/
transferencia_repository.py`) jamás incluyó `'INGRESO'` como categoría (no
existía hasta esta migración). Investigación en vivo inicial sugirió además
que `eventos_bajas` faltaba en `modulo2.vw_rf46_historial_completo_activo`,
pero eso resultó ser un diagnóstico equivocado: BAJA nunca dependió de esa
vista -- se resuelve aparte contra `modulo2.vw_rf46_eventos_bajas`, una vista
dedicada ya existente que el mismo repository consulta en un bloque separado
(`consultar_historial`, sección "── BAJA"). Corrección real aplicada: se
agrega la categoría `INGRESO` a `vw_rf46_historial_completo_activo` (mismo
patrón de columnas que `SANITARIO`/`CRECIMIENTO`) y se agrega `'INGRESO'` al
set `categorias_a_consultar` del repository -- sin tocar la vista de BAJA,
que ya funcionaba. Verificado en vivo con un activo POBLACIONAL efímero
(creado y revertido dentro de la misma transacción de prueba): tras el fix,
un evento de BAJA y uno de INGRESO registrados sobre el mismo activo aparecen
ambos en `ConsultarFichaLoteUseCase.execute(...).historial`.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "2848535f94f5"
down_revision: Union[str, Sequence[str], None] = "c8d4f1a9b7e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'modulo2' AND table_name = 'eventos_activos'
            ) THEN
                RAISE EXCEPTION 'RF-36: modulo2.eventos_activos no existe -- revisar supuestos de esta migración';
            END IF;

            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'enum_evento_ingreso_tipo') THEN
                CREATE TYPE enum_evento_ingreso_tipo AS ENUM (
                    'compra', 'nacimiento', 'donacion', 'transferencia_interna'
                );
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'modulo2' AND table_name = 'eventos_ingresos'
            ) THEN
                CREATE TABLE modulo2.eventos_ingresos (
                    id_evento INT PRIMARY KEY
                        REFERENCES modulo2.eventos_activos(id_eventos),
                    cantidad_ingresada INT NOT NULL
                        CONSTRAINT chk_ingreso_cantidad_positiva CHECK (cantidad_ingresada > 0),
                    tipo enum_evento_ingreso_tipo NOT NULL,
                    detalles TEXT
                );

                COMMENT ON TABLE modulo2.eventos_ingresos IS
                    'RF-36: alta de individuos a un lote POBLACIONAL. Sub-tabla 1:1 de eventos_activos, mismo patrón que eventos_bajas.';
                COMMENT ON COLUMN modulo2.eventos_ingresos.cantidad_ingresada IS
                    'Cantidad de individuos que ingresan al lote en este evento.';
            END IF;

            IF EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'chk_poblacional_cantidad_actual_coherente'
                  AND conrelid = 'modulo2.detalles_activos_biologicos_poblacionales'::regclass
            ) THEN
                ALTER TABLE modulo2.detalles_activos_biologicos_poblacionales
                    DROP CONSTRAINT chk_poblacional_cantidad_actual_coherente;
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE VIEW modulo2.vw_rf46_historial_completo_activo AS
        SELECT h.fecha_cambio AS fecha_evento,
            h.id_activo_biologico,
            ab.identificador,
            'ESTADO'::text AS categoria,
            ea_ant.nombre::text AS detalle_1,
            ea_nvo.nombre::text AS detalle_2,
            h.motivo_cambio AS observacion,
            COALESCE(concat_ws(' ', u.nombre, u.apellidos), 'Sin usuario') AS usuario_responsable
        FROM modulo2.historicos_estados_activos h
            JOIN modulo2.activos_biologicos ab ON ab.id_activo_biologico = h.id_activo_biologico
            JOIN modulo2.estados_activos_biologicos ea_ant ON ea_ant.id_estado_activo_biologico = h.id_estado_anterior
            JOIN modulo2.estados_activos_biologicos ea_nvo ON ea_nvo.id_estado_activo_biologico = h.id_estado_nuevo
            LEFT JOIN modulo1.usuarios u ON u.id_usuario = h.id_usuario
        UNION ALL
        SELECT COALESCE(gf.fecha_finalizacion, gf.fecha_inicio) AS fecha_evento,
            gf.id_activo_biologico,
            ab.identificador,
            'FASE_PRODUCTIVA'::text AS categoria,
            cp.nombre::text AS detalle_1,
            CASE WHEN gf.es_activa THEN 'Activa'::text ELSE 'Finalizada'::text END AS detalle_2,
            (((('duracion_dias='::text || cp.duracion_dias) || ', es_activa='::text) || gf.es_activa) || ', fecha_finalizacion='::text) || COALESCE(gf.fecha_finalizacion::text, 'NULL'::text) AS observacion,
            COALESCE(concat_ws(' '::text, u.nombre, u.apellidos), 'Sin usuario'::text) AS usuario_responsable
        FROM modulo2.gestiones_fases gf
            JOIN modulo2.activos_biologicos ab ON ab.id_activo_biologico = gf.id_activo_biologico
            JOIN modulo9.ciclos_productivos cp ON cp.id_ciclo_productivo = gf.id_ciclo_productiva
            LEFT JOIN modulo1.usuarios u ON u.id_usuario = gf.id_usuario
        UNION ALL
        SELECT ea.fecha AS fecha_evento,
            ea.id_activo_biologico,
            ab.identificador,
            'SANITARIO'::text AS categoria,
            es.diagnostico AS detalle_1,
            es.medicamento::text AS detalle_2,
            ea.descripcion AS observacion,
            COALESCE(concat_ws(' '::text, u.nombre, u.apellidos), 'Sin usuario'::text) AS usuario_responsable
        FROM modulo2.eventos_activos ea
            JOIN modulo2.activos_biologicos ab ON ab.id_activo_biologico = ea.id_activo_biologico
            JOIN modulo2.eventos_sanitarios es ON es.id_evento = ea.id_eventos
            LEFT JOIN modulo1.usuarios u ON u.id_usuario = ea.id_usuario
        UNION ALL
        SELECT ea.fecha AS fecha_evento,
            ea.id_activo_biologico,
            ab.identificador,
            'CRECIMIENTO'::text AS categoria,
            ec.tipo_medicion::text AS detalle_1,
            (ec.valor_medicion || ' '::text) || ec.unidad_medida::text AS detalle_2,
            ea.descripcion AS observacion,
            COALESCE(concat_ws(' '::text, u.nombre, u.apellidos), 'Sin usuario'::text) AS usuario_responsable
        FROM modulo2.eventos_activos ea
            JOIN modulo2.activos_biologicos ab ON ab.id_activo_biologico = ea.id_activo_biologico
            JOIN modulo2.eventos_crecimeinto ec ON ec.id_evento = ea.id_eventos
            LEFT JOIN modulo1.usuarios u ON u.id_usuario = ea.id_usuario
        UNION ALL
        SELECT ea.fecha AS fecha_evento,
            ea.id_activo_biologico,
            ab.identificador,
            'PRODUCTIVO'::text AS categoria,
            COALESCE(mp.nombre, ep.id_metrica_produccion::text::character varying) AS detalle_1,
            ep.cantidad || COALESCE(' '::text || mp.unidad_medida::text, ''::text) AS detalle_2,
            ea.descripcion AS observacion,
            COALESCE(concat_ws(' '::text, u.nombre, u.apellidos), 'Sin usuario'::text) AS usuario_responsable
        FROM modulo2.eventos_activos ea
            JOIN modulo2.activos_biologicos ab ON ab.id_activo_biologico = ea.id_activo_biologico
            JOIN modulo2.eventos_productivos ep ON ep.id_evento = ea.id_eventos
            LEFT JOIN modulo9.metricas_produccion mp ON mp.id_metrica_produccion = ep.id_metrica_produccion
            LEFT JOIN modulo1.usuarios u ON u.id_usuario = ea.id_usuario
        UNION ALL
        SELECT ea.fecha AS fecha_evento,
            ea.id_activo_biologico,
            ab.identificador,
            'REPRODUCTIVO'::text AS categoria,
            er.categoria::text AS detalle_1,
            er.resultado::text AS detalle_2,
            ea.descripcion AS observacion,
            COALESCE(concat_ws(' '::text, u.nombre, u.apellidos), 'Sin usuario'::text) AS usuario_responsable
        FROM modulo2.eventos_activos ea
            JOIN modulo2.activos_biologicos ab ON ab.id_activo_biologico = ea.id_activo_biologico
            JOIN modulo2.eventos_reproductivos er ON er.id_evento_reproductivo = ea.id_eventos
            LEFT JOIN modulo1.usuarios u ON u.id_usuario = ea.id_usuario
        UNION ALL
        SELECT lower(iz.rango_fecha)::timestamp with time zone AS fecha_evento,
            iz.id_activo_biologico,
            ab.identificador,
            'INDICADOR'::text AS categoria,
            iz.tipo::text AS detalle_1,
            upper(iz.rango_fecha)::text AS detalle_2,
            iz.paramtros_calculo::text AS observacion,
            NULL::text AS usuario_responsable
        FROM modulo2.indicadores_zootecnicos iz
            JOIN modulo2.activos_biologicos ab ON ab.id_activo_biologico = iz.id_activo_biologico
        UNION ALL
        SELECT ea.fecha AS fecha_evento,
            ea.id_activo_biologico,
            ab.identificador,
            'INGRESO'::text AS categoria,
            ei.tipo::text AS detalle_1,
            ei.cantidad_ingresada::text AS detalle_2,
            COALESCE(ea.descripcion, ei.detalles) AS observacion,
            COALESCE(concat_ws(' ', u.nombre, u.apellidos), 'Sin usuario') AS usuario_responsable
        FROM modulo2.eventos_activos ea
            JOIN modulo2.activos_biologicos ab ON ab.id_activo_biologico = ea.id_activo_biologico
            JOIN modulo2.eventos_ingresos ei ON ei.id_evento = ea.id_eventos
            LEFT JOIN modulo1.usuarios u ON u.id_usuario = ea.id_usuario;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE VIEW modulo2.vw_rf46_historial_completo_activo AS
        SELECT h.fecha_cambio AS fecha_evento,
            h.id_activo_biologico,
            ab.identificador,
            'ESTADO'::text AS categoria,
            ea_ant.nombre::text AS detalle_1,
            ea_nvo.nombre::text AS detalle_2,
            h.motivo_cambio AS observacion,
            COALESCE(concat_ws(' ', u.nombre, u.apellidos), 'Sin usuario') AS usuario_responsable
        FROM modulo2.historicos_estados_activos h
            JOIN modulo2.activos_biologicos ab ON ab.id_activo_biologico = h.id_activo_biologico
            JOIN modulo2.estados_activos_biologicos ea_ant ON ea_ant.id_estado_activo_biologico = h.id_estado_anterior
            JOIN modulo2.estados_activos_biologicos ea_nvo ON ea_nvo.id_estado_activo_biologico = h.id_estado_nuevo
            LEFT JOIN modulo1.usuarios u ON u.id_usuario = h.id_usuario
        UNION ALL
        SELECT COALESCE(gf.fecha_finalizacion, gf.fecha_inicio) AS fecha_evento,
            gf.id_activo_biologico,
            ab.identificador,
            'FASE_PRODUCTIVA'::text AS categoria,
            cp.nombre::text AS detalle_1,
            CASE WHEN gf.es_activa THEN 'Activa'::text ELSE 'Finalizada'::text END AS detalle_2,
            (((('duracion_dias='::text || cp.duracion_dias) || ', es_activa='::text) || gf.es_activa) || ', fecha_finalizacion='::text) || COALESCE(gf.fecha_finalizacion::text, 'NULL'::text) AS observacion,
            COALESCE(concat_ws(' '::text, u.nombre, u.apellidos), 'Sin usuario'::text) AS usuario_responsable
        FROM modulo2.gestiones_fases gf
            JOIN modulo2.activos_biologicos ab ON ab.id_activo_biologico = gf.id_activo_biologico
            JOIN modulo9.ciclos_productivos cp ON cp.id_ciclo_productivo = gf.id_ciclo_productiva
            LEFT JOIN modulo1.usuarios u ON u.id_usuario = gf.id_usuario
        UNION ALL
        SELECT ea.fecha AS fecha_evento,
            ea.id_activo_biologico,
            ab.identificador,
            'SANITARIO'::text AS categoria,
            es.diagnostico AS detalle_1,
            es.medicamento::text AS detalle_2,
            ea.descripcion AS observacion,
            COALESCE(concat_ws(' '::text, u.nombre, u.apellidos), 'Sin usuario'::text) AS usuario_responsable
        FROM modulo2.eventos_activos ea
            JOIN modulo2.activos_biologicos ab ON ab.id_activo_biologico = ea.id_activo_biologico
            JOIN modulo2.eventos_sanitarios es ON es.id_evento = ea.id_eventos
            LEFT JOIN modulo1.usuarios u ON u.id_usuario = ea.id_usuario
        UNION ALL
        SELECT ea.fecha AS fecha_evento,
            ea.id_activo_biologico,
            ab.identificador,
            'CRECIMIENTO'::text AS categoria,
            ec.tipo_medicion::text AS detalle_1,
            (ec.valor_medicion || ' '::text) || ec.unidad_medida::text AS detalle_2,
            ea.descripcion AS observacion,
            COALESCE(concat_ws(' '::text, u.nombre, u.apellidos), 'Sin usuario'::text) AS usuario_responsable
        FROM modulo2.eventos_activos ea
            JOIN modulo2.activos_biologicos ab ON ab.id_activo_biologico = ea.id_activo_biologico
            JOIN modulo2.eventos_crecimeinto ec ON ec.id_evento = ea.id_eventos
            LEFT JOIN modulo1.usuarios u ON u.id_usuario = ea.id_usuario
        UNION ALL
        SELECT ea.fecha AS fecha_evento,
            ea.id_activo_biologico,
            ab.identificador,
            'PRODUCTIVO'::text AS categoria,
            COALESCE(mp.nombre, ep.id_metrica_produccion::text::character varying) AS detalle_1,
            ep.cantidad || COALESCE(' '::text || mp.unidad_medida::text, ''::text) AS detalle_2,
            ea.descripcion AS observacion,
            COALESCE(concat_ws(' '::text, u.nombre, u.apellidos), 'Sin usuario'::text) AS usuario_responsable
        FROM modulo2.eventos_activos ea
            JOIN modulo2.activos_biologicos ab ON ab.id_activo_biologico = ea.id_activo_biologico
            JOIN modulo2.eventos_productivos ep ON ep.id_evento = ea.id_eventos
            LEFT JOIN modulo9.metricas_produccion mp ON mp.id_metrica_produccion = ep.id_metrica_produccion
            LEFT JOIN modulo1.usuarios u ON u.id_usuario = ea.id_usuario
        UNION ALL
        SELECT ea.fecha AS fecha_evento,
            ea.id_activo_biologico,
            ab.identificador,
            'REPRODUCTIVO'::text AS categoria,
            er.categoria::text AS detalle_1,
            er.resultado::text AS detalle_2,
            ea.descripcion AS observacion,
            COALESCE(concat_ws(' '::text, u.nombre, u.apellidos), 'Sin usuario'::text) AS usuario_responsable
        FROM modulo2.eventos_activos ea
            JOIN modulo2.activos_biologicos ab ON ab.id_activo_biologico = ea.id_activo_biologico
            JOIN modulo2.eventos_reproductivos er ON er.id_evento_reproductivo = ea.id_eventos
            LEFT JOIN modulo1.usuarios u ON u.id_usuario = ea.id_usuario
        UNION ALL
        SELECT lower(iz.rango_fecha)::timestamp with time zone AS fecha_evento,
            iz.id_activo_biologico,
            ab.identificador,
            'INDICADOR'::text AS categoria,
            iz.tipo::text AS detalle_1,
            upper(iz.rango_fecha)::text AS detalle_2,
            iz.paramtros_calculo::text AS observacion,
            NULL::text AS usuario_responsable
        FROM modulo2.indicadores_zootecnicos iz
            JOIN modulo2.activos_biologicos ab ON ab.id_activo_biologico = iz.id_activo_biologico;
        """
    )
    op.execute(
        """
        DROP TABLE IF EXISTS modulo2.eventos_ingresos;
        """
    )
    op.execute(
        """
        DROP TYPE IF EXISTS enum_evento_ingreso_tipo;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'chk_poblacional_cantidad_actual_coherente'
                  AND conrelid = 'modulo2.detalles_activos_biologicos_poblacionales'::regclass
            ) THEN
                -- Restaurarlo tal cual estaba requeriría que ya no existan
                -- filas con cantidad_actual > cantidad_inicial (producto de
                -- ingresos reales aplicados mientras esta migración estuvo
                -- activa). Si las hay, este ALTER falla a propósito -- señal
                -- de que el downgrade no es seguro sin decidir qué hacer con
                -- esos datos primero.
                ALTER TABLE modulo2.detalles_activos_biologicos_poblacionales
                    ADD CONSTRAINT chk_poblacional_cantidad_actual_coherente
                    CHECK (cantidad_actual <= cantidad_inicial);
            END IF;
        END
        $$;
        """
    )
