# TC-M03-G124 — preparación RF-59

Automatización canónica de API, solo lectura, para TC-M03-249, 250 y 254. No hay UI obligatoria ni spec Cypress. El ejecutor es `g124.mjs`, la única colección es `G124.postman_collection.json`, y `validadores.mjs` conserva la inspección PDF/XLSX para cuando M08 genere archivos. El legado importaba `../TC-M03-G120/rf59_base.mjs` inexistente y contenía ingestas y SQL; se retiró.

## Oráculos y dependencia

Fuente primaria: fila `TC-M03-G124` de `Casos_Prueba(Modulo3 Agrupado).csv` (Windows-1252). PDF: encabezado de granja, periodo, filtros y usuario; gráfica de tendencia; tabla con semáforo; resumen estadístico; pie con timestamp. Excel: datos crudos completos, resumen por variable, alertas correlacionadas y metadatos por hoja. Volumen: 5.000/50.000 se procesan; 5.001/50.001 se fragmentan con aviso. No se evalúa concurrencia.

RF-59: precondición 8, líneas 5654-5655, exige generadores RF-10 de M08; CA-10, 6263-6264; CA-11, 6266-6267; restricción 13, 5703-5716; E5, 6056-6068. La matriz cita CU04 FA-10 para fragmentación, pero las anotaciones disponibles `anotaciones/modulo_3/cu04_gaps_bd_rf58_rf59.md:92` y `curls_m03_cu04_monitoreo_historial.md:317` describen FA-10 como truncado de consultas de 10.000; la fuente independiente de fragmentación sigue siendo la matriz y requiere aclaración documental de QA. La documentación API `anotaciones/modulo_3/api_reference_m03_telemetria_iot.md:559-567` identifica FA-11 y `400 EXPORTAR_SIN_FILTROS`; `curls_m03_cu04_monitoreo_historial.md:290-303,318` da el mismo código. El router de `origin/test` commit `254deee6f3d3cb68bd14a76aabdac8fa4afae3fd`, `src/telemetry/infrastructure/routers/monitoreo_router.py:157-202`, comprueba filtro adicional (194-198) y lanza `M08_NO_DISPONIBLE` (200-202); no declara `response_model`. Se consultaron realmente esos archivos de referencia y el requisito; no se infiere el despliegue de TEST. La ausencia del motor en el código revisado es `DEFECTO_FUNCIONAL_CANDIDATO`, nunca un veredicto; el GET filtrado es la comprobación pública mínima.

`503 M08_NO_DISPONIBLE` con semilla válida produce **BLOQUEADO / REQUISITO_DEPENDIENTE** para 249 y 250, y BLOQUEADO para 254: sin archivo no es comprobable la estructura ni la fragmentación. Este bloqueo coincide con la nota explícita de la matriz y requiere decisión final del responsable QA. Un archivo 200 se inspecciona; si faltan elementos verificables se RECHAZA, si el parser no puede leerlo queda NO_CONCLUYENTE. Un 200 con PDF/Excel válidos aprueba 249/250; 254 sigue NO_CONCLUYENTE hasta probar los cuatro volúmenes reales. Error del ejecutor o falta de eco es técnico, nunca prueba de defecto. Otro 5xx solo RECHAZA cuando la respuesta pública contradice E5 (por ejemplo, sin orientación de reducción de rango/filtros). No se atribuye causa raíz a `origin/test`.

## Diseño, contrato y presupuesto

Solo el lanzador externo puede crear un RUN y pasar `--operacion`, `--version`, `--intento`, `--run-id`, `--autorizacion`, `--contexto`. El preflight exige `QA_AUTORIZADO=SI` en el proceso, base TEST canónica, contexto coherente y credenciales de `.env.qa`; no requiere variables `G124_*`. Tras el login Productor, la selección automática consulta con eco el historial del sensor 6 durante los últimos 7 días y, si no hay resultados, 30 días. Si ambos rangos dan cero, consulta el dashboard global y hasta ocho unidades (1, 268, 337 y las visibles), y prueba hasta doce sensores distintos del dashboard. Para lecturas antiguas usa un rango de siete días alrededor de la última captura expuesta. Elige la primera consulta con `total > 0` y una fila del sensor elegido; registra solo IDs, rangos, totales, HTTP y eco en `diagnostico_seleccion`. Si ninguna consulta acotada tiene resultados, los tres casos quedan BLOQUEADO por datos, sin `ERROR_QA_SEMILLA`. Un error de transporte, contrato o eco se registra como problema técnico.

Los filtros elegidos (`sensor_id`, `fecha_inicio`, `fecha_fin`) se reutilizan en historial Newman y en ambas exportaciones; `sensor_id` satisface el filtro adicional de FA-11. No hay ingesta, SQL, `/test-control/query`, k6 ni carga masiva. El presupuesto único en `lib/g124_escenario.mjs` es 25 solicitudes directas como máximo (1 login + 2 historiales iniciales + 1 dashboard global + 8 unidades + 12 historiales descubiertos + 1 DELETE), 3 Newman, 720 s, timeout de selección 20 s por solicitud y respuesta máxima inspeccionable 20 MB. La selección termina en el primer resultado. Se comprueba Newman CLI `--version` con 30 s de límite. Los reportes JSON y HTML de Newman se guardan saneados en el RUN; los cuerpos de error conservan código y mensaje, los cuerpos de datos/archivos se resumen por tamaño, SHA-256 y validación sin exponer datos privados.

La emulación fiel del registro QA exige casos APROBADO/RECHAZADO y comprobaciones obligatorias con esos estados para un RUN OFICIAL. Por eso BLOQUEADO ×3 produce RUN **TÉCNICO** y no consume versión, aunque sea el resultado esperado mientras M08 falta. Los informes futuros se generan solo dentro del RUN: V1 `Resultados/RUN-.../TC-M03-G124_resultado.md`; V2+ `EvaluacionV2/Resultados/RUN-.../TC-M03-G124_reevaluacion_VN.md`. Se conserva un Markdown oficial único por RUN junto con `resultado.json`, `preflight.json` y reportes Newman generados. No se crea ninguno en fase preparar.

Efectos remotos que deberán considerarse en una autorización futura: login Productor fuera del RUN podría persistir sesión/auditoría; los GET de historial/exportación podrían auditar fuera del RUN; los GET de dashboard podrían registrar auditoría y enviar correo a administradores si hay sensores sin umbral; DELETE cierra el sandbox. La ausencia de escrituras de escenario permite declarar rollback solo si DELETE devuelve 200. Los archivos de exportación, cuando existan, pueden contener datos privados y no se guardan crudos: se inspeccionan en memoria y se conserva evidencia saneada.

## Validación local

`node g124.mjs --capacidades`

`node g124.mjs --comprobar`

`node pruebas/g124.test.mjs`

`node pruebas/g124_ensayo.mjs`

El ensayo usa únicamente `127.0.0.1` y un directorio temporal, con siete modos: `m08_no_disponible`, `exporta_ok`, `pdf_incompleto`, `excel_sin_hojas`, `otro_5xx`, `sin_respuesta`, `seleccion_automatica`. Este último devuelve cero lecturas para el sensor 6 en 7 y 30 días y una lectura del sensor 73 visible en la unidad 1. Verifica `resultado.json`, informe, clasificación del registro QA, filtros de exportación y secuencia de solicitudes. Ningún modo alcanza TEST.

Salida observada de `node pruebas/g124_ensayo.mjs`:

```text
OK m08_no_disponible: BLOQUEADO, BLOQUEADO, BLOQUEADO; registro TÉCNICO
OK exporta_ok: APROBADO, APROBADO, NO_CONCLUYENTE; registro TÉCNICO
OK pdf_incompleto: RECHAZADO, APROBADO, NO_CONCLUYENTE; registro TÉCNICO
OK excel_sin_hojas: APROBADO, RECHAZADO, NO_CONCLUYENTE; registro TÉCNICO
OK otro_5xx: RECHAZADO, RECHAZADO, NO_CONCLUYENTE; registro TÉCNICO
OK sin_respuesta: NO_CONCLUYENTE, NO_CONCLUYENTE, NO_CONCLUYENTE; registro TÉCNICO
OK seleccion_automatica: APROBADO, APROBADO, NO_CONCLUYENTE; registro TÉCNICO
OK G124: 7/7 modos, resultado.json = informe, registro QA fiel
```
