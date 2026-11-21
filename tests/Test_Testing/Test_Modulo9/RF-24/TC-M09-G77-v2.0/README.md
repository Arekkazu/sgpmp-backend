# TC-M09-G77-v2.0 — RF-24 v2.0

Seguridad **OWASP API5** sobre el registro de calibraciones: los roles no autorizados no deben
poder calibrar sensores.

- **Requisito:** RF-24 v2.0
- **Caso de uso:** CU05 — Gestionar Dispositivos IoT, Flujo D
- **Caso:** TC-M09-148-v2.0 — subescenarios **Productor** y **Contador**
- **Tipo:** Seguridad — capa API
- **Ambiente decisorio:** TEST
- **Informe de cada corrida:** `RESULTADOS/<RUN_ID>/TC-M09-G77_resultado.md`

La única condición negativa intencional de cada subescenario es el **rol**. Todo lo demás debe
ser válido: cuenta activa, usuario autenticado, dispositivo activo, sensor del dispositivo,
área de la asociación vigente, valor dentro del rango y body funcionalmente correcto.

Esperado en ambos: **HTTP 403** con el mensaje exacto del FA, sin crear calibraciones y sin
alterar el historial.

## Aislamiento de carpetas

Esta carpeta es la **única** autorizada para la prueba v2.0. La carpeta histórica
`../TC-M09-G77/`, **incluida su `EvaluacionV2/`**, es de solo lectura: no se modifica, no
recibe resultados y no se usa como directorio de trabajo.

`helpers.cjs` incluye la protección programática, de modo que todo aborta si se ejecuta desde
una carpeta cuyo nombre no sea exactamente `TC-M09-G77-v2.0`:

```javascript
if (path.basename(__dirname) !== 'TC-M09-G77-v2.0') {
  throw new Error('Directorio no autorizado para TC-M09-G77-v2.0');
}
```

## Credenciales

Solo por variables de proceso. Nunca en archivos, colección, reportes, informe ni Git.

```powershell
$env:QA_BASE_URL="https://api.inmero.co/back-sigab-test"

$env:TEST_PRODUCTOR_EMAIL="m2m.nuevo@ejemplo.com"
$env:TEST_PRODUCTOR_PASSWORD="<secreto>"
$env:TEST_CONTADOR_EMAIL="contador@pecuaria.co"
$env:TEST_CONTADOR_PASSWORD="<secreto>"

# Actor de discovery y de lectura del historial.
$env:TEST_ENGINEER_EMAIL="ingeniero@pecuaria.co"
$env:TEST_ENGINEER_PASSWORD="<secreto>"

# Administrador: localizar cuentas, GET de fixture y, si hiciera falta, estado de cuenta.
$env:TEST_ADMIN_PRIMARY="admin.dev@gmail.com"
$env:TEST_ADMIN_SECONDARY="administador.dev@gmail.com"
$env:TEST_ADMIN_PASSWORD="<secreto>"
```

Cada POST de calibración lo ejecuta **su propio actor negativo**, nunca el Administrador. El
Administrador se intenta en el orden autorizado, una sola vez por cuenta, sin probar otras
contraseñas, y el runner registra cuál quedó en uso.

### Detalle del alcance del Ingeniero

Para ese actor el listado de dispositivos responde **HTTP 200 con una lista vacía**, no 404.
Por eso el lector auxiliar de `helpers.cjs` acepta `exigirNoVacio`: sin él, un escalado de
lectura guiado solo por el código de estado no se activaría y el discovery concluiría por error
que no existe ningún dispositivo.

## Ejecución

```powershell
$env:G77_RUN_ID="run-YYYYMMDD-HHMMSS"
node .\precheck.cjs          # solo lectura: contrato, fixture, cuentas y estados
node .\run-newman.cjs        # RUN oficial: 2 POST negativos
node .\verificar-cierre.cjs  # solo lectura: estados restaurados y sin persistencia
```

Opcionales (fixture preferido, con estos valores por defecto):

```powershell
$env:G77_DEVICE_ID="3"
$env:G77_SENSOR_ID="6"
$env:G77_AREA_ID="3"
$env:G77_CATEGORY="TEMPERATURA"
$env:G77_VALOR="22.5000"
```

## Estado de cuenta: activación temporal y restauración

Cada actor negativo debe estar **Activo** antes de su POST, porque un 403 con la cuenta
inactiva no sería evidencia RBAC válida: el rechazo podría deberse al estado y no al rol.

- **Ya Activo** → no se ejecuta ninguna acción de gestión.
- **Inactivo o Bloqueado** → se permite una activación temporal y se restaura después con
  `inactivar` o `bloquear`, porque existe una acción oficial que devuelve exactamente al estado
  original.
- **Pendiente, Pendiente de datos o Eliminado** → **no se activa**: el producto no ofrece una
  operación que permita volver con exactitud a ese estado, así que el subescenario queda
  BLOQUEADO. El principio es no dejar una cuenta en un estado que luego no pueda restaurarse
  por API oficial.

La preparación es *just-in-time*, un actor a la vez, para minimizar el tiempo que una cuenta
originalmente inactiva permanece activa. La restauración se intenta siempre que sea posible,
incluso si el subescenario falla o se activó STOP_ALL. Si no se logra, el runner lo marca como
**RESTAURACIÓN PENDIENTE** en lugar de ocultarlo, y no prueba estados alternativos ni SQL.

## Reglas que la automatización hace cumplir

- **Presupuesto: 2 POST de calibración**, uno por rol, sin reintentos. Por actor, y solo si su
  estado original no era Activo, como máximo 1 activación y 1 restauración, contabilizadas
  aparte de los POST de calibración.
- **El RUN no se sobrescribe:** el runner aborta si la carpeta del `RUN_ID` ya existe.
- **Mensaje comparado de forma exacta.** El FA de RF-24 v2.0 exige un texto concreto; un
  mensaje genérico como `Acceso denegado. Su rol no tiene permisos...` no es PASS, y la
  assertion no se ajusta después de ver la respuesta.
- **Un 403 por sí solo no aprueba:** el oráculo exige además cuenta activa, rol correcto,
  mensaje exacto, ausencia de `id_calibracion`, cero persistencia, históricos intactos y estado
  de cuenta restaurado.
- **Permiso RBAC inesperado → observación, no bloqueo.** Si un rol apareciera con permiso de
  creación, eso podría ser el propio defecto de seguridad bajo examen: se registra y el POST se
  ejecuta igual para observar el comportamiento real.
- **STOP_ALL:** si un rol no autorizado llegara a crear una calibración, el RUN se detiene y no
  se envían más POST. La calibración inesperada **se conserva como evidencia**, nunca se borra.
- **Concurrencia:** un ID nuevo se correlaciona por `id_usuario`, fecha y observaciones; si no
  puede atribuirse con certeza, se documenta como posible interferencia y no se imputa al
  producto.
- `observaciones` es exactamente `QA TC-M09-148-v2.0`, sin el `RUN_ID`.
- Todos los bodies envían `"modo_calibracion": "SENSOR"` aunque el schema no lo declare. G77 no
  prueba los valores de ese campo.
- Secretos sanitizados del HTML y de todo JSON de evidencia.

## Trazabilidad de la automatización

Antes del primer POST, el runner copia la automatización dentro del RUN y registra su SHA-256
en `automation_manifest.json`, de modo que el resultado siga siendo reproducible aunque los
archivos reutilizables cambien después.

## Artefactos por corrida

```text
RESULTADOS/<RUN_ID>/
├── git_pre.txt
├── openapi_preflight.json
├── precheck.json
├── admin_efectivo.json
├── fixture.json
├── usuarios_pre.json                 estado original de cada actor
├── <rol>_estado_pre.json
├── <rol>_setup.json                  solo si hubo activación temporal
├── <rol>_identidad_activa.json
├── <rol>_permisos.json
├── <rol>_historial_pre.json          <rol>_request.json
├── <rol>_response.json               <rol>_historial_post.json
├── <rol>_restauracion.json           solo si hubo cambio de estado
├── automation/                       copia de la automatización usada
├── automation_manifest.json          SHA-256 de cada artefacto
├── verificacion-final-readonly.json
├── seguridad-evidencias.json
├── newman/newman-TC-M09-G77-v2.0.html
└── TC-M09-G77_resultado.md
```
