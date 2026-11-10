# TC-M06-G40 — preparación local

Caso `TC-M06-018`, RF-86 v2.0, CA-21 y FA-5. Oráculo original: sin par en RF-109, el hecho queda `PENDIENTE_CUENTA`, visible en M06, el Contador recibe una alerta con la combinación, y al completar la matriz se genera la línea. QA aprobó D1: una línea pendiente sin cuentas representa el hecho; no debe haber línea `REGISTRADA` con cuentas antes de completar la matriz. D2 permite desactivar la asignación genérica y crear una específica dentro del RUN.

## Inventario y fuentes

G40 contiene un ejecutor (`g40.mjs`), una colección Newman, un spec/config Cypress y auxiliares en `lib/` y `pruebas/`. No hay archivos duplicados ni RUN históricos en G40. Se revisaron G39 (`g39.mjs`, `g39_core.mjs`, contrato, hijo Newman, registro QA, ensayos, README), G38 (predictor/flujo de pesaje, contrato, ensayos) y G34 (spec/config Cypress, bandeja y auditoría, RUN oficial). No se modificaron.

Fuentes primarias leídas: `tests/Test_Testing/Test_Modulo6/Casos_Prueba(Modulo6Agrup).csv:383`; `tests/Test_Testing/Test_Modulo6/CASOS_DE_USO_actualizado - Modulo 6.csv:653-654`; `src/financial_valuation/application/services/contabilizador.py:70-86`; `src/financial_valuation/infrastructure/routers/m06_router.py:79-85,115-129,225-230,498-511`; `src/financial_valuation/infrastructure/dto/m06_dto.py:49-62`; `src/identity_access/infrastructure/routers/notificaciones_routers.py:34-67`; `src/identity_access/infrastructure/schema/notificacion_schema.py:9-39`; frontend `src/financial_valuation/pages/FinanzasPage.tsx:68-96`, `ConfiguracionContableView.tsx:24-48` y `AuditoriaView.tsx:29`. La ruta UI es `/finanzas/configuracion`; el aviso existente solo muestra el conteo. El código local no determina el veredicto de TEST.

`DEFECTO_FUNCIONAL_CANDIDATO`: en el flujo local de `contabilizador.asentar`, la línea pendiente se audita pero no se llama al notificador del Contador. La prueba pública compara la bandeja propia del Contador antes y después del hecho, y abre la bandeja en Cypress. Solo un RUN autorizado en TEST puede confirmar el incumplimiento.

## Uso previsto por el lanzador autorizado

`node g40.mjs --capacidades` y `node g40.mjs --comprobar` son locales. El lanzador crea el contexto en `Resultados/RUN-G40-V1-.../contexto_operacion.json` o `EvaluacionVN/Resultados/RUN-G40-VN-.../contexto_operacion.json`, aporta autorización particular y ejecuta el CLI. `leerEnv` y `preflight.json` se evalúan antes de cualquier petición. El ejecutor no crea RUN; DELETE se hace en `finally`. El informe, `resultado.json`, Newman y Cypress se guardan en el RUN. No se declara oficial si faltan UI, Newman o rollback comprobado.

La bandeja `/notificaciones` exige usuario autenticado y lista solo las propias; no tiene recurso RBAC `notificaciones` en el router revisado. Se verifica la sesión del Contador y su permiso para configuración R/C/U, valoración R/E, auditoría R; el acceso real a la bandeja se contrasta antes de escribir.

Presupuesto: 150 solicitudes del ejecutor y 1800 segundos; Newman y Cypress agregan lecturas con límites propios. El procesamiento M06 puede atender eventos ajenos pendientes: revisar este efecto antes de autorizar un RUN real. Las credenciales nunca se escriben en evidencias.

## Ensayos

ORD-G40-004: se corrigió la clasificación de URLs del interceptor para el frontal con pathname raíz. En el ensayo, los GET del origen frontal se admiten como recursos del frontal salvo los que pertenecen a la base del API; la base del API tiene prioridad si ambos comparten origen. La afirmación de ORD-G40-004 sobre la ruta relativa del API era incorrecta cuando su pathname base era `/`.

ORD-G40-005: `clasificarIntercepcion` devuelve `{destino,ruta}`; para API, `ruta` empieza en `/`, excluye el pathname base normalizado y conserva `/sesiones/`. Para frontal o bloqueado, `ruta` es `null`. El spec usa este valor en la sonda, el login local, los alias y el acta. Las pruebas `node:test` cubren rutas reales y de ensayo, incluida la consulta de notificaciones. No se ejecutó Cypress ni TEST; el humo local de Cypress queda pendiente de repetir en Windows. Estos ensayos no acreditan el producto.

Revisión completa de operaciones de URL en `g40.cy.js` (líneas tras ORD-G40-005):

| Línea | Operación | Conclusión |
| --- | --- | --- |
| 3 | Quitar barras finales de `API` y `FRONT` | La concatenación con rutas que empiezan en `/` produce una sola barra; se conserva. |
| 9, 11, 13–14 | Validar base real o loopback con pathname `/` | Ambas formas aceptadas corresponden a los dos modos; se conserva. |
| 19 | `clean(...).slice(0,160)` | Limita texto del acta, no calcula pathname; se conserva. |
| 22–28 | Construir URL, clasificar y registrar `ruta` | Se eliminó el `pathname.slice(base.pathname.length)` defectuoso; el acta recibe la ruta normalizada del clasificador. El pathname de host bloqueado es absoluto y solo se sanea. |
| 30–38 | Comparar ruta con sonda, sesión y alias | Todos usan la misma ruta normalizada, incluidos `/sesiones/` y `/notificaciones` con query. |
| 52–53 | `FRONT+'/login'` y `API+'/__g40_sonda__'` | Las bases ya carecen de barra final; las rutas tienen barra inicial; se conservan. |
| 58–60 | Quitar barra final del pathname frontal, concatenar ruta y comprobar ubicación | Base raíz produce `/finanzas/configuracion`; base real produce `/sigab-test/finanzas/configuracion`; se conserva. |

Los ensayos de `pruebas/` usan un servidor loopback temporal y datos simulados; no son evidencia de producto. La palabra `oficial=sí` en estos ensayos valida solo la regla de decisión simulada. Ejecutar en este Windows con `node --test --experimental-test-isolation=none pruebas/g40_env.test.mjs pruebas/g40_decisiones.test.mjs`, `node pruebas/g40_ensayo.mjs` y `node pruebas/g40_cypress_smoke.mjs`. El humo usa Cypress real con Electron headless mediante `cypress_hijo.mjs`, verifica tres escenarios de panel y bandeja, cabeceras del RUN, acta y captura, y borra el RUN sintético en `finally`. El modo de ensayo solo admite 127.0.0.1 o localhost; el modo de RUN exige los hosts canónicos. En un entorno que devuelva `spawn EPERM`, repetir el humo en Windows antes del RUN autorizado.

## Tabla de decisiones del ensayo

Cada fila se ejecuta por `principal()` contra el servidor loopback serial de `fixture_g40.mjs`, con el catálogo simulado del contrato. `g40_decisiones.test.mjs` imprime `OK escenario_fila_*` y verifica estado, oficialidad, ausencia de solapamiento y presupuesto. `g40_ensayo.mjs` conserva los cuatro escenarios integrales.

| Fila | Estado esperado | Oficial simulado |
| --- | --- | --- |
| Selección sin bovino apto | BLOQUEADO | no |
| Permiso faltante de configuración del Contador | NO_CONCLUYENTE | no |
| Matriz sin asignación esperada | BLOQUEADO | no |
| DELETE matriz 404 | NO_CONCLUYENTE | no |
| Pesaje 4xx | NO_CONCLUYENTE | no |
| Procesar 4xx | NO_CONCLUYENTE | no |
| Línea REGISTRADA pese a faltar el par | RECHAZADO | sí |
| Línea ausente | RECHAZADO | sí |
| Panel sin aviso | RECHAZADO | sí |
| Panel con conteo distinto | RECHAZADO | sí |
| Alerta presente con combinación | APROBADO | sí |
| Alerta traducida con combinación | APROBADO | sí |
| Alerta genérica sin combinación | RECHAZADO | sí |
| Alerta anterior a la línea base | RECHAZADO | sí |
| Alerta ausente | RECHAZADO | sí |
| POST matriz sin `lineas_resueltas` | RECHAZADO | sí |
| Línea que no pasa a REGISTRADA | RECHAZADO | sí |
| Matriz no restaurada tras cierre | NO_CONCLUYENTE | no |
| Cypress caído | NO_CONCLUYENTE | no |
| Newman con fallo | NO_CONCLUYENTE | no |

Para el aviso al Contador se aceptan `VARIACION_VR_TB` o «Variación por transformación biológica» para el tipo de hecho y `GANANCIA` o «Ganancia» para el sentido; si el mensaje menciona especie, debe identificar la seleccionada por ID (`39` en el fixture) o nombre («Bovino» en el fixture). Las etiquetas provienen de `SGPMP-FRONT-END-PWA/src/shared/i18n/locales/es-CO/finanzas.json`, claves `hecho.VARIACION_VR_TB` y `sentido.GANANCIA` (líneas 215 y 206). `NotificationTray.tsx:222-245` pinta `notificacion.mensaje` en cada artículo. La API y Cypress cotejan IDs nuevos frente a la bandeja base del Contador; un mensaje anterior o genérico no satisface FA-5.

## ORD-G40-006 — bandeja sin aviso

El humo informado para ORD-G40-005 llegó a `@notificaciones` con HTTP 200 y eco, pero Cypress salió con código 1 antes del veredicto. La aserción que podía fallar solo con bandeja vacía era `g40.cy.js:78` anterior a esta orden: `cy.get('#notification-tray',{timeout:30000}).should('be.visible')`. El frontal falso creaba una sección vacía sin tamaño, que Cypress podía considerar invisible. La aserción posterior de artículos estaba condicionada a `avisosNuevos.length`. Esta identificación se basa en el flujo y el humo informado; la salida original de Cypress no se conservó. El humo local de esta orden no pudo arrancar Cypress aquí (`spawn EPERM`); confirmar la línea con el nuevo registro en Windows.

El componente real `SGPMP-FRONT-END-PWA/src/notificaciones/components/NotificationTray.tsx:116-127` renderiza `#notification-tray` cuando está abierto y en `:211-220` pinta un estado vacío sin notificaciones; los artículos se generan en `:221-234`. El frontal falso reproduce ahora carga y estado vacío. El spec registra `bandeja_abierta`, `avisos_en_ui` y `avisos_nuevos_api` sin aserciones por ausencia de aviso. La API consultada desde la UI determina cuáles avisos son nuevos y coinciden con la combinación; la bandeja y el texto visible son comprobación complementaria. Sin aviso nuevo y con panel y conteo correctos resulta `RECHAZADO`; con aviso nuevo visible resulta `APROBADO`. HTTP, eco y carga del panel siguen siendo fallos técnicos.

`cypress_hijo.mjs` guarda stdout y stderr saneados en `cypress/G40-cypress-salida.log` dentro del directorio temporal del escenario, limitado a las últimas 4000 líneas, y los muestra si Cypress falla. El humo también muestra ese archivo al fallar. El directorio sintético se elimina en `finally`; no es un RUN de TEST.

## ORD-G40-008 — localizador del panel

El RUN-G40-V1-20261109-125342 queda intacto. Su captura muestra el aviso, pero el spec buscaba `#cfg-general [role="alert"]`. En el frontal, `cfg-general` es el `h2` de General y el aviso precede a esa sección. El spec ahora busca el `Alert` de advertencia por rol y clases en toda la vista, lee el título con singular o plural real y espera hasta 30 s. Si no aparece tras una respuesta válida de configuración, registra `panel_visible=false` y continúa a la bandeja para emitir `RECHAZADO` por el panel. Un fallo de host, eco o respuesta sigue siendo técnico.

El humo local reproduce el aviso como hermano anterior a General y añade un escenario de dos líneas. `node --test --experimental-test-isolation=none pruebas/g40_env.test.mjs pruebas/g40_decisiones.test.mjs pruebas/g40_panel_contrato.test.mjs` verifica también el localizador contra `ConfiguracionContableView.tsx`, `Alert.tsx` y `finanzas.json`. `node pruebas/g40_ensayo.mjs` conserva los escenarios simulados. Repetir `node pruebas/g40_cypress_smoke.mjs` en Windows antes de un RUN autorizado; ese humo no acredita TEST.
