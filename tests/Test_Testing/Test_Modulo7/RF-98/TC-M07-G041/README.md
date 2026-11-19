# G041 — RF-98 v1.2, preparación local

Ejecutor canónico: `g041.mjs`; una colección `G041.postman_collection.json`; un spec `g041.cy.js` y una configuración `g041.cypress.config.cjs`. Solo la orden externa autorizada puede crear un RUN y acceder a TEST. `--comprobar` y `--capacidades` son locales. La verificación local es `node pruebas/verificar.mjs`.

El ejecutor exige `QA_AUTORIZADO=SI`, contexto precreado `Resultados/RUN-G041-V1-<timestamp>/contexto_operacion.json`, origen API exacto de TEST y variables `QA_ADMIN_EMAIL`, `QA_ADMIN_PASSWORD`, `QA_CONTADOR_EMAIL`, `QA_CONTADOR_PASSWORD`, `QA_SANDBOX_SECRET`, `SIGAB_API_TEST_BASE`. En producción, Cypress usa el FRONT fijo `https://api.inmero.co/sigab-test`; `SIGAB_FRONT_TEST_BASE` solo se exige y usa en ensayos locales de loopback. Hay un login real del Administrador y uno del Contador, ambos por API. Cypress reutiliza el token del Contador con un login interceptado y credenciales ficticias. El ejecutor nunca lee `.env.qa` durante `--comprobar` ni `--capacidades`.

El directorio de Cypress en producción es `Resultados/<run_id>/cypress`. El RUN real guarda `preflight.json`, `resultado.json`, `TC-M07-G041_resultado.md`, reportes Newman JSON/HTML y acta, metadatos y captura explícita `viewport` de Cypress si fueron generados. Vídeo y captura automática de fallo están desactivados. El cierre usa DELETE incluso ante preflight de datos bloqueante y compara la firma completa de contratos con la lectura pública posterior. Un fallo técnico de Cypress deja UI en `NO_CONCLUYENTE`. Los ensayos locales usan exclusivamente directorios temporales y quedan identificados como simulación.

SHA-256 esperado de `g041.mjs`: `94bbf0489a7cdf0c9d5859403d9e40cd6d8be7ae96c59291a974a41a22373754`

SHA-256 esperado de `verificar.mjs`: `1d7602bfa0c8cadadda6bce12ad14713e5a9d60a66e23cff79831954785585eb`
