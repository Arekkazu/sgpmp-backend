| Fecha | Autor | Qué se hizo |
|---|---|---|
| 2026-11-19 | Juan Sebastian Gutierrez | Fases 1 y 2 de TC-M08-G018: análisis del código, diseño de checkpoints, colección Newman y runner |
| 2026-11-20 | Juan Sebastian Gutierrez | v3: corrida oficial de la ronda 1 (CP-10 con 2946, línea base completa, escaneo al final) |

# TC-M08-G018: diseño (RF-106, consulta del historial por API)

**Casos agrupados:** TC-M08-047 (validaciones) y TC-M08-059 (solo lectura), más la observación por API de TC-M08-048 (Productor).
**Árbol:** `tests/Test_Testing/Test_Modulo8/RF-106/TC-M08-G018/` (backend). Herramienta: Newman con htmlextra.
**Endpoint:** `GET /historial-predictivo/{id_activo_biologico}` (backend #1186, lanzamiento v7).

## Archivos

| Archivo | Dónde | Para qué |
|---|---|---|
| `tc-m08-g018.postman_collection.json` | raíz del caso | 22 peticiones, 13 checkpoints |
| `ejecutar_tc_m08_g018.ps1` | raíz del caso | Runner: credenciales en memoria, staging, escaneo de secretos que solo reporta |
| `evidencias/DISENO_TC-M08-G018.md` | evidencias (no lo lee el escáner) | Este documento |

El runner **nunca escribe en `resultados/`**. La promoción es un paso aparte.

## Fase 1: lo observado en el código (rama test-JuanSG, commit 8606b90)

- Router `src/reporting/infrastructure/routers/historial_predictivo_router.py`:
  - :36 permiso `historial_clinico_predictivo` · Leer (la docstring :9 dice Veterinario y Administrador).
  - :55-57 `nivel_riesgo` fuera de 0 a 3 → 400 VAL_ENTRADA.
- Caso de uso `src/reporting/application/use_cases/historial/consultar_historial_predictivo_use_case.py`:
  - :54-55 sin fechas: fin = hoy del usuario, inicio = fin − 365 días.
  - :56-58 inicio > fin → 400.
  - :59-61 más de `RANGO_MAXIMO_DIAS` → 400.
  - :62-65 inexistente → 404 ACTIVO_INEXISTENTE.
  - :66-68 finca fuera de `modulo9.usuarios_fincas` → 403 FINCA_NO_AUTORIZADA.
  - :69-72 estado distinto de ACTIVO o EN_TRATAMIENTO → 422 ACTIVO_NO_VIGENTE.
  - No valida fechas futuras. No escribe auditoría.
- `src/reporting/domain/historial_predictivo.py` :23 `RANGO_MAXIMO_DIAS = 731`. Hoy 24 meses son 730 días, así que **24 meses + 1 día se acepta**: CP-09b, FALLA probable.
- `src/shared/error_handlers.py` :194-201: la validación de tipos da 400 salvo que la ruta declare `x-codigo-validacion` (esta no lo declara).
- `src/reporting/infrastructure/adapters/instantanea_reportes.py` :40-41: la lectura va en **otra sesión**, de solo lectura y en REPEATABLE READ. No ve lo escrito en el sandbox; a G018 no le afecta porque solo lee datos persistentes, pero **sí afecta a G023**.
- Alcance del Veterinario (punto 5 del pedido al DBA): `modulo9.usuarios_fincas` con `es_activo` (`src/shared/alcance_finca_adapter.py`).

## Checkpoints (13)

Todas las peticiones llevan `X-Test-Run-Id`, `X-Sandbox-Secret` y `X-Zona-Horaria: America/Bogota`. Las fechas se calculan por calendario en Bogotá.

| CP | Paso | Petición | Esperado | Fuente |
|---|---|---|---|---|
| CP-01 | 047.1 | 885, hoy − 12 meses a hoy | 200; `rango_fechas_aplicado` igual a lo enviado; ≥ 1 predicción y todas dentro del rango | RF-106 Entradas; RF-67 |
| CP-02 | 047.2 | inicio 2026-10-01, fin 2026-09-01 | 400 sin datos | RF-67 E3; openapi de TEST |
| CP-04 | 047.4 | 885 sin fechas | 200; rango = hoy − 12 meses a hoy | RF-106 Entradas; valores por defecto del Swagger |
| CP-05 | 047.5 | 999999 | 404 sin datos | RF-67 E2; Swagger |
| CP-06a | 047.6 | id `abc` | 400 o 422 sin datos | RF-106 Entradas; openapi publica 400 y 422 |
| CP-06b | 047.6 | id −1 | 400, 404 o 422 sin datos | RF-106 Entradas; openapi |
| CP-07a | 047.7 | `nivel_riesgo=4` | 400 o 422 sin datos | RF-106 Entradas (0 a 3); openapi |
| CP-07b | 047.7 | `nivel_riesgo=-1` | 400 o 422 sin datos | RF-106 Entradas (0 a 3); openapi |
| CP-08 | 047.8 | activo de una finca no asignada | 403 sin datos | Swagger (otra finca → 403); RF-67 alcance |
| CP-09a | 047.9 | 24 meses exactos | 200; rango igual a lo enviado | RF-106 Restricción 2 |
| CP-09b | 047.9 | 24 meses + 1 día | 400 sin datos | RF-106 Restricción 2; Swagger (máximo 24 meses → 400) |
| CP-10 | 047.10 | activo dado de baja | 422 `ACTIVO_NO_VIGENTE` sin datos | RF-106 Precondición 2; Swagger; contrato v7 (sección 3) |
| CP-11 | 059 | 885 al final | Igual a la línea base T00: metadatos, ids de predicciones, eventos y retroalimentaciones, total de pendientes y TVCO | RF-106 Restricción 3 y Postcondición 3 |

«Sin datos» quiere decir que la respuesta no trae la clave `predicciones`. Las aserciones solo usan códigos que publica el openapi de TEST o que fija la especificación; los textos de error se registran como observación.

## Observaciones (no cuentan en el reporte)

| Id | Qué registra | Por qué no es checkpoint |
|---|---|---|
| OBS-03 | 047.3, `fecha_fin = hoy + 30` | RF-106 no define fechas futuras; RF-67 (Integridad temporal) es de otro endpoint. El código no las valida |
| OBS-P | Productor sobre el 885 (de TC-M08-048) | Así está diseñado el caso; esperado por RF-106: 403 |
| OBS-AUD-T00/T99 | total y primer `id_evento` de `GET /prediccion/auditoria` antes y después | RF-106 no exige auditar la consulta; RF-67 paso 7 es de otro endpoint; el código no audita |
| OBS-NOMBRES | claves de la respuesta frente a la Salida de RF-106 (`filtros_aplicados`, `activo_seleccionado`, `tvco`) | La Salida describe la vista, no el contrato de la API; se exige en G019 |
| OBS-TEXTO-CP02/05/08 | `message` de los errores | RF-106 no define textos |
| OBS-VENTANA, OBS-TIMESTAMP, OBS-FUENTES | ventana de correspondencia, formato de fecha, `fuentes_no_disponibles` | Datos de contexto para G020 y G021 |

## Precondiciones (si fallan, la corrida queda inválida: no es un FALLA del producto)

- Z00: login del Veterinario 200. Z01: `nombre_rol = Veterinario`. T00: el 885 responde 200 con ≥ 1 predicción, ≥ 1 evento sanitario y ≥ 1 retroalimentación.
- Si falla alguna, la colección salta a Z99 (cierre del sandbox), escribe `ABORT|` y el runner sale con 3.
- Un solo login por cuenta (Veterinario y Productor) en el run. Un login fallido no se reintenta.

## Datos

- Activo A: 885 (sembrado por el DBA). Se puede cambiar con `-IdActivoA`.
- `-IdActivoOtraFinca` y `-IdActivoBaja` son **obligatorios**: los ids del pedido al DBA (puntos 4 y 11). Prohibidos: 930, 900, 901 y 825.
- Cuentas de `.env.test`: `TEST_VET_*`, `TEST_PRODUCER_*`, `TEST_SANDBOX_SECRET`, `TEST_BASE_URL`.

## Salida del runner (en `evidencias/run-<yyyyMMdd-HHmmss>/`)

- `resultado_TC-M08-G018[_reintentoN].html`: htmlextra, sin cabeceras `Authorization` ni `X-Sandbox-Secret`; los cuerpos del login y de `/usuarios/me` van ocultos.
- `consola_…txt`, `checkpoints_…txt` (una línea por checkpoint con esperado, obtenido real y X-Request-Id), `trazas_…txt` (CP, OBS, PRE y CIERRE).
- `escaneo_secretos_…txt`: solo reporta, nunca reescribe.
- `resumen_…txt`: SHA-256 de la colección y del runner, run_id, conteos y cierre.
- Códigos de salida: 0 todos OK; 1 hay FALLA; 2 configuración; 3 corrida inválida; 4 secretos; 5 cierre; 6 `resultados/` cambió.

## Prueba de la herramienta (no del producto)

Se corrió la colección en un entorno aislado contra un servidor simulado que replica la lógica leída en el código, con credenciales falsas:

- 13 aserciones y 1 fallida (CP-09b, como predice el código).
- El HTML trae «Total Assertions» y «Total Failed Tests».
- 0 apariciones de contraseñas, secreto, correos, «Bearer» o el prefijo JWT en el HTML y en la consola.
- El parseo de checkpoints y trazas del runner se validó con la misma lógica sobre esa consola.
- **No se probó en PowerShell 5.1**: la verificación estática del agente que ejecuta debe correr `[System.Management.Automation.Language.Parser]::ParseFile`.

## Resultado esperado de la ronda 1 (inferencia desde el código)

Rechazado, 12/13: CP-09b daría 200 en lugar de 400. Si se confirma, el INC sería VAL_ENTRADA sobre RF-106 Restricción 2 (`domain/historial_predictivo.py:23`, el límite debe ser por calendario y no 731 días fijos).

## Sonda de datos (agregada el 2026-11-19)

**Por qué existe.** El DBA cerró el pedido sin responder, así que no hay ids confirmados para CP-08 (activo de otra finca) ni para CP-10 (activo dado de baja). Tampoco se sabe qué se sembró en el 885. En un intento anterior el agente ejecutor investigó por su cuenta (consultó la BD, hizo peticiones fuera del runner y borró sus scripts). **Todo lo que obtuvo se descarta.**

**Qué hace.** `ejecutar_sonda_g018.ps1` corre `tc-m08-g018-sonda.postman_collection.json`:
- Solo lectura, en su propio run de sandbox, con el Veterinario y el Productor (un login cada uno).
- Sin aserciones y sin reporte para el dashboard. Escribe en `evidencias/sonda-<ts>/`.

| Petición | Qué registra |
|---|---|
| S02 `GET /reportes/opciones/finca` | Fincas del Veterinario, con la misma regla de alcance que el historial (`modulo9.usuarios_fincas`) |
| S03 `GET /historial-predictivo/{A}` | Predicciones, eventos y retroalimentaciones que ve el historial |
| S04 `GET /activos-biologicos/{A}` | Estado y finca del activo A |
| S05 `GET /activos-biologicos/{A}/eventos` | Eventos sanitarios según M02 (fuente RF-41) |
| S06 `GET /prediccion/retroalimentacion/bandeja` (EVALUADO, activo A, último año) | Valoraciones según M04 (fuente RF-72) |
| S07 `GET /prediccion/historial/{A}` | Eventos de RF-67 por tipo |
| S08 `GET /activos-biologicos?id_finca=` (cada finca del Veterinario) | Activos no vigentes: candidatos para CP-10 |
| S10 `GET /activos-biologicos` con el Productor | Activos fuera de las fincas del Veterinario: candidatos para CP-08 |

**Cómo se usa el resultado.**
- **Si las fuentes (S05/S06) tienen datos y el historial (S03) no los muestra:** la línea base de la colección oficial se ajusta para registrar las fuentes, y se agrega un checkpoint de consolidación (RF-106 Proceso). Ese caso sería un defecto del producto, no del ambiente.
- **Si las fuentes están vacías:** faltan datos semilla. La corrida oficial no se lanza, y el caso queda Pendiente con una nota.
- Los ids de CP-08 y CP-10 salen de los candidatos de S08 y S10. Los prohibidos (930, 900, 901 y 825) ya están excluidos.

## Versión 2: ronda 1 parcial (2026-11-19)

Resultado de la sonda `evidencias/sonda-20261119-170457/` (verificado contra sus archivos):

- **Activo 885.** 24 predicciones, 0 eventos sanitarios y 0 retroalimentaciones en el historial. Las fuentes tampoco tienen datos: M02 tiene 0 eventos (`bc9a7370-…`), la bandeja de M04 tiene 0 evaluadas (`1085374e-…`) y RF-67 tiene 24 INFERENCIA. Faltan los datos semilla de los puntos 1, 2 y 9; no es un defecto del producto.
- **Fincas del Veterinario 97:** 84 (sin activos) y 184 (8 activos, todos ACTIVO). No hay ningún activo dado de baja.
- **Candidato para CP-08:** el **957** (ACTIVO, finca 1 del Productor).

Decisión de Sebastian: ejecutar ahora con lo que hay, para obtener un resultado parcial. Cambios:

| Cambio | Motivo |
|---|---|
| T00 solo exige ≥ 1 predicción; los conteos de eventos y retroalimentaciones van a OBS-DATOS | Faltan los datos semilla de los puntos 2 y 9. CP-11 sigue comparando el estado completo, que no queda vacío porque hay 24 predicciones |
| **CP-10 retirado** (traza `RETIRADO|CP-10|…`) | No hay activos dados de baja en las fincas del Veterinario (punto 11). Crear una baja en el sandbox no sirve porque el historial lee en otra sesión |
| Se quita el parámetro del activo dado de baja; el runner espera **12** checkpoints | Consecuencia del retiro de CP-10 |

Comando de la ronda 1: `.\ejecutar_tc_m08_g018.ps1 -IdActivoOtraFinca 957`.

Cuando el DBA siembre los datos, un reintento con CP-10 y la línea base completa cubre lo pendiente (`-Reintento 1`).

Prueba de la herramienta v2 contra el simulador, en el escenario de hoy (predicciones sin eventos ni valoraciones): 12 aserciones, 1 fallida (CP-09b), T00 sin ABORT, la traza RETIRADO presente, cierre 200 y 0 secretos.

## Versión 2.1: cuenta del Veterinario de la finca 494 (2026-11-19)

El DBA atendió otro pedido, el de la líder, y dejó datos de M08 en la finca **494**, con cuentas dedicadas. Para G018:

- **Veterinario 177** (finca 494).
- **Activo 2563**, según el DBA con inferencias, el evento sanitario 2241 y una «valoración a valor razonable». Esa valoración es de M06, no la clínica de RF-72.
- **Activo 2562**, de la finca 495, ajena al Veterinario.

Riesgo: el historial descarta las inferencias en modo sombra (`fuente_reportes_repository.py`:44 y :632), y el DBA reporta que el motor solo genera inferencias en modo sombra.

Cambios:

- Los dos runners aceptan `-CuentaVet M08`. Con esa opción leen `TEST_M08_VET_EMAIL` y `TEST_M08_VET_PASSWORD` de `.env.test` y no tocan `TEST_VET_*`, que usan otros módulos. Sin la opción, todo sigue igual.
- La sonda acepta `-IdActivoOtraFinca` (2562 por defecto) y agrega S03b, que consulta ese historial con el Veterinario y registra el HTTP.

Siguiente paso: correr la sonda con `-IdActivoA 2563 -CuentaVet M08` y decidir el activo A de la ronda 1 (2563 si el historial muestra sus predicciones; si no, 885 con el Veterinario de `TEST_VET_*`).

## Versión 3: corrida oficial de la ronda 1 (2026-11-20)

- Decisión de Sebastian (2026-11-20): la corrida del 19/11 (`qa-m08-g018-20261119-172144`) es preliminar y no oficial (`ARCHIVADO_NO_OFICIAL.txt`): datos incompletos del DBA. La oficial es la ronda 1 (`-Reintento 0`).
- Datos: activo A 885 (finca 184; la ficha trae `id_finca: null`, no se usa), Veterinario 97 (`-CuentaVet TEST`), otra finca 2556 (finca 475), baja 2946 (finca 184, BAJA). Verificados con la sonda DBA-885 (2026-11-20 13:08).
- CP-10 recuperado: GET /historial-predictivo/2946 → 422 `ACTIVO_NO_VIGENTE` sin datos (RF-106 Precondición 2; Swagger; v7). Código: `consultar_historial_predictivo_use_case.py`:62-73 (orden: rango, 404, 403, 422; el 422 exige `estado` no vacío, que `ubicar` lee con `est.nombre`, `fuente_reportes_repository.py`:64). Previsto OK.
- CP-11: la línea base exige ≥1 predicción, ≥1 evento y ≥1 valoración (si no, ABORT en T00); `snap` compara ids de predicciones, `id_evento` de eventos y `id_resultado_inferencia:valoracion:fecha` de valoraciones (claves verificadas en el caso de uso, :105 y :109). Previsto OK.
- 13 checkpoints; sin retirados. CP-09b previsto FALLA (731 días).
- Runner v3: `-IdActivoBaja` obligatorio y distinto de A y de la otra finca, prohibidos 930/900/901/825; el resumen y RUN_INVALIDA se escriben antes del escaneo; el resumen se reescribe con el conteo y se reescanean resumen y escaneo.
- Prueba de la herramienta: mock en 5 escenarios (completo, vacío, sin valoraciones, baja con 200, historial que cambia), salidas en `evidencias/prueba_herramienta_v3/`. Respaldo de v2 en `evidencias/fuentes_generador/v2/`.
- Resultado de la prueba de la herramienta (Argon, 2026-11-20; revisado por Claude contra los archivos):
  - completo: 13 aserciones, 1 fallida (CP-09b, 731 días como el código); CP-10 recibe 422 `ACTIVO_NO_VIGENTE`; sin ABORT ni RETIRADO; cierre 200.
  - vacío y sin valoraciones: ABORT en T00 (eventos=0 o retroalimentaciones=0), 0 aserciones, cierre 200.
  - baja con 200 (control): fallan CP-09b y CP-10. Historial que cambia (control): fallan CP-09b y CP-11.
  - `node --check` de los 24 scripts: 0 errores. ParseFile del runner: 0 errores; ASCII, CRLF y sin BOM.
  - La colección es idéntica a la que produce `gen_coleccion.py` v3; los diff contra `fuentes_generador/v2/` son solo los cambios pedidos.
- SHA-256 v3: colección `70EBD36243B756A406C8C67C2C6A4A9A5A1AD51CC43DFAE784DAFA27721DF0B4`; runner `F733E08BA19B51C646B4B19DE1AF07C580BF2D7FC1060967697275E828034917`; `gen_coleccion.py` `6227E708DE47430881C132AC169929BA4E1C692A29FF7B3926A586CB2D2C158D`; `mock_api.py` `AA17CA115388201106B3874EA88B8609B6162ADA5FEDC2C92B18C642ED62F222`.
- Comando de la corrida oficial: `.\ejecutar_tc_m08_g018.ps1 -IdActivoA 885 -CuentaVet TEST -IdActivoOtraFinca 2556 -IdActivoBaja 2946 -Reintento 0`. Resultado previsto: 13 checkpoints, 12 OK y CP-09b FALLA (exit 1).
- La nota «Siguiente paso» de la versión 2.1 (sonda con 2563) queda superada por esta versión.
