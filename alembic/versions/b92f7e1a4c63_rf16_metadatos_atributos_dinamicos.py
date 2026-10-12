"""RF-16: tipo y obligatoriedad de atributos dinámicos

Revision ID: b92f7e1a4c63
Revises: fa915f4d113e
Create Date: 2026-09-09

INC-M02-47-G17 / #208. Agrega a las métricas productivas los metadatos que
RF-33 necesita para validar atributos dinámicos antes de persistir un activo.

TC-M09-G91 (#312): en el entorno TEST, esta migración quedó bloqueada desde
2026-09-04 (ver runs fallidos del workflow "Deploy Migrations - test") porque
el UPDATE original de abajo toca todas las filas de `metricas_produccion`, y
Postgres revalida en cada UPDATE el CHECK `chk_metricas_tipo_medicion` -- que
es `NOT VALID`, así que nunca validó datos preexistentes. Una fila con
`tipo_medicion='manual'` (dato inválido, cargado antes de que el constraint
empezara a aplicarse) hacía fallar el UPDATE con `CheckViolation`, y con eso
toda la cadena de migraciones posteriores a esta quedó sin aplicarse en TEST.

Dos fixes independientes llegaron a esta misma migración para el mismo
bloqueo: este (normalización defensiva justo antes del UPDATE original,
paso 3 de abajo) y otro en paralelo que resuelve el caso general por
adelantado (paso 1: mapeo acordado con el equipo de análisis para los
valores de prueba conocidos -- manual -> CONTEO, calculada -> PESO,
TALLA -> OTRO -- y paso 2: `VALIDATE CONSTRAINT chk_metricas_tipo_medicion`
explícito antes de tocar nada más). Con los pasos 1-2 corriendo primero, el
paso 3 queda como red de seguridad redundante para cualquier valor legado
no contemplado en el mapeo explícito -- se conserva por defensa en
profundidad, no por necesidad estricta. Es seguro para los entornos donde
esta migración ya se aplicó (dev, pruebas locales): Alembic no la re-ejecuta
ahí, así que este cambio solo afecta la próxima vez que alguien la aplique
donde todavía no llegó.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'b92f7e1a4c63'
down_revision: Union[str, Sequence[str], None] = 'fa915f4d113e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Normalizar valores de prueba en tipo_medicion antes de que
    #    cualquier UPDATE posterior fuerce la re-evaluación del check.
    op.execute(
        """
        UPDATE modulo9.metricas_produccion
        SET tipo_medicion = 'CONTEO'
        WHERE tipo_medicion = 'manual';

        UPDATE modulo9.metricas_produccion
        SET tipo_medicion = 'PESO'
        WHERE tipo_medicion = 'calculada';

        UPDATE modulo9.metricas_produccion
        SET tipo_medicion = 'OTRO'
        WHERE tipo_medicion = 'TALLA';
        """
    )

    # 2. Validar chk_metricas_tipo_medicion contra los datos existentes.
    #    Si quedara algún valor fuera del set permitido, esto falla aquí
    #    con un mensaje claro, antes de tocar tipo_dato/es_obligatorio.
    op.execute(
        """
        ALTER TABLE modulo9.metricas_produccion
            VALIDATE CONSTRAINT chk_metricas_tipo_medicion;
        """
    )

    # 3. Lógica original de RF-16 (sin cambios).
    op.execute(
        """
        -- TC-M09-G91 (#312): normaliza tipo_medicion inválido preexistente
        -- (constraint NOT VALID, nunca revalidó filas viejas) antes de que el
        -- UPDATE de abajo dispare CheckViolation al tocar esas filas.
        UPDATE modulo9.metricas_produccion
        SET tipo_medicion = 'OTRO'
        WHERE upper(tipo_medicion) NOT IN ('PESO', 'VOLUMEN', 'LONGITUD', 'CONTEO', 'OTRO');

        ALTER TABLE modulo9.metricas_produccion
            ADD COLUMN IF NOT EXISTS tipo_dato varchar(10),
            ADD COLUMN IF NOT EXISTS es_obligatorio boolean;

        UPDATE modulo9.metricas_produccion
        SET tipo_dato = CASE upper(tipo_medicion)
            WHEN 'CONTEO' THEN 'ENTERO'
            WHEN 'PESO' THEN 'NUMERICO'
            WHEN 'VOLUMEN' THEN 'NUMERICO'
            WHEN 'LONGITUD' THEN 'NUMERICO'
            ELSE 'TEXTO'
        END
        WHERE tipo_dato IS NULL;

        UPDATE modulo9.metricas_produccion
        SET es_obligatorio = false
        WHERE es_obligatorio IS NULL;

        ALTER TABLE modulo9.metricas_produccion
            ALTER COLUMN tipo_dato SET DEFAULT 'NUMERICO',
            ALTER COLUMN tipo_dato SET NOT NULL,
            ALTER COLUMN es_obligatorio SET DEFAULT false,
            ALTER COLUMN es_obligatorio SET NOT NULL;

        COMMENT ON COLUMN modulo9.metricas_produccion.tipo_dato IS
            'Tipo primitivo del atributo dinámico: NUMERICO, ENTERO, TEXTO o BOOLEANO.';
        COMMENT ON COLUMN modulo9.metricas_produccion.es_obligatorio IS
            'Indica si RF-33 exige el atributo al registrar el activo.';
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'ck_metrica_produccion_tipo_dato'
                  AND conrelid = 'modulo9.metricas_produccion'::regclass
            ) THEN
                ALTER TABLE modulo9.metricas_produccion
                    ADD CONSTRAINT ck_metrica_produccion_tipo_dato
                    CHECK (tipo_dato IN ('NUMERICO', 'ENTERO', 'TEXTO', 'BOOLEANO'));
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    # No se revierte la normalización de tipo_medicion ni se invalida
    # chk_metricas_tipo_medicion: eran datos de prueba corregidos con el
    # equipo de análisis, no un cambio reversible de negocio.
    op.execute(
        """
        ALTER TABLE modulo9.metricas_produccion
            DROP CONSTRAINT IF EXISTS ck_metrica_produccion_tipo_dato,
            DROP COLUMN IF EXISTS es_obligatorio,
            DROP COLUMN IF EXISTS tipo_dato;
        """
    )