TC-M04-G060 — BLOQUEADO (impedimento de entorno: el sandbox de TEST no admite concurrencia real)

RF-69 v2.1, originales TC-M04-166 a TC-M04-169: se quería comprobar la activación simultánea y la unicidad por llave.
El responsable QA decidió BLOQUEADO el 2026-10-28 porque cada RUN comparte una sola sesión y conexión de base de datos.
El intento V1 dejó 72 solicitudes registradas, errores 500 intermitentes y ningún veredicto de producto. La recuperación autorizada del 2026-10-29 acreditó el rollback de los datos del RUN; persisten 13 archivos ONNX fuera del rollback transaccional.
El ejecutor [g060.mjs](g060.mjs) está listo para un entorno con transacciones concurrentes reales y limpieza garantizada.
La operación `recuperar` de SOL-G060-005 fue autorizada y ejecutada como `AUT-G060-V1-REC-20261028`; el registro QA cerró el RUN con rollback CONFIRMADO.

Informe y evidencias del intento: [TC-M04-G060_resultado.md](Resultados/RUN-G060-V1-20261028-162607/TC-M04-G060_resultado.md).
