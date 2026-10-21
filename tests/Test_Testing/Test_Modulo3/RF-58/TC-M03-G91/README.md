# TC-M03-G91 — RF-58 / CU04

Matriz oficial: TC-M03-179 y TC-M03-194. Newman registra la lectura A y confirma el dashboard real. Cypress inicia sesión en la interfaz, registra B por la API oficial en el mismo sandbox y comprueba recuperación automática sin recarga. Para la pérdida se interrumpen peticiones de polling del navegador; no se devuelven respuestas simuladas. Para la reconexión se cambian el estado de red y eventos del navegador. Toda B se verifica en backend antes de juzgar la vista.

**Estado de construcción: PREPARADO CON DEPENDENCIA.** El frontend consultado emplea polling cada 30 s, sin canal de eventos. La prueba de TC-M03-179 reproduce pérdida de entrega de las actualizaciones mediante interrupción de solicitudes, y evalúa recuperación tras 12 min simulados; la equivalencia con pérdida de un evento en tiempo real requiere revisión de QA cuando se autorice TEST. El aislamiento de todas las solicitudes del navegador también debe confirmarse con el eco `X-Test-Run-Id` de la ejecución real.

Validación local: `node ejecutar_tc_m03_g91.mjs --validar-local`.

Comando futuro, solo con autorización expresa de Desarrollo y `QA_AUTORIZADO=SI`: `node ejecutar_tc_m03_g91.mjs --ejecutar --ambiente TEST --autorizacion "<referencia>" --tipo evaluacion --aceptar-efectos notificacion-login`.

El mismo ejecutor gestiona V1, reintentos y V2 en adelante. Cada RUN conserva `evidencia.json`, informe histórico y capturas relevantes, dentro de `RESULTADOS/<RUN_ID>/` o `EvaluacionVN/RESULTADOS/<RUN_ID>/`. Los logins pueden producir notificaciones fuera del rollback; el runner exige su aceptación expresa.
