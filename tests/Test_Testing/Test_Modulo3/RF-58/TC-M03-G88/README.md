# TC-M03-G88 — Automatización QA reutilizable

RF-58 Monitoreo Ambiental en Tiempo Real · CU04 · Responsable QA: Juan Esteban · Prioridad Alta.
Fuente: `Casos_Prueba(Modulo3 Agrupado).csv`, fila TC-M03-G88. Endpoint: `GET /iot/monitoreo/dashboard`.

Sin ejecuciones oficiales todavía: Desarrollo no ha autorizado la evaluación del Módulo 03.

## Casos

| Caso | Qué se comprueba | Herramienta |
| --- | --- | --- |
| TC-M03-169 | Umbral 35–39: lecturas 35, 37 y 39 en VERDE (bordes inclusivos) | Newman |
| TC-M03-170 | Umbral 20–30, T=1: lecturas 19.1, 19.9, 30.1 y 30.9 en AMARILLO | Newman |
| TC-M03-171 | Umbral 20–30, T=1: lecturas 18.9 y 31.1 en ROJO | Newman |
| TC-M03-172 | Umbral 20–30 con T=2 configurada: lecturas 18.5 y 31.5 en AMARILLO | Newman |
| TC-M03-180 | Variable sin umbral: valor y unidad, GRIS, «Sin umbral configurado», notificación al administrador, sin ocultarse | Newman + Cypress |
| TC-M03-266 | Umbral 10–20 con lectura 15 en VERDE; al reconfigurarlo a 20–30, la misma lectura pasa a ROJO/AMARILLO | Newman |

Las aserciones (PRE/ASSERT) están en `g88_casos.mjs` con un id estable.

## Representación de los umbrales de la matriz en M09 (RF-17)

RF-17 no tiene tolerancia T. Exige tres niveles contiguos (normal, precaución y crítico) que
cubran exactamente `[valor_min, valor_max]`. Cada umbral «mín–máx con T» se registra así:

- Tolerancia inferior: `precaucion [mín−T, mín] · normal [mín, máx] · critico [máx, máx+T]`
- Tolerancia superior: `critico [mín−T, mín] · normal [mín, máx] · precaucion [máx, máx+T]`

Un umbral solo puede tener una banda de precaución, así que cada lado de la tolerancia se
evalúa con su propia configuración. La colección edita el umbral entre fases, y el dashboard
se consulta antes de cada reconfiguración. T por defecto = 10 % de (máx − mín).

## Archivos

| Archivo | Función |
| --- | --- |
| `ejecutar_tc_m03_g88.mjs` | Único ejecutor. Validación local y ejecución oficial: preflight, sandbox, datos, Newman, Cypress, cierre, evidencia e informe. Incluye la configuración de Cypress. |
| `g88_casos.mjs` | Catálogo de casos y aserciones, plan de datos y efectos persistentes conocidos. |
| `g88_lib.mjs` | Funciones comunes del ejecutor (copia idéntica a la de G87 y G89). |
| `TC-M03-G88.postman_collection.json` | Escenarios API (39 peticiones). Usa las sesiones del ejecutor y sin autorización omite todas las peticiones. |
| `tc_m03_g88.cy.js` | UI de TC-M03-180. Sin mocks; añade las cabeceras del sandbox y serializa las peticiones. |
| `validar_local_g88.mjs` | Pruebas unitarias locales (`node --test`). |

## Uso

```powershell
node ejecutar_tc_m03_g88.mjs --validar-local
# Solo con autorización expresa de Desarrollo y QA_AUTORIZADO=SI:
node ejecutar_tc_m03_g88.mjs --ejecutar --ambiente TEST --autorizacion "<referencia>" --tipo evaluacion --aceptar-efectos notificacion-login
# Para un reintento técnico, usar --tipo reintento.
```

Resultados:

- V1: `RESULTADOS/<RUN_ID>/TC-M03-G88_resultado.md`
- V2 y siguientes: `EvaluacionVN/RESULTADOS/<RUN_ID>/TC-M03-G88_reevaluacion_VN.md`

Cada RUN contiene el informe y `evidencia.json`. Si aplican, también `newman/` con el HTML y `capturas/` de TC-M03-180.

## Datos que prepara el ejecutor (sandbox, API oficial)

- **Especie:** la primera especie activa que cumple tres condiciones:
  - no tiene Gateway Edge (se comprueba por SQL antes de escribir), así que editar el umbral no publica por MQTT;
  - no tiene umbral para TEMPERATURA_AMBIENTAL ni HUMEDAD_RELATIVA, así que no se toca configuración ajena;
  - no tiene métricas obligatorias para activos INDIVIDUAL.
- **Finca y área:** finca compartida por el Administrador y el Productor; si no existe, se crea con acceso para el Productor. El área es nueva y de esa especie.
- **Dispositivo y sensores:** dispositivo sin gateway y 13 sensores calibrados, uno por lectura (12 de temperatura y 1 de humedad).
- **Activo:** un único activo INDIVIDUAL en el área, porque RF-61 solo VINCULA la lectura, y RF-17 solo la clasifica, si hay exactamente uno.
- **Umbral:** lo registra y edita la propia colección como parte de cada escenario.

## Riesgos y efectos conocidos

- **Notificación de login:** cada login genera una notificación persistente fuera del sandbox. Exige `--aceptar-efectos notificacion-login` (3 logins por RUN).
- **Cuentas QA bloqueadas:** quedan bloqueadas para uso externo mientras el RUN está abierto.
- **Timeout del sandbox:** 180 s de inactividad.
- **Aislamiento:** se verifica con testigos sin RLS.
- **Hipótesis estáticas** (no son defectos confirmados): la fórmula con T de la Fase 3 no se usa en el dashboard; no hay recálculo al editar el umbral; sin umbral el estado queda VERDE. Se contrastan con lo observado.

## Ejecución de Cypress

- **Proyecto:** la carpeta del grupo. **Configuración:** su archivo propio, `cypress.g88.config.cjs`, que no contiene ningún destino. Nunca se carga el `cypress.config.cjs` raíz, cuyo `baseUrl` es el API remoto. Sustituye a `configFile: false`, que Cypress 14 rechaza («`--config-file` cannot be false»): con esa opción las pruebas de interfaz nunca llegaban a ejecutarse.
- **Destinos:** las anulaciones van dentro de `e2e`. `baseUrl` es el frontend de TEST, que debe ser HTTPS y distinto del API (`env.API_BASE`); si no lo es, la ejecución se rechaza.
- **Artefactos y arranque:** el reporter es de consola, las capturas y descargas van a la carpeta del RUN y el proceso de Cypress no hereda `ELECTRON_RUN_AS_NODE`. La lógica está en `cypress_seguro.mjs`.
- **`--verificar-spec`:** descubre el spec sin red. Antes de lanzar Cypress comprueba que no haya destinos en la configuración, las anulaciones, `cypress.env.json` ni las variables `CYPRESS_*`, y bloquea la salida con un proxy de loopback inexistente. Si algo falla, Cypress no se ejecuta. Exige el spec descubierto, la barrera `BLOQUEO_G88` en el `before` y ningún artefacto nuevo.

```
node ejecutar_tc_m03_g88.mjs --verificar-spec
```
