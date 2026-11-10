# TC-M06-G43 — preparación local de RF-87

Casos `TC-M06-024` a `027`. El oráculo procede de la fila original `TC-M06-G43` de `Casos_Prueba(Modulo6Agrup).csv` (Windows-1252), RF-87 y decisiones de `ORD-G43-001`. El contrato de respuestas procede del código local citado en `pruebas/contrato_g43.json`; no redefine las expectativas.

## Inventario

G43 estaba vacía. Se revisaron en solo lectura el ejecutor, librería, contrato, colección, pruebas, registro QA y README de G42; estructura de RUN y registro de G41; spec/config y método de lectura del sandbox de G40. No había archivos activos, duplicados ni legado en G43. La colección `G43.postman_collection.json`, el spec `g43.cy.js`, la configuración `g43.cypress.config.cjs` y `g43.mjs` son los únicos vigentes.

## Ejecución

`node g43.mjs --capacidades`, `node g43.mjs --comprobar`, `node pruebas/g43_local.test.mjs`, `node pruebas/g43_decisiones.test.mjs`, `node pruebas/g43_escenarios.test.mjs` y `../../../../../.venv/Scripts/python.exe pruebas/g43_dto.test.py` son locales. Los escenarios usan Newman real contra loopback y no crean RUN. El lanzador externo debe suministrar contexto de RUN, autorización particular y variables de entorno; ejecutar `g43.mjs` con `--operacion`, `--version`, `--intento`, `--run-id`, `--autorizacion` y `--contexto`. Esta preparación no crea RUN ni toca TEST.

El ejecutor usa los períodos 8, 219 y 220 una vez cada uno, comprueba permisos (incluida auditoría financiera R) antes de escribir, limita a 240 solicitudes y 1800 s, y envía peticiones en serie. Prepara dentro del RUN hasta cuatro pares de matriz faltantes mediante `POST /finanzas/configuracion/matriz`, tomando cuentas de un par genérico del mismo sentido; si no hay par de origen, termina sin escrituras. `cierre8CoincideG32` está copiada en G43 y cita su origen G42, sin importación entre grupos. El frontend de TEST recibe las cabeceras del RUN mediante interceptación de Cypress; Cypress bloquea escrituras y hosts ajenos. La UI jamás ejecuta cierres. Newman lee datos finales; los reportes, capturas, video, `resultado.json` y un único Markdown oficial se escriben dentro del RUN. Un `DELETE` del RUN va seguido de lecturas sin cabeceras del sandbox, incluidas las asignaciones de matriz creadas.

## Cobertura y riesgos

| Caso | API | UI |
|---|---|---|
| 024 | 409, estado EN_CIERRE, P_ini/P_nuevo, precio congelado y cálculos | panel de autorización de 8 |
| 025 | lista, No con rollback, Sí con exclusión y cierre | panel de 219, lista y decisión |
| 026 | contrato de confirmación, exclusiones, costo y RF-92 | panel de 220, confirmación por activo |
| 027 | línea 17 y faltantes, EN_CIERRE, No y Sí | panel de 8, asientos y activos |

El código revisado sugiere `DEFECTO_FUNCIONAL_CANDIDATO` en la pausa de 024/027, en la confirmación de 026 y en la lista UI de 027. Solo evidencia de un RUN autorizado permite `RECHAZADO`. La cuenta de Contador descrita en la orden carece de `auditoria_financiera R`; si el cierre 8 falla con 500 y ese permiso sigue ausente, el ejecutor no atribuye el error a G32 por conjetura. Los equinos con costo y precio vigente, y la vida útil M06/M09, son observaciones externas al veredicto de G43.

## Corrección de arranque ORD-G43-008

El CLI carga `.env.qa` del repositorio solo cuando `QA_AUTORIZADO=SI`, con precedencia de `process.env`, igual que G42. Antes de cualquier petición guarda `preflight.json` con identificación, barreras por nombre y efectos. Si falla, termina con código 2 y cero peticiones. `SIGAB_FRONT_TEST_BASE` es opcional y, si existe, debe ser el frontend canónico.

El contexto del RUN mantiene la validación de ruta y contenido. Newman recibe sus variables mediante el entorno de colección; Cypress las recibe en su entrada. Los dos procesos hijos heredan el entorno cargado. `node pruebas/g43_cli.test.mjs` ejercita el punto de entrada CLI sin modo ensayo con `.env.qa` sintético y contexto temporal. Intercepta `fetch` antes de la red y verifica cero conexiones a un servidor espía en loopback. La ruta alternativa de archivo y contexto solo se habilita con `NODE_ENV=test` y `--prueba-cli-local`.

## Rutas de código leídas

`src/financial_valuation/infrastructure/routers/m06_router.py`, `infrastructure/dto/m06_dto.py`, `application/use_cases/cierre/ejecutar_cierre_periodo_use_case.py`, `application/use_cases/precios/registrar_precio_use_case.py`, `domain/services/precios.py`, `infrastructure/repositories/periodo_repository.py`, `infrastructure/repositories/valoracion_repository.py`, `infrastructure/repositories/reporte_repository.py`, `application/services/reportes.py`, y `SGPMP-FRONT-END-PWA/src/financial_valuation/pages/CierreView.tsx` y `components/comunes.tsx` (solo lectura). Las demás citas del contrato copiadas de G42 se indican como derivadas de esa referencia, no como rutas reabiertas en esta orden.
