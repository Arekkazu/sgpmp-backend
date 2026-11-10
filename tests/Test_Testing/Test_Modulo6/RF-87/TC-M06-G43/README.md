# TC-M06-G43 — preparación local de RF-87

La cobertura conserva los oráculos de `TC-M06-024` a `TC-M06-027`, la matriz, la expiración, las ramas 409/500 y la comparación de cierre 8 con el paso 3 observadas en G43. La colección `G43.postman_collection.json`, `g43.cy.js`, `g43.cypress.config.cjs` y `g43.mjs` son las entradas vigentes. Los RUN anteriores permanecen históricos y no forman parte de esta preparación.

## Verificación local única

```powershell
node pruebas/verificar.mjs
```

El procedimiento usa `os.tmpdir()`, ejecuta ocho pasos en orden, bloquea intentos de red externa en los procesos Node que controla y comunica clasificación por paso. En el sandbox de Codex, `spawn EPERM` impide Cypress real, los lanzadores en proceso hijo y Pydantic desde el procedimiento; el responsable QA debe ejecutarlo en un entorno que permita procesos hijos. No requiere acceso a TEST. La validación local en proceso de CLI, escenarios y forma de resultado sí se ejecuta aquí.

## Infraestructura copiable

Cada archivo deduce el grupo por la carpeta `TC-M06-Gnn` o recibe capacidades y datos específicos. La copia a otro grupo debe incluir sus propios archivos de escenario y contrato, sin importar G43 en tiempo de ejecución.

| Archivo | Origen o función | SHA-256 |
|---|---|---|
| `lib/infra.mjs` | `g43.mjs` de ORD-G43-008; forma del `resultado.json` oficial de G40 | `9880c8b7c192560bed6875fa33a50bb2cd12d3bd411816f762413978c400d416` |
| `lib/contrato.mjs` | módulo de contrato existente en G43, sin nombre de grupo fijo | `bfd07b9e5de3c12ac466c9fe0ff4a4f82afa7c91ffd0d190cb6e529a0b750fff` |
| `lib/informe.mjs` | plantilla extraída del ejecutor G43 | `9b463aba8eda7ea510987fefb7703aea8a8b5ac57b81f66c3af7d215aaae6c62` |
| `pruebas/newman_hijo.mjs` | `TC-M06-G42/pruebas/newman_hijo.mjs` | `38ecb80490ff6e8fe05bd86896e01c835f850313c04fca0c91c734d4a7b08455` |
| `pruebas/cypress_hijo.mjs` | `TC-M06-G40/pruebas/cypress_hijo.mjs` | `0ba473fe11ddaed69a9611603af66752447ee368960e97e32d3f7c9692b440f6` |
| `pruebas/simulador_base.mjs` | nuevo simulador local parametrizado | `7f2c25452a91aced28df47883ff69431aca3a9e7149a35e024d247abc6e1e16c` |
| `pruebas/verificar.mjs` | nuevo procedimiento local único | `e57b8217888b21ad5200029c0becba49f132ceed3a7342a5e5926e698c439a1e` |

`g43.cy.js` adapta la base de `TC-M06-G40/g40.cy.js` (validación de entorno, `LOCAL_SMOKE`, sonda, login local, intercepción, acta y captura difuminada). `g43.cypress.config.cjs` adapta la configuración de G40. `pruebas/escenarios_g43.json` contiene únicamente las expectativas de los paneles usadas por el simulador local. Los datos de caso y veredictos siguen en `g43.mjs` y `lib/g43_core.mjs`.

## Forma del resultado

El ejecutor conserva los campos anteriores y agrega `cierre.run.cierre_http`, `cierre.rollback.verificado`, `cypress.total_pruebas`, `comprobaciones`, `consume_version`, `clasificacion_fallo` y `sha256`. `lib/infra.mjs` contiene la validación de forma y la clasificación local. El informe oficial se genera una sola vez dentro del RUN correspondiente, junto con `resultado.json` y los artefactos reales. La fase de preparación no crea RUN ni informe.

Las rutas de código de producto consultadas en órdenes anteriores figuran en el historial de G43. Esta corrección leyó la automatización de G43 y las referencias acotadas de G40/G42, sin reabrir código de producto.
