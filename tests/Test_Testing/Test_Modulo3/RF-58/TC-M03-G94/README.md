# TC-M03-G94 — TC-M03-185 (RF-58 / CU04)

Matriz oficial: fila G94. El ejecutor usa la cuenta QA Productor configurada, comprueba sus asignaciones y, si existen, las retira mediante `PUT /usuarios/{id_usuario}/fincas` solo dentro del sandbox. Una segunda transacción debe conservar el número original; el rollback se comprueba al cerrar. El dashboard con arreglos vacíos y HTTP 200, el mensaje exacto de la UI, la sugerencia de contactar al administrador y la ausencia de datos ajenos son aserciones funcionales. La preparación no las anticipa como preflight.

Local: `node ejecutar_tc_m03_g94.mjs --validar-local` y `node --test validar_local_g94.mjs`. No realizan conexiones remotas.

Futura ejecución: `node ejecutar_tc_m03_g94.mjs --ejecutar --ambiente TEST --autorizacion "<referencia Desarrollo>" --tipo evaluacion --aceptar-efectos notificacion-login`. Exige `QA_AUTORIZADO=SI`, TEST, sandbox y aceptación de la posible notificación de login fuera del rollback. `--tipo reintento` conserva versión; las reevaluaciones concluidas usan V2, V3, etc. Cada RUN produce un informe Markdown y `evidencia.json` consolidado.
