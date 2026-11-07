# TC-M04-G070 — RF-72, reevaluación V2

## Ajuste ORD-G070-011

El [extracto del reintento técnico V2](EvaluacionV2/Resultados/RUN-G070-V2-20261101-045537/api/antecedentes/intento_2.json) registra 214–216 APROBADO y 217–218 NO_CONCLUYENTE porque A/B solo admitían exactamente 120 días; los resultados de 122 días y otros vencidos libres quedaron fuera. La selección vigente reserva primero los cuatro resultados de 215 y después elige A/B entre resultados libres con más de 91 días completos, hasta el límite de búsqueda de 125 días, empezando por los más antiguos. `d120a` y `d120b` son claves internas; el informe V2 muestra la antigüedad real. Si faltan dos, 217 y 218 conservan NO_CONCLUYENTE técnico. La fixture saneada `pruebas/semilla_observada_G070_V2.json` conserva únicamente identificadores y edades observados del RUN; `pruebas/g070_seleccion.test.mjs` y el ensayo `vencidos_sin_120` validan el caso sin acceso a TEST.

ORD-G070-013 conserva en el RUN oficial los [extractos e índice SHA-256](EvaluacionV2/Resultados/RUN-G070-V2-20261101-045537/api/antecedentes/indice.json) de ambos intentos técnicos. Sus carpetas de origen tienen eliminación autorizada por el responsable QA; el orquestador ejecutará esa eliminación. README y automatización usan los extractos conservados para la trazabilidad.

## Orden ORD-G070-006

Preparación local de 214, 215, 216, 217 y 218 tras issue #865 / PR #871. No se consultó TEST ni se creó un RUN en esta fase. La fuente de los oráculos es RF-72 (líneas 4096–4110, 4166, 4272–4276, 4285–4297 y 4390–4391) y el caso original G070 del CSV de módulo 4. V1 se conserva como evidencia histórica en `Resultados/RUN-G070-V1-20261029-133841/`.

La automatización vigente consta de un ejecutor (`g070.mjs`), una colección Newman (`G070.postman_collection.json`), un módulo de reglas (`lib/g070_core.mjs`) y pruebas locales en `pruebas/`. No hay Cypress porque estos cinco casos exigen API; no se identificaron duplicados activos. El ejecutor genera el único Markdown V2 en `EvaluacionV2/Resultados/RUN-G070-V2-<timestamp>/TC-M04-G070_reevaluacion_V2.md`, junto a `resultado.json`, preflight y reportes Newman derivados de la ejecución real.

El contexto canónico para `--operacion reevaluar` o `--operacion reintentar` con `--version 2` exige `version_anterior: 1`, alcance de reevaluación, autorización particular y `semilla_commit` ISO con hora. El ejecutor lee `semilla_commit` primero del contexto y luego de `alcance_reevaluacion`; lee el commit de código del contexto o `alcance_reevaluacion.commit_despliegue`, y cita `alcance_reevaluacion.alembic_test` por separado. La ausencia del commit de código no bloquea el RUN y se declara como no verificado. El preflight impide iniciar V2 si falta una hora ISO válida o si transcurrieron más de 10 h desde el COMMIT. Si falla y el directorio del RUN ya existe, guarda `preflight.json` y `resultado.json` no oficial sin solicitar cierre ni hacer peticiones. El lanzador externo controla TEST. `--capacidades` y `--comprobar` son locales.

Secuencia: una sesión por cuenta; descubrir la semilla libre desde historial respecto a la cabecera `Date` del servidor, tolerando el reloj fijo del sandbox; ejecutar Newman una vez con 214, W89, W90, W90H, W91 y 218/B con ventana 90; verificar historial y auditoría; probar 216 por GET/PATCH y W91 al subir a 365; restaurar 90 por PATCH/GET; probar 217 ampliando solo A y verificando B, auditoría, validaciones y RBAC; cerrar por DELETE y verificar historial, configuración y evento identificable. Cada caso independiente conserva su propio veredicto. W90H mantiene OBS-M04-G070-215. La caducidad de la ampliación es imposible de observar en un único RUN con now() fijo y al menos un día habilitado.

La semilla observada incluye cuatro resultados para 215 de 89/90/90 h/91 días y otros vencidos libres de 91–93 días. A/B se eligen por antigüedad real y sin reutilizar 215; los de 122 días también son elegibles cuando aparecen en el historial. No incluye resultados de 7/8 ni 365/366 días. Por ello los límites del parámetro se comprueban con PATCH/GET y la lectura dinámica con W91, que cambia de rechazado a aceptado; el informe declara la cobertura de frontera de registro no disponible. Si faltan W89/W90/W90H/W91 o A/B libres, el caso dependiente queda NO_CONCLUYENTE técnico. Nunca se sustituye un resultado por un id fijo.

Presupuesto máximo: 209 peticiones, 1800 s, 120 s para POST/PATCH y login, 30 s para lecturas. Un POST/PATCH sin respuesta no se repite: se consulta GET, historial o auditoría para conciliar. El cierre DELETE se intenta siempre. Efectos remotos de un RUN futuro: sesiones, lecturas, retroalimentaciones, cambios temporales de ventana global, ampliación puntual y auditoría dentro del sandbox; posibles lecturas de historial poscierre fuera de él.

Validación local: `node --check g070.mjs`, `node --check lib/g070_core.mjs`, `node g070.mjs --capacidades`, `node g070.mjs --comprobar`, `node pruebas/g070_env.test.mjs` y `node pruebas/g070_ensayo.mjs`. El ensayo usa solo loopback y archivos temporales.

## Notas históricas V1

Automatización canónica solo API para TC-M04-214 a TC-M04-218. La orden `ORD-G070-001` permite preparación local y ensayo loopback; **no autoriza TEST ni crear un RUN**. El responsable QA insertará la semilla retroactiva el día del RUN; el RUN debe comenzar dentro de las 10 horas siguientes.

## Oráculos y decisiones

Fuente: `Casos_Prueba(Mod4Agrupfinal)_actualizada.csv`, fila G070 (Windows-1252, `;`); RF-72 de `Requerimientos/Especificacion-Requerimientos-Modulo4 (1).md`, líneas 4096–4110, 4166, 4272–4276, 4285–4297 y 4390–4391.

- 214: E7 exige 422 y no persistencia si se admite `timestamp_retroalimentacion`. Si la API lo ignora, se acepta 201 solo si la fecha generada es posterior a la inferencia y distinta de la enviada.
- 215: 89 y 90 días → 201; 91 → 422 E9 sin registro. 90 días más 12 horas es observación, conforme a la decisión QA.
- 216: rango configurable 7–365 desde M09 por Administrador. Si el OpenAPI y `GET /configuracion/parametros` de TEST no exponen una operación para cambiar el valor, se rechaza por funcionalidad ausente. Si aparece una operación, se marca NO_CONCLUYENTE y no se ejecuta sin SOL específica. Una lectura sola tampoco satisface la configuración.
- 217: dos resultados de 120 días deben ser rechazados antes de la ampliación. La ausencia de operación pública para ampliar uno de ellos se registra como funcionalidad ausente; si aparece, se marca NO_CONCLUYENTE y no se ejecuta.
- 218: E9 debe informar días, id, fecha límite exacta en zona del usuario y contacto al administrador.

Los casos 216 y 217 son `DEFECTO_FUNCIONAL_CANDIDATO` según la lectura de código; solo la superficie pública observada en TEST permite un RECHAZADO. Un 5xx aislado de POST rechaza su caso; tres consecutivos o 403 de clave bloquean técnicamente. Una semilla fuera de tramo deja NO_CONCLUYENTE solo sus casos dependientes. No se cambia el oráculo según el comportamiento del código.

## Preparación de datos y ejecución

El activo 885 debe estar ACTIVO y los resultados del modelo INDIVIDUAL, versión 43. Se requieren un resultado reciente libre para 214; 89 días + 1 h, 90 días + 1 h, 90 días + 12 h, 91 días + 1 h y dos resultados de 120 días, todos con fechas retroactivas. El ejecutor lee `fecha_evento` desde `/prediccion/historial/885` (rango de 125 días, cursor, 50 eventos por página), resuelve el modelo y calcula `floor((ahora UTC − fecha_inferencia)/24 h)` antes de los POST. El informe muestra las edades observadas.

La colección `G070.postman_collection.json` contiene siete POST. El runner hace una sola invocación Newman por RUN y escribe únicamente `newman/newman-G070.json` y `.html`, derivados del reporte de esa ejecución y saneados. Logins, descubrimiento, OpenAPI, configuración, verificación de historial/auditoría, DELETE y poscierre usan fetch secuencial. Hace un login por cuenta, con 120 s de timeout; el resto usa 30 s. Siempre intenta DELETE después de iniciar peticiones. El rollback se considera verificado solo con DELETE 200 y lectura poscierre sin nuevos registros. El RUN se declara oficial únicamente con cinco estados APROBADO/RECHAZADO, Newman único y rollback verificado.

Presupuesto máximo exacto: **142 solicitudes** = 2 sesiones + 1 activo + 40 páginas iniciales + 8 modelos + 2 superficies + 7 POST + 40 páginas de verificación + 1 auditoría + 1 DELETE + 40 páginas poscierre. Duración límite: 900 s, con 30 s reservados para cierre. La lectura de 120 días queda NO_CONCLUYENTE si el historial supera las 40 páginas permitidas. La colección omite solo POST de resultados faltantes, sin bloquear casos independientes.

El despachador debe aportar el contexto canónico y la autorización de RUN particular. `node g070.mjs --capacidades` y `node g070.mjs --comprobar` son locales. `node pruebas/g070_ensayo.mjs` ejecuta 31 modos solo en loopback, crea artefactos temporales y los elimina. No se leen ni imprimen valores de `.env.qa` en las pruebas: `g070_env.test.mjs` usa un archivo temporal propio.

## Código consultado en `origin/test` (`daefc3a5c62771c8952706ae7a7fe128e66b0b02`)

- `src/prediction/infrastructure/dto/registrar_retroalimentacion_dto.py:10–17` no declara el timestamp. `src/shared/base_dto.py:18–26` no prohíbe campos extra; Pydantic los ignora por defecto.
- `src/prediction/application/use_cases/retroalimentacion/registrar_retroalimentacion_use_case.py:68–82` lee dinámicamente RF72_VENTANA, usa `.days`, produce E9; `:92–97` produce E7 con hora del servidor. `src/shared/errors.py:91–99` asigna HTTP 422 a `BusinessRuleError`.
- `src/configuration/domain/entities/parametro_mlops.py:26,36–64` define el parámetro y valida límites; `src/configuration/application/use_cases/configuracion_global/configurar_parametros_mlops_use_case.py:6,26–33` contiene la carga administrativa explícita y 7–365. `scripts/configurar_parametros_dev14.py:4–9,55–66` es vía fuera de línea con conexión directa a BD.
- `src/configuration/infrastructure/routers/configuracion_global_router.py:4–9,36–39,46–47,78–100,106–130` solo expone la configuración operativa RF-18; `_respuesta` usa `ConfiguracionGlobalResponse`, cuyos campos en `src/configuration/infrastructure/schema/configuracion_global_schema.py:11–39` no incluyen RF72_VENTANA. La búsqueda de rutas de ampliación en `origin/test:src/prediction` y `origin/test:src/configuration` no halló una operación. Esto es una inferencia del código revisado, no evidencia de TEST.
- `src/prediction/infrastructure/routers/historial_diagnostico_router.py:28–52` publica GET con RBAC de lectura (`_RECURSO=42`), rango y cursor; `src/prediction/application/use_cases/historial_diagnostico/consultar_historial_use_case.py:22,55–90` limita 50 por página, sin máximo de días del rango. `main.py:802–805` construye FastAPI con `root_path=/api` y conserva el OpenAPI predeterminado `/openapi.json` en el código. La disponibilidad en el despliegue y su eco de RUN deben comprobarse en TEST; el esquema OpenAPI no impone un rol para la ruta generada.

No se pudo regenerar el OpenAPI local desde `main.py`: el Python disponible carece de `requests` (después de cargar el wheel local `audit_sdk`). El archivo histórico `openapi-test.json` muestra 193 rutas, ninguna de ventana o ampliación, pero ya difiere del router actual (su configuración carece de PATCH). Por ello no se usa como prueba concluyente de `origin/test`; la inspección de `/openapi.json` de TEST sigue siendo la comprobación decisiva de 216 y 217.

## Efectos para una futura SOL

Dos logins (Veterinario A y Administrador), lecturas de activo, historial, modelo, OpenAPI, configuración y auditoría; retroalimentaciones 201 de 214, 89, 90 y posiblemente 90 + 12 h, con su auditoría, revertidas por DELETE; intentos 422 sin persistencia; ningún cambio de configuración ni excepción; lecturas poscierre con posibles eventos `HISTORIAL_CONSULTADO` fuera del sandbox. Sin correos, archivos externos ni cambio de semilla.
