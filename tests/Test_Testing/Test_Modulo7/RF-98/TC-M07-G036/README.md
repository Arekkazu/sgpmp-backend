# TC-M07-G036 — verificación local de preparación

Este grupo usa un único ejecutor (`g036.mjs`), una colección Newman y un spec/config Cypress. El procedimiento local usa solo `127.0.0.1`, escribe ensayos bajo `%TEMP%` y no consulta TEST. El responsable QA debe ejecutarlo en Windows desde esta carpeta:

```powershell
Set-Location 'C:\Users\yoloh\OneDrive\Escritorio\pruebas\sgpmp-backend\tests\Test_Testing\Test_Modulo7\RF-98\TC-M07-G036'
node pruebas/verificar.mjs
```

SHA-256 esperado de `g036.mjs`: `4062ab99737ef342ad312617d97ac3ec0dd96f0b272ab0f18bc462a1ed66ee9c`. SHA-256 esperado de `verificar.mjs`: `ccd389fb82b2a3f3890a62b6438ca34aef0002c8dff4849a329afc89331006fe`. SHA-256 de `pruebas/g036_local.test.mjs`: `485604dbf2e87dc9c81003c0151297515da0851e183c87c3a8a94686468173b4`. La salida de `verificar.mjs` incluye el hash efectivo y una tabla de diez pasos; todos deben quedar `OK`, incluido `RED` con cero intentos externos. Si hay fallo, el directorio temporal de diagnóstico se indica en la salida. El detalle de preparación se conserva en `SIGAB_QA_ORQUESTACION/informes/` y `SIGAB_QA_ORQUESTACION/estado/preparaciones/M07/TC-M07-G036/`.

El paso 5 comprueba doce escenarios locales (a-l), sus cinco veredictos, oficialidad, rollback y ausencia de problemas técnicos cuando corresponde. El paso 10 conserva un ejemplo local completo en `%TEMP%\g036-verificar-ejemplo\RUN-G036-V1-20261117-000000\` y `capacidades.json` en la carpeta superior. El responsable QA ejecuta después:

```powershell
Set-Location 'C:\Users\yoloh\OneDrive\Escritorio\pruebas\SIGAB_QA_ORQUESTACION'
& 'C:\Users\yoloh\OneDrive\Escritorio\pruebas\sgpmp-backend\.venv\Scripts\python.exe' scripts\registro_qa.py validar --grupo G036 --resultado "$env:TEMP\g036-verificar-ejemplo\RUN-G036-V1-20261117-000000\resultado.json" --capacidades "$env:TEMP\g036-verificar-ejemplo\capacidades.json"
```

El ejemplo es una simulación local. Los archivos bajo `%TEMP%` no son un RUN de TEST ni evidencia funcional. La ejecución futura en TEST requiere autorización humana independiente; el login previo puede persistir último acceso, auditoría de sesión y notificación.

## Orden ORD-G036-007: validación local en proceso

Se ejecutaron los diez escenarios con el simulador HTTP de `127.0.0.1`, Newman real mediante `newman.run` en el mismo proceso y un lanzador Cypress inyectado que escribió un acta simulada en `%TEMP%`. Se comprobaron para cada escenario los cinco veredictos, oficialidad, rollback, problemas técnicos vacíos y todas las aserciones del paso 6 de `verificar.mjs` sobre `resultado.json`. La oficialidad aquí califica solo el resultado simulado; no acredita TEST. El navegador Cypress y los lanzadores que requieren `spawn` siguen pendientes de ejecución local por el responsable QA.

```text
OK escenario_a_conforme: 01=APROBADO 02=APROBADO 03=APROBADO 04=RECHAZADO 05=APROBADO; oficial=true; rollback=true
OK escenario_b_inyectado: 01=APROBADO 02=APROBADO 03=APROBADO 04=RECHAZADO 05=APROBADO; oficial=true; rollback=true
OK escenario_c_barajado: 01=APROBADO 02=APROBADO 03=APROBADO 04=RECHAZADO 05=APROBADO; oficial=true; rollback=true
OK escenario_d_inyectado_barajado: 01=APROBADO 02=APROBADO 03=APROBADO 04=RECHAZADO 05=APROBADO; oficial=true; rollback=true
OK escenario_e_sin_revision: 01=APROBADO 02=APROBADO 03=NO_CONCLUYENTE 04=RECHAZADO 05=APROBADO; oficial=false; rollback=true
OK escenario_f_sin_permisos: 01=NO_CONCLUYENTE 02=NO_CONCLUYENTE 03=NO_CONCLUYENTE 04=NO_CONCLUYENTE 05=NO_CONCLUYENTE; oficial=false; rollback=true
OK escenario_g_revision_rechazada: 01=APROBADO 02=APROBADO 03=RECHAZADO 04=RECHAZADO 05=APROBADO; oficial=true; rollback=true
OK escenario_h_sin_aprobado: 01=NO_CONCLUYENTE 02=NO_CONCLUYENTE 03=NO_CONCLUYENTE 04=NO_CONCLUYENTE 05=NO_CONCLUYENTE; oficial=false; rollback=true
OK escenario_i_rollback_fallido: 01=APROBADO 02=APROBADO 03=APROBADO 04=RECHAZADO 05=APROBADO; oficial=false; rollback=false
OK escenario_j_01_fallido: 01=RECHAZADO 02=APROBADO 03=APROBADO 04=RECHAZADO 05=APROBADO; oficial=true; rollback=true
```

### Correspondencia del spec con la UI real y el doble

| Selector o texto de `g036.cy.js` | Fuente consultada | Presente en el doble |
| --- | --- | --- |
| `/login`, `input[type=email]`, `input[type=password]`, `button[type=submit]`, `POST /sesiones/` | `g43.cy.js:21-25,56-61`; `AuthContext.tsx:227-234` | Sí: formulario, interceptación local y navegación tras `pushState` |
| `/integracion/contrato` | `IntegracionPage.tsx:34-38` | Sí: `popstate` carga la tabla |
| `section[aria-label="Versiones del contrato"] tbody tr strong` | `integracion.json:contrato.versiones`; `ContratosView.tsx:102-120` | Sí: sección, tabla y versión en `strong` |
| `Activa`, `En retiro`, `Retirada`, `Pendiente` | `integracion.json:estado.ACTIVO/DEPRECADO/INACTIVO/PENDIENTE`; `ContratosView.tsx:28-30,118-137` | Sí: celdas de estado |
| `Retirar con plazo`, `Activar` | `integracion.json:contrato.deprecar/activar`; `ContratosView.tsx:129-136` | Sí: botones condicionados por estado |
| `Registrar versión`, `[role="dialog"]` | `integracion.json:contrato.registrar_version`; `ContratosView.tsx:105,224` | Sí: botón y modal |
| `.ds-field > label` + `input` para `Versión`, `Fecha de vigencia`, `Plazo de retiro de la versión anterior (días)` | `integracion.json:contrato.version_campo/fecha_vigencia/gracia`; `ContratosView.tsx:234,239,250`; `Input.tsx:50-64` | Sí: las tres etiquetas y controles |
| `.ds-field > label` + `select` para `Tipo de cambio`, `Anexo de mapeo` | `integracion.json:contrato.tipo_cambio/anexo`; `ContratosView.tsx:235-242`; `Select.tsx:34-42` | Sí: ambas etiquetas y controles |
| `input[type=checkbox]` marcado, `Facturas de compra` | `integracion.json:mapeador.COMPRAS`; `ContratosView.tsx:243-245` | Sí: casilla marcada y deshabilitada |
| `Cambio mayor (retira la anterior con plazo)` | `integracion.json:tipo_cambio.MAJOR`; `ContratosView.tsx:120,236` | Sí: opción y fila |
| `Guardar` | `integracion.json:comun.guardar`; `ContratosView.tsx:225` | Sí: botón del modal |

Los hashes vigentes figuran arriba. La revisión de codificación UTF-8 no encontró signos `?` que sustituyan letras acentuadas. Quedan para QA únicamente los pasos de `verificar.mjs` que invocan procesos hijos: Cypress real contra el doble, comprobación de bloqueo de host, lanzadores Newman/Cypress con `spawn` y ejecución completa del verificador. `node --test` produjo `spawn EPERM` en este entorno; la misma suite ejecutada con `node pruebas/g036_local.test.mjs` pasó sus 60 pruebas.




## Orden ORD-G036-009: contrato del lanzador

`g036.mjs` declara `sigab-qa-ejecutor/1`, `evaluar`/`reintentar` y las comprobaciones de los cinco casos. El punto de entrada valida `contexto_operacion.json`, escribe `preflight.json` antes de peticiones y usa el RUN precreado por el lanzador. La prueba local en proceso validó capacidades, contexto, preflight sin peticiones y resultado/informe contra el simulador con Cypress inyectado. `node pruebas/g036_local.test.mjs` pasó 60/60; los diez escenarios en proceso dieron las diez líneas `OK`. `node --check` y `--comprobar` pasaron. Queda para el responsable QA ejecutar `node pruebas/verificar.mjs` en un entorno que permita `spawn`; esta ronda no ejecutó sus diez pasos ni TEST.

## Orden ORD-G036-010: restauración del contrato de resultado

`completarResultado()` conserva `cierre.run` y restaura `autorizacion_referencia`, `consume_version`, `cypress` con contador numérico, los IDs por caso, comprobaciones `ASSERT` e incidencias por comprobación. `pruebas/verificar.mjs` exporta las comprobaciones de los pasos 6 y 10. La clasificación local sigue `registro_qa.py:226-263`: coherencia y cierre (231-244), cobertura de ASSERT (245-254), evidencias y clasificación (255-263).

Validación local: 61/61 pruebas unitarias, diez escenarios y diez contratos de `resultado.json` OK; `a_conforme` fue OFICIAL y `i_rollback_fallido`, `f_sin_permisos`, `h_sin_aprobado` fueron TECNICO en la reproducción Node. La prueba de reglas confirmó auditoría ausente MEDIA, versión creada ALTA y `VAL_ENTRADA` sin creación BAJA. `node --check` y `--comprobar` pasaron. El verificador completo se intentó, pero este entorno devuelve `spawn EPERM` para procesos hijos; sus diez pasos requieren ejecución por QA en un entorno que permita `spawn`. No hubo acceso a TEST.

## ORD-G036-011: correccion local R8/R9

FRONT canonico: `https://api.inmero.co/sigab-test` (API: `https://www.api.inmero.co/api-sgpmp-test`). `SIGAB_FRONT_TEST_BASE` es opcional y usa ese valor por defecto. La intercepcion y la validacion Cypress aceptan los dos origenes del patron de G43. El acta registra cinco hitos y el error saneado. Un fallo tecnico anterior a pantalla o en visita, red, intercepcion o navegacion deja 05 NO_CONCLUYENTE sin incidencia de producto. Una asercion de producto tras pantalla se clasifica como rechazo; la lectura API de 4.2 se realiza solo despues del registro.

La prueba local ejecuto los 12 escenarios a-l en proceso; `k_frontal_404` quedo TECNICO sin incidencia 05 y `l_ui_accion_incorrecta` quedo OFICIAL con UI_ACCIONES_INCORRECTAS MEDIA. Los pasos 6 y 10 importados de `verificar.mjs` pasaron para los 12 resultados. `node pruebas/g036_local.test.mjs`: 64/64; sintaxis y `--comprobar`: OK. El verificador integral sigue fallando por `spawn EPERM` en este entorno; su paso de red registro cero intentos externos. No se ejecuto TEST ni se altero el RUN historico.

SHA-256 de los demas archivos modificados: `g036.cy.js` f46db1ae99a535900221105e7d7f31a7bcf32a12a12179920b00c2ab51078eff; `lib/g036_core.mjs` 86a8bdd0fe6bf4b295cd031ea9621702374e860ce08598f75121829f100467c5; `lib/intercepcion.cjs` 3856eeb9c638fd1d9375c8d370122e8e2df5aff4597d6d84788f4a3bc174239e; `pruebas/cypress_hijo.mjs` c87339777455d7016ed05f764ae79ea4cd5a6465540ffe4d624932f3c9fd09c6; `pruebas/escenarios_g036.mjs` e4b73920f07baf940fb6dc266f853b9f6c699350dbde6ea09da22f190d93daa9; `pruebas/escenarios_g036.json` c32b011e505dc457f50229a0a938daf6f388b3415a111e8a5cbfc158028ec42a.

## ORD-G036-013: enmienda local de saneado

Se enmascaró la contraseña de `POST /sesiones/` en los dos `resultado.json`, sin cambiar veredictos ni otros datos. `g036.mjs` sanea claves sensibles en solicitudes, respuestas, errores y salidas JSON/Markdown del ejecutor. SHA-256 vigentes de `resultado.json`: `RUN-G036-V1-20261118-034446` = `eb9e4bfe0c67c7a51723029f756bca29b2789f819b3c8797885fc4e610579301`; `RUN-G036-V1-20261118-040435` = `9c2b369bd070e72d9b595127876d0fe9743924f6bbe9ff533a12288bea7d634d`. Los SHA anteriores figuran en la enmienda de cada informe.

Validación local: `node --check`, `--comprobar` y 65/65 pruebas locales OK. La comparación byte a byte confirmó que cada `resultado.json` cambió solo en el valor de `contrasena`; el barrido de ambos RUN no halló el valor previo en otros archivos. Se reprodujo `actualizar_desde_resultado` de `registro_qa.py` con los RUN enmendados: 034446 = TECNICO y 040435 = OFICIAL. Las copias temporales usadas para comparar se eliminaron.

## ORD-G036-014: enmienda del informe oficial

El informe del RUN `RUN-G036-V1-20261118-040435` se reescribió con detalle esperado/observado por caso y una ficha consolidada `INC-M07-G036-01`. La función `informe()` y la prueba local `a_conforme` generan y comprueban esa estructura. Los veredictos y `resultado.json` no cambiaron. Las versiones previas se conservan en la orquestación QA.

SHA-256: `resultado.json` `9c2b369bd070e72d9b595127876d0fe9743924f6bbe9ff533a12288bea7d634d`; informe oficial de esta enmienda `e16ad054b88caf00afc7c99557bfeeb5da0792ef12b09f2afb50f4aeb680a486`. Los SHA-256 de Newman y Cypress se conservaron.
## ORD-G036-016: sustituci?n literal del informe oficial

SHA-256 del informe oficial `Resultados/RUN-G036-V1-20261118-040435/TC-M07-G036_resultado.md`: `526d6fa8a2c49cd61e71e4ea956a618af606820eaf4a5168b161b1ecf975f6e2`.
