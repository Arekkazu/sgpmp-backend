# Narrativa de Diseño y Ejecución — TC-M04-G100

## Resumen Ejecutivo
El grupo TC-M04-G100 analiza dos requerimientos fundamentales de resiliencia y gobernanza: el principio de desacoplamiento (la auditoría debe ser no bloqueante y fallar en modo silencioso/fallback sin interrumpir la operación del negocio pecuario) y la garantía de conservación histórica (retención mínima de 365 días).

## FASE SEPARADA — AISLAMIENTO DE AUDITORÍA
1. Desacoplamiento de Negocio (TC-M04-306): En el código del backend, la función `_escribir_fallback()` absorbe cualquier fallo de base de datos escribiendo en `logs/audit_fallback_M04_<YYYYMMDD>.log`. Para validar esto en ejecución, se requiere un entorno donde se corte la base de datos deliberadamente, lo cual corresponde a la FASE SEPARADA fuera del sandbox.
2. Gobernanza de Retención (TC-M04-307): La retención contractual de 365 días se valida a través de la política de rechazo de purgas anticipadas y el diseño contra el endpoint administrativo esperado `GET /prediccion/auditoria/configuracion`.
