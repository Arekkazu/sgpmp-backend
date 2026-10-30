# TC-M04-G070 — RF-72, ventana temporal

Automatización canónica solo API para TC-M04-214 a TC-M04-218. La orden `ORD-G070-001` permite preparación local y ensayo loopback; **no autoriza TEST ni crear un RUN**. El responsable QA insertará la semilla retroactiva el día del RUN; el RUN debe comenzar dentro de las 10 horas siguientes.

## Oráculos y decisiones

Fuente: `Actualizacion_Matriz_RF69_RF72/Casos_Prueba(Mod4Agrupfinal)_actualizada.csv`, fila G070 (Windows-1252, `;`); RF-72 de `Requerimientos/Especificacion-Requerimientos-Modulo4 (1).md`, líneas 4096–4110, 4166, 4272–4276, 4285–4297 y 4390–4391.

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
