# TC-M03-G92 — RF-58 / CU04

Matriz oficial: TC-M03-181, TC-M03-182 y TC-M03-183. Suite exclusivamente API (Postman/Newman). El runner crea en el sandbox una unidad con 60 sensores y otra con un sensor. Las lecturas sitúan un sensor en AMARILLO, el número 55 en ROJO y los demás en VERDE; la colección registra una alerta crítica del sensor 55, confirma la segunda página y comprueba que el resumen de la primera sigue en ROJO. El filtro de la segunda unidad debe excluir todos los sensores de la primera.

Validación local: `node ejecutar_tc_m03_g92.mjs --validar-local`.

Comando futuro, únicamente tras autorización expresa de Desarrollo y `QA_AUTORIZADO=SI`: `node ejecutar_tc_m03_g92.mjs --ejecutar --ambiente TEST --autorizacion "<referencia>" --tipo evaluacion --aceptar-efectos notificacion-login`.

**Estado de construcción: PREPARADO PARA EJECUCIÓN**, sujeto a preflight remoto y comprobación funcional tras la autorización. Se usa el mismo ejecutor para V1, reintentos y V2 en adelante. Cada RUN conserva `evidencia.json` e informe histórico en `RESULTADOS/<RUN_ID>/` o `EvaluacionVN/RESULTADOS/<RUN_ID>/`, sin sobrescribir resultados. El runner verifica el rollback; los logins pueden producir notificaciones fuera del sandbox, por lo que exige aceptación expresa.
