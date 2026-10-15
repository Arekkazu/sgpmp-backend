# TC-M09-G136 — Resultado

## Decisión

**Caso:** TC-M09-274
**Resultado:** RECHAZADO

**Motivo:** el mecanismo best-effort **funciona**: con el `INSERT` sobre `modulo1.eventos`
denegado, los dos rechazos conservaron su código funcional (400 y 422), ninguno se convirtió en
500, ninguno creó calibraciones, el evento RF-10 realmente no se escribió y cada intento dejó su
propia constancia observable del fallo de auditoría. Lo que incumple es el **texto** de los dos
mensajes funcionales, que no corresponde al FA de RF-24 v2.0.

| Variante | HTTP esperado | HTTP obtenido | ¿500? | Mensaje FA | Calibración creada | Evento RF-10 | Alerta observable | Resultado |
|---|---:|---:|---|---|---|---|---|---|
| RANGE | 400 | 400 | NO | **FAIL** | NO | NO | SÍ | RECHAZADO |
| INACTIVE | 422 | 422 | NO | **FAIL** | NO | NO | SÍ | RECHAZADO |

## Laboratorio

- **Prueba local:** SÍ. Ninguna sentencia de esta prueba se ejecutó contra TEST, DEV, MAIN ni
  ninguna base compartida.
- **Tipo:** local aislado, con volumen exclusivo
- **Base:** `sgpmp_g136_lab`
- **PostgreSQL:** PostgreSQL 18.6 (Debian 18.6-1.pgdg13+2), en contenedor
- **Compose project:** `sgpmp-g136` · contenedores `sgpmp-g136-db` y `sgpmp-g136-backend`
- **Volumen:** `sgpmp_g136_pgdata` (exclusivo; no se reutilizó `sgpmp_pgdata` ni ningún volumen
  de DEV/TEST)
- **Puertos:** PostgreSQL `127.0.0.1:55436`, backend `127.0.0.1:18036`, ambos solo en localhost
- **Alembic:** `78f6f579b5ba (head)` — migraciones reales del proyecto, sin modificar
- **Rama:** qa/juan-esteban-rf24-v2
- **Commit:** 30ddd72144102a60af006b265a20cb18c1c72c85
- **RUN_ID:** run-20261007-140122

**Guard del laboratorio: PASS.** Se verificó por SQL `current_database()`, `current_user` y el
puerto, y que tanto el DSN administrativo como la URL de la API apuntan a `127.0.0.1`, sin
referencias a `inmero.co`, `sslip.io`, `back-sigab` ni `dokploy`. La base se creó desde cero, se
le aplicaron las migraciones reales y se sembró únicamente el fixture del caso: **no se copió
ningún dato de TEST**.

### Identidades de base de datos

| Identidad | Uso | Condición |
|---|---|---|
| `g136_owner` | migraciones, seed, REVOKE/GRANT, consultas administrativas | owner |
| `g136_app` | `DATABASE_URL` real del backend | LOGIN, **no** superusuario, **no** owner de `modulo1.eventos`, sin herencia de otros roles |

Owners reales de las tablas implicadas: `modulo1.eventos` → `postgres`,
`modulo9.calibraciones` → `postgres`, `modulo9.auditorias_calibraciones` → `g136_owner`.
Ninguna pertenece a `g136_app`, y se comprobó que `g136_app` no es miembro de ningún rol.

**Sobre `BYPASSRLS` en el app role.** Es necesario y no debilita la prueba: las políticas RLS de
`modulo1` leen `app.current_user_id`, que la aplicación fija en `get_current_user`, es decir
**después** de autenticar. Un rol sujeto a RLS no vería filas en `modulo1.usuarios` y no podría
ni iniciar sesión. `BYPASSRLS` afecta solo políticas de **fila**, no privilegios de **tabla**, de
modo que el `REVOKE INSERT` sobre `modulo1.eventos` siguió frenando a la aplicación — lo que
quedó demostrado empíricamente en este mismo RUN.

El rol `sgpmp_app` existe en el laboratorio únicamente como marcador `NOLOGIN`, porque una
migración del proyecto ejecuta `GRANT ... TO sgpmp_app` sin condicional. Nadie es miembro suyo,
así que no puede prestar privilegios por herencia.

## Fault injection

| Momento | `INSERT` sobre `modulo1.eventos` para `g136_app` |
|---|---|
| antes | **permitido** (`true`) |
| durante | **denegado** (`false`) |
| después | **restaurado** (`true`) |

El `REVOKE` tocó exclusivamente `modulo1.eventos`. Se comprobó que durante el fault se
conservaban `INSERT` sobre `modulo9.calibraciones` y sobre
`modulo9.auditorias_calibraciones`, y que el `SELECT` del fixture seguía funcionando: el único
fallo inducido fue la escritura del historial RF-10.

La efectividad del `REVOKE` se verificó **antes** de enviar los POST. Si el privilegio hubiera
sobrevivido por ownership, superusuario o herencia, el laboratorio habría sido inválido y los
POST no se habrían enviado.

El token del Ingeniero se obtuvo **antes** del `REVOKE`, junto con un control de solo lectura
(`GET /configuracion/sensores/1/calibraciones` → 200). Esto importa: el login escribe auditoría
RF-10 y habría contaminado el fault injection.

## Actor y fixture

**Ingeniero de Campo** — `ingeniero.g136@pecuaria.co` · `id_usuario = 3` · rol
`Ingeniero de Campo` · cuenta `Activo` · credencial [REDACTED]. Su hash se generó con el propio
value object del proyecto (`src/identity_access/domain/value_objects/contrasena.py`), sin
inventar hashes.

**Fixture A (variante RANGE):**

```text
dispositivo 1 | IOT-G136-LAB-ACT   | activo
sensor      1 | TEMPERATURA        | activo | área 1 | asociación vigente
rango         | 0.0000 – 45.0000
valor_fuera   | 45.0001            (max + 0.0001, determinista respecto al rango sembrado)
```

**Fixture B (variante INACTIVE):**

```text
dispositivo 2 | IOT-G136-LAB-INACT | INACTIVO
sensor      2 | TEMPERATURA        | activo | área 1 | asociación vigente
valor usado   | 22.5000            (válido, interior al rango)
```

En cada variante la **única** invalidez es la intencional: en RANGE el valor excede el máximo y
todo lo demás es válido; en INACTIVE el valor es válido y lo único inválido es el estado del
dispositivo.

## Variante RANGE — valor fuera de rango

### Request

```json
{
  "modo_calibracion": "SENSOR",
  "id_dispositivo_iot": 1,
  "id_infraestructura": 1,
  "valor_referencia": 45.0001,
  "observaciones": "QA TC-M09-274 RANGE",
  "fecha_calibracion": "<ISO del RUN>"
}
```

### Respuesta

**HTTP esperado:** 400 · **HTTP obtenido:** 400 · **¿Se convirtió en 500?** NO
**error_code:** `VALOR_FUERA_DE_RANGO`

**Mensaje esperado (FA):**
Valor fuera de límites: El ajuste de 45.0001 excede los rangos de seguridad para la variable TEMPERATURA. Verifique el estándar de calibración utilizado.

**Mensaje obtenido:**
El ajuste de 45.0001 excede los rangos de seguridad para la variable TEMPERATURA (permitido 0.0000–45.0000). Verifique el estándar de calibración utilizado.

**Diferencia exacta:** falta el prefijo `Valor fuera de límites: ` y se añade
` (permitido 0.0000–45.0000)` tras el nombre de la variable. El valor y la variable sí se
interpolan correctamente y la frase final coincide.

### Persistencia y auditoría

```text
calibraciones del sensor 1   PRE: []   POST: []     -> ninguna creada
evento RF-10 en la ventana   ninguno                -> la escritura de auditoría falló de verdad
```

### Alerta observable

```text
RF-24: no se pudo auditar el rechazo de calibración del sensor 1
  └─ psycopg2.errors.InsufficientPrivilege: permission denied for table eventos
     (142 líneas de la misma excepción, agrupadas como UN evento de alerta)
```

La constancia nombra el sensor 1, lo que la correlaciona de forma inequívoca con este POST.

### Decisión

**RECHAZADO** — cinco de las seis verificaciones pasan; falla la del mensaje.

## Variante INACTIVE — dispositivo inactivo

### Request

```json
{
  "modo_calibracion": "SENSOR",
  "id_dispositivo_iot": 2,
  "id_infraestructura": 1,
  "valor_referencia": 22.5,
  "observaciones": "QA TC-M09-274 INACTIVE",
  "fecha_calibracion": "<ISO del RUN>"
}
```

### Respuesta

**HTTP esperado:** 422 · **HTTP obtenido:** 422 · **¿Se convirtió en 500?** NO
**error_code:** `DISPOSITIVO_INACTIVO`

**Mensaje esperado (FA):**
Operación rechazada: El dispositivo IOT-G136-LAB-INACT está inactivo. Debe activar el dispositivo antes de proceder con el registro de nuevos parámetros de calibración.

**Mensaje obtenido:**
Solo se pueden calibrar sensores de dispositivos activos.

**Diferencia exacta:** es un texto completamente distinto. Falta el prefijo
`Operación rechazada: `, **no interpola el serial del dispositivo** y no indica que deba
activarse antes de registrar nuevos parámetros. De las dos variantes, esta es la que más se
aparta del FA: el serial es justamente el dato que permitiría al operario saber qué equipo
activar.

### Persistencia y auditoría

```text
calibraciones del sensor 2   PRE: []   POST: []     -> ninguna creada
evento RF-10 en la ventana   ninguno                -> la escritura de auditoría falló de verdad
```

### Alerta observable

```text
RF-24: no se pudo auditar el rechazo de calibración del sensor 2
  └─ psycopg2.errors.InsufficientPrivilege: permission denied for table eventos
     (142 líneas de la misma excepción, agrupadas como UN evento de alerta)
```

La constancia nombra el sensor 2, lo que la correlaciona con este POST y la distingue de la del
intento anterior.

### Decisión

**RECHAZADO** — cinco de las seis verificaciones pasan; falla la del mensaje.

## Dos fallos de auditoría independientes

El log del backend contiene exactamente **2 eventos de alerta**, no uno genérico de arranque:

```text
línea   3  RF-24: no se pudo auditar el rechazo de calibración del sensor 1   (POST RANGE)
línea 146  RF-24: no se pudo auditar el rechazo de calibración del sensor 2   (POST INACTIVE)
```

Cada uno arrastra su propio stacktrace con `permission denied for table eventos`, y el origen
queda identificado en
`src/configuration/application/use_cases/sensores/registrar_calibracion_use_case.py`, en
`auditar_rechazo_calibracion`. Las múltiples líneas de cada excepción se agrupan como **un**
evento de alerta, no se cuentan como varias.

La captura de logs quedó demostrada como operativa (el archivo `backend.log` tiene contenido y
registra ambos POST con sus códigos 400 y 422), de modo que la presencia de las constancias es
un hecho verificado y no una inferencia.

## Verificación de que el fault fue real

Mientras el `INSERT` estaba revocado se consultó `modulo1.eventos` en la ventana de cada intento
y **no existe** el evento de calibración rechazada correspondiente. Esto prueba que la escritura
de auditoría falló de verdad y que el best-effort no se limitó a no intentarla.

Conviene señalarlo con precisión: esa ausencia de evento RF-10 **no es un defecto**. Es parte
intencional del fault injection de este caso, igual que el `permission denied`.

## Incidencia

**INCIDENCIA REQUERIDA:** SÍ
**Grupo responsable:** Desarrollo
**Grupo de prueba:** TC-M09-G136
**Caso:** TC-M09-274
**Variantes afectadas:** ambas (RANGE e INACTIVE)
**Resultado:** RECHAZADO

**Motivo:**
Los mensajes funcionales de los dos rechazos no corresponden al FA de RF-24 v2.0. El
comportamiento best-effort en sí es correcto.

**Esperado:**

```text
RANGE:    Valor fuera de límites: El ajuste de [VALOR] excede los rangos de seguridad para la
          variable [TIPO_VARIABLE]. Verifique el estándar de calibración utilizado.
INACTIVE: Operación rechazada: El dispositivo [SERIAL] está inactivo. Debe activar el
          dispositivo antes de proceder con el registro de nuevos parámetros de calibración.
```

**Obtenido:**

```text
RANGE:    El ajuste de 45.0001 excede los rangos de seguridad para la variable TEMPERATURA
          (permitido 0.0000–45.0000). Verifique el estándar de calibración utilizado.
INACTIVE: Solo se pueden calibrar sensores de dispositivos activos.
```

**Causa raíz:**
Los mensajes implementados en la validación de calibración no son los definidos por el flujo
alterno de RF-24 v2.0. En RANGE falta el prefijo y sobra el fragmento de rango permitido; en
INACTIVE el texto es otro y omite el serial del dispositivo. No es un fallo del mecanismo
best-effort ni de la validación: los códigos HTTP, los `error_code`, la ausencia de persistencia
y las constancias de auditoría son correctos.

Se asigna a **Desarrollo** porque la evidencia señala la capa de aplicación: el flujo detecta y
rechaza correctamente, y solo el texto diverge del requisito. No corresponde a **DBA**: no hay
defecto de esquema ni de migración, y el `REVOKE` intencional no es una incidencia DBA. No
corresponde a **AIoT**. No se usa **Por determinar**, porque la causa es atribuible con la
evidencia obtenida.

**Type:** bug
**Severity:** Normal
**Priority:** Normal

Se proponen Normal y Normal, y no la combinación `bug`/`High` que el paquete reserva para un
defecto real del best-effort, precisamente porque el best-effort **no** falló: no hubo 500, no
se creó ninguna calibración y las alertas quedaron registradas. El incumplimiento se limita al
texto que recibe el cliente.

**Evidencia:** `evidencia.json` / `backend.log` / `pytest.xml`

## Observaciones

1. **El best-effort cumple su propósito.** Es el hallazgo principal de este caso y conviene no
   perderlo entre el rechazo: con la auditoría RF-10 denegada, el error funcional del cliente se
   conservó intacto en ambas variantes y la excepción de auditoría quedó absorbida, registrada en
   el log y no propagada.

2. **La excepción SQL no se filtró al cliente.** Las respuestas fueron los mensajes funcionales
   del backend; la `InsufficientPrivilege` quedó únicamente en el log del servidor.

3. **Ejecución previa marcada como inválida por error QA.** El RUN `run-20261007-140032` se
   conserva con su marcador `EJECUCION_INVALIDA.md`: la consulta de verificación del test usaba
   la columna `id_tipo_evento`, que no existe (es `tipo_evento`), y falló después del POST de
   RANGE. Es un defecto de la automatización, no del producto. Su bloque `finally` restauró el
   privilegio, lo que quedó verificado. El resultado de este informe proviene exclusivamente del
   RUN `run-20261007-140122`.

4. **Refinamiento del detector de alertas, posterior a este RUN.** La primera versión atribuía
   las constancias por orden de aparición en el log, lo que era impreciso. Se corrigió para
   agrupar cada excepción como un único evento y correlacionarla con su POST por el sensor que la
   propia constancia nombra. El agrupamiento presentado arriba se derivó del **mismo**
   `backend.log` ya capturado, sin reejecutar ningún POST. El cambio no altera el resultado: con
   cualquiera de los dos criterios, ambas variantes tienen su alerta.

5. **Presupuesto de escrituras respetado:** exactamente 2 POST funcionales en este RUN, uno por
   variante, sin reintentos.

## Conclusión

**TC-M09-274 queda RECHAZADO**, y con él el grupo **TC-M09-G136**, sobre evidencia empírica de un
laboratorio local aislado con PostgreSQL 18.6 real y el backend real del proyecto, sin mocks de
persistencia.

La cadena del caso quedó demostrada casi por completo: el app role tenía `INSERT` sobre RF-10; se
obtuvo el token del Ingeniero antes de tocar permisos; se revocó únicamente el `INSERT` sobre
`modulo1.eventos` y se verificó que la denegación era real; el rechazo por valor fuera de rango
conservó su **HTTP 400** y el rechazo por dispositivo inactivo su **HTTP 422**, ninguno se
convirtió en 500; no se creó ninguna calibración; el evento RF-10 efectivamente no se escribió; y
cada intento dejó su propia constancia observable, correlacionable por sensor. Al cerrar, el
privilegio se restauró y se confirmó.

El único eslabón que no se cumple son los **mensajes funcionales**, que no corresponden al FA de
RF-24 v2.0 en ninguna de las dos variantes. Por el criterio del caso, conservar el HTTP correcto
con un mensaje que incumple el FA es variante rechazada, y el esperado no se reinterpretó después
de observar la respuesta.

Para reevaluar el grupo basta alinear esos dos mensajes con el requisito: según esta corrida, el
mecanismo best-effort, la no persistencia y la generación de alertas no requieren cambios.
