# TC-M03-G95 — APROBADO (RUN oficial RUN-G95-V1-20261026-160451) — [informe](Resultados/RUN-G95-V1-20261026-160451/TC-M03-G95_resultado.md)

**Estado:** RUN oficial APROBADO para TC-M03-186, con evidencia en `Resultados/RUN-G95-V1-20261026-160451/`. La automatización se preparó frente a `SGPMP-FRONT-END-PWA origin/test` **81058af57d5d80d523fb5225f8eab48e0307ba85** (2026-10-26). Fuente del oráculo: fila G95/TC-M03-186 de `Casos_Prueba(Modulo3 Agrupado).csv` (Windows-1252), RF-58/CU04 E5 y `anotaciones/modulo_3/cu04_gaps_bd_rf58_rf59.md:9-20,59-65`. Oráculo literal: «La actualización automática se detiene, se muestra el aviso de sesión expirada y se redirige al login sin pérdida del estado visual; al reingresar, el dashboard se recarga con el estado más reciente.»

## Historial y estructura vigente

- Intento 1 `RUN-G95-V1-20261026-154635`: NO_CONCLUYENTE, técnico y no oficial. El selector `input[type="number"]` quedó obsoleto frente al combobox «Área»; se corrigió en ORD-G95-012. El responsable QA autorizó eliminar su evidencia nativa el 2026-10-26, tras transcribir lo esencial al informe oficial.
- Intento 2 `RUN-G95-V1-20261026-160451`: APROBADO y oficial. Sus evidencias permanecen en el único RUN conservado.

Archivos vigentes: `README.md`, `g95.mjs` (ejecutor), `G95.postman_collection.json`, `g95.cy.js`, `g95.cypress.config.cjs`, `lib/` (contrato, escenario, presupuesto, seguridad y selección de unidad), `pruebas/` (regresiones locales) y `Resultados/RUN-G95-V1-20261026-160451/` (informe y evidencias). El límite futuro de lecturas del dashboard se define una sola vez en `lib/g95_presupuesto.cjs`: **6**, según SOL-G95-013. El RUN oficial registró 7 porque su spec entonces permitía 8; la desviación consta en el informe.

## Decisiones metodológicas

El responsable QA decidió el **2026-10-26**: «Acepto el segundo login real como mecanismo equivalente para G95. Corrige los detalles pendientes y deja listo el ensayo.» La constante `DECISION_METODOLOGICA` queda en `lib/g95_escenario.mjs`; `decidir()` no exige una segunda aceptación. El segundo login real invalida la primera sesión y permite observar la rama de 401 del dashboard y refresh anterior rechazado (401/410), seguida de `forzarLogout()`. **Límite:** esto no demuestra vencimiento temporal del JWT ni el temporizador frontend de inactividad de 30 min.

El responsable QA decidió el **2026-10-26**: «No quiero que seas tan estricto con la evaluación, no rechaces la prueba simplemente porque no dice exactamente lo que se espera, Sesión cerrada o sesión expirada dan a entender lo mismo.» El aviso visible en `/login` se evalúa por su significado: comunica que la sesión terminó o pide volver a ingresar. «Sesión cerrada» y «sesión expirada» son equivalentes para UI-186-01; el acta y el informe futuro conservan el texto exacto observado. Sin aviso visible, esa comprobación es RECHAZADA si se acreditan las demás precondiciones. Esta decisión no cambia las demás condiciones del oráculo.

El responsable QA decidió el **2026-10-26**: «Sí, ajusta UI-186-02: aprueba si tras reingresar el dashboard de monitoreo se recarga con datos nuevos (navegando a él si hace falta); la página de aterrizaje y la pérdida de filtro/Auto ON van como observación.» Fuente: `tests/Test_Testing/Requerimientos/Especificacion-Requerimientos-Modulo3.md:5338-5350,5442-5446` (RF-58 E5 y postcondición 1). El informe futuro cita esta decisión y separa las observaciones de UX de las incidencias de producto.

Fundamento A/B previo: `src/shared/jwt.py:26-38,50-54,70-79,82-131` fija JWT de 8 h, refresh de 7 días y 401 `TOKEN_EXPIRADO`/`TOKEN_INVALIDO`; `src/identity_access/application/use_cases/sesiones/sesion_comun.py:153-179` cierra la sesión anterior; `src/identity_access/infrastructure/dependencies.py:80-99,124-151` da 401 `TOKEN_REVOCADO` y actualiza último acceso. En esta orden se releyeron la matriz y RF-58 E5; el código backend citado pertenece a la preparación previa y no se volvió a consultar.

### Análisis C: frontend `origin/test` 81058af5

Se consultó `git show origin/test:<ruta>` y el diff autorizado frente a `d69b6e17`, sin modificar el frontend. `src/telemetry/pages/MonitoreoView.tsx:51-79,132-147`: `area=''`, `idArea=null`, Auto ON inicial; el filtro `id_infraestructura` se agrega solo al elegir área; cambiarlo dispara `cargar(filtros)` y el polling ocurre cada 30 s. Refresco manual: botón con `aria-label="Refrescar ahora"`. `src/telemetry/components/SelectorArea.tsx:18-34` usa `Combobox`, etiqueta «Área», opción «Nombre (#id)» y admite ID escrito. `src/shared/design-system/Combobox.tsx:99-159` renderiza `label[for]`, `input[role=combobox]`, `ul[role=listbox]`, `li[role=option]`; la opción se elige con clic o Enter. `src/shared/lib/catalogo.ts:6-15` interpreta ID, `#ID`, nombre o «Nombre (#id)». `src/telemetry/hooks/useAreas.ts:19-35` carga opciones con otra petición `dashboard?por_pagina=1`; la vista usa `por_pagina=50` y `pagina=1`. Al remontar, el área vuelve a vacío y Auto vuelve a ON; no se observó persistencia del filtro en estas rutas.

`src/shared/api/http.ts:68-84,100-118,144-157,203-243`: cualquier 401 protegido intenta refresh; si este devuelve 401/410, guarda el motivo según `error_code` y la ruta actual, limpia token y va a `/login`. `src/shared/auth/AuthContext.tsx:129-142,162-189,224-234` sincroniza token y distingue rechazo 401/410 de error 5xx/red al restaurar. `src/auth/pages/LoginPage.tsx:29-45,74-80` lee el motivo sin borrarlo y muestra `.auth-alert`; `src/shared/i18n/locales/es-CO/auth.json:52-63` distingue «Sesión cerrada», otro dispositivo, inactividad y expiración. `src/shared/auth/rutaRetorno.ts:22-51` guarda la ruta interna sin la base y la consume una vez. `src/auth/hooks/useLogin.ts:29-46` borra el aviso y vuelve a esa ruta, o `/dashboard` si no existe; `src/auth/hooks/useLogout.ts:13-29` conserva ruta solo para cierre con motivo. `src/App.tsx:87-95,293-308,366-389` enlaza el cierre por inactividad y protege la ruta de telemetría. `src/auth/components/SessionExpirationWarning.tsx:16-44` muestra la advertencia previa por inactividad y «Seguir conectado»; es distinta del aviso de sesión cerrada en `/login` que evalúa este spec. El retorno automático al monitoreo es una expectativa derivada del código, pendiente de prueba pública; conservación de área y Auto son observaciones UX bajo la decisión QA vigente.

El intento técnico 1 registró «Área» y Auto ON, coherentes con `origin/test`; Cypress falló antes del segundo login al buscar `input[type="number"]`. Su evidencia nativa se eliminó por decisión del responsable QA y sus datos esenciales constan en el informe oficial. La discrepancia fue del selector de automatización frente al frontend desplegado; ese fallo no acreditó un defecto de producto. Antes de cualquier nueva ejecución se debe verificar el commit y DOM del frontend desplegado y comparar con el commit de referencia registrado en el informe generado.

## Mecanismos y alcance

- Espera natural: el JWT puede renovarse mientras viva la cookie; `useSessionTimeout.ts:5-11,44-108` ejecuta logout tras 30 min sin interacción DOM aunque el dashboard consulte cada 30 s (`MonitoreoView.tsx:21,64-69`). No recorre necesariamente el aviso exigido.
- Segundo login: `sesion_comun.py:153-157` y `sesion_repository.py:99-111` revocan access/refresh previos; `dependencies.py:80-99` entrega 401; `http.ts:152-192` intenta refresh y redirige. Mecanismo equivalente aprobado para este caso, con el límite indicado.
- Borrar cookie y enviar Authorization inválida produce 401 `TOKEN_INVALIDO` y 401 `REFRESH_TOKEN_REQUERIDO` (`sesiones_routers.py:290-306`); no acredita el rechazo del token real anterior. `cy.clock/tick` adelanta el logout de inactividad frontend, no el tiempo del servidor. No se usan como prueba.

## Diseño del ejecutor vigente

`g95.mjs` es el ejecutor canónico; hay una colección `G95.postman_collection.json` y un spec/config `g95.cy.js` / `g95.cypress.config.cjs`. La revisión previa retiró el legado `ejecutar_tc_m03_g95.mjs`, `tc_m03_g95.cy.js`, `cypress.config.cjs` y `validar_local_g95.mjs`; las referencias activas apuntan a las rutas canónicas. El contrato `sigab-qa-ejecutor/1` se contrastó con `TC-M03-G94/lib/contrato_ejecutor.mjs:5-49` y `g94.mjs:31-178,401-565`. Solo el lanzador externo autorizado crea `Resultados/RUN-G95-V1-<timestamp>/`; V2 exige decisión explícita y va a `EvaluacionV2/Resultados/RUN-G95-V2-<timestamp>/`.

El orden es: login del Administrador fuera del RUN; Cypress y Newman del Productor fuera del sandbox; GET `/usuarios/me` del Administrador con cabeceras y eco que abre el RUN; DELETE inmediato y verificación HTTP del cierre. **Ninguna petición del Productor lleva `X-Test-Run-Id` o `X-Sandbox-Secret`.** Si Cypress o Newman fallan, el ejecutor registra el problema y aun así intenta abrir y cerrar el RUN; si falla antes de intentar la apertura, registra `RUN_NO_ABIERTO` sin DELETE. El token/cookie anteriores se guardan solo en temporal y Newman los usa únicamente en los dos negativos explícitos de API-186-01. El nuevo token del segundo login no se reutiliza. Newman usa el reporter JSON; el ejecutor genera un HTML local de los HTTP observados. Los reportes Newman JSON saneado/HTML, acta, conteo, PNG real, `resultado.json` y un solo informe oficial se conservan dentro del RUN. Un código 0 no implica APROBADO ni rollback verificado.

API-186-01 comprueba que el token y refresh anteriores sean rechazados (401/410). UI-186-01 comprueba Auto detenido (ningún GET 200 del dashboard después del 401), aviso visible que comunique sesión terminada o pida volver a ingresar, y redirección a `/login`. El texto exacto se guarda en `aviso_texto` y el resultado semántico en `aviso_sesion_terminada`. UI-186-02 comprueba que, tras reingresar por el formulario, `/telemetria/monitoreo` cargue con un GET nuevo de `/iot/monitoreo/dashboard` HTTP 200 y sin error interno visible; si aterriza en otra ruta, navega al monitoreo. Ruta de aterrizaje, navegación manual, filtro y Auto ON se registran en el acta como observaciones UX, sin alterar el veredicto. El spec escribe el ID elegido en el combobox «Área», verifica que la petición use `id_infraestructura`, comprueba Auto ON sin apagarlo y exige un GET periódico 200 antes del segundo login. Un selector faltante deja `error_selector` con etapa y selector, y las UI se clasifican `ERROR_QA` técnico. Un 5xx de sesión/dashboard bloquea ambos; sin cierre observado ambos son NO_CONCLUYENTE. La paginación global no bloquea: se prefiere una unidad cuyo `total_sensores` completo esté en la primera página y sin sensor GRIS vigente; si ninguna es acreditable, se elige la primera con sensores y el acta registra `e7_riesgo: true` y motivo. Solo un `resumen_unidades` vacío bloquea por datos.

## Invocaciones locales y ensayo Windows

Desde esta carpeta, sin credenciales ni red remota:

```powershell
node g95.mjs --capacidades
node g95.mjs --comprobar
node pruebas/g95.test.mjs
node pruebas/g95_ensayo_spec_real.mjs
```

El ensayo levanta solo `127.0.0.1`, usa Chrome/Cypress real y temporales, y exige acta y PNG por modo. Salida exacta esperada:

En el entorno de esta preparación, el intento de ensayo terminó antes de abrir Cypress por `spawn EPERM` al crear el proceso hijo. Las líneas siguientes son **expectativas del ensayo, no resultados observados**; sintaxis, `--comprobar` y regresiones Node sí se ejecutaron.

```text
ENSAYO ok: UI-186-01 APROBADO; UI-186-02 APROBADO
ENSAYO texto: UI-186-01 APROBADO; UI-186-02 APROBADO
ENSAYO sin_aviso: UI-186-01 RECHAZADO; UI-186-02 APROBADO
ENSAYO sin_recarga: UI-186-01 APROBADO; UI-186-02 RECHAZADO
ENSAYO sesion500: UI-186-01 BLOQUEADO; UI-186-02 BLOQUEADO
ENSAYO lento: UI-186-01 NO_CONCLUYENTE; UI-186-02 NO_CONCLUYENTE
```

## Presupuesto y efectos de una SOL futura

El presupuesto autorizado en SOL-G95-013 fue **hasta 6 lecturas del dashboard UI** fuera del RUN. El flujo del RUN oficial hizo 7: vista y catálogo al montar, filtro aplicado, una periódica con Auto ON, intento rechazado tras cierre, vista y catálogo tras reingreso. El spec de ese RUN permitía 8. El código actual registra `e7_riesgo`, su motivo y `lecturas_dashboard`; superar el límite vigente de 6 produce `ERROR_QA`. Con el flujo observado de 7 lecturas, una nueva ejecución necesitaría un presupuesto autorizado suficiente o un flujo que realmente use menos lecturas; esta orden no prepara SOL ni ejecuta TEST. Otras solicitudes UI (sesiones, refresh y recursos de página) están sujetas al presupuesto general de 60. El preflight declara `login_y_auditoria_fuera_run` y `lecturas_dashboard_y_posible_correo_E7` como efectos informativos. Logins, rotación/cierre de sesiones, último acceso, auditoría, notificaciones y refresh pueden persistir (`sesion_comun.py:153-200`, `login_use_case.py:193-216`, `refresh_token_use_case.py:147-175`, `dependencies.py:148-151`). El primer GET global del monitoreo ocurre antes de filtrar y puede activar correo E7 incluso con `e7_riesgo: false` para la unidad elegida. `obtener_dashboard_use_case.py:53-78,132-138` y `aviso_sin_umbral_email_adapter.py:98-135` pueden emitir correo E7 si hay sensor GRIS sin umbral y no desactualizado; DELETE no revierte ese correo.
