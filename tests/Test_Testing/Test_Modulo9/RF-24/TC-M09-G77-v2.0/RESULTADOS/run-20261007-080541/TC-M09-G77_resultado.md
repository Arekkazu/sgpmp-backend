# TC-M09-G77-v2.0 — RESULTADO

## DECISIÓN GENERAL

**Grupo:** TC-M09-G77-v2.0
**Caso:** TC-M09-148-v2.0
**Resultado:** RECHAZADO

| Subescenario | Resultado |
|---|---|
| Productor | RECHAZADO |
| Contador | RECHAZADO |

## RESUMEN DEL RESULTADO

Los dos POST de calibración negativos se ejecutaron, uno por rol, sin reintentos y sin
STOP_ALL. **No fue necesaria ninguna escritura sobre el estado de cuenta**: ambas cuentas ya
estaban `Activo`, así que no se activó ni se restauró nada y el ambiente quedó intacto.

La restricción de seguridad **funciona**: ambos roles no autorizados fueron rechazados con
**HTTP 403**, ninguno creó calibraciones y el historial quedó idéntico. La condición negativa
fue estrictamente el rol: ambas cuentas estaban activas, autenticadas, con el rol esperado, y
el request era funcionalmente válido sobre un fixture verificado.

Sin embargo, el mensaje devuelto no es el que exige el FA de RF-24 v2.0. Ambos subescenarios
responden con el texto genérico del RBAC común:

```text
Acceso denegado. Su rol no tiene permisos para realizar esta operación.
```

en lugar del mensaje específico del requisito, que nombra la función crítica y los roles
autorizados. Este es exactamente el texto que el criterio del grupo señala como no aceptable,
de modo que un 403 correcto con mensaje genérico no se convierte en aprobación. Las dos
diferencias provienen de la misma causa raíz, por lo que se consolidan en **una sola
incidencia**.

## ANTECEDENTES

RF-24 v2.0.
CU05 — Gestionar Dispositivos IoT, Flujo D.
Seguridad — OWASP API5 (Broken Function Level Authorization).

Objetivo: verificar que Productor y Contador no puedan registrar calibraciones aunque la
cuenta esté activa, el usuario autenticado y el request sea completamente válido.

## ENTORNO

**Ambiente:** TEST
**Backend:** https://api.inmero.co/back-sigab-test
**Rama:** qa/juan-esteban-rf24-v2
**Commit:** 30ddd72144102a60af006b265a20cb18c1c72c85
**RUN_ID:** run-20261007-080541
**Carpeta:** tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G77-v2.0/

La carpeta histórica `TC-M09-G77/`, incluida su `EvaluacionV2/`, se consultó solo como
referencia y no fue modificada: `git diff` y `git status` sobre esa ruta quedan vacíos. Esta
es la primera evaluación del grupo actualizado: no se creó ninguna `EvaluacionV2`, no se
compara con la prueba histórica y no se usan sus resultados como evidencia de esta corrida.

La automatización incorpora la protección programática que aborta si se ejecuta desde una
carpeta cuyo nombre no sea exactamente `TC-M09-G77-v2.0`, verificada en esta corrida.

### Preflight OpenAPI

```text
POST /usuarios/{id_usuario}/gestionar                     200, 400, 403, 404, 409, 422
POST /configuracion/sensores/{id_sensor}/calibrar          201, 400, 401, 403, 404, 422, 500
GET  /configuracion/sensores/{id_sensor}/calibraciones     200, 401, 403, 422
GET  /usuarios/admin                                       200, 400, 401, 403, 422
GET  /usuarios/{id_usuario}/detalle                        200, 403, 404, 429, 422
```

El endpoint de calibración **declara 403** en su contrato. `modo_calibracion` no está
declarado en el schema; se envió como `"SENSOR"` en ambos POST, según exige el caso. G77 no
prueba los valores válidos o inválidos de ese campo y esta corrida no concluye nada sobre él.

## ADMINISTRADOR DE SETUP

**Admin utilizado:** administador.dev@gmail.com
**Credencial:** [REDACTED]

Orden autorizado respetado: `admin.dev@gmail.com` se intentó una sola vez y no autenticó
(HTTP 400); se continuó con el secundario, que sí autenticó. No se probaron otras
contraseñas.

**Uso:** localizar las cuentas de los actores (`GET /usuarios/admin?correo=`) y los GET de
precondición del fixture que el Ingeniero no puede leer por alcance de finca. **No activó ni
restauró ninguna cuenta**, porque no hizo falta, y **no ejecutó ningún POST de calibración**.

Detalle del alcance que conviene registrar: para el Ingeniero el listado de dispositivos
responde HTTP 200 con una lista **vacía**, no 404, de modo que el escalado de lectura se
decide por colección vacía y no solo por el código de estado.

## FIXTURE

**Origen:** fixture oficial del caso, validado por GET (no se requirió alternativa)

**sensor:** 6 — `Sensor temperatura alevinera-01`, activo
**dispositivo:** 3 — `IOT-ALE01-HLA-003`, `es_activo = true`
**área:** 3 — asociación vigente (`tiene_estado = true`, `fecha_finalizacion = null`)
**categoría:** TEMPERATURA
**rango:** 0.0000 – 45.0000
**valor:** 22.5000 (estrictamente interior al rango)

El mismo body funcional se usó para los dos subescenarios, sin `ganancia`, sin `offset` y sin
el `RUN_ID` dentro de `observaciones`.

## PRODUCTOR

### Estado original

```text
id_usuario: 35
correo: m2m.nuevo@ejemplo.com
rol: Productor
estado_cuenta: Activo
```

### Preparación

**Activación temporal requerida:** NO

La cuenta ya estaba `Activo`, así que no se ejecutó ningún `POST /usuarios/35/gestionar`. No
se modificó su estado en ningún momento.

### Identidad antes del POST

```text
correo: m2m.nuevo@ejemplo.com
id_usuario: 35
rol: Productor
estado: Activo
```

Confirmado por `GET /usuarios/me` con el token del propio Productor, de modo que el rechazo
posterior no puede atribuirse al estado de la cuenta.

### Permisos observados

```text
acciones sobre el recurso 12 (calibraciones): [2]   (solo lectura)
permiso de creación inesperado: NO
total de permisos: 56
```

La configuración RBAC observada es coherente con el caso: el Productor no tiene permiso de
creación sobre calibraciones.

### Historial PRE

```text
GET /configuracion/sensores/6/calibraciones -> HTTP 200
total: 5 | ids: [14, 13, 12, 11, 10]
```

### Request

```json
{
  "modo_calibracion": "SENSOR",
  "id_dispositivo_iot": 3,
  "id_infraestructura": 3,
  "valor_referencia": 22.5000,
  "observaciones": "QA TC-M09-148-v2.0",
  "fecha_calibracion": "2026-10-07T08:05:44.186Z"
}
```

### Respuesta

**HTTP esperado:** 403
**HTTP obtenido:** 403
**error_code:** `ACCESO_DENEGADO`
**Devuelve `id_calibracion`:** NO

**Mensaje esperado:**
Acceso denegado: La calibración de sensores es una función crítica restringida exclusivamente al Ingeniero de Campo o al Administrador.

**Mensaje obtenido:**
Acceso denegado. Su rol no tiene permisos para realizar esta operación.

**Diferencia exacta:** el backend devuelve el mensaje genérico del RBAC común. Tras
`Acceso denegado` usa punto en lugar de dos puntos, y **omite por completo** la parte
específica del FA: que la calibración de sensores es una función crítica y que está
restringida al Ingeniero de Campo o al Administrador.

### Historial POST

```text
total: 5 | ids: [14, 13, 12, 11, 10]
```

Sin IDs nuevos, sin calibraciones atribuibles al `id_usuario 35` y con los cinco registros
históricos conservando valor, fecha, usuario y observaciones.

### Restauración

```text
Estado original: Activo
Estado final:    Activo
Restaurado:      NO APLICABA
```

### Resultado Productor

**RECHAZADO** — 403 correcto, sin persistencia e historial intacto, pero el mensaje no
coincide con el FA.

## CONTADOR

### Estado original

```text
id_usuario: 5
correo: contador@pecuaria.co
rol: Contador
estado_cuenta: Activo
```

### Preparación

**Activación temporal requerida:** NO

La cuenta ya estaba `Activo`; no se ejecutó ninguna acción de gestión sobre ella.

### Identidad antes del POST

```text
correo: contador@pecuaria.co
id_usuario: 5
rol: Contador
estado: Activo
```

### Permisos observados

```text
acciones sobre el recurso 12 (calibraciones): []   (ninguna)
permiso de creación inesperado: NO
total de permisos: 25
```

### Historial PRE

```text
total: 5 | ids: [14, 13, 12, 11, 10]
```

### Request

```json
{
  "modo_calibracion": "SENSOR",
  "id_dispositivo_iot": 3,
  "id_infraestructura": 3,
  "valor_referencia": 22.5000,
  "observaciones": "QA TC-M09-148-v2.0",
  "fecha_calibracion": "2026-10-07T08:05:45.012Z"
}
```

### Respuesta

**HTTP esperado:** 403
**HTTP obtenido:** 403
**error_code:** `ACCESO_DENEGADO`
**Devuelve `id_calibracion`:** NO

**Mensaje esperado:**
Acceso denegado: La calibración de sensores es una función crítica restringida exclusivamente al Ingeniero de Campo o al Administrador.

**Mensaje obtenido:**
Acceso denegado. Su rol no tiene permisos para realizar esta operación.

**Diferencia exacta:** idéntica a la del Productor. Es el mismo mensaje genérico, sin la parte
específica que exige el FA.

### Historial POST

```text
total: 5 | ids: [14, 13, 12, 11, 10]
```

Sin IDs nuevos, sin calibraciones atribuibles al `id_usuario 5` y con los históricos intactos.

### Restauración

```text
Estado original: Activo
Estado final:    Activo
Restaurado:      NO APLICABA
```

### Resultado Contador

**RECHAZADO** — 403 correcto, sin persistencia e historial intacto, pero el mensaje no
coincide con el FA.

## ORÁCULO

| Verificación | Productor | Contador |
|---|---|---|
| Cuenta activa al probar | PASS | PASS |
| Rol correcto | PASS | PASS |
| HTTP 403 | PASS | PASS |
| Mensaje exacto | **FAIL** | **FAIL** |
| Sin `id_calibracion` en la respuesta | PASS | PASS |
| Sin persistencia | PASS | PASS |
| Históricos intactos | PASS | PASS |
| Estado original restaurado | NO APLICABA | NO APLICABA |

Siete de las ocho verificaciones pasan en cada subescenario. La única que falla es la del
mensaje, y basta para rechazar el caso: el oráculo no se satisface con recibir cualquier 403.

## VERIFICACIÓN FINAL (SOLO LECTURA)

Comprobado en `verificacion-final-readonly.json`, sin SQL:

- **estado final Productor == estado original:** sí (`Activo`);
- **estado final Contador == estado original:** sí (`Activo`);
- **restauración pendiente:** NO — ninguna cuenta fue modificada durante la prueba;
- **historial del sensor 6:** total 5, ids `[14, 13, 12, 11, 10]`, sin registros atribuibles a
  los roles rechazados, verificado tanto por `id_usuario` como por coincidencia de
  observaciones y fecha enviada;
- **fixture sin cambios:** dispositivo 3 sigue activo, la asociación vigente del sensor 6 al
  área 3 no fue alterada y el rango TEMPERATURA sigue en 0.0000 – 45.0000.
- **concurrencia:** no apareció ningún ID nuevo entre PRE y POST de ninguno de los dos
  subescenarios, por lo que no hubo interferencia que correlacionar ni clasificar.

## RESULTADO NEWMAN

**POST calibración planificados:** 2
**POST calibración ejecutados:** 2
**POST setup ejecutados:** 0
**POST restauración ejecutados:** 0
**Assertions:** 50
**Failures:** 2
**STOP_ALL:** NO

Los 2 fallos son exactamente las dos comparaciones de mensaje:

```text
1. 12. Productor — message coincide exactamente con el FA del RF
2. 12. Contador  — message coincide exactamente con el FA del RF
```

Ninguna otra assertion falló: localización de cuentas, roles, estado activo antes del POST,
logins, identidad, permisos, fixture completo, historiales PRE y POST, el código 403, la
ausencia de `id_calibracion`, la ausencia de persistencia y la integridad de los históricos
pasaron todas.

## EVIDENCIAS

```text
git_pre.txt
openapi_preflight.json
precheck.json
admin_efectivo.json
fixture.json
usuarios_pre.json

productor_estado_pre.json      productor_identidad_activa.json   productor_permisos.json
productor_historial_pre.json   productor_request.json            productor_response.json
productor_historial_post.json

contador_estado_pre.json       contador_identidad_activa.json    contador_permisos.json
contador_historial_pre.json    contador_request.json             contador_response.json
contador_historial_post.json

automation/                    copia de la automatización que produjo este RUN
automation_manifest.json       SHA-256 de cada artefacto
verificacion-final-readonly.json
seguridad-evidencias.json
newman/newman-TC-M09-G77-v2.0.html
TC-M09-G77_resultado.md
```

No existen los archivos `*_setup.json` ni `*_restauracion.json` porque ninguna cuenta fue
modificada: ambas estaban ya activas.

`seguridad-evidencias.json` reporta la carpeta del RUN limpia: ningún archivo contiene
contraseñas, JWT, `Authorization` con token, cookies, tokens en pares clave-valor ni cadenas
de conexión. El reporte Newman se generó con `omitHeaders`, sin environment ni globals,
omitiendo las variables sensibles, y se sanitizó después.

## OBSERVACIONES

Solo hechos demostrados por esta corrida.

1. **La autorización funciona; el mensaje no.** Los dos roles no autorizados fueron
   rechazados con 403, con `error_code` coherente (`ACCESO_DENEGADO`), sin crear calibraciones
   y sin tocar el historial. El incumplimiento se limita al contenido de `message`.

2. **El mensaje obtenido es el genérico del RBAC común,** idéntico en ambos subescenarios. No
   menciona que la calibración sea una función crítica ni nombra los roles autorizados, que es
   justamente la información que el FA pide entregar al usuario. Que ambos roles devuelvan el
   mismo texto es coherente con un rechazo resuelto en la capa de autorización genérica y no
   en el caso de uso de calibración.

3. **La configuración RBAC observada es correcta.** El Productor tiene únicamente lectura
   sobre el recurso 12 y el Contador no tiene ninguna acción. No se observó el permiso de
   creación inesperado que habría constituido un defecto de seguridad adicional, de modo que
   esta corrida no revela una asignación de permisos indebida.

4. **No se alteró el ambiente.** Ambas cuentas estaban activas de antemano, así que el
   presupuesto de gestión de cuentas quedó sin usar: 0 activaciones y 0 restauraciones. No hay
   restauración pendiente y ninguna cuenta quedó en un estado distinto del original.

5. **El rechazo es atribuible al rol, no al estado de cuenta.** Antes de cada POST se verificó
   login 200 y `GET /usuarios/me` con `estado_cuenta = Activo` y el rol esperado, de modo que
   el 403 no puede explicarse por una cuenta inactiva.

6. **Sobre el nombre de este informe.** El paquete pedía `TC-M09-F77_resultado.md`. Se usa
   `TC-M09-G77_resultado.md`, con el identificador del grupo, por indicación expresa del
   responsable de QA de mantener los informes nombrados como el grupo al que pertenecen.

## INCIDENCIA

**INCIDENCIA REQUERIDA:** SÍ
**Grupo responsable:** Desarrollo
**Grupo de prueba:** TC-M09-G77-v2.0
**Caso:** TC-M09-148-v2.0
**Subescenarios afectados:** ambos (Productor + Contador)
**RF:** RF-24 v2.0

**Causa raíz:** el rechazo por privilegios del registro de calibración se resuelve con el
mensaje genérico del RBAC común y no implementa el texto específico que RF-24 v2.0 define para
este flujo alterno. No es un fallo de autorización ni de integridad: el 403, el `error_code` y
la ausencia de persistencia son correctos, y los permisos de ambos roles están bien
configurados.

Se asigna a **Desarrollo** porque la evidencia apunta a la lógica de aplicación: el endpoint
deniega correctamente pero no emite el mensaje del requisito. No se asigna a DBA, porque no
hay señal de permisos desalineados en TEST — los permisos observados son los esperados y la
denegación ocurre. No se asigna a AIoT, que no interviene en este flujo RBAC. No se usa
`Por determinar`, porque la evidencia es suficiente para decidir.

**Detalle a corregir:**

```text
Obtenido (ambos roles, error_code ACCESO_DENEGADO, HTTP 403):
  Acceso denegado. Su rol no tiene permisos para realizar esta operación.

Esperado por RF-24 v2.0:
  Acceso denegado: La calibración de sensores es una función crítica restringida
  exclusivamente al Ingeniero de Campo o al Administrador.
```

**Type:** bug
**Severity:** Normal
**Priority:** Normal

**Evidencias:**

```text
tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G77-v2.0/RESULTADOS/run-20261007-080541/
  productor_response.json          403 + mensaje genérico obtenido
  contador_response.json           403 + mensaje genérico obtenido
  productor_request.json           body funcionalmente válido enviado
  contador_request.json
  productor_identidad_activa.json  cuenta Activa y rol Productor antes del POST
  contador_identidad_activa.json   cuenta Activa y rol Contador antes del POST
  productor_permisos.json          sin permiso de creación
  contador_permisos.json
  productor_historial_pre.json / productor_historial_post.json   sin persistencia
  contador_historial_pre.json  / contador_historial_post.json
  verificacion-final-readonly.json
  TC-M09-G77-v2.0.json             oráculo consolidado
  newman/newman-TC-M09-G77-v2.0.html
```

Una sola incidencia consolidada: ambos subescenarios fallan por la misma causa raíz y el mismo
texto. No se crearon tickets separados ni se abrió nada en GitHub o Taiga en esta ejecución.

## CONCLUSIÓN

El caso **TC-M09-148-v2.0 queda RECHAZADO** y, con él, el grupo **TC-M09-G77-v2.0**. Ninguno
de los dos subescenarios se presenta como aprobado por el hecho de haber recibido un 403.

Lo que quedó demostrado empíricamente en TEST, con las dos cuentas activas y autenticadas y un
request funcionalmente válido sobre el fixture sensor 6 / dispositivo 3 / infraestructura 3
(TEMPERATURA, valor 22.5000 interior al rango):

- el **Productor** (`id_usuario 35`) no puede registrar calibraciones: HTTP 403, sin crear
  ningún registro;
- el **Contador** (`id_usuario 5`) tampoco: HTTP 403, sin crear ningún registro;
- en ambos casos el historial quedó idéntico, sin registros atribuibles al actor y con los
  históricos intactos;
- la configuración de permisos de ambos roles no incluye creación sobre calibraciones;
- el fixture y el estado de las cuentas no fueron alterados por la prueba.

Lo que **no** se cumple: el mensaje de los dos rechazos es el texto genérico del RBAC y no el
que RF-24 v2.0 exige para este flujo. Por el criterio del grupo, un 403 con mensaje incorrecto
es RECHAZADO, y la assertion del mensaje no se reinterpreta después de observar una respuesta
genérica.

Desde el punto de vista de OWASP API5 la función crítica **está protegida**: no existe
escalada de privilegios ni persistencia indebida. El defecto es de comunicación del error, no
de control de acceso. Para reevaluar el grupo basta que el flujo de calibración emita el
mensaje específico del requisito; según esta corrida, la lógica de autorización no requiere
cambios.
