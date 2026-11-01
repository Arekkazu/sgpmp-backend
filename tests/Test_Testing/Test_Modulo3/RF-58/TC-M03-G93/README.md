# TC-M03-G93 / TC-M03-184 — automatización y antecedentes V1

Estado: **RUN V1 oficial del intento 8: RECHAZADO**. La API acreditó la presencia del área nueva; la UI no mostró su tarjeta. Esta preparación documental conserva antecedentes de los intentos 6 y 7 sin crear otro RUN ni SOL. Una nueva decisión del caso requiere API y UI públicas en un RUN autorizado por el lanzador externo.

## Fuente y alcance

Fuente primaria: fila TC-M03-G93 de `Casos_Prueba(Modulo3 Agrupado).csv`, RF-58 / CU04 E1. Oráculo literal: «La unidad se muestra con estado GRIS y el mensaje "Sin datos disponibles", junto con la fecha del último dato histórico si existe; la unidad no desaparece del panel y no se devuelven errores 5xx ni valores fabricados.» La precondición exige una unidad autorizada recién creada sin lecturas y otra con todos los sensores sin señal. QA acepta «Sin datos» en UI e INACTIVO en la segunda variante. La decisión QA del 2026-10-31 añade BUFFER_ACTIVO como ausencia de señal, únicamente cuando todos los sensores están en SIN_SEÑAL, INACTIVO o BUFFER_ACTIVO y ninguno ACTIVO. Fundamento consultado en lectura: `src/telemetry/application/use_cases/infraestructura/evaluar_estado_dispositivos_use_case.py:49` y `src/telemetry/application/use_cases/infraestructura/recibir_heartbeat_use_case.py:115`, donde los tres estados se clasifican como `FALLO_CONECTIVIDAD`. La fecha solo se exige si existe.

En esta continuación se consultaron realmente los dos casos de uso citados arriba del backend, solo en lectura, `anotaciones/modulo_3/api_reference_m03_telemetria_iot.md:625-638` (contrato RF-58 del dashboard) y `RF-58/TC-M03-G88/g88.cy.js:155-245` como referencia de automatización. Las otras rutas backend indicadas en el párrafo previo se consultaron en una preparación anterior. El criterio de aceptación literal procede de la matriz original; no se encontró un documento RF-58 autónomo en las rutas de requisitos revisadas. El checkout frontend no está accesible desde este workspace; la observación sobre `MonitoreoView.tsx` procede del intento previo y queda pendiente de comprobación pública en TEST. La lectura local no prueba lo desplegado en TEST.

**DEFECTO_FUNCIONAL_CANDIDATO:** el intento previo señaló que `MonitoreoView.tsx` podría mostrar un párrafo en vez de la tarjeta cuando `sensores.length === 0 && !error`, aun si `resumen_unidades` contiene la unidad. UI-184-01 comprueba por API/UI pública si eso ocurre en TEST; no se emite veredicto por esa lectura previa.

## Inventario

| Clase | Archivos |
|---|---|
| Canónico | `g93.mjs`, `G93.postman_collection.json`, `g93.cy.js`, `g93.cypress.config.cjs` |
| Auxiliar activo | `lib/contrato_ejecutor.mjs`, `lib/g93_escenario.mjs`, `lib/g93_ui.cjs`, `lib/registro_local.mjs`, `lib/seguridad.mjs` |
| Test local | `pruebas/g93.test.mjs`, `pruebas/g93_ensayo_spec_real.mjs`, `pruebas/g93_arranque_local.mjs`, `pruebas/g93_ensayo.ps1` |
| Diagnóstico | operación `diagnostico` en el ejecutor, inactiva para este reintento |
| Evidencia oficial | `Resultados/RUN-G93-V1-20261031-080847/`; antecedentes saneados en `api/antecedentes/` dentro del mismo RUN |
| Duplicado o legado activo | ninguno detectado |

## Historial de intentos V1

| Intento | Registro documental |
|---|---|
| 1 | Previo al material conservado en este grupo; no se infiere veredicto ni resultado técnico. |
| 2 | Previo al material conservado en este grupo; no se infiere veredicto ni resultado técnico. |
| 3 | Previo al material conservado en este grupo; no se infiere veredicto ni resultado técnico. |
| 4 | Previo al material conservado en este grupo; no se infiere veredicto ni resultado técnico. |
| 5 | Previo al material conservado en este grupo; no se infiere veredicto ni resultado técnico. |
| 6 | API: área 519 ausente de `resumen_unidades` antes de #785. UI: refresh 200 y luego `/usuarios/me` y `/sesiones/me/permisos` 500 con eco; captura de acceso denegado. Extractos saneados y captura preservados en el RUN oficial. |
| 7 | API-184-01/02 APROBADO, primera confirmación de #785. Sesión UI concurrente con respuestas 500/401; candidatas V2 descartadas antes de la decisión QA sobre BUFFER_ACTIVO. Extractos saneados y captura preservados en el RUN oficial. |
| 8 | RUN oficial V1 RECHAZADO: API V1/V2 aprobada; UI-184-01 rechazada por ausencia de tarjeta del área 700. Con cola de peticiones, los errores de sesión 500/401 no se reprodujeron. |

Los RUN técnicos de los intentos 6 y 7 se eliminan por el orquestador después de esta preservación. La automatización y los enlaces del informe oficial apuntan solo a archivos conservados en el RUN oficial.

## Secuencia preparada

Preflight, login Administrador/Productor, apertura del RUN por el lanzador, consulta de finca 184 y área de referencia 349, POST de una unidad M09 sin sensores, descubrimiento y revalidación de área 1 o alternativa íntegramente sin señal (SIN_SEÑAL/INACTIVO/BUFFER_ACTIVO), canarios E7 filtrados con `por_pagina=1`, una ejecución Newman con API-184-01/02/03, observación técnica RLS-G93-01, Cypress UI-184-01/02, DELETE del RUN y comprobación pública del rollback. Cypress usa el token del login Productor obtenido por el ejecutor, espera `/usuarios/me` y `/sesiones/me/permisos` con HTTP 200 y eco del RUN y serializa las solicitudes API reales antes de abrir el dashboard. El ejecutor hace un login nuevo después del DELETE para las lecturas de cierre. La variante 2 se prepara aunque falle la semilla de la variante 1. En la unidad nueva, `ultimo_dato_recibido` nulo o una fecha histórica válida no decide por sí solo el rechazo; una fecha inválida sí incumple el oráculo.

Newman consulta exclusivamente `GET /iot/monitoreo/dashboard?id_infraestructura=<id>&pagina=1&por_pagina=50`. Cypress también envía al servidor solo consultas filtradas: cuando el frontend intenta su carga inicial sin filtro, el spec añade `id_infraestructura` a esa petición real y lo consigna en el acta como `filtro_aplicado_por_spec`. No simula la respuesta. El selector actual `#monitoreo-area` se ejerce para la segunda vista.

## Peticiones y efectos previstos en TEST

**Trayecto mínimo con área 1 elegible y sin finca ajena identificada: 23 peticiones API directas/Newman, más las peticiones del navegador.** La lista exacta de ese trayecto es: `POST /sesiones/` ×2; `GET /usuarios/me` ×2 para acreditar roles; `GET /configuracion/fincas/184` ×2; `GET /configuracion/infraestructuras/349` ×1; `POST /configuracion/infraestructuras` ×1; `GET /configuracion/infraestructuras/<nueva>` ×2 (alcance y rollback); `GET /configuracion/fincas?solo_activas=true` ×1; `GET /iot/monitoreo/dashboard?id_infraestructura=1&pagina=1&por_pagina=1` ×1; `GET /iot/monitoreo/dashboard?id_infraestructura=1&pagina=1&por_pagina=50` ×3 (búsqueda, revalidación, Newman); `GET /configuracion/infraestructuras/1` ×2 (preparación y control posterior); `GET /iot/monitoreo/dashboard?id_infraestructura=<nueva>&pagina=1&por_pagina=1` ×1; `GET /iot/monitoreo/dashboard?id_infraestructura=<nueva>&pagina=1&por_pagina=50` ×2 (Newman y rollback); `GET /iot/dispositivos?estado=INACTIVO` ×1; `DELETE /test-control/runs/<RUN>` ×1; `POST /sesiones/` ×1 para lectura de cierre tras UI. Los recuentos se confirman en la bitácora real.

Las alternativas 2/3 y la búsqueda acotada pueden añadir peticiones, incluida `GET /iot/dispositivos?estado=BUFFER_ACTIVO`; también puede haber hasta tres lecturas de detalles para RLS y una consulta filtrada de finca ajena. El ejecutor limita las directas a 56 con margen de 5 para cierre; Newman se invoca una vez y hace una o dos GET según las variantes preparadas. Cypress limita a 25 solicitudes API por vista; el número exacto de sus solicitudes depende de la versión desplegada y se contará en el acta real. Habrá una escritura de negocio M09 (`POST /configuracion/infraestructuras`), revertida solo si el DELETE y las lecturas de cierre lo acreditan. Login modifica la sesión; el DELETE modifica el sandbox. El canario corta consultas amplias ante sensor GRIS sin dato desactualizado o sin umbral, porque E7 podría auditar o enviar correo. No se presume reversión de esos efectos.

## Corrección documental del intento 7

El informe técnico del intento 7 asignaba por error INC-M03-184-G93-02 a Desarrollo y citaba #779. La asignación vigente de INC-02 es **DBA** (sandbox de pruebas; relación con DBA-01), sin issue de Desarrollo. **#779 corresponde a INC-M03-184-G93-01** y a la discrepancia UI posterior relacionada en INC-03. El generador del informe oficial consigna INC-02 como «NO REPRODUCIDA con peticiones serializadas»; la concurrencia sobre una conexión/transacción única sigue siendo hipótesis para DBA, sin causa raíz atribuida.

## Comprobaciones locales

```powershell
node --check g93.mjs
node --check g93.cy.js
node g93.mjs --capacidades
node g93.mjs --comprobar
node pruebas/g93.test.mjs
```

El responsable QA puede ejecutar, en un entorno local con Cypress/Chrome y loopback disponibles, `node pruebas/g93_ensayo_spec_real.mjs`. El ensayo usa temporales del sistema y nunca TEST. Este Codex no lanza Cypress porque el proceso hijo queda impedido por `spawn EPERM`. El RUN V1 intento 7 corresponde exclusivamente al lanzador externo y a una autorización humana particular; este README no es una SOL.
