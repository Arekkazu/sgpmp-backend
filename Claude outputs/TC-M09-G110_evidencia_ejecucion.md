# Evidencia de ejecución — TC-M09-G110 (TC-M09-210)

| Campo | Valor |
|---|---|
| Caso de prueba | TC-M09-G110 (TC-M09-210) |
| Descripción | Creación exitosa de una plantilla con nombre, especie activa y snapshot JSON válido (camino feliz) |
| Categoría | Funcional |
| RF | RF-31 |
| CU | CU-07 — Gestionar Plantillas de Configuración |
| Tipo | Prueba funcional — Frontend (Cypress) + Backend (Newman/Postman) |
| Entorno (frontend) | TEST — `http://sigab-frontendtest-6aqrny-d2b730-158-69-200-27.sslip.io` |
| Backend | TEST — `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test` |
| Cuenta usada | `admin.test@sgpmp.com.co` (Administrador) |
| Fecha de ejecución | 2026-09-05 |
| Ejecutado por | Daniela Castillo |
| Resultado | ⚠️ **DEFECTO CONFIRMADO en el flujo de creación desde la interfaz — el backend (API) funciona correctamente** |

## Validación contra el API (Newman)

Se inició sesión como Administrador, se consultó el catálogo de especies activas del entorno (Cachama Blanca, Camarón Blanco, Mojarra Plateada, Tilapia, Trucha Arcoíris — no existe una especie llamada "Bovino" en este entorno de TEST, que es de especies acuícolas; se usó Cachama Blanca como especie activa) y se registró la plantilla directamente contra `POST /configuracion/plantillas` con un `params_snapshot` JSON válido. La API respondió `201 Created`, la plantilla quedó en `version=1`, con el nombre y la especie enviados, y al consultar `GET /configuracion/plantillas` la plantilla recién creada aparece en el listado conservando su versión. Los 9 assertions de la colección pasaron sin fallos.

Esto confirma que la lógica de negocio de RF-31 (registrar una plantilla con nombre, especie activa y snapshot válido) está correctamente implementada en el backend.

## Defecto confirmado en el flujo de creación desde la interfaz (Cypress)

Al intentar el mismo camino feliz desde la interfaz (Configuración → Plantillas → "Nueva plantilla"), el formulario nunca permite completar la creación: después de elegir cualquier especie activa, la sección "Parámetros a incluir en la plantilla" no llega a mostrar los parámetros disponibles y en su lugar aparece el mensaje "No se pudo leer la configuración de la especie. Reintenta o elige otra.", dejando el botón "Crear plantilla" deshabilitado de forma permanente.

Se reprodujo este comportamiento con dos especies distintas — Cachama Blanca y Camarón Blanco (esta última con parámetros reales ya confirmados en TC-M09-G104) —, en ambas con el mismo resultado, lo que descarta que se trate de una especie sin datos configurados y confirma que el problema afecta a cualquier especie que se elija.

Revisando el código fuente del frontend se identificó la causa: la función `capturarConfiguracionEspecie()` (`src/configuration/api/especiesConfigApi.ts`) llama `.map()` directamente sobre el resultado de `ciclosApi.listar()`, `patologiasApi.listar()`, `metricasApi.listar()` y `umbralesApi.listar()`. Sin embargo, los cuatro endpoints que consultan (`GET /configuracion/ciclos`, `/patologias`, `/metricas` y `/umbrales`) responden con la forma `{ total, items }` y no con un arreglo directo, a diferencia de otros puntos de la aplicación (por ejemplo los consumidores de `especiesApi` y `plantillasApi`) que sí desenvuelven ese formato antes de usarlo. Como resultado, `.map()` falla sobre un objeto que no es un arreglo, la promesa se rechaza, y `PlantillaModal.tsx` cae en su rama de error, bloqueando por completo la creación de plantillas desde la interfaz — para cualquier usuario y cualquier especie.

## Impacto

RF-31 funciona correctamente a nivel de backend (API), pero el flujo de creación de plantillas está completamente bloqueado desde la interfaz de usuario, que es la vía principal por la que un usuario real crearía una plantilla. Ningún usuario puede crear una plantilla nueva desde Configuración en este momento.

## Recomendación

Corregir `capturarConfiguracionEspecie()` en `especiesConfigApi.ts` para desenvolver la respuesta `{ total, items }` de los 4 endpoints que consulta (`ciclosApi.listar`, `patologiasApi.listar`, `metricasApi.listar`, `umbralesApi.listar`) antes de aplicar `.map()`, siguiendo el mismo patrón defensivo ya usado en `useEspecies.ts` y `usePlantillas.ts` (`Array.isArray(raw) ? raw : raw?.items ?? []`).

## Herramientas

**Cypress (UI):**
```bash
CYPRESS_ADMIN_EMAIL="admin.test@sgpmp.com.co" CYPRESS_ADMIN_PASSWORD="Administrador123#" npx cypress run --browser chrome
```
Evidencia visual generada automáticamente en `RESULTADOS/`: video completo de la corrida (sin capturas de pantalla, ya que la creación no llega a completarse).

**Newman (API):**
```bash
newman run tc-m09-g110.json --reporters "cli,htmlextra" --reporter-htmlextra-export resultado-g110.html
```
