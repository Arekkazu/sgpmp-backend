# TC-M03-G87 — RF-58 Monitoreo Ambiental en Tiempo Real

La fuente de los criterios es la fila `TC-M03-G87` de `Casos_Prueba(Modulo3 Agrupado).csv`. El flujo comprueba:

| Caso | Oráculo de la matriz | Cobertura |
| --- | --- | --- |
| TC-M03-168 | Tras tres lecturas `LECTURA_VALIDA` y una posterior `FUERA_DE_RANGO`, HTTP 200 y `ultimo_valor`, `ultima_unidad` y `ultimo_timestamp_captura` de la última válida. | API (Newman) |
| TC-M03-177 | El Productor conserva la última lectura válida (25) como referencia operativa; la anomalía `FUERA_DE_RANGO` permanece visible mediante ROJO/ícono. | API + UI (Newman y Cypress) |
| TC-M03-178 | `ERROR_CALIBRACION` no es valor ni alerta operativa del Productor y no expone sus datos técnicos; el Ingeniero identifica el error y el detalle para reconocer que requiere calibración. El sensor sigue visible. | API + UI (Newman y Cypress) |

## Estructura vigente

- `g87.mjs`: único ejecutor canónico.
- `G87.postman_collection.json`: única colección Newman vigente.
- `g87.cy.js` y `g87.cypress.config.cjs`: spec y configuración Cypress vigentes.
- `lib/g87_preparacion.mjs`, `lib/g87_seguridad.mjs`, `lib/g87_cierre.mjs`, `lib/g87_cypress_runner.mjs`, `lib/g87_cypress_worker.mjs` y `lib/g87_informe.mjs`: auxiliares del ejecutor.
- `pruebas/`: suites locales y ensayo V2 en memoria; `Resultados/`: evidencia histórica V1 intacta.

## Uso

Desde esta carpeta, `node g87.mjs --comprobar` hace comprobaciones locales sin red ni RUN. La ejecución en TEST corresponde exclusivamente al lanzador externo con autorización particular. La invocación heredada `node g87.mjs --autorizacion <ref> [--tipo reintento]` permanece para compatibilidad del ejecutor, con V1 fija. La recuperación directa con `--recuperar` está bloqueada; requiere el contrato del lanzador y permiso propio. Ningún comando de TEST se ejecuta durante la preparación local.

Para preparar una corrección documental sin consultar TEST: `node g87.mjs --regenerar-informe RUN-G87-V1-20261023-145303 --salida _paquete_responsables/TC-M03-G87_resultado.md`. La salida debe ser un Markdown nuevo en la raíz de G87 o en `_paquete_responsables/`; el comando lee las evidencias del RUN, conserva el informe oficial y no escribe en `Resultados/` ni `EvaluacionVn/`. El borrador registra el hash del informe vigente, conserva la trazabilidad de la primera regeneración y toma los metadatos locales del informe histórico, sin consultar Git. Los enlaces relativos de evidencia están preparados para la instalación dentro del RUN.

## Contrato propuesto sigab-qa-ejecutor/1

node g87.mjs --capacidades imprime JSON local, sin red ni autorización: operaciones evaluar, reintentar, reevaluar, recuperar, versiones 1..n. El paquete _paquete_orquestacion/ propone la extensión del lanzador protegido; no está instalada.

Tras instalarse, el lanzador reserva y registra el RUN y escribe contexto_operacion.json antes de invocar:

node g87.mjs --autorizacion <ref> --operacion <evaluar|reintentar|reevaluar|recuperar> --version <n> --intento <k> --run-id <RUN> --contexto <ruta-absoluta> [--run-objetivo <RUN>].

El ejecutor valida argumentos, contexto, grupo, casos y ruta antes de leer credenciales o acceder a TEST. V1 usa Resultados/; V2+ usa EvaluacionV<n>/Resultados/. Recuperación escribe una evidencia aparte dentro del RUN objetivo y no reemplaza resultado.json ni el informe. La utilidad neutra lib/contrato_ejecutor.mjs implementa la validación local para poder copiarla a otro grupo en una orden futura.

Las invocaciones heredadas siguen disponibles para compatibilidad local del ejecutor. Toda operación remota requiere lanzador y autorización específica. El registro persistente, las referencias consumidas y las versiones los administra únicamente el lanzador.

Dependencias de datos a verificar antes de cualquier escritura autorizada: S1, sensor 552, dispositivo 357 en infraestructura 349, especie 126, umbral 70 de 15–30 °C y calibración 68; S2, sensor 77, dispositivo 266, con asociación original al área 328 y sin calibración. El ejecutor comprueba por API las relaciones, el umbral activo, el rango físico, las asociaciones y el cupo; estos IDs son referencias de preparación, no resultados confirmados en esta fase. Si S1 no cumple sus precondiciones, 168 y 177 se bloquean sin impedir la comprobación independiente de 178 cuando S2 sí cumple las suyas.

Suites locales, sin TEST ni red, ejecutadas individualmente desde esta carpeta:

```powershell
node pruebas/validar_flujo_g87.mjs
node pruebas/g87_orden013.test.mjs
node pruebas/validar_orden_g87_005.mjs
node pruebas/validar_orden_g87_007.mjs
node pruebas/contrato_g87.test.mjs
```

## Evidencia de una evaluación autorizada

- V1 por defecto o reintento V1: `Resultados/RUN-G87-V1-<timestamp>/TC-M03-G87_resultado.md`.
- V2 únicamente por decisión expresa de reevaluación: `EvaluacionV2/Resultados/RUN-G87-V2-<timestamp>/TC-M03-G87_reevaluacion_V2.md`.
- Cada RUN guarda `resultado.json`, los reportes Newman JSON/HTML realmente generados en `newman/` y las capturas Cypress reales, si existen, en `cypress/`. Hay un solo Markdown oficial dentro del RUN, sin copia en la raíz de `Resultados/` ni `informe.md`.

El historial de intentos descartados se conserva en la carpeta de coordinación QA.

## Reevaluación V2 — ajuste local ORD-G87-039

La decisión QA reevalúa TC-M03-168, 177 y 178 sin cambiar sus oráculos ni los IDs API/UI de V1. Issue #678: Desarrollo informó backend PR #793 (última lectura válida separada de la condición reciente) y frontend PR #453 (referencia «Última lectura válida», anomalía visible y detalle de calibración por permiso). La revisión local no acredita el despliegue en TEST; el RUN autorizado debe conservar el contrato recibido por ambos roles y capturas de la UI servida.

El Productor debe ver 25 °C como última lectura válida de S1 después de 31 °C FUERA_DE_RANGO y un indicador claro de anomalía: semáforo ROJO o ícono con etiqueta. En S2 no debe recibir 21.7/22.3 °C como valor operativo, alerta operativa ni batería/RSSI/SNR o diagnóstico técnico reservado. El Ingeniero debe reconocer ERROR_CALIBRACION o «Requiere calibración» en API y detalle UI. Los campos nuevos `estado_calidad_valor_operativo`, `timestamp_estado_actual`, `indicador_anomalia`, `es_valor_operativo` y `etiqueta_estado` son evidencia complementaria; si faltan, el informe lo registra y aplica los oráculos V1.

El ejecutor V2 busca exactamente S1=552/dispositivo=357, S2=77/dispositivo=266 y área=349 en la finca 184, con umbral activo 15–30 °C; verifica sus relaciones reales antes de ingerir. Por decisión QA, las cuentas Productor UI e Ingeniero UI se usan también para las comprobaciones API de su rol: `/usuarios/me`, Newman, dashboard, visibilidad y host frontend. La RLS forzada desde 2026-10-29 impide que las cuentas API anteriores vean esta finca. V2 exige solo Administrador, Productor UI e Ingeniero UI; las variables `QA_PROD_*` y `QA_ENG_*` continúan siendo necesarias para V1. `/usuarios/me` debe confirmar rol Productor o Ingeniero de Campo y finca 184 para cada cuenta UI; si falla, los casos dependientes quedan `NO_CONCLUYENTE`. La ausencia de un sensor con rol y finca verificados sigue siendo comprobación funcional. El bloqueo de S1 no impide las comprobaciones independientes de S2, ni la falta de S2 impide comprobar 168/177.

Presupuesto para la SOL futura: tres logins de preparación fuera del RUN (Administrador, Productor UI e Ingeniero UI), uno por cuenta; lecturas públicas de perfil, infraestructura, umbrales, dispositivos, sensores y asociaciones; un RUN aislado con reasociación reversible de sensores existentes cuando haga falta, tres ingestas válidas y una fuera de rango para S1, dos ingestas con error de calibración para S2; una ejecución Newman, consultas API del dashboard por rol y host frontend, una ejecución Cypress que reutiliza los tokens UI mediante respuesta local interceptada al formulario (sin nuevos logins remotos), DELETE de cierre y lecturas de asociación, ocupación e historial para comprobar rollback. Los tres logins y posibles notificaciones de sesión son efectos externos al RUN. No ejecutar sin autorización particular y SOL revisada.

Ensayo sin red ni RUN: `node pruebas/g87_ensayo_v2.mjs` cubre 25 modos en memoria, incluidos los 21 originales, las cuentas UI en API y los fallos de rol/finca. El contrato exige `--operacion reevaluar --version 2`, `version_anterior=1` y `alcance_reevaluacion` en el contexto reservado por el lanzador. La ruta oficial es `EvaluacionV2/Resultados/RUN-G87-V2-<timestamp>/TC-M03-G87_reevaluacion_V2.md`.

## Corrección local ORD-G87-041 — intento técnico V2

El frontend consultado (`SGPMP-FRONT-END-PWA`, HEAD indicado por QA `0e92f570`) usa el token de `POST /sesiones/` para pedir `/usuarios/me` y `/sesiones/me/permisos` (`src/auth/hooks/useLogin.ts:43-46`, `src/shared/auth/AuthContext.tsx:235-258`). Guarda el JWT en memoria y el perfil/permisos en el contexto; conserva una copia de sesión offline cuando tiene los tres (`AuthContext.tsx:261-262,289-291`). El menú de Telemetría se renderiza si hay permiso de lectura en alguno de los recursos 33, 32, 34, 35, 37, 38 o 39 (`src/shared/design-system/Sidebar.tsx:37,65-73`); no utiliza `aria-disabled`. La pestaña de monitoreo se rotula «En vivo» y requiere `[33,2]` (`src/telemetry/pages/TelemetryPage.tsx:37-38`); `PestanasModulo.tsx:69-92` filtra las pestañas sin permiso y tampoco pone `aria-disabled`.

En V2, el ejecutor conserva **en memoria** el cuerpo íntegro de cada respuesta de login API ya realizada y lo entrega al formulario interceptado de la misma cuenta (`g87.mjs`, `g87.cy.js`). No inicia una segunda sesión UI. Cypress navega por el enlace visible de Telemetría y el botón visible «En vivo»; las llamadas reales posteriores a perfil, permisos y dashboard siguen dentro del RUN, con eco exigido. El worker sanea los JWT de esas respuestas antes de escribir el reporte local. Si falla la navegación, PRE-UI-01 se registra como ERROR_QA y sus comprobaciones dependientes quedan BLOQUEADO; el RUN continúa técnico y no acredita un rechazo funcional.

El intento V2 saneado muestra `Vigencia admin` HTTP 0 por timeout de 30 s antes del DELETE 200 (`resultado.json`, bitácora); el código anterior no reintentaba login para ese estado. Tras el DELETE del RUN, `lib/g87_cierre.mjs` valida el token inicial del Administrador con `/usuarios/me`; si no obtiene 200, hace un login nuevo **fuera del sandbox** antes de consultar asociaciones, ocupación e historial. Si el login falla, el rollback queda NO_CONCLUYENTE y el RUN no es oficial. El login adicional puede registrar último acceso, auditoría, notificaciones o cierre de una sesión anterior; la SOL nueva debe incluirlo como efecto y presupuestar hasta **cuatro logins** (tres iniciales y uno posible del Administrador tras el DELETE). No se prevé login UI adicional con la estrategia elegida. Las lecturas poscierre son públicas autenticadas y pueden tener los efectos de consulta ya descritos para RF-58. El ensayo local ahora cubre 27 modos, incluidos `ui_login_completo`, `ui_menu_no_habilita`, `admin_token_invalido_en_cierre` y `admin_relogin_falla`.

## Preparación local ORD-G87-043

En `0e92f570`, `TelemetryPage.tsx:37,82` abre «En vivo» en `/telemetria/monitoreo`. `MonitoreoView.tsx:52,65-69,81-89,161-170` carga el dashboard, ofrece el filtro «Área» y hace polling cada 30 s. `SelectorArea.tsx:27-33` usa el combobox de `Combobox.tsx:99-125`: entrada de texto con `role="combobox"`, etiqueta «Área» e ID `monitoreo-area`; escribir `349` fija `id_infraestructura=349`. `useAreas.ts:23-28` consulta `/iot/monitoreo/dashboard?por_pagina=1`; `useMonitoreo.ts:24-37` consulta el mismo endpoint con `por_pagina=50`, `pagina=1` y, tras filtrar, `id_infraestructura=349` (`monitoreoApi.ts:37-45`).

`MonitoreoView.tsx:218-249` agrupa por área plegable y renderiza `SensorCard` solo para problemas ROJO/AMARILLO; VERDE es `SensorFila.tsx:15-33`, y sensores sin datos pueden quedar bajo `<details>`. Las dos variantes usan botón `OptionCard.tsx:15-22`. La píldora de anomalía sale de `EstadoLecturaPill.tsx:42-49` y `estadoLectura.ts:24-35`; el texto «Última lectura válida» se muestra en `SensorCard.tsx:60-62` y en `SensorDetalleModal.tsx:45-47` solo cuando `indicador_anomalia && es_valor_operativo`. El detalle usa `ModalShell.tsx:31-45`, que expone `role="dialog"` y botón de cierre etiquetado.

El contrato saneado del intento 9 tiene S1 con `estado_semaforo=VERDE`, `indicador_anomalia=true` y `es_valor_operativo=true`. En la vista actual lo coloca en `SensorFila`, que muestra el valor y `EstadoSensorPills`; «Última lectura válida» es evidencia complementaria y no un oráculo de `UI-177-02`. El spec comprueba 25 °C y el indicador claro de anomalía por separado, filtra por combobox, abre el área y cualquier `<details>` necesario, y encuentra sensores por el texto del botón. Cypress toma capturas de las comprobaciones y de fallos; el ejecutor copia `cypress/` al RUN también si Cypress falla.

No se completó el ensayo de extremo a extremo local: Vite intentó cargar `vite.config.ts` con el `esbuild` instalado y Windows devolvió `Error: spawn EPERM` antes de servir la página. No se instalaron paquetes ni se generó RUN. El ensayo en memoria cubre 27 modos, incluidos `ui_filtro_area_no_encontrado` y `ui_flujo_completo`.

## Ensayo UI local de G87 V2 — ORD-G87-044

Desde esta carpeta, en el Windows del responsable QA:

```powershell
node pruebas/g87_ui_local.mjs --comprobar
node pruebas/g87_ui_local.mjs
```

`--comprobar` valida sin iniciar procesos las dependencias ya instaladas y el contrato del RUN oficial V2. El segundo comando sirve `SGPMP-FRONT-END-PWA` en `127.0.0.1` con Vite y su plugin React ya instalados, ejecuta el único spec `g87.cy.js` con Cypress Electron y detiene Vite al terminar. Vite usa configuración en memoria y caché temporal para no escribir en el frontend. No instala paquetes, no consulta TEST y no crea RUN. La API apunta a otro puerto local libre sin servidor, que Cypress intercepta. El modo local bloquea peticiones de la página hacia otros hosts y responde con fixtures en memoria para login, perfil, permisos y dashboard. El login usa un JWT ficticio sin firma y un correo sintético `.invalid` solo en el formulario; ningún token o correo real se copia de la evidencia.

Los dashboards salen de las dos respuestas Newman del RUN oficial V2 más reciente, actualmente `RUN-G87-V2-20261030-150450`. El script comprueba `oficial=true` y `clasificacion=OFICIAL` en `resultado.json`, compara sus campos de negocio y sustituye nombres por alias locales. Perfil y permisos son simulaciones mínimas para navegar la UI. Las capturas, `vite.log` y `resultado-ui-local.json` quedan en la ruta temporal que el comando imprime. La línea final esperada es `OK G87 UI local: 11/11 comprobaciones UI`; si falla, separa comprobaciones fallidas y omitidas, y el JSON conserva sus estados y las rutas API sin fixture. Las capturas locales sirven para diagnosticar el spec y la presentación; solo un RUN TEST autorizado puede sustentar un veredicto de producto.

## Corrección local ORD-G87-045

El spec usa viewport de 1440×900 y navega a `/telemetria/monitoreo` dentro de la SPA después de que el login llegue a `/dashboard`; conserva así la sesión en memoria y evita depender del menú lateral plegable. Espera la respuesta `/iot/monitoreo/dashboard` antes de filtrar por área. El ensayo local completa peticiones HTTP a `/`, a la ruta de monitoreo y a los módulos iniciales de Vite antes de abrir Cypress; solo allí amplía `pageLoadTimeout` a 180 s. Los fixtures locales cubren las peticiones observadas de portada, shell y monitoreo, y el resumen cuenta únicamente pruebas `passed`. Los IDs y oráculos UI no cambian. En este entorno de Codex, Vite respondió HTTP 500 al precalentar `src/main.tsx` porque `esbuild` recibió `spawn EPERM`; la ejecución de Cypress local quedó pendiente del Windows del responsable QA.
