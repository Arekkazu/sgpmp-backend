# TC-M09-G26 — RESULTADO

## DECISIÓN GENERAL

**APROBADO**

Los tres originales quedaron APROBADOS. Las tres reglas de integridad de RF-17 se
cumplen: la referencia de especie se valida, la unicidad por combinación se respeta
y el catálogo predefinido es inviolable. No se creó ningún umbral ni ninguna
variable, y no hay ningún defecto que reportar a Desarrollo.

TC-M09-65 presentó una discrepancia entre el código HTTP que declara la matriz
(400) y el que devuelve el contrato real y publicado (404). Se analizó, se resolvió
como **expectativa desactualizada de la matriz** —no como incumplimiento del
producto—, se corrigió la assertion QA y el reintento cerró 16/16. El fundamento
completo está en la sección **DECISIÓN SOBRE TC-M09-65** y la recomendación para el
dueño del requisito en **OBSERVACIÓN DE CONTRATO**.

| Caso | Resultado | Motivo | ¿Reportar a Desarrollo? |
| --------- | -------------------------------- | ------ | ----------------------- |
| TC-M09-57 | APROBADO | Especie inexistente (ID 911) y especie inactiva (ID 11, `es_activo=false`) rechazadas con HTTP 422 `ESPECIE_INACTIVA` sobre `id_especie`, sin persistencia en ninguna de las dos variantes. 13/13 assertions cada una | No |
| TC-M09-58 | APROBADO | Segundo umbral para especie 4 + variable 1, con configuración activa previa #10: HTTP 409 `UMBRAL_DUPLICADO`; después sigue existiendo exactamente una configuración, la original y activa. 14/14 assertions | No |
| TC-M09-65 | APROBADO | Variable 916 ausente del catálogo rechazada con `VARIABLE_AMBIENTAL_NO_ENCONTRADA` sobre `id_variable_ambiental`, sin umbral y **sin crear la variable**. El status real es 404, el declarado por el contrato publicado; la expectativa de 400 de la matriz quedó desactualizada. Reintento con el oráculo corregido: 16/16 assertions | No — se propone actualizar la matriz, ver **OBSERVACIÓN DE CONTRATO** |

### Detalle interno de TC-M09-57

| Variante TC57 | Resultado | HTTP | Persistencia |
| ------------------- | --------- | ---- | ------------ |
| Especie inexistente | APROBADO | 422 `ESPECIE_INACTIVA` | Ninguna — GET 200, especie 911 con 0 umbrales |
| Especie inactiva | APROBADO | 422 `ESPECIE_INACTIVA` | Ninguna — GET 200, especie 11 con 0 umbrales |

Responsable del grupo: Juan Esteban. M09 / RF-17 / CU-03 (trazabilidad de los
originales: CU-07). Prioridad alta. Tipo: integridad / validación / seguridad.
Herramienta: Newman. Actor: Administrador TEST. Sin Cypress. G22, G23, G24 y G25
no se ejecutaron ni se modificaron. G27 no se inició.

### Discrepancia de responsable

Discrepancia de responsable detectada entre caso agrupado e individual; para esta
ejecución se siguió la asignación del grupo TC-M09-G26. El caso agrupado está
asignado a Juan Esteban mientras la fila individual de `TC-M09-65` muestra
Juan Manuel. **La matriz no fue modificada.**

---

## ORIGEN DE LOS FALLOS

Ningún original quedó DESAPROBADO ni BLOCKED, y no se detectó ningún defecto. La
única incidencia de ejecución fue la assertion de status del primer intento de
TC-M09-65, cuyo origen se detalla aquí por trazabilidad:

### TC-M09-65 — assertion de status del intento 1

- **Producto:** No — rechazó la referencia inválida, no persistió el umbral y no
  creó la variable; el código de error es específico de la regla probada.
- **Automatización/prueba:** **Sí** — la expectativa de status provenía de la matriz
  (400) y no del contrato real y publicado (404). El resto del caso estaba bien
  construido: 15 de 16 assertions pasaron en el intento 1.
- **Entorno:** No — TEST accesible; preflight, login y todos los GET en 200.
- **Bloqueo:** No — se resolvió con el análisis de contrato y el reintento
  disponible.
- **Acción:** `CORREGIR AUTOMATIZACIÓN` — hecho y verificado (16/16 en el intento
  2). **NO REPORTAR A DESARROLLO.** Adicionalmente,
  `REVISIÓN HUMANA DE CONTRATO/REQUISITO` como recomendación documental para
  actualizar la matriz: ver **OBSERVACIÓN DE CONTRATO**.

TC-M09-57 y TC-M09-58 no tienen entradas en esta sección.

---

## CONTRACT_REQUIREMENT_MISMATCH

Detectado **antes del primer POST**, durante la revisión del contrato, y confirmado
después con la respuesta real.

| Fuente | Resultado esperado para «variable fuera del catálogo» | Evidencia |
|---|---|---|
| Matriz agrupada y RF-17 (TC-M09-65) | **HTTP 400** | Enunciado del caso original: «Resultado esperado en matriz: HTTP 400 y ausencia de persistencia» |
| Contrato implementado | **HTTP 404** | `registrar_umbral_use_case.py` lanza `NotFoundError(code='VARIABLE_AMBIENTAL_NO_ENCONTRADA')`; `src/shared/errors.py` documenta `NotFoundError → 404` |
| Contrato publicado | **404 declarado** | El `openapi.json` desplegado declara para `POST /configuracion/umbrales` los estados `201, 401, 403, 404, 409, 422`. El 404 está declarado; el 400 **no** aparece |
| Comportamiento real observado | **HTTP 404** | Respuesta real del POST, registrada en `newman-TC-M09-65-intento1.json` y en el HTML de Newman |

Ambas posturas son defendibles a priori: RF-17 pide un rechazo por dato inválido
(400) y el contrato aplica la semántica de recurso referenciado inexistente (404),
declarada en OpenAPI. Por eso:

1. se conservaron ambas evidencias, en dos intentos independientes;
2. **no se inventó un bug**;
3. no se modificó el producto;
4. no se modificó el requisito ni la matriz;
5. **no se cambió el oráculo en silencio**: el intento 1 ejecutó y dejó registrada
   como fallida la assertion `HTTP exactamente 400 (oráculo declarado por la matriz
   y RF-17)`, y la corrección solo se aplicó después del análisis, quedando
   explícita en el nombre de la nueva assertion y en este informe.

## DECISIÓN SOBRE TC-M09-65

Analizada la discrepancia, **se resuelve que el 400 de la matriz es una expectativa
desactualizada y que el comportamiento del producto es correcto**. TC-M09-65 queda
APROBADO. Fundamento, en orden de peso:

1. **La regla normativa de RF-17 se cumple íntegramente.** Lo que el requisito
   protege es que solo se usen variables del catálogo predefinido y que el módulo no
   pueda crear variables. Ambas cosas se verificaron: rechazo con código específico
   de la variable, ningún umbral creado y **catálogo intacto**, con los mismos 16
   IDs antes y después. La sustancia del requisito no está incumplida.
2. **El contrato publicado declara 404 y no declara 400.** El `openapi.json`
   desplegado —el contrato contra el que se integran los clientes— lista
   `201, 401, 403, 404, 409, 422`. Cualquier consumidor construido hoy maneja 404;
   cambiarlo a 400 sería un cambio incompatible de API motivado por un matiz de
   código, sin ganancia funcional.
3. **El impacto sobre el usuario es nulo, y está verificado.** El cliente HTTP del
   frontend solo trata de forma especial 401, 403 y 412 (`src/shared/api/http.ts`);
   el formulario de umbrales solo distingue 412 y para cualquier otro status muestra
   la misma alerta con el mensaje del servidor (`UmbralesSection.tsx`). Un 404 y un
   400 producen exactamente la misma experiencia. Además el campo de variable es un
   `<select>` alimentado del catálogo, así que por interfaz no es posible enviar una
   variable arbitraria: el escenario solo se alcanza por API directa.
4. **404 es coherente con la arquitectura documentada del backend.** `NotFoundError`
   está definido como «el recurso solicitado no existe → 404» en `src/shared/errors.py`
   y así se aplica en todo el proyecto, no como una decisión aislada de RF-17.

Por tanto: **no se abre incidencia y no se reporta a Desarrollo.** Se corrigió
únicamente la assertion de status del archivo QA
`TC-M09-G26.postman_collection.json`, en el item `TC-M09-65`, y se usó el único
reintento disponible; el intento 2 cerró con 16/16 assertions. El intento 1 se
conserva íntegro como evidencia de la discrepancia.

## OBSERVACIÓN DE CONTRATO

Para el dueño del requisito y de la matriz, no para Desarrollo. Sin impacto
funcional; se documenta para que la trazabilidad quede coherente:

1. **Actualizar el resultado esperado de TC-M09-65 en la matriz de 400 a 404**, o
   redactarlo como «rechazo específico por variable fuera del catálogo, sin
   persistencia», dejando el código al contrato. QA no modificó la matriz.
2. **Inconsistencia interna del contrato, detectada de paso.** Dos referencias
   equivalentes del mismo payload se resuelven con códigos distintos: una especie
   inexistente devuelve **422** `ESPECIE_INACTIVA` —no 404, pese a que tampoco
   existe— y una variable inexistente devuelve **404**. Ambas son claves foráneas
   del mismo POST. No es un defecto y no afecta al usuario, pero conviene decidir un
   criterio único y reflejarlo en RF-17 y en OpenAPI. Queda como observación de
   diseño de contrato para revisión humana, con severidad no asignada por QA.

---

## Entorno

- Fecha: 2026-09-06 UTC. POST de TC-M09-57 (inexistente) 00:26:36, TC-M09-57
  (inactiva) 00:26:54, TC-M09-58 00:27:19 y TC-M09-65 00:27:48. Los JSON conservan
  los timestamps exactos.
- Frontend TEST: `https://sigab-frontendtest-6aqrny-d2b730-158-69-200-27.sslip.io`
- Backend TEST: `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`
- Rama backend: `qa/juan-esteban-m09` · SHA local `adc3932b9f0293a76ebec7e89ed877274791b6a1`
- Rama frontend: `qa/juan-esteban-m09` · SHA local `966621df4e2c6a1f2c9233ea5ebefbb9e3bc2f56`
- **SHA desplegado en TEST no confirmado.** Los SHA anteriores son locales.
- Status Git inicial: backend con untracked únicamente de TC-M09-G24 y TC-M09-G25;
  frontend con untracked únicamente de TC-M09-G22. Ningún archivo versionado modificado.
- Preflight antes de cada ejecución: `/login` del frontend, `/health` y
  `/openapi.json` del backend en **200**; se comprobó la publicación del POST.
  Login real 200; permisos del recurso 20 (crear y consultar) verificados.
- Dependencias verificadas, ninguna instalada: Newman **6.2.2**,
  `newman-reporter-htmlextra` **1.23.1**, Node 22.15.1. Cypress no se ejecutó.
- Ubicación de los archivos QA:
  `sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-17/TC-M09-G26/`, siguiendo la
  indicación explícita de trabajar en `RF-17/TC-M09-G26` del repositorio de backend
  y la estructura ya usada por G23, G24 y G25.

## Revisión del contrato

Revisión enfocada y de solo lectura, realizada una sola vez antes del primer POST.

| Punto | Hallazgo |
|---|---|
| Endpoint POST | `POST /configuracion/umbrales` |
| Endpoint GET | `GET /configuracion/umbrales?id_especie={id}` (incluye activos e inactivos) y `GET /configuracion/variables-ambientales` |
| Payload | `id_especie`, `id_variable_ambiental`, `valor_min`, `valor_max`, `niveles` |
| Representación de la especie | **ID entero** (`id_especie`), FK al catálogo de especies |
| Representación de la variable | **ID entero** (`id_variable_ambiental`), FK al catálogo. No es string, código ni enum: el campo `tipo_variable` de la matriz académica **no existe** en el contrato real |
| Campos obligatorios | Todos los anteriores |
| Niveles | Obligatorios: exactamente 3 (`normal`, `precaucion`, `critico`), cada uno con `limite_inferior < limite_superior` |
| Especie inexistente o inactiva | `BusinessRuleError(code='ESPECIE_INACTIVA', field='id_especie')` → **422** ✓ coincide con RF-17 |
| Duplicado | `ConflictError(code='UMBRAL_DUPLICADO')` → **409** ✓ coincide con RF-17 |
| Variable fuera del catálogo | `NotFoundError(code='VARIABLE_AMBIENTAL_NO_ENCONTRADA', field='id_variable_ambiental')` → **404** ✗ la matriz declara 400 |
| Estructura de errores | `{ error_code, message, fields[], timestamp }` |

Orden de validación, decisivo para el aislamiento: **especie → variable → niveles →
rangos (físico, nivel fuera de rango, solapamiento) → unicidad**. Las tres reglas de
G26 se evalúan en momentos distintos, así que cada payload debe superar todas las
anteriores para llegar a la suya. Detalles relevantes:

- La unicidad se consulta **sin filtrar por `es_activo`**: cualquier registro previo
  de la combinación bloquea uno nuevo.
- El catálogo de especies (`GET /configuracion/especies`, `solo_activas=false` por
  defecto) devuelve la lista **completa** con `total`, sin paginación: sirve como
  evidencia de que un ID no existe. No hay endpoint `GET especies/{id}`.
- El catálogo de variables expone **solo las activas** (`listar_activas`).

---

## TC-M09-57 — APROBADO

**Impedir configuración para especie inexistente o inactiva.** Esperado: HTTP 422 y
ausencia de configuración. Presupuesto: **2 POST, uno por variante. No hubo tercero.**

Datos comunes a las dos variantes — variable válida y activa del catálogo:
**Humedad Relativa** (ID 10, `%`, límites físicos `[0, 100]`), rango enviado
`20 – 80` con niveles `20–40`, `40–60`, `60–80`: contiguos, sin huecos ni
solapamientos, dentro de los límites físicos. La única invalidez es la especie.

### TC57-A — especie inexistente

| Dato | Valor |
|---|---|
| ID inexistente seleccionado | **911** |
| Evidencia de inexistencia | Catálogo completo `GET /configuracion/especies`: `total = 7`, IDs `[1, 2, 3, 4, 5, 10, 11]`; 911 ausente. ID entero positivo válido para el schema, sin overflow |
| Variable válida | 10 Humedad Relativa, activa, `[0, 100] %` |
| Rango | `20 – 80` con tres niveles contiguos |

No se asumió el ID 999 de la matriz: se calculó un candidato y se demostró su
ausencia contra el catálogo completo antes del POST.

```json
{
  "error_code": "ESPECIE_INACTIVA",
  "message": "No se pueden configurar umbrales para una especie inactiva o inexistente.",
  "fields": [{ "field": "id_especie", "message": "No se pueden configurar umbrales para una especie inactiva o inexistente." }],
  "timestamp": "2026-09-06T00:26:36.475210+00:00"
}
```

HTTP **422**, con `fields[].field = id_especie`: el rechazo corresponde a la
referencia de especie. Se comprobó explícitamente que **no** es `VAL_ENTRADA`,
`VARIABLE_AMBIENTAL_NO_ENCONTRADA`, `RANGO_FISICO_INVALIDO`, `NIVEL_FUERA_DE_RANGO`,
`SOLAPAMIENTO_NIVELES`, `UMBRAL_DUPLICADO` ni `ERROR_INTERNO`, y que el status no
fue 400, 404, 409 ni 500 — es decir, **no es un 422 de schema**. Sin ID ni estado de
éxito. GET posterior **200**: la especie 911 tiene 0 umbrales.

### TC57-B — especie inactiva

| Dato | Valor |
|---|---|
| Especie ID | **11** |
| Nombre | Miguel |
| `es_activo` | **false** (descubierta en el catálogo real; no se desactivó ninguna especie) |
| Combinación | Libre: la especie 11 no tenía ningún umbral |
| Variable / rango | 10 Humedad Relativa, `20 – 80` con tres niveles contiguos |

Respuesta idéntica en código y campo, HTTP **422**, `timestamp`
`2026-09-06T00:26:54.047641+00:00`. GET posterior **200** con 0 umbrales para la
especie 11: sin persistencia.

**TC-M09-57 = APROBADO**: ambas variantes rechazadas con 422 por la regla correcta y
sin persistencia. No se escribió «APROBADO parcial».

Evidencia: [HTML inexistente](newman/newman-TC-M09-57-inexistente.html) ·
[JSON inexistente](newman-TC-M09-57-inexistente.json) ·
[datos inexistente](datos-TC-M09-57-inexistente.json) ·
[HTML inactiva](newman/newman-TC-M09-57-inactiva.html) ·
[JSON inactiva](newman-TC-M09-57-inactiva.json) ·
[datos inactiva](datos-TC-M09-57-inactiva.json).

---

## TC-M09-58 — APROBADO

**Impedir una segunda configuración activa para la misma especie y variable.**
Esperado: HTTP 409. Ejecutado con **1 solo POST**; no se usó el reintento.

| Dato | Valor |
|---|---|
| Configuración original ID | **#10** |
| Especie | 4 Cachama Blanca, activa |
| Variable | 1 Temperatura del agua, `°C`, límites físicos `[0, 45]`, en el catálogo activo |
| `es_activo` de la original | **true** |
| Rango de la original | `0.00 – 100.00` |
| Cantidad previa de umbrales de la especie | 2 (#10 y #11) |
| Cantidad posterior | 2 (#10 y #11) — sin cambios |
| Configuraciones de la combinación (4, 1) después | **exactamente 1**, la original #10, activa y con sus valores intactos |

No se creó ningún prerequisito: se reutilizó una configuración activa ya existente
en TEST. No se asumió «Bovino + Temperatura»; la combinación se descubrió
dinámicamente. **No se usó PostgreSQL**: el GET demostró la configuración activa
previa y la unicidad posterior.

Payload del segundo POST — misma especie y misma variable, todo lo demás válido:

```json
{
  "id_especie": 4,
  "id_variable_ambiental": 1,
  "valor_min": 9,
  "valor_max": 36,
  "niveles": [
    { "nivel": "normal",     "limite_inferior": 9,  "limite_superior": 18 },
    { "nivel": "precaucion", "limite_inferior": 18, "limite_superior": 27 },
    { "nivel": "critico",    "limite_inferior": 27, "limite_superior": 36 }
  ]
}
```

Nota de aislamiento importante: el registro existente guarda `0.00 – 100.00`, que
excede el límite físico `[0, 45]` de su propia variable (dato heredado de TEST).
Copiar esos valores habría disparado `RANGO_FISICO_INVALIDO` (400) **antes** de la
comprobación de unicidad y habría producido un rechazo por la regla equivocada. Por
eso el payload usa un rango propio dentro de los límites físicos, que supera todas
las validaciones previas y llega efectivamente a la regla de duplicidad.

```json
{
  "error_code": "UMBRAL_DUPLICADO",
  "message": "Ya existe un umbral para la variable 'Temperatura del agua' en esta especie. Edite la configuración existente.",
  "fields": [],
  "timestamp": "2026-09-06T00:27:19.934341+00:00"
}
```

HTTP **409**, con mensaje que nombra la variable en conflicto. Se comprobó que no es
`ESPECIE_INACTIVA`, `VARIABLE_AMBIENTAL_NO_ENCONTRADA`, `RANGO_FISICO_INVALIDO`,
`NIVEL_FUERA_DE_RANGO`, `SOLAPAMIENTO_NIVELES`, `VAL_ENTRADA` ni `ERROR_INTERNO`, y
que el status no fue 400, 404, 422 ni 500. Sin ID nuevo.

GET posterior **200**: total 2, IDs `[10, 11]`; para la combinación (4, 1) hay
**exactamente una** configuración y es la original #10, aún activa y con
`0.00 – 100.00`. No apareció una segunda configuración activa.

Evidencia: [HTML Newman](newman/newman-TC-M09-58-intento1.html) ·
[JSON](newman-TC-M09-58-intento1.json) · [datos](datos-TC-M09-58-intento1.json).

---

## TC-M09-65 — APROBADO

**Rechazar una variable ambiental no perteneciente al catálogo predefinido.**
Ejecutado con **2 POST**: el intento 1 con el oráculo de la matriz (400) y el
intento 2 con el oráculo del contrato real (404), tras el análisis documentado en
**DECISIÓN SOBRE TC-M09-65**. Payload, especie, variable y verificaciones idénticos
en ambos: lo único que cambió fue la assertion de status del archivo QA.

| Dato | Valor |
|---|---|
| Catálogo observado | 16 variables, IDs `[1 … 16]` (`GET /configuracion/variables-ambientales`) |
| Tipo real del campo | `id_variable_ambiental`, **entero** (FK al catálogo). El `tipo_variable` de la matriz no existe en el contrato |
| Valor inválido enviado | **916** — entero positivo, respeta el tipo del DTO, sin error de parsing |
| Evidencia de ausencia previa | El ID 916 no figura entre los 16 IDs del catálogo antes del POST |
| Especie | 4 Cachama Blanca, activa |
| Rango | `10 – 40`, niveles `10–20`, `20–30`, `30–40`: contiguos y estructuralmente válidos |
| Ausencia posterior | Catálogo con los mismos 16 IDs; umbrales de la especie 4 sin cambios (`[10, 11]`) |

No se usó la cadena «Radiación» de la matriz porque el contrato no acepta un nombre
de variable: exige un ID entero. Enviar un string habría probado validación de
schema, no pertenencia al catálogo.

```json
{
  "error_code": "VARIABLE_AMBIENTAL_NO_ENCONTRADA",
  "message": "No existe una variable ambiental activa con ID 916.",
  "fields": [{ "field": "id_variable_ambiental", "message": "No existe una variable ambiental activa con ID 916." }],
  "timestamp": "2026-09-06T00:27:48.832462+00:00"
}
```

**Intento 1: 15 de 16 assertions PASS. Intento 2, con el oráculo corregido: 16/16.**
En ambos, la respuesta del servidor fue idéntica. Todo lo sustantivo se cumplió:

- el rechazo es específico de la variable: código, mensaje con el ID y
  `fields[].field = id_variable_ambiental`;
- no es otra regla: se comprobó que no es `VAL_ENTRADA`, `ESPECIE_INACTIVA`,
  `RANGO_FISICO_INVALIDO`, `NIVEL_FUERA_DE_RANGO`, `SOLAPAMIENTO_NIVELES`,
  `UMBRAL_DUPLICADO` ni `ERROR_INTERNO`, y que no hubo 201, 409 ni 500;
- sin ID creado y sin estado de éxito;
- **no se creó ningún umbral**: GET de umbrales 200 con los mismos IDs `[10, 11]`;
- **no se creó ninguna variable**: GET del catálogo 200 con los mismos 16 IDs y sin
  el 916. El módulo no permite dar de alta variables arbitrarias, como exige RF-17.

**La única assertion fallida del intento 1 fue el status**: `expected response to
have status code 400 but got 404`. Es exactamente la discrepancia documentada
arriba, no un fallo de comportamiento; resuelta a favor del contrato y verificada en
el intento 2. El caso queda **APROBADO** y no se abre incidencia.

Evidencia intento 1 (oráculo de la matriz, 400):
[HTML](newman/newman-TC-M09-65-intento1.html) ·
[JSON](newman-TC-M09-65-intento1.json) ·
[datos y catálogo previo](datos-TC-M09-65-intento1.json).
Evidencia intento 2 (oráculo del contrato, 404):
[HTML](newman/newman-TC-M09-65-intento2.html) ·
[JSON](newman-TC-M09-65-intento2.json) ·
[datos](datos-TC-M09-65-intento2.json).

---

## Newman

| Newman | Reporter | TC | Variante / intento | POST | Status | Error code | Assertions | Failures | GET | Persistencia | HTML | JSON |
|---|---|---|---|---|---:|---|---:|---:|---:|---|---|---|
| 6.2.2 | htmlextra 1.23.1 | TC-M09-57 | inexistente | `POST /configuracion/umbrales` | 422 | `ESPECIE_INACTIVA` | 13 | 0 | 200 | 0 | `newman/newman-TC-M09-57-inexistente.html` | `newman-TC-M09-57-inexistente.json` |
| 6.2.2 | htmlextra 1.23.1 | TC-M09-57 | inactiva | `POST /configuracion/umbrales` | 422 | `ESPECIE_INACTIVA` | 13 | 0 | 200 | 0 | `newman/newman-TC-M09-57-inactiva.html` | `newman-TC-M09-57-inactiva.json` |
| 6.2.2 | htmlextra 1.23.1 | TC-M09-58 | intento1 | `POST /configuracion/umbrales` | 409 | `UMBRAL_DUPLICADO` | 14 | 0 | 200 | 1 (la original) | `newman/newman-TC-M09-58-intento1.html` | `newman-TC-M09-58-intento1.json` |
| 6.2.2 | htmlextra 1.23.1 | TC-M09-65 | intento1 | `POST /configuracion/umbrales` | 404 | `VARIABLE_AMBIENTAL_NO_ENCONTRADA` | 16 | 1 (status, oráculo de la matriz) | 200 + 200 catálogo | 0 | `newman/newman-TC-M09-65-intento1.html` | `newman-TC-M09-65-intento1.json` |
| 6.2.2 | htmlextra 1.23.1 | TC-M09-65 | intento2 | `POST /configuracion/umbrales` | 404 | `VARIABLE_AMBIENTAL_NO_ENCONTRADA` | 16 | 0 | 200 + 200 catálogo | 0 | `newman/newman-TC-M09-65-intento2.html` | `newman-TC-M09-65-intento2.json` |

**5 POST en total: 2 en TC-M09-57 (una por variante, presupuesto agotado, sin
tercero), 1 en TC-M09-58 y 2 en TC-M09-65.** El único reintento del grupo fue el de
TC-M09-65, justificado por la corrección del oráculo tras el análisis de contrato y
seguro porque el intento 1 no dejó ninguna persistencia. El runner
impide por diseño un tercer POST por original y sobrescribir evidencia existente.
Cada invocación ejecutó un único original mediante `G26_CASE`. Los conteos excluyen
login, preflight, descubrimiento y los GET de comprobación del runner. Los HTML los
generó el reporter real `htmlextra`.

Los nombres de TC-M09-57 usan las variantes funcionales (`inexistente`, `inactiva`)
y no `intento1`/`intento2`, para no confundirlas con reintentos.

## Persistencia

| Momento | Especie afectada | Total umbrales | IDs | Configuraciones de la combinación probada |
|---|---|---:|---|---:|
| TC57-A, después | 911 (inexistente) | 0 | `[]` | 0 |
| TC57-B, después | 11 Miguel | 0 | `[]` | 0 |
| TC58, antes | 4 Cachama Blanca | 2 | `[10, 11]` | 1 (#10) |
| TC58, después | 4 Cachama Blanca | 2 | `[10, 11]` | 1 (#10, la original) |
| TC65 intento 1, después | 4 Cachama Blanca | 2 | `[10, 11]` | 0 |
| TC65 intento 2, después | 4 Cachama Blanca | 2 | `[10, 11]` | 0 |
| Cierre read-only | todas las anteriores | igual | igual | igual |

Catálogos al cierre: **7 especies** (mismos IDs, 2 inactivas) y **16 variables**
(mismos IDs). **No se creó ningún umbral ni ninguna variable durante G26**, y no se
eliminó, desactivó ni modificó ningún registro existente. Comprobación en
[verificacion-final-readonly.json](verificacion-final-readonly.json).

## DEFECTO DETECTADO

**Ninguno.** Las tres reglas de integridad se comportaron como exige RF-17:
referencia de especie validada, unicidad respetada y catálogo predefinido
inviolable. La divergencia de código HTTP de TC-M09-65 se resolvió como expectativa
desactualizada de la matriz, con el fundamento documentado en **DECISIÓN SOBRE
TC-M09-65**. No se propone ID de incidencia, no se asigna severidad y no se creó
ningún ticket en Taiga ni GitHub.

Si en la revisión humana se prefiriera revertir el criterio y exigir el 400 de
RF-17, la incidencia resultante llevaría:
`ID pendiente de asignación según Registro de Errores vigente`,
`Severidad: pendiente de validar contra Registro de Errores vigente`,
`Tiempo máximo: pendiente`, `Fecha límite: pendiente`, equipo `Desarrollo`. La
evidencia del intento 1 basta para abrirla sin repetir la ejecución.

## Preguntas obligatorias antes de reportar un bug

### TC-M09-57

- ¿El ID inexistente realmente no existía? **Sí** — 911 ausente del catálogo
  completo (`total = 7`, IDs `[1,2,3,4,5,10,11]`), verificado antes del POST.
- ¿La especie inactiva realmente tenía `activo=false`? **Sí** — especie 11 Miguel,
  descubierta como inactiva en el catálogo; no se desactivó nada.
- ¿El resto del payload era válido? **Sí** — variable activa del catálogo, rango
  dentro de los límites físicos, tres niveles contiguos que cubren el padre.
- ¿El error correspondió a la referencia? **Sí** — `ESPECIE_INACTIVA` sobre
  `id_especie`, con exclusión explícita de los demás códigos y statuses.

### TC-M09-58

- ¿La configuración previa estaba activa? **Sí** — #10, `es_activo = true`.
- ¿Era la misma especie? **Sí** — 4 en ambos.
- ¿Era la misma variable? **Sí** — 1 en ambos.
- ¿El resto del payload era válido? **Sí** — rango dentro de `[0, 45]` y niveles
  contiguos, precisamente para superar las validaciones previas.
- ¿El 409 correspondía a duplicidad? **Sí** — `UMBRAL_DUPLICADO`, con la variable
  nombrada en el mensaje.

### TC-M09-65

- ¿La variable realmente no pertenecía al catálogo? **Sí** — 916 ausente de los 16
  IDs, antes y después.
- ¿Se respetó el tipo del DTO? **Sí** — entero positivo, sin error de schema.
- ¿El payload tenía otra invalidez? **No** — especie activa, `min < max`, niveles
  contiguos.
- ¿La respuesta correspondió al catálogo? **Sí** —
  `VARIABLE_AMBIENTAL_NO_ENCONTRADA` sobre `id_variable_ambiental`, con el ID en el
  mensaje. Solo el código HTTP divergía del oráculo de la matriz, y esa divergencia
  se resolvió a favor del contrato publicado.

## Seguridad

- No se modificó código funcional: ni `src/` del backend ni `src/` del frontend, ni
  DTO, modelo, router, servicio, repositorio, caso de uso, migraciones o seeds. Solo
  se leyeron para la revisión del contrato.
- No se instalaron ni actualizaron dependencias.
- No se tocó infraestructura: Docker, Dokploy, Nginx, contenedores, dominios ni
  variables de despliegue.
- **No se usó PostgreSQL, ni siquiera `SELECT`.** La API fue suficiente para el
  catálogo, la configuración activa previa, la unicidad y la ausencia de
  persistencia. Ningún SQL de escritura ni migración.
- No se eliminaron, desactivaron ni modificaron registros propios ni ajenos. No se
  crearon prerequisitos.
- Contraseña y token solo en memoria del proceso. No se persistieron credenciales,
  Authorization, Bearer, JWT, access token, refresh token, cookies ni cadenas de
  conexión.
- Reporter con `omitHeaders`, `showEnvironmentData: false`, `showGlobalData: false`
  y `skipEnvironmentVars: ['token']`, más sanitización posterior de HTML y JSON.
- Escaneo final de secretos sobre los archivos de evidencia del run, buscando
  **valores** y no vocabulario: JWT, cabecera de autorización con token real,
  cabecera de cookie, tokens de acceso o refresco en pares clave-valor, credenciales
  en pares clave-valor, cadenas de conexión, y el valor concreto de la contraseña y
  el correo TEST. **Sin hallazgos.** Los términos sí aparecen como prosa en este
  informe al enumerar lo que no se persistió, y se contabilizan aparte como
  menciones de vocabulario. Registrado en
  [seguridad-evidencias.json](seguridad-evidencias.json).
- No se ejecutó Cypress ni se abrió ningún navegador.
- No hubo `git commit`, `push`, `pull`, `merge`, `rebase`, `reset`, `clean`,
  `stash`, `checkout`, `switch`, creación o borrado de rama, tags ni PR.
- G22, G23, G24 y G25 no se ejecutaron ni se modificaron. G27 no se inició.

## Git final

Backend (`qa/juan-esteban-m09`, `adc3932b9f0293a76ebec7e89ed877274791b6a1`):
`git diff --stat` vacío — ningún archivo versionado modificado. Lo nuevo son los
archivos QA de este grupo bajo `TC-M09-G26/`, más los untracked previos de
`TC-M09-G24/` y `TC-M09-G25/` que ya existían al comenzar.

Frontend (`qa/juan-esteban-m09`, `966621df4e2c6a1f2c9233ea5ebefbb9e3bc2f56`):
`git diff --stat` vacío y `git status --short` con exactamente los mismos archivos
untracked preexistentes de `TC-M09-G22/`. **G26 no escribió nada en el repositorio
de frontend.**

No aparecieron cambios funcionales fuera de la carpeta del caso. Detalle en
[git-final.json](git-final.json).

---

## Estado de cierre

G26 queda ejecutado y detenido para revisión humana. TC-M09-57 APROBADO;
TC-M09-58 APROBADO; TC-M09-65 APROBADO tras resolver la discrepancia de oráculo a
favor del contrato publicado y verificarlo con el reintento disponible. Decisión
general **APROBADO**. Nada que reportar a Desarrollo. Queda pendiente de decisión
del dueño del requisito, sin impacto funcional, la **OBSERVACIÓN DE CONTRATO**:
actualizar el resultado esperado de TC-M09-65 en la matriz y unificar el criterio de
código para referencias inexistentes. No se inicia G27.
