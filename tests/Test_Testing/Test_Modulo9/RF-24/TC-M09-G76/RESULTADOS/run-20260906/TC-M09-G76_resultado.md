# TC-M09-G76 — RESULTADO

## DECISIÓN GENERAL

**APROBADO**

Los dos originales quedaron APROBADOS. RF-24 impide calibrar un sensor de un
dispositivo inactivo (HTTP 422) y rechaza la calibración cuando el sensor no está
asociado al área indicada (HTTP 400), en ambos casos sin crear registro y sin alterar
las calibraciones históricas. No hay defectos que reportar.

| Caso | Resultado | Motivo | Categoría de error | Equipo responsable | Acción |
| ---------- | --------- | ------ | ------------------ | ------------------ | ------ |
| TC-M09-146 | **APROBADO** | Dispositivo **47** existente pero `es_activo=false`, con sensor propio, área correcta y valor válido: **HTTP 422 `DISPOSITIVO_INACTIVO`**, sin calibración creada | — | — | Ninguna |
| TC-M09-147 | **APROBADO** | Dispositivo **3** activo, sensor **6** suyo, área correcta **3**, área enviada **1** —existente pero no asociada—: **HTTP 400 `SENSOR_AREA_INVALIDA`** por conflicto de ubicación, sin persistencia y con las dos calibraciones históricas intactas | — | — | Ninguna |

Responsable QA: Juan Esteban. M09 / RF-24 / CU-05. Prioridad alta. Técnica: pruebas
de validación. Herramienta: Newman. Actor: **Ingeniero de campo**. Sin Cypress, sin
mocks y **sin PostgreSQL**: la API bastó para demostrar todas las relaciones. G74 y
G75 no se ejecutaron. No se avanzó a ningún otro grupo.

---

## Entorno

- Fecha: 2026-09-06 UTC. POST de TC-M09-146 a las 04:53:51 y de TC-M09-147 a las
  04:54:23. Los JSON conservan los timestamps exactos.
- Backend TEST: `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`
- Frontend TEST: `https://sigab-frontendtest-6aqrny-d2b730-158-69-200-27.sslip.io`
- Rama backend: `qa/juan-esteban-m09` · SHA local `adc3932b9f0293a76ebec7e89ed877274791b6a1`
- Rama frontend: `qa/juan-esteban-m09` · SHA local `966621df4e2c6a1f2c9233ea5ebefbb9e3bc2f56`
- **SHA desplegado en TEST no confirmado.** Los SHA anteriores son locales.
- Preflight antes de cada ejecución: `/login` del frontend, `/health` y
  `/openapi.json` del backend en **200**, con verificación de que OpenAPI publica
  `POST /configuracion/sensores/{id_sensor}/calibrar`.
- Dependencias verificadas, ninguna instalada: Newman **6.2.2**,
  `newman-reporter-htmlextra` **1.23.1**.
- Ubicación de los archivos QA:
  `sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G76/`, siguiendo la
  indicación explícita de trabajar en `RF-24/TC-M09-G76` del repositorio de backend.

## Actor

Los dos POST se ejecutaron como **Ingeniero de campo** (`ingeniero@pecuaria.co`),
autenticado realmente contra TEST. Permisos comprobados antes del primer POST sobre
el recurso 12 (sensores): **C=1, R=2, U=3**. El propio runner aborta si el actor no
tiene la acción de creación, para no confundir un 403 con un fallo de la regla.
El mismo actor realizó todo el descubrimiento: no hizo falta otro usuario.

## Revisión del contrato

Revisión enfocada y de solo lectura, una sola vez antes del primer POST.

| Punto | Hallazgo |
|---|---|
| Endpoint de calibración | `POST /configuracion/sensores/{id_sensor}/calibrar`, éxito **201** |
| Historial | `GET /configuracion/sensores/{id_sensor}/calibraciones` |
| Dispositivo inexistente | `DISPOSITIVO_NO_ENCONTRADO` (`NotFoundError`) → 404 |
| **Dispositivo inactivo** | `DISPOSITIVO_INACTIVO` (`BusinessRuleError`) → **422** ✓ RF-24 |
| Sensor de otro dispositivo | `SENSOR_DISPOSITIVO_INVALIDO` (`BusinessRuleError`) → 422 |
| **Sensor no asociado al área** | `SENSOR_AREA_INVALIDA` (`ValidationError`, `field: id_infraestructura`) → **400** ✓ RF-24 |
| Relación dispositivo–sensor | `GET /configuracion/dispositivos-iot/{id}/sensores` |
| Relación sensor–área | `GET /configuracion/sensores/{id}/asociaciones`; vigente = `fecha_finalizacion: null` |
| Existencia de un área | `GET /configuracion/infraestructuras/{id}` → 200 si existe, 404 `INFRAESTRUCTURA_NO_ENCONTRADA` si no |
| Rango técnico | `GET /configuracion/sensores/rangos-calibracion`, por categoría |

**Sin `CONTRACT_REQUIREMENT_MISMATCH`:** RF-24 y el contrato implementado coinciden
en 422 para dispositivo inactivo y en 400 para el conflicto de ubicación. No hizo
falta ajustar ninguna expectativa.

Orden de validación, decisivo para el aislamiento: **dispositivo existe → dispositivo
activo → sensor existe → sensor pertenece al dispositivo → asociación de área vigente
coincide con la enviada → valor decimal válido → rango técnico**. Cada payload supera
todas las reglas anteriores a la suya, de modo que el rechazo observado solo puede
provenir de la regla bajo prueba.

---

## TC-M09-146 — APROBADO

Impedir calibración con dispositivo existente pero inactivo. **1 POST**, sin
reintento.

### TC-M09-146 — DATOS UTILIZADOS

| Dato | Valor |
| ------------------------------- | -------- |
| Dispositivo | **47** — serial `BUGCHECK-REASIGN-001` |
| Estado | **Inactivo** (`es_activo: false`, tal como estaba en TEST) |
| Sensor | **29** — «SensorBugcheck», categoría `PH`, activo |
| Sensor pertenece al dispositivo | **Sí** (`id_dispositivo_iot: 47`) |
| Área | **3** — asociación vigente del sensor (`fecha_finalizacion: null`) |
| Área correcta | **Sí**, es la de la asociación vigente |
| Rango técnico | `PH 0.0000 – 14.0000` |
| Valor | **7.0000** — claramente interior, sin tocar fronteras |

El dispositivo inactivo se **descubrió** entre los 59 que ya estaban inactivos en
TEST: no se desactivó ninguno ni se modificó el catálogo. La única invalidez
intencional es el estado del dispositivo.

### Resultado

```json
{
  "error_code": "DISPOSITIVO_INACTIVO",
  "message": "Solo se pueden calibrar sensores de dispositivos activos.",
  "fields": [],
  "timestamp": "2026-09-06T04:53:51.917589+00:00"
}
```

HTTP **422**, exactamente el que exige RF-24, con un mensaje que corresponde
inequívocamente a la regla: solo se calibran dispositivos activos. Se comprobó
explícitamente que **no** es `DISPOSITIVO_NO_ENCONTRADO`, `SENSOR_NO_ENCONTRADO`,
`SENSOR_DISPOSITIVO_INVALIDO`, `SENSOR_AREA_INVALIDA`, `VALOR_CALIBRACION_INVALIDO`,
`VALOR_FUERA_DE_RANGO` ni `ERROR_INTERNO`, y que el status no fue 201, 400, 404 ni
500. Sin `id_calibracion` y sin ningún indicio de creación.

No se obtuvo 404: el dispositivo **existe**, que es justo la precondición del caso.

**13/13 assertions.**

## TC-M09-147 — APROBADO

Impedir calibración cuando el sensor no pertenece al área indicada. **1 POST**, sin
reintento.

### TC-M09-147 — DATOS UTILIZADOS

| Dato | Valor |
| -------------------------------- | ------ |
| Dispositivo | **3** — serial `IOT-ALE01-HLA-003` |
| Estado | **Activo** |
| Sensor | **6** — «Sensor temperatura alevinera-01», `TEMPERATURA`, activo, del dispositivo 3 |
| Área correcta real | **3** — «Zona de incubación, profundidad 15 cm», asociación vigente |
| Área enviada | **1** |
| Área enviada existe | **Sí** — `GET /configuracion/infraestructuras/1` → **200**, área activa |
| Sensor pertenece al área enviada | **No** — el historial completo de asociaciones del sensor 6 contiene únicamente el área `[3]` |
| Valor | **22.5000** |
| Valor válido | **Sí** — interior del rango `TEMPERATURA 0.0000 – 45.0000` |

**El área alternativa es real, no un identificador inventado.** Se comprobó durante
el descubrimiento que `GET /configuracion/infraestructuras/999` devuelve **404
`INFRAESTRUCTURA_NO_ENCONTRADA`**: usar el 999 del ejemplo de la matriz habría
probado «área inexistente», no «asociación incorrecta». Por eso se seleccionó un área
existente, activa y demostrablemente ajena al sensor, que es lo que aísla la regla.

### Resultado

```json
{
  "error_code": "SENSOR_AREA_INVALIDA",
  "message": "El sensor 6 no está asociado al área 1. Verifique la ubicación física y lógica del equipo antes de calibrar.",
  "fields": [{ "field": "id_infraestructura", "message": "El sensor 6 no está asociado al área 1. Verifique la ubicación física y lógica del equipo antes de calibrar." }],
  "timestamp": "2026-09-06T04:54:23.040373+00:00"
}
```

HTTP **400**, el que exige RF-24, con un mensaje que corresponde conceptualmente al
**conflicto de ubicación**: nombra el sensor, el área solicitada y remite a verificar
la ubicación física y lógica del equipo. El campo señalado es `id_infraestructura`.
Se comprobó que **no** es `DISPOSITIVO_INACTIVO` ni ninguna otra regla, y que el
status no fue 201, 404, 422 ni 500.

No se obtuvo 404, lo que confirma que todas las entidades enviadas existían: el
rechazo es por inconsistencia de asociación, no por referencia inexistente.

**15/15 assertions.**

---

## PERSISTENCIA

| Caso | Historial BEFORE | Historial AFTER | Nuevo registro inválido | Históricos intactos |
| ----- | ---------------- | --------------- | ----------------------- | ------------------- |
| TC-M09-146 | **0** (sensor 29) | **0** | **No** | **Sí** (sin históricos previos) |
| TC-M09-147 | **2** (sensor 6: #10 y #11) | **2** (#10 y #11) | **No** | **Sí** — mismos IDs, mismos valores y mismas fechas |

En TC-M09-147 la comprobación de integridad es **significativa**: el sensor elegido
ya tenía dos calibraciones válidas, y tras el rechazo ambas conservan su
`valor_referencia` y su `fecha_calibracion` sin cambio alguno. Es decir, una petición
rechazada no altera el historial.

La verificación final de solo lectura confirma además que **nada del entorno se
movió**: el dispositivo 47 sigue inactivo, el dispositivo 3 sigue activo, la
asociación vigente del sensor 6 sigue apuntando al área 3 y el área 1 sigue
existiendo. G76 no modificó dispositivos, sensores, áreas ni asociaciones.

## Newman

| Newman | Reporter | Caso | Intento | POST | Status | Error code | Assertions | Fallidas | HTML | JSON |
|---|---|---|---:|---|---:|---|---:|---:|---|---|
| 6.2.2 | htmlextra 1.23.1 | TC-M09-146 | 1 | `POST .../29/calibrar` | 422 | `DISPOSITIVO_INACTIVO` | 13 | 0 | `newman/newman-TC-M09-146-intento1.html` | `newman-TC-M09-146-intento1.json` |
| 6.2.2 | htmlextra 1.23.1 | TC-M09-147 | 1 | `POST .../6/calibrar` | 400 | `SENSOR_AREA_INVALIDA` | 15 | 0 | `newman/newman-TC-M09-147-intento1.html` | `newman-TC-M09-147-intento1.json` |

**2 POST en total, uno por original.** Ningún original usó reintento —no se reintenta
un PASS— y ninguno hizo un tercer POST: el runner lo impide por diseño y también
rechaza sobrescribir la evidencia de un intento ya registrado. Cada invocación
ejecuta un único original mediante `G76_CASE`.

## ORIGEN DE LOS FALLOS

No hubo fallos: ningún original quedó DESAPROBADO ni BLOCKED, no se usó ningún
reintento y no se detectó ningún defecto. Esta sección queda sin entradas por
ausencia de casos no aprobados.

## DEFECTO DETECTADO

**Ninguno.** Las dos precondiciones de integridad de RF-24 se comportan como el
requisito exige: el estado del dispositivo se verifica antes de calibrar y la
coherencia sensor–área se valida con el código HTTP y el mensaje previstos, en ambos
casos sin persistencia y sin tocar el historial. No se propone ID de incidencia, no
se asigna severidad y no se creó ningún ticket en Taiga ni GitHub.

## Comprobaciones previas exigidas antes de clasificar

### TC-M09-146

1. ¿Dispositivo existe? **Sí** — figura en el catálogo y el error no es 404.
2. ¿`activo=false` demostrado? **Sí** — descubierto inactivo y reconfirmado al cierre.
3. ¿Sensor pertenece al dispositivo? **Sí** — `id_dispositivo_iot: 47`.
4. ¿Área correcta? **Sí** — la de la asociación vigente del sensor.
5. ¿Valor válido? **Sí** — 7.0000, interior de `PH 0–14`.
6. ¿Actor autorizado? **Sí** — Ingeniero con C=1 sobre el recurso 12.
7. ¿HTTP 422? **Sí.**
8. ¿Mensaje corresponde a dispositivo inactivo? **Sí.**
9. ¿Sin persistencia? **Sí.**
10. ¿Históricos intactos? **Sí.**

### TC-M09-147

1. ¿Dispositivo activo? **Sí.**
2. ¿Sensor existe? **Sí.**
3. ¿Sensor pertenece al dispositivo? **Sí.**
4. ¿Área correcta real conocida? **Sí** — área 3, asociación vigente.
5. ¿Área enviada existe? **Sí** — GET directo 200.
6. ¿Área enviada es distinta? **Sí** — 1 ≠ 3.
7. ¿Sensor NO está asociado al área enviada? **Sí** — su historial de asociaciones
   solo contiene el área 3.
8. ¿Valor válido? **Sí** — 22.5000, interior de `TEMPERATURA 0–45`.
9. ¿HTTP 400? **Sí.**
10. ¿Mensaje corresponde a ubicación/asociación? **Sí.**
11. ¿Sin persistencia? **Sí.**
12. ¿Históricos intactos? **Sí**, verificado sobre dos calibraciones reales.

## Seguridad

- No se modificó código funcional del backend ni del frontend, ni DTO, modelo,
  router, servicio, repositorio, caso de uso, migraciones o seeds. Solo se leyeron.
- **No se modificó ningún dispositivo, sensor, área ni asociación.** En particular,
  no se desactivó ningún dispositivo para fabricar el escenario de TC-M09-146: se
  usó uno que ya estaba inactivo.
- No se instalaron ni actualizaron dependencias. No se tocó infraestructura.
- **No se usó PostgreSQL, ni siquiera `SELECT`**: la API demostró la pertenencia
  sensor–dispositivo, la asociación sensor–área, la existencia del área alternativa y
  la ausencia de persistencia. Ningún SQL de escritura.
- **Sin cleanup**: no había nada que limpiar, porque ninguna de las dos peticiones
  creó registros. No se eliminó ni se restauró nada.
- Contraseña y token solo en memoria del proceso. Reporter con `omitHeaders`,
  `showEnvironmentData: false`, `showGlobalData: false` y
  `skipEnvironmentVars: ['token']`, más sanitización posterior de HTML y JSON.
- Escaneo final de secretos sobre los artefactos del run buscando **valores** y no
  vocabulario: JWT, cabecera de autorización con token real, cabecera de cookie,
  tokens y credenciales en pares clave-valor y cadenas de conexión. **Sin hallazgos.**
  Registrado en [seguridad-evidencias.json](seguridad-evidencias.json).
- No se ejecutó Cypress ni se usaron mocks: las dos peticiones fueron reales.
- No hubo `git commit`, `push`, `pull`, `merge`, `rebase`, `reset`, `clean`, `stash`,
  `checkout`, `switch`, creación o borrado de rama, tags ni PR.

## Git final

Backend (`qa/juan-esteban-m09`, `adc3932b9f0293a76ebec7e89ed877274791b6a1`):
`git diff --stat` vacío — ningún archivo versionado modificado. Lo nuevo son los
archivos QA de este grupo bajo `RF-24/TC-M09-G76/`, más los untracked previos de
otros grupos que ya existían al comenzar.

Frontend (`qa/juan-esteban-m09`, `966621df4e2c6a1f2c9233ea5ebefbb9e3bc2f56`):
**G76 no ejecutó ninguna operación sobre el repositorio de frontend.**

### Hallazgo del estado del repositorio, fuera del alcance de G76

`git diff --stat` del frontend no está vacío: el archivo versionado
`testing/test_testing/Modulo9/RF-17/TC-M09-G22/.gitkeep` sigue figurando como
**eliminado**. Es la misma observación ya registrada en el cierre de TC-M09-G75:
pertenece a RF-17 y es ajena a este grupo. Conforme a las reglas **no se revirtió, no
se reseteó y no se restauró**; se documenta de nuevo para que la revisión humana
decida. No afecta a ninguna comprobación de G76.

Detalle en [git-final.json](git-final.json).

---

## Estado de cierre

G76 queda ejecutado y detenido para revisión humana. TC-M09-146 y TC-M09-147
**APROBADOS**. Decisión general **APROBADO**. Sin defectos que reportar a ningún
equipo y sin categorías de error que asignar. No se avanza a otro grupo.
