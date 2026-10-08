# TC-M09-G75-v2.0 — RF-24 v2.0

Valores límite y validación de formato de `valor_referencia` en una calibración
`modo_calibracion = SENSOR`, ejecutada por el **Ingeniero de Campo**.

- **Requisito:** RF-24 v2.0
- **Caso de uso:** CU05 — Gestionar Dispositivos IoT, Flujo D
- **Tipo:** Valores límite / Validación — capa API
- **Ambiente decisorio:** TEST
- **Informe de cada corrida:** `RESULTADOS/<RUN_ID>/TC-M09-G75_resultado.md`

| Caso | Qué comprueba |
|---|---|
| TC-M09-142-v2.0 | el mínimo técnico vigente se acepta |
| TC-M09-143-v2.0 | el máximo técnico vigente se acepta |
| TC-M09-144-v2.0 | `min - 0.0001` y `max + 0.0001` se rechazan con 400 |
| TC-M09-145-v2.0 | `""`, `null` y `"abc"` se rechazan con 400 |

En todos los casos: los intentos inválidos no crean calibraciones y las calibraciones
válidas anteriores permanecen intactas.

## Aislamiento de carpetas

Esta carpeta es la **única** autorizada para la prueba v2.0. La carpeta histórica
`../TC-M09-G75/` es de **solo lectura**: no se modifica, no recibe resultados y no se usa
como directorio de trabajo.

`helpers.cjs` incluye la protección programática, de modo que el runner aborta si se
ejecuta desde cualquier carpeta que no se llame exactamente `TC-M09-G75-v2.0`:

```javascript
if (path.basename(__dirname) !== 'TC-M09-G75-v2.0') {
  throw new Error('Directorio no autorizado para TC-M09-G75-v2.0');
}
```

## Credenciales

Solo por variables de proceso. Nunca en archivos, colección, reportes, informe ni Git.

```powershell
$env:QA_BASE_URL="https://api.inmero.co/back-sigab-test"
$env:QA_EMAIL="ingeniero@pecuaria.co"
$env:QA_PASSWORD="<secreto>"

# Administrador auxiliar: SOLO GET de precondición, nunca un POST.
$env:QA_ADMIN_PRIMARY="admin.dev@gmail.com"
$env:QA_ADMIN_SECONDARY="administador.dev@gmail.com"
$env:QA_ADMIN_PASSWORD="<secreto>"
```

El Ingeniero ejecuta **todos** los POST. El Administrador aparece únicamente en los GET de
precondición que el Ingeniero no puede leer por alcance (detalle de dispositivo RF-21 e
historial de asociaciones RF-22, que para ese actor responden 404 porque su listado de
dispositivos está vacío). El runner intenta el administrador primario una vez y, si no
autentica, el secundario una vez; no prueba otras contraseñas y registra qué GET lo
requirieron.

## Ejecución

```powershell
$env:G75_RUN_ID="run-YYYYMMDD-HHMMSS"
node .\run-newman.cjs
node .\verificar-cierre.cjs
```

Opcionales (fixture preferido, con estos valores por defecto):

```powershell
$env:G75_DEVICE_ID="3"
$env:G75_SENSOR_ID="6"
$env:G75_AREA_ID="3"
$env:G75_CATEGORY="TEMPERATURA"
```

## Reglas que la automatización hace cumplir

- **Presupuesto exacto de 7 POST**, uno por variante funcional. No hay reintentos: una
  variante no se repite ni para "confirmar" ni porque una assertion falló.
- **Rango leído dinámicamente** de `GET /configuracion/sensores/rangos-calibracion` antes
  de cualquier POST; no se asume `0 / 45`. La colección vuelve a comprobar que el rango no
  cambió entre el discovery y los POST.
- **Aritmética decimal exacta** sobre `numeric(10,4)` con `BigInt`, nunca coma flotante
  binaria: `low = min - 0.0001`, `high = max + 0.0001`. Los literales viajan en el JSON con
  sus cuatro decimales.
- **Mensajes comparados de forma exacta.** El esperado del RF no se recorta ni se adapta al
  backend, y un mensaje "parecido" no es PASS. Si el HTTP es correcto pero el mensaje no
  coincide, la variante falla y el informe muestra esperado, obtenido y la diferencia.
- **STOP_ALL:** si tras un intento inválido aparece una calibración nueva, la colección
  detiene el RUN (`postman.setNextRequest(null)`) y los POST restantes no se envían.
- **Concurrencia:** un ID nuevo que no sea atribuible al intento por coincidencia de fecha
  se registra como posible interferencia de otro tester, sin atribuirlo al producto y sin
  borrarlo.
- **Inmutabilidad:** cada variante posterior revalida, campo por campo, que las
  calibraciones válidas ya creadas siguen presentes y sin cambios.
- **El RUN no se sobrescribe:** el runner aborta si la carpeta del `RUN_ID` ya existe.
- `observaciones` es exactamente `QA TC-M09-14X-v2.0`, sin el `RUN_ID` concatenado.
- Éxito es cualquier `2xx`; no se exige `201`.
- Secretos sanitizados del HTML y de todo JSON de evidencia.

## Trazabilidad de la automatización

Antes del primer POST, el runner copia la automatización dentro del RUN y registra su
SHA-256 en `automation_manifest.json`. Así queda demostrado qué automatización produjo el
resultado aunque los archivos reutilizables cambien después.

## Alcance de `modo_calibracion`

Todos los bodies envían `"modo_calibracion": "SENSOR"` como exige el caso, incluso si
OpenAPI no declara el campo. G75-v2.0 evalúa **límites y formato de `valor_referencia`**:
no es el grupo que determina si el discriminador de modalidad está implementado, y no se
ejecutan variantes con otros valores de modalidad aquí.

## Artefactos por corrida

```text
RESULTADOS/<RUN_ID>/
├── git_pre.txt
├── openapi_preflight.json
├── identidad_actor.json
├── permisos_actor.json
├── fixture_descubierto.json
├── rango_temperatura.json
├── automation/                     copia de la automatización usada
├── automation_manifest.json        SHA-256 de cada artefacto
├── 142_|143_|144_low_|144_high_|145_empty_|145_null_|145_abc_
│     historial_pre.json, request.json, response.json, historial_post.json
├── 142_calibracion_creada.json, 143_calibracion_creada.json
├── TC-M09-G75-v2.0.json            artefacto con el oráculo por variante y por caso
├── verificacion-final-readonly.json
├── seguridad-evidencias.json
├── newman/newman-TC-M09-G75-v2.0.html
└── TC-M09-G75_resultado.md
```
