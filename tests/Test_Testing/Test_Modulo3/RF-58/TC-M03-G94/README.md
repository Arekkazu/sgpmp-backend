# TC-M03-G94 — RF-58/CU04 E4

**Caso:** TC-M03-185. Oráculo literal de la matriz: «HTTP 200 con arreglos vacíos. La interfaz muestra "No tiene unidades productivas asignadas" y sugiere contactar al administrador; no se devuelve ningún dato de otras granjas ni error interno». La UI es obligatoria.

## Historial V1

- Intento 1 (26-oct, RUN-G94-V1-20261026-041954): API-185-01/02 APROBADO; UI-185-01 BLOQUEADO por refresh 200 y perfil/permisos 500 dentro del sandbox. El dashboard no se solicitó. DELETE 200 y fincas [1,57,80,184] restituidas. Su evidencia nativa fue eliminada por decisión QA; la transcripción conservada es fuente secundaria.
- Intento 2 (26-oct, RUN-G94-V1-20261026-043704): API-185-01/02 APROBADO; UI-185-01 NO_CONCLUYENTE. Refresh fuera del sandbox 200; perfil y permisos fuera sin respuesta durante unos 34 s. Dentro, tema 401 y luego tema e idioma 500; dashboard no solicitado. DELETE 200 y fincas originales restituidas. El responsable QA autorizó preservar extractos antes de eliminar este RUN técnico.
- Intento 3 (31-oct, RUN-G94-V1-20261031-090629): RUN oficial V1, TC-M03-185 **RECHAZADO**. API-185-01/02 APROBADO; UI-185-01 RECHAZADO: el dashboard respondió 200, pero el aviso visual fue distinto del exigido. Véase el [informe oficial](Resultados/RUN-G94-V1-20261031-090629/TC-M03-G94_resultado.md) y su [índice de antecedentes](Resultados/RUN-G94-V1-20261031-090629/api/antecedentes/indice.json).

## Automatización vigente

`g94.mjs` es el ejecutor canónico; `G94.postman_collection.json` verifica las dos API y `g94.cy.js` con `g94.cypress.config.cjs` verifica la UI. `lib/` contiene el contrato, escenario y saneamiento; `pruebas/g94.test.mjs` es la validación local. `pruebas/g94_arranque_local.mjs` y `pruebas/g94_ensayo_spec_real.mjs` son auxiliares de ensayo local. No hay ejecutor, colección ni spec/config duplicados. La automatización y este README no enlazan el RUN técnico del intento 2.

## Validación y siguiente acción

Ejecutar localmente `node --check g94.mjs`, `node g94.mjs --comprobar` y `node pruebas/g94.test.mjs`; estas operaciones no acceden a TEST ni crean RUN. El responsable QA revisa INC-M03-185-G94-01 con Desarrollo y decide una reevaluación autorizada tras la corrección. Los antecedentes de sesión de los intentos 1 y 2 no cambian el veredicto del intento 3 ni acreditan una causa raíz.
