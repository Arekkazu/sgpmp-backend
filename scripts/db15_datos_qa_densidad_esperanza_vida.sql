-- | Fecha      | Nombre   | Que se hizo |
-- |------------|----------|-------------|
-- | 2026-10-23 | Arekkazu | DB-15 RF-15: densidad y esperanza de vida de ejemplo para QA (RFC-012/014) |
--
-- DB-15 (RFC-012 / RFC-014): datos de QA en DEV y TEST. Correr DESPUÉS de aplicar
-- la cadena de migraciones de integracion/rfc012-016 (DB-07 crea esperanza_vida_dias).
--
-- - Idempotente: solo completa valores en NULL; no pisa lo que QA ya configuró.
-- - Ubica las especies por nombre: los ids difieren entre DEV y TEST.
-- - Valores de EJEMPLO para pruebas, no zootécnicos validados por Análisis.
--
-- Uso:  psql "$URL" -v ON_ERROR_STOP=1 -f scripts/db15_datos_qa_densidad_esperanza_vida.sql

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'modulo9' AND table_name = 'especies' AND column_name = 'esperanza_vida_dias'
    ) THEN
        RAISE EXCEPTION 'DB-15: falta modulo9.especies.esperanza_vida_dias; aplique primero las migraciones (DB-07).';
    END IF;
END $$;

-- Densidad poblacional máxima (ind/m²) por grupo de manejo, para toda especie activa sin
-- densidad: sin ella toda operación de capacidad responde 422 ESPECIE_SIN_DENSIDAD.
UPDATE modulo9.especies e
SET densidad_maxima_por_especie = v.densidad
FROM (VALUES
    ('ACUICULTURA', 10.00),
    ('AVES', 8.00),
    ('PORCINOS', 1.00),
    ('ESPECIES_MEDIANAS', 0.50),
    ('ESPECIES_GRANDES', 0.05)
) AS v(grupo, densidad)
WHERE e.grupo_manejo = v.grupo
  AND e.es_activo
  AND e.densidad_maxima_por_especie IS NULL;

-- Esperanza de vida (días) de ejemplo para las especies que usan los casos de QA.
UPDATE modulo9.especies e
SET esperanza_vida_dias = v.dias
FROM (VALUES
    ('Cachama Blanca', 5475),
    ('Tilapia Roja', 3650),
    ('Tilapia', 3650),
    ('Tilapia Nilo', 3650),
    ('Trucha Arcoíris', 2555),
    ('Camarón Blanco', 730),
    ('Mojarra Plateada', 2920)
) AS v(nombre, dias)
WHERE lower(e.nombre) = lower(v.nombre)
  AND e.esperanza_vida_dias IS NULL;

-- Resumen para el registro de la ejecución.
SELECT id_especie, nombre, grupo_manejo, densidad_maxima_por_especie, esperanza_vida_dias
FROM modulo9.especies
WHERE es_activo
ORDER BY id_especie;

COMMIT;
