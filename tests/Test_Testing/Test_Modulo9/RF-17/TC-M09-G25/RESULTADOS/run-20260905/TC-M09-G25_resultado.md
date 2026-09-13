# TC-M09-G25 — RESULTADO

## DECISIÓN GENERAL

**APROBADO**

Los dos originales quedaron APROBADOS en su primer y único POST. En ambos, RF-17
rechazó la configuración con **HTTP 400** y el código `RANGO_FISICO_INVALIDO`,
citando el nombre de la variable y sus límites físicos, sin crear ningún ID y sin
dejar ninguna configuración persistida.

| Caso | Resultado | Motivo | ¿Reportar a Desarrollo? |
| --------- | -------------------------------- | ------ | ----------------------- |
| TC-M09-55 | APROBADO | Humedad Relativa con `valor_max=120 %` sobre un máximo físico de 100: HTTP 400 `RANGO_FISICO_INVALIDO`, sin ID, GET posterior 200 y combinación sin persistir. 15/15 assertions | No |
| TC-M09-56 | APROBADO | pH del agua con `valor_max=18` sobre la escala 0–14: HTTP 400 `RANGO_FISICO_INVALIDO`, sin ID, GET posterior 200 y combinación sin persistir. 15/15 assertions | No |

Responsable: Juan Esteban. M09 / RF-17 / CU-03 (trazabilidad de los originales:
CU-07). Prioridad alta. Tipo y técnica: pruebas de valores límite. Herramienta:
Newman. Actor: Administrador TEST. Sin Cypress, según el alcance del grupo.
G22, G23 y G24 no se ejecutaron ni se modificaron. G26 no se inició.

## ORIGEN DE LOS FALLOS

No hubo fallos: ningún original quedó DESAPROBADO ni BLOCKED, no se usó ningún
reintento y no se detectó ningún defecto. Esta sección queda sin entradas por
ausencia de casos no aprobados.

---

## Entorno

- Fecha: 2026-09-05. POST de TC-M09-55 a las 00:04:50 UTC del 2026-09-06 y de
  TC-M09-56 a las 00:05:22 UTC; los JSON conservan los timestamps exactos.
- Frontend TEST: `https://sigab-frontendtest-6aqrny-d2b730-158-69-200-27.sslip.io`
- Backend TEST: `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`
- Rama backend: `qa/juan-esteban-m09` · SHA local `adc3932b9f0293a76ebec7e89ed877274791b6a1`
- Rama frontend: `qa/juan-esteban-m09` · SHA local `966621df4e2c6a1f2c9233ea5ebefbb9e3bc2f56`
- **SHA desplegado en TEST no confirmado.** Los SHA anteriores son locales; no se
  asume que coincidan con lo desplegado en Dokploy.
- Status Git inicial: backend con archivos untracked únicamente de TC-M09-G24;
  frontend con archivos untracked únicamente de TC-M09-G22. Ninguno modificado.
- Preflight antes de cada ejecución: `/login` del frontend, `/health` y
  `/openapi.json` del backend devolvieron **200**, y se comprobó que OpenAPI
  publica `POST /configuracion/umbrales`. Login real 200. Permisos del recurso 20
  (crear y consultar) verificados en cada descubrimiento.
- Dependencias verificadas, ninguna instalada ni actualizada: Newman **6.2.2**,
  `newman-reporter-htmlextra` **1.23.1**, Node 22.15.1.
- Ubicación de los archivos QA:
  `sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-17/TC-M09-G25/`, siguiendo la
  indicación explícita de trabajar en `RF-17/TC-M09-G25` y la estructura ya usada
  por G23 y G24 en el repositorio de backend.

## Revisión única del contrato

Revisión enfocada y de solo lectura, hecha una sola vez antes del primer POST:

| Punto | Hallazgo |
|---|---|
| Endpoint | `POST /configuracion/umbrales` |
| Método | POST, `status_code=201` en caso de éxito |
| Payload | `id_especie`, `id_variable_ambiental`, `valor_min`, `valor_max`, `niveles` |
| Campos obligatorios | Todos los anteriores; `niveles` **sí es obligatorio** |
| Estructura de niveles | Exactamente 3: `normal`, `precaucion`, `critico`; cada uno con `limite_inferior < limite_superior` (`registrar_umbral_dto.py`, `nivel_dto.py`) |
| Response schema | `UmbralAmbientalResponse` (`umbral_schema.py`) |
| Código de validación física | `RANGO_FISICO_INVALIDO`, lanzado como `ValidationError` en `_validar_rangos` de `registrar_umbral_use_case.py` |
| HTTP de esa validación | **400** (`src/shared/errors.py`: `ValidationError.status_code = 400`, aplicado por `error_handlers.py`) |
| GET posterior | `GET /configuracion/umbrales?id_especie={id}`; incluye activos e inactivos por defecto |
| Duplicados | `ConflictError UMBRAL_DUPLICADO` → 409, evaluado **después** de `_validar_rangos` |
| Límites físicos | Expuestos por `GET /configuracion/variables-ambientales` (`valor_fisico_min`, `valor_fisico_max`) |

Orden de validación relevante para el aislamiento de G25: especie activa →
variable activa → construcción de niveles → **`_validar_rangos`, cuya primera
regla es el rango físico (FA-04)** → unicidad (409). Es decir, el límite físico se
evalúa antes que el duplicado, y dentro de `_validar_rangos` antes que
`NIVEL_FUERA_DE_RANGO` y `SOLAPAMIENTO_NIVELES`.

**RF-17 y contrato coinciden en 400**, por lo que se usó 400 como assertion. No se
declara `CONTRACT_REQUIREMENT_MISMATCH`: OpenAPI no define otro código para esta
regla concreta.

**Observación documental (no bloqueante).** La lista `responses` que el
`openapi.json` desplegado publica para este POST es `201, 401, 403, 404, 409, 422`
y no enumera el 400. No es una definición contradictoria —OpenAPI no asocia
códigos a reglas—, sino una lista de documentación incompleta: el 400 lo produce
el manejador global para `ValidationError`, y así se observó realmente en los dos
POST de este grupo. Se deja registrado para revisión humana como posible mejora de
documentación del contrato, no como defecto funcional.

**Catálogo conforme a RF-17**, sin `CATALOG_REQUIREMENT_MISMATCH`: Humedad
Relativa expone `[0, 100] %` (RF-17 exige ≤ 100) y pH del agua expone `[0, 14] pH`
(RF-17 exige 0–14).

---

## TC-M09-55 — APROBADO

**Rechazar humedad superior al límite físico permitido.** Regla: `Humedad <= 100 %`.

### Datos dinámicos descubiertos

| Dato | Valor |
|---|---|
| Especie ID | 4 |
| Especie nombre | Cachama Blanca |
| Especie activa | Sí |
| Variable ID | 10 |
| Variable nombre | Humedad Relativa |
| Unidad | % |
| Variable activa en catálogo | Sí |
| Límite físico mínimo | 0 |
| Límite físico máximo | 100 |
| Combinación libre previa | Sí — la especie 4 tenía los umbrales 10 (variable 1) y 11 (variable 3), ninguno de la variable 10 |
| Rango enviado | `valor_min = 50`, `valor_max = 120` |
| Status | 400 |
| Error code | `RANGO_FISICO_INVALIDO` |
| Persistencia | Ninguna |

Ningún ID fue fijado en la automatización: especie, variable, límites y
combinación libre se descubrieron por GET antes del POST.

### Payload sanitizado

```json
{
  "id_especie": 4,
  "id_variable_ambiental": 10,
  "valor_min": 50,
  "valor_max": 120,
  "niveles": [
    { "nivel": "normal",     "limite_inferior": 50, "limite_superior": 70 },
    { "nivel": "precaucion", "limite_inferior": 70, "limite_superior": 90 },
    { "nivel": "critico",    "limite_inferior": 90, "limite_superior": 120 }
  ]
}
```

Aislamiento verificado por assertions sobre el propio payload: `valor_min` (50)
está dentro del rango físico, `valor_min < valor_max`, hay exactamente tres
niveles con los nombres exigidos, cada nivel cumple `inferior < superior`, son
contiguos, no se solapan y cubren exactamente `[50, 120]`. **La única condición
inválida intencional es que `valor_max = 120` supera el máximo físico de 100 %.**

### Respuesta real sanitizada

```json
{
  "error_code": "RANGO_FISICO_INVALIDO",
  "message": "Los valores deben estar dentro del rango físico permitido para 'Humedad Relativa': [0, 100] %.",
  "fields": [],
  "timestamp": "2026-09-06T00:04:50.662682+00:00"
}
```

HTTP **400**, exactamente el que exige RF-17. El rechazo corresponde
inequívocamente al límite físico: el mensaje nombra la variable y sus límites, y
se comprobó explícitamente que el código **no** es `VAL_ENTRADA`,
`NIVEL_FUERA_DE_RANGO`, `SOLAPAMIENTO_NIVELES`, `UMBRAL_DUPLICADO`,
`ESPECIE_INACTIVA`, `VARIABLE_AMBIENTAL_NO_ENCONTRADA` ni `ERROR_INTERNO`, y que
el status no fue 409, 422 ni 500.

Sin `id_umbral_ambiental`, sin `id`, sin `es_activo: true`, sin `success: true` y
status distinto de 201.

### Verificación posterior

`GET /configuracion/umbrales?id_especie=4` → **200**, total 2, IDs 10 y 11,
**0 umbrales de la variable 10**. Los umbrales previos quedaron intactos. Se
confirmó también con el GET del runner y con la verificación final de cierre.

Evidencia: [HTML Newman](newman/newman-TC-M09-55-intento1.html) ·
[JSON sanitizado](newman-TC-M09-55-intento1.json) ·
[datos y preflight](datos-TC-M09-55-intento1.json).

---

## TC-M09-56 — APROBADO

**Rechazar pH fuera de escala física 0–14.** Regla: `0 <= pH <= 14`.

### Datos dinámicos descubiertos

| Dato | Valor |
|---|---|
| Especie ID | 4 |
| Especie nombre | Cachama Blanca |
| Especie activa | Sí |
| Variable ID | 2 |
| Variable nombre | pH del agua |
| Unidad | pH |
| Variable activa en catálogo | Sí |
| Límite físico mínimo | 0 |
| Límite físico máximo | 14 |
| Combinación libre previa | Sí — la especie 4 seguía con los umbrales 10 y 11, ninguno de la variable 2 |
| Rango enviado | `valor_min = 6.5`, `valor_max = 18` |
| Status | 400 |
| Error code | `RANGO_FISICO_INVALIDO` |
| Persistencia | Ninguna |

Los datos se volvieron a descubrir antes de este original; no se reutilizó el
descubrimiento de TC-M09-55.

### Payload sanitizado

```json
{
  "id_especie": 4,
  "id_variable_ambiental": 2,
  "valor_min": 6.5,
  "valor_max": 18,
  "niveles": [
    { "nivel": "normal",     "limite_inferior": 6.5, "limite_superior": 10 },
    { "nivel": "precaucion", "limite_inferior": 10,  "limite_superior": 14 },
    { "nivel": "critico",    "limite_inferior": 14,  "limite_superior": 18 }
  ]
}
```

Mismo aislamiento verificado: `6.5` está dentro de la escala, `valor_min <
valor_max`, tres niveles contiguos, sin huecos ni solapamientos, cubriendo
exactamente `[6.5, 18]`. **La única violación intencional es `valor_max = 18 > 14`.**

### Respuesta real sanitizada

```json
{
  "error_code": "RANGO_FISICO_INVALIDO",
  "message": "Los valores deben estar dentro del rango físico permitido para 'pH del agua': [0, 14] pH.",
  "fields": [],
  "timestamp": "2026-09-06T00:05:22.158264+00:00"
}
```

HTTP **400**, con las mismas comprobaciones de exclusión de otras reglas que en
TC-M09-55. Sin ID ni estado de éxito.

### Verificación posterior

`GET /configuracion/umbrales?id_especie=4` → **200**, total 2, IDs 10 y 11,
**0 umbrales de la variable 2**. Umbrales previos intactos.

Evidencia: [HTML Newman](newman/newman-TC-M09-56-intento1.html) ·
[JSON sanitizado](newman-TC-M09-56-intento1.json) ·
[datos y preflight](datos-TC-M09-56-intento1.json).

---

## Newman

| Newman | Reporter | TC | Intento | POST | Status | Assertions | Failures | GET | Persistencia | HTML | JSON |
|---|---|---|---:|---|---:|---:|---:|---:|---:|---|---|
| 6.2.2 | htmlextra 1.23.1 | TC-M09-55 | 1 | `POST /configuracion/umbrales` | 400 | 15 | 0 | 200 | 0 | `newman/newman-TC-M09-55-intento1.html` | `newman-TC-M09-55-intento1.json` |
| 6.2.2 | htmlextra 1.23.1 | TC-M09-56 | 1 | `POST /configuracion/umbrales` | 400 | 15 | 0 | 200 | 0 | `newman/newman-TC-M09-56-intento1.html` | `newman-TC-M09-56-intento1.json` |

**2 POST en total, uno por original. No se usó ningún reintento** (no se reintenta
un PASS) y no existe ningún intento 2. El runner impide por diseño un tercer POST.
Cada invocación ejecutó un único original mediante la variable `G25_CASE`. Los
conteos de assertions excluyen login, preflight, descubrimiento y el GET de
comprobación del runner. Los HTML los generó el reporter real `htmlextra` durante
la ejecución; no son HTML escritos a mano.

En ningún POST hubo 201, 409, 422 ni 500.

## Persistencia

| Momento | Especie 4 — total | IDs | Umbrales de la variable probada |
|---|---:|---|---:|
| Antes del POST de TC-M09-55 | 2 | 10, 11 | 0 (variable 10) |
| Después de TC-M09-55 | 2 | 10, 11 | 0 |
| Antes del POST de TC-M09-56 | 2 | 10, 11 | 0 (variable 2) |
| Después de TC-M09-56 | 2 | 10, 11 | 0 |
| Verificación final de cierre | 2 | 10, 11 | 0 |

**No se creó ningún umbral en TEST durante G25** y no se eliminó, desactivó ni
modificó ningún registro existente. Comprobación en
[verificacion-final-readonly.json](verificacion-final-readonly.json).

## DEFECTO DETECTADO

Ninguno. Los dos originales se comportaron según RF-17, con el rechazo controlado
y sin persistencia, por lo que no procede abrir incidencia, no se propone ID, no
se asigna severidad y no se creó ningún ticket.

## Respuesta al criterio previo a declarar un defecto

Aunque no hay defecto que reportar, se deja constancia de las verificaciones
exigidas antes de cualquier clasificación:

1. ¿Especie activa? **Sí** (Cachama Blanca, `es_activo: true`, confirmado en el
   catálogo y en la verificación de cierre).
2. ¿Variable correcta? **Sí** — identificada por semántica del nombre, no por ID
   supuesto, y con coincidencia única en el catálogo.
3. ¿Variable activa? **Sí** — el catálogo de variables solo lista activas.
4. ¿Combinación libre? **Sí** en ambos originales, verificada por GET
   inmediatamente antes de cada POST, contando también umbrales inactivos.
5. ¿`min < max`? **Sí** (50 < 120 y 6.5 < 18).
6. ¿Payload conforme al DTO? **Sí**, incluidos los tres niveles obligatorios.
7. ¿Niveles estructuralmente válidos? **Sí**: contiguos, sin huecos ni
   solapamientos y cubriendo el rango padre.
8. ¿Única invalidez intencional física? **Sí**.
9. ¿Límite físico confirmado? **Sí**, contra el catálogo real de TEST.
10. ¿RF y OpenAPI coinciden en el resultado esperado? **Sí en 400**, con la
    observación documental registrada más arriba.
11. ¿El status provino del servidor? **Sí**: respuesta real con `timestamp` del
    backend, sin mocks ni interceptores.
12. ¿Hubo persistencia? **No**, en ninguno de los dos casos.
13. ¿Se usó el segundo intento? **No**, no fue necesario en ningún original.

## Seguridad

- No se modificó código funcional: ni `src/` del backend ni `src/` del frontend,
  ni DTO, modelo, router, servicio, repositorio, caso de uso, migraciones o seeds.
  Solo se leyeron para la revisión del contrato.
- No se instalaron ni actualizaron dependencias. No se ejecutó `npm install`,
  `npm ci`, `npm update`, `npm audit fix`, `yarn`, `pnpm` ni `pip`.
- No se tocó infraestructura: Docker, Dokploy, Nginx, contenedores, dominios ni
  variables de despliegue.
- **No se usó PostgreSQL, ni siquiera `SELECT`.** El API y los GET fueron
  suficientes para catálogo, combinación libre y ausencia de persistencia. Ningún
  SQL de escritura ni migración.
- No se eliminaron, desactivaron ni modificaron registros propios ni ajenos.
- Contraseña y token solo en memoria del proceso, vía `TEST_ADMIN_EMAIL` y
  `TEST_ADMIN_PASSWORD`. No se persistieron ni imprimieron credenciales,
  Authorization, Bearer, JWT, access token, refresh token, cookies ni cadenas de
  conexión.
- Reporter configurado con `omitHeaders`, `showEnvironmentData: false`,
  `showGlobalData: false` y `skipEnvironmentVars: ['token']`, más sanitización
  posterior del HTML y de todo JSON escrito.
- Escaneo final de secretos sobre los 10 archivos de evidencia del run (HTML, JSON
  y este informe), buscando **valores** de secreto: JWT, `Bearer` con token,
  `set-cookie`, `access_token`/`refresh_token` y `password` en pares clave-valor,
  cadenas de conexión y el valor concreto de la contraseña y el correo TEST.
  **Sin hallazgos.** Los términos `Authorization`, `Bearer`, `jwt`, `cookie`,
  `access_token`, `refresh_token` y `password` sí aparecen como **prosa** en este
  informe y en el propio registro del escaneo —al enumerar lo que no se
  persistió—, y se contabilizan aparte como menciones de vocabulario, no como
  fuga. Los dos HTML de Newman no contienen ni siquiera esas menciones.
  Registrado en [seguridad-evidencias.json](seguridad-evidencias.json).
- No se ejecutó Cypress ni se abrió ningún navegador. No se hicieron escrituras
  por UI.
- No hubo `git commit`, `push`, `pull`, `merge`, `rebase`, `reset`, `clean`,
  `stash`, `checkout`, `switch`, creación o borrado de rama, tags ni PR.
- G22, G23 y G24 no se ejecutaron ni se modificaron. G26 no se inició.

## Git final

Backend (`qa/juan-esteban-m09`, `adc3932b9f0293a76ebec7e89ed877274791b6a1`):
`git diff --stat` vacío — ningún archivo versionado modificado. Lo único nuevo son
los archivos QA de este grupo, bajo `TC-M09-G25/`, más los untracked previos de
`TC-M09-G24/` que ya existían al comenzar.

Frontend (`qa/juan-esteban-m09`, `966621df4e2c6a1f2c9233ea5ebefbb9e3bc2f56`):
`git diff --stat` vacío y `git status --short` con exactamente los mismos archivos
untracked preexistentes de `TC-M09-G22/`. **G25 no escribió nada en el repositorio
de frontend.**

No aparecieron cambios funcionales fuera de la carpeta del caso. El detalle queda
en [git-final.json](git-final.json).

---

## Estado de cierre

G25 queda ejecutado y detenido para revisión humana. TC-M09-55 APROBADO;
TC-M09-56 APROBADO; grupo **APROBADO**. Sin defectos que reportar a Desarrollo.
No se inicia G26.
