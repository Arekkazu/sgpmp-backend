# TC-M03-G87 — Automatización QA reutilizable

RF-58 Monitoreo Ambiental en Tiempo Real · CU04 · Responsable QA: Juan Esteban · Prioridad Alta.
Fuente: `Casos_Prueba(Modulo3 Agrupado).csv`, fila TC-M03-G87. Endpoint: `GET /iot/monitoreo/dashboard`.

Sin ejecuciones oficiales todavía. G87-V1 queda pendiente del preflight autenticado y de la habilitación QA; `QA_AUTORIZADO=NO` permanece sin cambios.

## Casos

| Caso | Qué se comprueba | Actor | Herramienta |
| --- | --- | --- | --- |
| TC-M03-168 | Tras tres LECTURA_VALIDA y una FUERA_DE_RANGO, el dashboard devuelve valor, unidad y timestamp de la última válida | Productor | Newman |
| TC-M03-177 | La FUERA_DE_RANGO no reemplaza el valor operativo 25 y la anomalía sigue visible (ROJO/ícono) | Productor | Newman + Cypress |
| TC-M03-178 | ERROR_CALIBRACION: el Productor no ve valor operativo, alerta ni datos técnicos; el Ingeniero identifica el error y ve el detalle; el sensor sigue visible | Productor + Ingeniero | Newman + Cypress |

Las aserciones están en `g87_casos.mjs` con un id estable. Newman y Cypress nombran cada prueba
`[CASO][PRE|ASSERT|INFO][ID]`.

## Archivos

| Archivo | Función |
| --- | --- |
| `ejecutar_tc_m03_g87.mjs` | Único ejecutor: validación local y ejecución oficial (preflight, sandbox, datos, Newman, Cypress, cierre, evidencia e informe). Incluye la configuración de Cypress. |
| `g87_casos.mjs` | Catálogo de casos y aserciones, plan de datos y efectos persistentes conocidos. |
| `g87_lib.mjs` | Funciones del grupo: configuración, barreras, sandbox, sanitización, versiones, veredictos, consolidación de evidencias e informe. |
| `TC-M03-G87.postman_collection.json` | Escenarios API. No inicia sesión: usa las sesiones del ejecutor. Sin autorización omite todas las peticiones. |
| `tc_m03_g87.cy.js` | Escenarios UI de 177 y 178. Sin mocks: solo añade las cabeceras del sandbox y serializa las peticiones. |
| `validar_local_g87.mjs` | Pruebas unitarias locales (`node --test`). |

## Uso

```powershell
node ejecutar_tc_m03_g87.mjs --validar-local

# Solo tras el preflight autenticado y con QA_AUTORIZADO=SI (lo habilita el responsable QA):
node ejecutar_tc_m03_g87.mjs --ejecutar --ambiente TEST --autorizacion "<referencia>" --tipo evaluacion --aceptar-efectos notificacion-login,sesion-observador
# Reintento técnico dentro de la misma evaluación:
node ejecutar_tc_m03_g87.mjs --ejecutar --ambiente TEST --autorizacion "<referencia>" --tipo reintento --aceptar-efectos notificacion-login,sesion-observador
```

`--version N` solo se usa para confirmar la versión cuando el historial es ambiguo.

## Resultados por evaluación

| Evaluación | Carpeta | Informe |
| --- | --- | --- |
| V1 | `RESULTADOS/G87-EVAL-V1-AAAAMMDD-HHMMSS/` | `TC-M03-G87_resultado.md` |
| V2 y siguientes | `EvaluacionVN/RESULTADOS/G87-REEVAL-VN-…/` | `TC-M03-G87_reevaluacion_VN.md` |

Cada RUN contiene:

- **Siempre:** el informe y un único `evidencia.json`.
- **Si aplica:** `newman/newman-TC-M03-G87.html` y `capturas/` con las tarjetas de los sensores, el detalle del Ingeniero y, si una tarjeta no aparece, una captura de la vista.
- **No se conservan:** el JSON bruto de Newman, el entorno temporal ni las descargas. Se eliminan siempre, también ante errores o interrupciones.

Reglas de versión:

- Un reintento técnico conserva la versión de la evaluación.
- Un RUN abortado en el preflight no consume versión.
- Si el historial es ambiguo, el ejecutor se detiene.
- Nada se sobrescribe.

## Datos que prepara el ejecutor (APIs oficiales)

- **Finca y testigo:** usa una finca persistente compartida por Preparacion, Productor e Ingeniero. Un Administrador QA distinto, autenticado fuera del RUN, debe poder leer un dispositivo SENSOR persistente de esa finca. Si falta cualquiera de estas condiciones, no prepara el fixture.
- **Area y dispositivo:** crea en el sandbox un area y un dispositivo sin gateway, con serial `QA_DEVICE_PREFIX-G87-<sello>`. El dispositivo debe ser visible dentro del RUN y ausente fuera, mientras el observador sigue viendo el control comparable. Repite el testigo antes y despues de los escenarios, cierra el RUN mediante `DELETE /test-control/runs/{run_id}` y vuelve a comprobarlo por API.
- **Sensores:** A y B calibrados; C sin calibracion, para que sus lecturas sean ERROR_CALIBRACION.
- **Rango operativo:** exige un umbral RF-17 activo y apto, descubierto por API. No crea umbrales, ya que no hay contrato API para descartar de forma segura una publicacion MQTT hacia Gateway Edge.
- **Hosts:** Newman usa `www.api.inmero.co/api-sgpmp-test`. Antes de Cypress, el host del frontend `api.inmero.co/api-sgpmp-test` debe leer el mismo dispositivo dentro del RUN. Si no, los criterios UI quedan bloqueados y Cypress no inicia.

## Veredicto propuesto (QA lo confirma revisando la evidencia)

- **BLOQUEADO:**
  - Hay una dependencia del entorno o de la preparación.
  - Falla una precondición (PRE). Si el sistema respondió en contra, también queda como hallazgo de la funcionalidad de la que depende.
  - Hay un error de automatización o de infraestructura.
- **RECHAZADO:** un criterio falla con evidencia de una respuesta real del producto.
- **APROBADO:** todo se verificó.

## Riesgos y efectos conocidos

- Los hasta seis logins pueden generar notificaciones persistentes fuera del sandbox. El login y cierre de sesion del observador ocurren fuera del RUN. Ambos efectos requieren aceptacion expresa mediante `--aceptar-efectos`.
- El sandbox vence tras 180 s de inactividad. Un testigo API fallido interrumpe los escenarios dependientes y fuerza el cierre.
- Un 404 del fixture no demuestra aislamiento por si solo: el observador debe leer correctamente un control comparable de la misma finca.
- No se usa SQL ni `/test-control/query`. Si falta el control, el umbral existente o la equivalencia de RUN entre hosts, se registra una dependencia, sin alterar las aserciones originales.

## Ejecución de Cypress

- **Proyecto:** la carpeta del grupo. **Configuración:** su archivo propio, `cypress.g87.config.cjs`, que no contiene ningún destino. Nunca se carga el `cypress.config.cjs` raíz, cuyo `baseUrl` es el API remoto. Sustituye a `configFile: false`, que Cypress 14 rechaza («`--config-file` cannot be false»): con esa opción las pruebas de interfaz nunca llegaban a ejecutarse.
- **Destinos:** las anulaciones van dentro de `e2e`. `baseUrl` es el frontend de TEST, que debe ser HTTPS y distinto del API (`env.API_BASE`); si no lo es, la ejecución se rechaza.
- **Artefactos y arranque:** el reporter es de consola, las capturas y descargas van a la carpeta del RUN y el proceso de Cypress no hereda `ELECTRON_RUN_AS_NODE`. La lógica está en `cypress_seguro.mjs`.
- **`--verificar-spec`:** comprueba destinos y barrera del spec con un proxy local. Ejecuta un proceso Cypress; úsese solo cuando exista además un bloqueo efectivo de salida externa. En esta preparación se verificaron estáticamente configuración y sintaxis sin iniciar Cypress.

```
node ejecutar_tc_m03_g87.mjs --verificar-spec
```
