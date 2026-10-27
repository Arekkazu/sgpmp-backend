# TC-M03-G127 — auditoría del historial (RF-59)

## Oráculo original

`Casos_Prueba(Modulo3 Agrupado).csv:194-195`, TC-M03-256:

> Para la consulta existe un registro de auditoría con usuario, filtros aplicados, rango temporal, cantidad de registros y timestamp. Cuando se ejecute una exportación, el registro incluye además el formato de exportación utilizado.

La nota de la misma fila declara independiente la auditoría de la consulta normal y limita la comprobación del formato a una exportación disponible. RF-59, `Especificacion-Requerimientos-Modulo3.md`: Fase 8, líneas 5982-5990; Postcondición 6, líneas 6224-6226; CA-16, líneas 6281-6284. CA-16 exige registrar también “si se exportó” en cualquier consulta. Para la consulta normal se exige `exportado=false` o campo equivalente. La verificación en BD descrita por la matriz se sustituye por la API pública RF-63 porque la orden prohíbe SQL y acceso directo a BD.

## Código consultado y efecto

En `origin/test` consulté `src/telemetry/application/use_cases/monitoreo/consultar_historial_use_case.py:200-239`, que emite `HISTORIAL_CONSULTADO` con `id_usuario`, `id_rol`, `filtros` (incluye `fecha_inicio` y `fecha_fin`), `registros_devueltos`, `por_pagina` y `exportado=false`, y `src/telemetry/infrastructure/routers/auditoria_iot_router.py:49,64-112`, que expone `GET /iot/auditoria` con permiso `(39,2)` y filtros `tipo_evento`, `id_usuario`, `fecha_desde`, `fecha_hasta`. En el árbol local consulté además `src/telemetry/infrastructure/routers/monitoreo_router.py:261-267`, que pasa la misma sesión `db` a RF-63, y `src/telemetry/application/use_cases/auditoria/registrar_evento_auditoria_iot_use_case.py:84-125`, que hace `commit()` y absorbe fallos: la constancia puede persistir fuera del rollback del RUN. Estos archivos orientan la prueba; no acreditan el commit desplegado en TEST. La ausencia o divergencia se tratará como `DEFECTO_FUNCIONAL_CANDIDATO` hasta observarla por la API en un RUN autorizado.

## Diseño y contrato

Solo el lanzador externo puede crear el RUN y pasar `--operacion`, `--version`, `--intento`, `--run-id`, `--autorizacion` y `--contexto`; `contexto_operacion.json` se verifica antes de credenciales o red. La versión V2 exige `reevaluar`. El preflight acepta `.env.qa` y las variables normales `QA_*`, sin variables manuales G127. Los logins de Productor y Administrador van sin cabecera de RUN. Dentro del RUN se selecciona automáticamente una consulta con datos del sensor 6 en 7/30 días; el respaldo acotado usa el rango conocido 2026-10-20..27. Si no hay datos, el caso queda BLOQUEADO con diagnóstico.

Newman ejecuta una consulta distintiva (`por_pagina=37`), luego la lectura RF-63 del Administrador, luego el GET informativo de exportación PDF. El ejecutor compara usuario, rol, filtros y rango, cantidad de `items`, timestamp en ventana y `exportado=false`; no toma como evidencia un evento de la selección. Reintenta una ausencia de evento hasta dos veces por API pública. `503 M08_NO_DISPONIBLE` deja formato como NO APLICA sin bloquear la consulta; si la exportación responde 200 se busca el formato PDF en RF-63. No hay Cypress ni UI obligatoria.

Presupuesto único: hasta 14 solicitudes directas (incluidos dos logins, hasta tres consultas de selección, dos reintentos RF-63, hasta tres búsquedas de exportación y DELETE, con una solicitud reservada para cierre), tres solicitudes Newman, 720 s de duración, 120 s de inactividad máxima declarada, 30 s por solicitud y 20 s en selección. Los reportes Newman JSON y HTML generados se sanean y quedan en el RUN. La única comprobación obligatoria es `API-256-01`; solo APROBADO/RECHAZADO con evidencia y cierre correcto produce RUN OFICIAL según la emulación de `registro_qa`. BLOQUEADO y NO_CONCLUYENTE son TÉCNICOS. No se ejecuta Newman contra TEST durante preparación.

## Efectos para autorización posterior

No hay escritura de negocio, SQL, creación de datos ni llamadas a `/test-control/query`. Los logins pueden persistir sesión o auditoría. Los GET de historial y exportación pueden persistir auditoría RF-63 por el `commit()` indicado; DELETE del RUN no acredita revertirla. La lectura de bitácora es GET. El cierre se informa como DELETE 200, con rollback limitado a la ausencia de escrituras de escenario. Estos efectos requieren autorización particular para el lanzador externo.

## Validación local

```text
node g127.mjs --capacidades
node g127.mjs --comprobar
node pruebas/g127.test.mjs
node pruebas/g127_ensayo.mjs
```

El ensayo usa solo servidor loopback y archivos temporales; la salida esperada termina en `OK G127: 7/7 modos; resultado.json e informe coherentes; registro QA fiel`. El informe oficial futuro empieza `# TC-M03-G127 — <DECISIÓN>` y queda únicamente dentro de `Resultados/RUN-G127-V1-.../` o `EvaluacionV2/Resultados/RUN-G127-V2-.../`, junto con `resultado.json` y reportes generados.
