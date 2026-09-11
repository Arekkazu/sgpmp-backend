-- RF-01/RF-08/RF-09: convertir tokens de un solo uso existentes a SHA-256.
-- Ejecutar durante el despliegue, antes de levantar la versión que consulta por hash.

BEGIN;

UPDATE modulo1.cuentas_usuarios
SET token_activacion_actual = encode(
    sha256(convert_to(token_activacion_actual, 'UTF8')),
    'hex'
)
WHERE token_activacion_actual IS NOT NULL
  AND token_activacion_actual !~ '^[0-9a-f]{64}$';

COMMIT;