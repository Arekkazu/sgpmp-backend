# TC-M03-G90 — RF-58 / CU04

Matriz oficial: TC-M03-175 y TC-M03-176. La colección comprueba la respuesta real del dashboard y el spec Cypress comprueba la retención visual de la lectura, la alerta y el estado sin señal. No se califica la precedencia ROJO/GRIS cuando coinciden alerta crítica y ausencia de señal.

**Estado de construcción: PREPARADO CON DEPENDENCIA DE CAPACIDAD.** El ejecutor ya no contiene bloqueos incondicionales. Tras la autorización, crea dos sensores y sus últimas lecturas válidas (frecuencia de 5 min), registra la alerta CRITICO activa y verifica que las lecturas no sean visibles desde otra transacción. Luego consulta el dashboard real dentro del mismo `X-Test-Run-Id` cada 30 s, hasta 8 min. Newman y Cypress solo se inician si ambos sensores alcanzan `SIN_SEÑAL` después del intervalo. Si la transición no se observa, registra la observación y aborta como precondición no verificable. La conservación del valor y timestamp, el tiempo informado, `dato_desactualizado`, GRIS y la alerta crítica siguen siendo **aserciones funcionales**, no barreras de preflight.

El código del backend consultado no ofrece un reloj de pruebas ni un disparador oficial aislado. La tarea RF-60 usa una sesión global y no puede leer los datos aún no confirmados del RUN; el ejecutor no la invoca ni escribe SQL para forzar estados. La espera permite continuar automáticamente si el backend autorizado calcula o actualiza la pérdida de señal dentro del sandbox. Si la única capacidad futura es un endpoint nuevo, habrá que integrarlo en estos mismos scripts una vez documentado. `cy.clock` solo afecta al navegador.

Validación local: `node ejecutar_tc_m03_g90.mjs --validar-local`.

Una futura ejecución oficial requiere autorización expresa de Desarrollo, `QA_AUTORIZADO=SI`, referencia verificable y aceptación de la notificación de login. Comando previsto: `node ejecutar_tc_m03_g90.mjs --ejecutar --ambiente TEST --autorizacion "<referencia>" --tipo evaluacion --aceptar-efectos notificacion-login`.

Un solo conjunto de scripts sirve a V1 y posteriores. Tras una ejecución concluida: `RESULTADOS/<RUN_ID>/TC-M03-G90_resultado.md` o `EvaluacionVN/RESULTADOS/<RUN_ID>/TC-M03-G90_reevaluacion_VN.md`, junto a `evidencia.json` y capturas necesarias. Nunca se crean durante validación local.
