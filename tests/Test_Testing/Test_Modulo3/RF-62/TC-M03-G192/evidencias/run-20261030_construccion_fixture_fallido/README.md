# Intento de construcción — fixture fallido (2026-10-30)

**Motivo:** la suite se construyó contra el dispositivo 7
(`IOT-CAM02-COR-002`), que en el seed de TEST tiene `id_tipo_dispositivo=1`
(categoría SENSOR, no CAMARA). El backend rechazó correctamente con
`HTTP 422 DISPOSITIVO_NO_ES_CAMARA` en el primer POST /iot/telemetria/vision.
Los 116 checkpoints fallidos reportados por el consolidador tenían causa
raíz única (fixture mal elegido), no defecto del backend.

**Acción correctiva:** se reemplazó el fixture por la cámara 147
(`QA-M09-G55-cam-290655`, fps=30), se ajustaron los ratios fps y se
re-ejecutó. Esa ejecución es la **primera evaluación oficial del caso**
(125/125 checkpoints OK, veredicto APROBADO) y vive en `resultados/` como
`resultado_TC-M03-G192.{json,html}`.

**Este intento se preserva como evidencia de construcción, no como
evaluación del caso.**

