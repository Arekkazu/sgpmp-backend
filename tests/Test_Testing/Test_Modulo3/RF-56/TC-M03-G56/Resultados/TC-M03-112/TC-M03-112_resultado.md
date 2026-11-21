# TC-M03-112

G56. Estado `PENDIENTE` si M04 no está disponible **antes** del primer intento.

**SKIPPED** EXIT=0. El use case llama `enviar_paquete` de inmediato; el modelo ORM default `PENDIENTE` se pisa a `ENVIADO`/`FALLIDO` en el mismo execute. INC-M03-113-G56.

Evidencia: `evidencias/reeval-2026-10-25/test_tc_m03_112_pendiente_sin_primer_intento.*`
