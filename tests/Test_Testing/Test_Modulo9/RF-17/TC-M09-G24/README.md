# TC-M09-G24 — RF17, niveles de alerta

Responsable Juan Esteban. Solo TEST real. No ejecutar G22 ni G23 desde aquí. No iniciar G25.

Ejecución del 2026-09-05 concluida. Resultado del grupo: **DESAPROBADO**.
TC-M09-52 APROBADO · TC-M09-53 APROBADO (tras corregir la expectativa de status de
la prueba en su reintento) · TC-M09-54 DESAPROBADO por defecto del producto,
reproducción de `QA-JE-G22-01`, a reportar a Desarrollo.
Consultar `RESULTADOS/TC-M09-G24_resultado.md`.

| Caso | GIVEN | WHEN | THEN |
|---|---|---|---|
| TC-M09-52 | Admin autorizado, especie/variable activas, combinación libre, padre válido | POST con `critico` terminando por encima de `valor_max` | 400 `NIVEL_FUERA_DE_RANGO`, sin ID ni estado de éxito, GET sin registro |
| TC-M09-53 | Mismas precondiciones, tres niveles dentro del padre | POST con `precaucion` y `critico` compartiendo un intervalo | Rechazo `SOLAPAMIENTO_NIVELES` (422 real, no 400), sin persistencia |
| TC-M09-54 | Mismas precondiciones | POST con tres niveles contiguos que cubren exactamente el padre | 201, ID, tres niveles continuos y GET que los conserva |

## Contrato real revisado (solo lectura)

- `registrar_umbral_use_case.py::_validar_rangos` evalúa **primero** FA-08
  (`NIVEL_FUERA_DE_RANGO`, `ValidationError` → **400**) y después FA-05
  (`SOLAPAMIENTO_NIVELES`, `BusinessRuleError` → **422**).
- `src/shared/errors.py` documenta ese mapeo; `umbral_router.py` y el
  `openapi.json` desplegado declaran 422 para el POST, no 400.
- Un nivel que excede el padre rompe también la cobertura exacta; por eso el
  discriminante de TC-M09-52 es el `error_code`, no solo el status.
- `nivel_dto.py` exige `limite_inferior < limite_superior` en cada nivel y
  `registrar_umbral_dto.py` exige exactamente normal/precaucion/critico.
- El frontend (`src/configuration/lib/validarUmbral.ts`) replica ambas reglas y
  bloquea el envío en cliente: la UI no emite POST para TC52 ni TC53.

## Datos

Descubiertos dinámicamente antes de cada ejecución (permisos, especies activas,
variables activas, umbrales existentes). No hay IDs fijos en la automatización.
Los puntos salen del rango físico real de la variable: `a=20%`, `b=40%`,
`e=50%`, `c=60%`, `d=80%`, `g=90%`. Padre `[a,d]` en los tres originales; solo
cambia el defecto intencional de los niveles.

## Requisitos y ejecución

Ya instalados: Newman 6.2.2, `newman-reporter-htmlextra` 1.23.1, Cypress 13.17.0,
TypeScript 5.9.3, Python 3.13.13 (venv del backend). No ejecutar instalaciones.

Variables de proceso: `TEST_ADMIN_EMAIL`, `TEST_ADMIN_PASSWORD`, `G24_CASE`
(`TC-M09-52` | `TC-M09-53` | `TC-M09-54`) y `G24_RUN_ID` único. No colocar
credenciales en archivos ni en `package.json`.

Newman (una invocación = un original):

```
NODE_PATH=<npm root -g>  node run-newman.cjs
```

Cypress, desde la raíz del frontend:

```
NODE_PATH=<SGPMP-FRONT-END-PWA>/node_modules
ELECTRON_RUN_AS_NODE debe estar AUSENTE
node_modules/.bin/cypress.cmd run --project <ruta TC-M09-G24>
  --config-file cypress.config.cjs --browser electron
```

`NODE_PATH` resuelve `cypress` y `typescript`; con `ELECTRON_RUN_AS_NODE=1`
(heredado de un entorno VSCode) el binario arranca como Node y Cypress rechaza
su propio bytecode (`cachedDataRejected`). `tsconfig.json` local es necesario
porque el proyecto backend no tiene uno.

Máximo 2 POST y 2 recorridos de navegador por original. Si aparece 201 o
persistencia inválida en TC52/TC53: detener G24 sin limpiar datos.

## Evidencia

HTML real de htmlextra con headers y entorno omitidos y sanitización posterior.
JSON propio solo con negocio. Cypress: `video:false`, `screenshotOnRunFailure:true`,
`retries:0`, `trashAssetsBeforeRuns:false`, capturas por `G24_RUN_ID`, blackout de
correo y contraseña, sin mocks, sin esperas fijas y sin `force:true`.
`verificar-cierre.cjs` repite las comprobaciones por GET y barre secretos.

Estado inicial: ambas ramas en `qa/juan-esteban-m09`. Backend limpio; frontend
con archivos untracked preexistentes solo de G22. SHAs locales: backend
`adc3932b9f0293a76ebec7e89ed877274791b6a1`, frontend
`966621df4e2c6a1f2c9233ea5ebefbb9e3bc2f56`. SHA desplegado no confirmado.
