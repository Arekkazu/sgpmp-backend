# TC-M09-G23 — Resultado para revisión humana

**Estado general: PASS.**

Los originales TC-M09-50 y TC-M09-51 obtuvieron exactamente HTTP 400 por la relación min/max en su primer y único POST Newman, sin persistencia. La evidencia Cypress final mostró el formulario real con los datos inválidos, bloqueó el envío localmente, mostró ambos mensajes y confirmó por GET la ausencia de persistencia. Hay cuatro recorridos Cypress fallidos iniciales, preservados como evidencia de depuración; dos recorridos posteriores, autorizados para continuar la prueba, son los que validan la UI.

| Original | Regla enviada a API | API | POST de umbral | UI complementaria |
|---|---|---|---|---|
| TC-M09-50 | 10 == 10 | **PASS**, 400, sin persistencia | 1 Newman; 0 UI | **PASS**: ambos mensajes, 0 POST, GET 200 sin registro |
| TC-M09-51 | 40 > 10 | **PASS**, 400, sin persistencia | 1 Newman; 0 UI | **PASS**: ambos mensajes, 0 POST, GET 200 sin registro |

Responsable: Juan Esteban. M09 / RF-17 / CU-03. Prioridad alta. Técnica: valores límite. Actor: Administrador TEST. No hubo reintentos Newman. Las ejecuciones Cypress finales fueron evidencia visual adicional y no emitieron POST a umbrales. G22 no se ejecutó ni modificó; G24 no se inició.

## Entorno y versiones

- Fecha: 2026-09-05, ejecuciones entre 20:14 y 20:42 UTC (15:14–15:42 America/Bogota); los JSON conservan sus timestamps.
- Rama local en ambos repositorios, verificada al inicio y al cierre: `qa/juan-esteban-m09`.
- Frontend SHA local: `966621df4e2c6a1f2c9233ea5ebefbb9e3bc2f56`.
- Backend SHA local: `b6131f190e01768599f3ef5e4f9c13487cd78f68`.
- **SHA desplegado en TEST no confirmado. Los SHA anteriores son locales.**
- Frontend: `https://sigab-frontendtest-6aqrny-d2b730-158-69-200-27.sslip.io`.
- Backend base: `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`.
- Newman 6.2.2; reporter real `newman-reporter-htmlextra` 1.23.1, previamente instalado.
- Cypress 13.17.0, Electron 118.0.5993.159 headless, Node 22.15.1. TypeScript 5.9.3. Python backend 3.13.13.
- Antes de cada ejecución Newman: frontend `/login`, backend `/health` y `/openapi.json` devolvieron 200. Se verificó que OpenAPI contiene el POST de umbrales. Login real 200; permisos recurso 20, acciones crear/consultar comprobados.

## Contrato, selección de datos y aislamiento de la regla

Revisión read-only del backend local:

- `src/configuration/infrastructure/dto/registrar_umbral_dto.py`: `validar_rango` rechaza `valor_max <= valor_min` mediante un validador de campo Pydantic. También exige exactamente tres niveles: normal, precaucion y critico.
- `src/configuration/infrastructure/dto/nivel_dto.py`: cada intervalo debe tener inferior menor que superior.
- `src/configuration/infrastructure/routers/umbral_router.py`: recibe el DTO antes de invocar `RegistrarUmbralUseCase.execute` y el repositorio de escritura.
- `src/shared/error_handlers.py`: transforma `RequestValidationError` en 400 / `VAL_ENTRADA`, con detalles en `fields`. No hay código exclusivo de rango: se verificó además que el único campo rechazado fuera `valor_max` y el mensaje exigiera estrictamente mayor que `valor_min`.
- El router documenta también 422; para estas entradas se observó el 400 del manejador real. No se aceptó 422 como PASS.
- GET de umbrales incluye activos e inactivos por defecto (`solo_activas=False` en router/repositorio). El catálogo de variables lista únicamente activas mediante `listar_activas`.

Antes de cada POST se consultaron permisos, especies, variables y umbrales. Se filtraron especies activas y se eligió una combinación ausente en el GET completo. Los IDs de abajo fueron descubiertos, no fijados en la automatización. Se repitió el descubrimiento antes de cada recorrido Cypress.

La selección real fue Cachama Blanca, especie **4**, activa; Temperatura Ambiental, variable **9**, catálogo activo; unidad **°C** y límites físicos **−50 a 100**. Antes del POST existían umbrales 10 y 11 para otras variables, pero ninguno para especie 4 / variable 9. La [comprobación final](verificacion-final-readonly.json) volvió a confirmar esos registros, la especie activa, la variable del catálogo activo y los permisos.

Se usaron los mismos tres niveles en ambos payloads:

| Nivel | Inferior | Superior |
|---|---:|---:|
| normal | -20 | 10 |
| precaucion | 10 | 40 |
| critico | 40 | 70 |

Son intervalos individuales positivos, contiguos y físicamente válidos. Es matemáticamente imposible que tres intervalos positivos cubran un padre vacío o invertido. Por ello no se afirma que los niveles cubran estos padres inválidos: se observa la validación anterior del DTO. En TEST la respuesta identifica **solo la relación min/max**, sin errores de duplicidad, niveles, límites físicos ni referencias inexistentes. No se amplió la prueba a esas otras reglas.

## TC-M09-50 — PASS API

- Endpoint: `POST /configuracion/umbrales`.
- Especie 4 Cachama Blanca; variable 9 Temperatura Ambiental; física −50 a 100 °C.
- Payload: `id_especie=4`, `id_variable_ambiental=9`, `valor_min=10`, `valor_max=10`, con los tres niveles de la tabla anterior.
- Intentos: **1 POST**, sin reintento. HTTP **400**.
- Respuesta sanitizada real:

```json
{
  "error_code": "VAL_ENTRADA",
  "message": "Errores de validacion en la solicitud",
  "fields": [{
    "field": "valor_max",
    "message": "Value error, valor_max debe ser estrictamente mayor que valor_min."
  }],
  "timestamp": "2026-09-05T20:14:52.424778+00:00"
}
```

No devolvió ID creado ni estado de éxito. GET posterior `GET /configuracion/umbrales?id_especie=4`: **200**, total 2, IDs 10 y 11; **0 coincidencias** para variable 9. Un GET adicional del runner y el GET final después de Cypress confirmaron ausencia. No hubo limpieza ni modificaciones posteriores.

Evidencia: [datos y payload](datos-TC-M09-50-intento1.json), [HTML Newman](newman-TC-M09-50-intento1.html), [JSON Newman](newman-TC-M09-50-intento1.json).

## TC-M09-51 — PASS API

- Endpoint: `POST /configuracion/umbrales`.
- Especie 4 Cachama Blanca; variable 9 Temperatura Ambiental; física −50 a 100 °C.
- Payload: `id_especie=4`, `id_variable_ambiental=9`, `valor_min=40`, `valor_max=10`, con los tres niveles anteriores.
- Intentos: **1 POST**, sin reintento. HTTP **400**.
- Respuesta sanitizada real:

```json
{
  "error_code": "VAL_ENTRADA",
  "message": "Errores de validacion en la solicitud",
  "fields": [{
    "field": "valor_max",
    "message": "Value error, valor_max debe ser estrictamente mayor que valor_min."
  }],
  "timestamp": "2026-09-05T20:15:32.676569+00:00"
}
```

No devolvió ID creado ni estado de éxito. GET posterior `GET /configuracion/umbrales?id_especie=4`: **200**, total 2, IDs 10 y 11; **0 coincidencias** para variable 9. También se verificó con GET adicional y al cierre. TC-M09-51 se lanzó independientemente, después de inspeccionar el PASS y la ausencia de persistencia de TC-M09-50.

Evidencia: [datos y payload](datos-TC-M09-51-intento1.json), [HTML Newman](newman-TC-M09-51-intento1.html), [JSON Newman](newman-TC-M09-51-intento1.json).

## Newman

| Ejecución | Requests de colección | Assertions | Failures | Resultado |
|---|---:|---:|---:|---|
| TC-M09-50 intento1 | 2 (POST + GET) | 8 | 0 | PASS |
| TC-M09-51 intento1 | 2 (POST + GET) | 8 | 0 | PASS |
| Total | 4 | 16 | 0 | PASS API |

Los conteos excluyen login, preflight, descubrimiento y GET adicional del runner. Los HTML provienen del reporter htmlextra durante Newman real; no son HTML manuales. El JSON es un resumen estructurado propio con payload, respuesta, estadísticas y GET, sin volcar el entorno con credenciales. No hubo respuesta 500, 409, 422 o 201 en ninguno de los dos POST.

## Cypress — PASS, evidencia visual real

Configuración aplicada: `screenshotOnRunFailure: true`, `trashAssetsBeforeRuns: false`, `video: false`, `retries: 0`; directorios separados por `G23_RUN_ID`. Login y navegación reales en TEST. Los interceptores únicamente observaron tráfico: no sustituyeron respuestas. No se emplearon mocks, `cy.wait` numéricos, pausas fijas ni `force:true`.

La corrección quedó únicamente en la automatización G23: para un padre inválido no se rellenan los seis niveles. La UI bloquea el submit por `valor_min`/`valor_max` antes de una solicitud y los valores por defecto de niveles no son necesarios para evaluar esa regla. El cambio evita que una superposición visual de niveles contamine la prueba de límites.

| Run ID | Caso | Resultado | UI observada | POST umbral | GET posterior |
|---|---|---|---|---:|---|
| tc50-ui-evidencia1 | TC-M09-50 | PASS | 10 / 10; «Debe ser menor al máximo.» y «Debe ser mayor al mínimo.» | 0 | 200; 0 coincidencias de variable 9 |
| tc51-ui-evidencia1 | TC-M09-51 | PASS | 40 / 10; «Debe ser menor al máximo.» y «Debe ser mayor al mínimo.» | 0 | 200; 0 coincidencias de variable 9 |

Cada recorrido pasó un test Cypress. Los JSON de UI registran `posts: []`, `postGetStatus: 200`, `persisted: []` y `STOP_ALL: false`. Se produjeron cuatro capturas explícitas: datos inválidos y validación para cada original. Las imágenes no se editaron.

- [TC50 datos inválidos](<screenshots/tc50-ui-evidencia1/tc-m09-g23-rangos-invalidos.cy.ts/TC-M09-50-datos-invalidos.png>) y [validación](<screenshots/tc50-ui-evidencia1/tc-m09-g23-rangos-invalidos.cy.ts/TC-M09-50-validacion.png>).
- [TC51 datos inválidos](<screenshots/tc51-ui-evidencia1/tc-m09-g23-rangos-invalidos.cy.ts/TC-M09-51-datos-invalidos.png>) y [validación](<screenshots/tc51-ui-evidencia1/tc-m09-g23-rangos-invalidos.cy.ts/TC-M09-51-validacion.png>).
- [Resultado Cypress TC50](cypress-TC-M09-50-tc50-ui-evidencia1.json) y [evidencia estructurada TC50](ui-TC-M09-50-tc50-ui-evidencia1.json).
- [Resultado Cypress TC51](cypress-TC-M09-51-tc51-ui-evidencia1.json) y [evidencia estructurada TC51](ui-TC-M09-51-tc51-ui-evidencia1.json).

Se conservan cuatro recorridos fallidos iniciales como diagnóstico. Ninguno ejecutó un POST de umbral. No alteran el resultado de los recorridos de evidencia que sí completaron todos los asserts; se mantienen para trazabilidad.

| Run ID | Hallazgo inicial | POST umbral |
|---|---|---:|
| tc50-intento1 | Recarga tras login recibió 500 en `/sesiones/refresh`. | 0 |
| tc50-intento2 | Selector de automatización buscaba un enlace inexistente en Sidebar. | 0 |
| tc51-intento1 | Botón Nuevo umbral recortado en viewport 1440×1200. | 0 |
| tc51-intento2 | `normal_sup` cubierto por `precaucion_inf` al rellenar niveles. | 0 |

Resultados de diagnóstico: [TC50 intento1](cypress-TC-M09-50-tc50-intento1.json), [TC50 intento2](cypress-TC-M09-50-tc50-intento2.json), [TC51 intento1](cypress-TC-M09-51-tc51-intento1.json), [TC51 intento2](cypress-TC-M09-51-tc51-intento2.json).

## Hallazgos y limitaciones

**QA-JE-G23-AUTO-01 — Error de navegación/selector de automatización, resuelto en la prueba.** El segundo recorrido TC50 buscó un enlace inexistente. Se corrigió solo G23 para usar `nav.ds-sidebar button` con texto Configuración, verificado en `src/shared/design-system/Sidebar.tsx`. La navegación funcionó en los dos recorridos finales. No se atribuye este fallo al producto.

**QA-JE-G23-UI-01 — Superposición de campos de niveles, severidad propuesta media.** En TEST/Electron 118 y viewport 1920×1200, formulario Nuevo umbral ambiental: `normal_sup` está cubierto por `precaucion_inf`. Evidencia del segundo recorrido TC51: screenshot y error de actionability. Impide completar el formulario con clic estándar de Cypress. Código local relacionado: `NivelCard` y grillas de `UmbralesSection.tsx`; no se confirmó una causa CSS única ni se modificó el producto. La observación no demuestra que toda interacción por teclado sea imposible. Requiere revisión humana del diseño; no es un fallo demostrado de la regla min/max.

**QA-JE-G23-OBS-01 — Refresh 500 al recargar después de login.** Observado una vez durante TC50 intento1; la captura registra endpoint, status y vuelta a login. No se capturó el cuerpo del error ni se investigó la causa de autenticación fuera de G23. La navegación SPA permitió continuar con TC51; no constituye bloqueo transversal de RF-17.

**QA-JE-G23-OBS-02 — Nuevo umbral recortado en viewport 1440×1200.** Impidió el primer recorrido TC51; el segundo logró abrir el modal con viewport 1920×1200 y desplazamiento al botón. Evidencia de interacción, sin afirmar un defecto para todos los tamaños de pantalla.

**Relación con QA-JE-G22-01:** no impidió las dos validaciones API. Ambas retornaron 400 específico de rango antes del caso de uso de creación según el flujo local revisado. No se repitió la creación válida, la investigación de BD ni se corrigió el ORM. El resultado G23 no demuestra que el defecto de G22 esté resuelto.

## Seguridad y estado final

- Contraseña obtenida de la fuente del usuario solo en memoria; token solo en memoria de los procesos. No se imprimieron ni persistieron valores de credenciales, JWT, refresh tokens, cookies o Authorization completo.
- Reporter configurado para omitir headers/entorno; sanitización adicional de HTML y JSON. Revisión de secretos documentada en [seguridad-evidencias.json](seguridad-evidencias.json); las ocho capturas se revisaron visualmente y no muestran secretos ni DevTools abiertos.
- **No se usó PostgreSQL directo**, ni siquiera SELECT: API y GET resolvieron la comprobación requerida. Ningún SQL de escritura, migración o cambio de datos directo.
- Ningún POST de umbral exitoso; no se modificaron registros compartidos de configuración. La autenticación y las lecturas usaron las rutas normales del sistema. No hubo eliminación o desactivación de datos.
- Ningún cambio en código funcional, dependencias, infraestructura, G22 o ramas. No hubo commit, push, pull, merge ni ninguna operación Git de escritura.
- G23 queda completo: API y UI PASS. Los fallos iniciales se conservan como diagnóstico, sin alterar la clasificación de los casos originales. Se detiene aquí, sin iniciar G24.

## Git final

Backend: `git status --short` vacío y `git diff --stat` vacío. Frontend: `git diff --stat` vacío porque todo el trabajo G23 es nuevo/untracked. No hay archivos versionados modificados.

`git status --short` del frontend:

```text
?? testing/test_testing/Modulo9/RF-17/TC-M09-G22/README.md
?? testing/test_testing/Modulo9/RF-17/TC-M09-G22/RESULTADOS/
?? testing/test_testing/Modulo9/RF-17/TC-M09-G22/TC-M09-G22.postman_collection.json
?? testing/test_testing/Modulo9/RF-17/TC-M09-G22/cypress.config.cjs
?? testing/test_testing/Modulo9/RF-17/TC-M09-G22/helpers.cjs
?? testing/test_testing/Modulo9/RF-17/TC-M09-G22/investigar_bd.py
?? testing/test_testing/Modulo9/RF-17/TC-M09-G22/run-newman.cjs
?? testing/test_testing/Modulo9/RF-17/TC-M09-G22/tc-m09-g22-umbrales-validos.cy.ts
?? testing/test_testing/Modulo9/RF-17/TC-M09-G23/
```

Los elementos G22 ya estaban untracked al iniciar y se preservaron. Solo se crearon archivos dentro de G23: README, helpers, runner Newman, colección Postman, configuración/spec Cypress, auxiliar read-only de cierre y RESULTADOS. El resumen de Git queda en [git-final.json](git-final.json); la salida de `git ls-files --others --exclude-standard` limitada a G23 se verificó al cierre.
