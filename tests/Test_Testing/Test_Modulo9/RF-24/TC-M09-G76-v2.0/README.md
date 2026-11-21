# TC-M09-G76-v2.0 — RF-24 v2.0

Validación e integridad del registro de calibración, ejecutada por el **Ingeniero de Campo**.

- **Requisito:** RF-24 v2.0
- **Caso de uso:** CU05 — Gestionar Dispositivos IoT, Flujo D
- **Tipo:** Validación / Integridad — capa API
- **Ambiente decisorio:** TEST
- **Informe de cada corrida:** `RESULTADOS/<RUN_ID>/TC-M09-G76_resultado.md`

| Caso | Qué comprueba | Esperado |
|---|---|---|
| TC-M09-146-v2.0 | calibrar un sensor cuyo dispositivo IoT está inactivo | HTTP 422 + mensaje del FA con el serial real |
| TC-M09-147-v2.0 | informar un área existente distinta de la asociación vigente | HTTP 400 + mensaje del FA con sensor y área reales |

En ambos casos: el rechazo no puede crear calibraciones ni alterar el historial previo.

## Aislamiento de carpetas

Esta carpeta es la **única** autorizada para la prueba v2.0. La carpeta histórica
`../TC-M09-G76/` es de **solo lectura**: no se modifica, no recibe resultados y no se usa como
directorio de trabajo.

`helpers.cjs` incluye la protección programática, de modo que todo aborta si se ejecuta desde
una carpeta cuyo nombre no sea exactamente `TC-M09-G76-v2.0`:

```javascript
if (path.basename(__dirname) !== 'TC-M09-G76-v2.0') {
  throw new Error('Directorio no autorizado para TC-M09-G76-v2.0');
}
```

## Credenciales

Solo por variables de proceso. Nunca en archivos, colección, reportes, informe ni Git.

```powershell
$env:QA_BASE_URL="https://api.inmero.co/back-sigab-test"
$env:QA_EMAIL="ingeniero@pecuaria.co"
$env:QA_PASSWORD="<secreto>"

# Administrador auxiliar: SOLO GET de discovery, nunca un POST de calibración.
$env:QA_ADMIN_PRIMARY="admin.dev@gmail.com"
$env:QA_ADMIN_SECONDARY="administador.dev@gmail.com"
$env:QA_ADMIN_PASSWORD="<secreto>"
```

El Ingeniero ejecuta **los dos POST de calibración**. El Administrador solo aparece en los GET
de precondición que el Ingeniero no puede leer por alcance, y el runner registra exactamente
cuáles lo requirieron.

### Detalle importante del alcance del Ingeniero

Para este actor el alcance no siempre se manifiesta como 404: el listado de dispositivos
responde **HTTP 200 con una lista vacía**. Por eso el lector auxiliar de `helpers.cjs` acepta un
segundo argumento `exigirNoVacio`: sin él, un fallback guiado solo por el código de estado no se
activaría y el discovery concluiría por error que no existe ningún dispositivo.

## Ejecución

```powershell
$env:G76_RUN_ID="run-YYYYMMDD-HHMMSS"
node .\run-newman.cjs
node .\verificar-cierre.cjs
```

Opcionales (fixtures preferidos, con estos valores por defecto):

```powershell
$env:G76_146_DEVICE_ID="47"     # dispositivo inactivo preferido por la matriz
$env:G76_147_SENSOR_ID="6"
$env:G76_147_DEVICE_ID="3"
$env:G76_147_AREA_VIGENTE="3"
$env:G76_147_AREA_ALT="1"
$env:G76_147_VALOR="22.5000"
```

## Preparación de la precondición de TC-146

El caso necesita un dispositivo **inactivo**. El runner busca primero uno que **ya** lo esté,
priorizando el de la matriz, y solo si no existe ninguno utilizable plantea la preparación
autorizada por `PATCH /desactivar`.

Ese PATCH es **irreversible**: el contrato no expone reactivación de dispositivos. Por eso el
runner no lo ejecuta por iniciativa propia. Se detiene, deja los candidatos seguros en
`setup_146_candidatos.json` y exige una autorización explícita:

```powershell
$env:G76_AUTORIZAR_PATCH_DESACTIVAR="SI"
```

Un candidato solo se considera seguro si: está activo, su serial es claramente de prueba/QA,
**ningún otro dispositivo lo declara como su Gateway**, no tiene configuraciones
PENDIENTE/NO_CONF, tiene un sensor utilizable con asociación vigente y su categoría tiene rango
publicado. Si se usa, el dispositivo **queda inactivo a propósito** y sirve como fixture
reutilizable para futuras ejecuciones: no se intenta restaurarlo por SQL ni inventando
endpoints, y el informe declara que el actor de preparación y el actor funcional son distintos.

## Reglas que la automatización hace cumplir

- **Presupuesto: 2 POST de calibración y como máximo 1 PATCH de preparación.** Sin reintentos:
  si un POST falla, no se repite; la reconciliación es el GET del historial.
- **El RUN no se sobrescribe:** el runner aborta si la carpeta del `RUN_ID` ya existe, y exige el
  formato `run-YYYYMMDD-HHMMSS`.
- **Mensajes comparados de forma exacta.** El esperado del FA se construye con el serial y los
  IDs reales descubiertos, y no se recorta ni se adapta al backend. Un mensaje "parecido" no es
  PASS: si el HTTP es correcto pero el mensaje no coincide, el caso se rechaza y el informe
  muestra esperado, obtenido y la diferencia exacta.
- **Valor interior, nunca frontera:** el valor de TC-146 es el punto medio exacto del rango,
  calculado con aritmética decimal sobre `numeric(10,4)`, de modo que la única invalidez
  intencional del request sea el dispositivo inactivo.
- **El área alternativa de TC-147 debe ser real:** se comprueba con `GET
  /configuracion/infraestructuras/{id}` que existe, que es distinta de la vigente y que no está
  asociada al sensor. No se usan IDs inexistentes ni se crean o reasignan asociaciones.
- **STOP_ALL:** si tras el rechazo de TC-146 aparece una calibración nueva, el RUN se detiene
  (`postman.setNextRequest(null)`) y TC-147 no se ejecuta.
- **Concurrencia:** un ID nuevo que no sea atribuible al intento por coincidencia de fecha se
  registra como posible interferencia de otro tester, sin atribuirlo al producto y sin borrarlo.
- `observaciones` es exactamente `QA TC-M09-146-v2.0` y `QA TC-M09-147-v2.0`, sin el `RUN_ID`.
- Todos los bodies envían `"modo_calibracion": "SENSOR"` aunque OpenAPI no lo declare. G76 no
  prueba el enum ni la obligatoriedad de ese campo.
- Secretos sanitizados del HTML y de todo JSON de evidencia.

## Trazabilidad de la automatización

Antes de cualquier escritura, el runner copia la automatización dentro del RUN y registra su
SHA-256 en `automation_manifest.json`, de modo que el resultado siga siendo reproducible aunque
los archivos reutilizables cambien después.

## Artefactos por corrida

```text
RESULTADOS/<RUN_ID>/
├── git_pre.txt
├── openapi_preflight.json
├── identidad_actor.json
├── permisos_actor.json
├── administrador_discovery.json
├── fixture_146.json           rango_146.json
├── fixture_147.json           rango_147.json
├── setup_146_*.json           solo si hubo preparación por PATCH
├── 146_historial_pre.json     146_request.json  146_response.json  146_historial_post.json
├── 147_historial_pre.json     147_request.json  147_response.json  147_historial_post.json
├── automation/                copia de la automatización usada
├── automation_manifest.json   SHA-256 de cada artefacto
├── verificacion-final-readonly.json
├── seguridad-evidencias.json
├── newman/newman-TC-M09-G76-v2.0.html
└── TC-M09-G76_resultado.md
```
