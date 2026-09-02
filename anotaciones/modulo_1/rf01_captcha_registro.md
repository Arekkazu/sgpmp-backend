# RF-01 — CAPTCHA en el registro de usuarios

Issue #1600 · rama `feature/rf01-captcha-registro`

## Alcance verificado

RF-01 exige Google reCAPTCHA v2 o v3 como barrera de seguridad y define el
flujo alterno CAPTCHA fallido con HTTP 400. La medida aplica únicamente a
`POST /usuarios/`; no se extiende a login, recuperación ni activación porque el
RF no la exige en esos endpoints.

Se eligió Google reCAPTCHA v2. El frontend obtiene la respuesta del widget y la
envía como `captcha_token`. El backend conserva únicamente la clave secreta y
verifica el token mediante `POST https://www.google.com/recaptcha/api/siteverify`.

## Arquitectura

- `CaptchaVerifierPort` declara la verificación en la capa de dominio.
- `GoogleRecaptchaAdapter` implementa el puerto con `httpx`, timeout de cinco
  segundos y `RECAPTCHA_SECRET_KEY`.
- El router compone el adaptador mediante `get_captcha_verifier`, dependencia
  sustituible por un stub en pruebas.
- `CrearUsuarioUseCase` valida el CAPTCHA antes de construir la entidad o tocar
  repositorios. Si falla, no existen efectos parciales en usuario, cuenta,
  token, correo ni auditoría.

## Contrato HTTP

Campo nuevo obligatorio:

```json
{
  "captcha_token": "respuesta-generada-por-recaptcha-v2"
}
```

Resultados específicos:

| HTTP | Código | Condición |
|---|---|---|
| 400 | `VAL_ENTRADA` | Campo ausente o vacío |
| 400 | `CAPTCHA_INVALIDO` | Token inválido, expirado, duplicado o rechazado |
| 503 | `CAPTCHA_SERVICIO_NO_DISPONIBLE` | Secreto **ausente**, red, timeout o respuesta no confiable (ver la nota sobre secreto inválido más abajo) |

El adaptador falla cerrado: una indisponibilidad de Google nunca permite crear
la cuenta. El secreto no se recibe del frontend, no se persiste y no se incluye
en logs ni respuestas.

## Configuración y despliegue

Definir en el entorno del backend:

```env
RECAPTCHA_SECRET_KEY=<clave-secreta-recaptcha-v2>
```

La site key es pública y pertenece a la configuración del frontend. El valor
secreto se documenta vacío en `.env.example` y `docker-compose.yml` lo propaga
al contenedor del backend. No hay cambios de base de datos ni migración Alembic.

## Pruebas

- `tests/identity_access/test_rf01_captcha.py`: orden de validación, contrato
  del adaptador, rechazos, configuración inválida y fallo de red.
- `tests/integration/test_rf01_captcha_integration.py`: 400 sin persistencia,
  201 con token válido y 503 sin persistencia.
- Los fixtures de integración usan un stub válido para que las pruebas no
  dependan de Internet ni de secretos reales.

---

## Verificación con las llaves reales (2026-09-01)

Llaves del proyecto GCP/Firebase `notification-test-52854`. Se confirmó que son
un par **reCAPTCHA v2 clásico** gestionado desde la consola de Cloud, no
Enterprise: la consola muestra una clave secreta explícita, y la consola sugiere
—sin obligar— migrar de `siteverify` a `CreateAssessment`. Prueba adicional: el
site key renderiza el widget en el endpoint **clásico** `api2/anchor` (39.565
bytes, igual que la llave de prueba oficial de Google), mientras que un site key
inventado devuelve 1.495 bytes sin widget. Una llave Enterprise pura no tiene
secreto y no funciona con `siteverify`.

**Decisión: no se migra a `CreateAssessment`.** Costaría reescribir el adaptador
contra `recaptchaenterprise.googleapis.com/v1/projects/.../assessments` con una
API key de GCP restringida, más `enterprise: true` en el frontend, y exige
facturación habilitada en el proyecto. `siteverify` cumple RF-01 sin código
nuevo y las llaves con secreto legado siguen soportadas.

### Casos ejercitados contra la API real de Google

Backend en el host (`uvicorn`), sin stubs, llamando a `siteverify` de verdad.
El camino feliz se probó con las **llaves de prueba oficiales de Google**
(`6LeIxAcT...`), que siempre responden `success: true`; así se verifica el 201
completo sin tener que resolver el widget.

| Caso | Resultado | Verificado |
|---|---|---|
| Token basura, secreto real | 400 `CAPTCHA_INVALIDO` | ✅ |
| Sin el campo `captcha_token` | 400 `VAL_ENTRADA` — `Field required` | ✅ |
| `captcha_token` vacío | 400 `VAL_ENTRADA` — `String should have at least 1 character` | ✅ |
| Token válido (llaves de prueba de Google) | 201 + registro completo | ✅ |
| `RECAPTCHA_SECRET_KEY` ausente | 503 `CAPTCHA_SERVICIO_NO_DISPONIBLE` | ✅ |
| Secreto inválido | 400 `CAPTCHA_INVALIDO` (**no** 503 — ver abajo) | ⚠️ |

### Invariantes comprobados en base de datos

Con CAPTCHA rechazado no queda ningún rastro: `usuarios`, `cuentas_usuarios` y
`eventos` en cero para ese correo e identificación. Con CAPTCHA válido se crea
el usuario, la cuenta en estado `PENDIENTE` (1) sin correo verificado, el token
de activación **hasheado** (64 caracteres hex SHA-256, nunca en texto plano) y
un evento de auditoría con `hash_integridad`.

La clave secreta no aparece en ningún log del servidor (verificado por búsqueda
sobre la salida completa de `uvicorn`) ni en ninguna respuesta HTTP.

### Hallazgo: un secreto inválido no se distingue de un desafío rechazado

`_ERRORES_CONFIGURACION` en el adaptador contempla `invalid-input-secret`,
`missing-input-secret` y `bad-request` para responder 503 ante un error de
configuración. En la práctica **esa rama no se alcanza**: `siteverify` evalúa
primero el token y devuelve `invalid-input-response` aunque el secreto sea
inválido o falte por completo.

```
$ curl -s -X POST https://www.google.com/recaptcha/api/siteverify \
    -d "secret=<secreto-inventado>" -d "response=token-cualquiera"
{"success": false, "error-codes": ["invalid-input-response"]}

$ curl -s -X POST https://www.google.com/recaptcha/api/siteverify \
    -d "response=token-cualquiera"          # sin secreto
{"success": false, "error-codes": ["invalid-input-response"]}
```

Consecuencia operativa: si se despliega con un `RECAPTCHA_SECRET_KEY`
equivocado, **todos los registros fallan con 400 "Validación de seguridad
fallida"**, culpando al usuario, y el 503 pensado para avisar del error de
configuración nunca se dispara. El único caso de configuración que sí produce
503 es el secreto ausente, porque el adaptador lo comprueba antes de llamar.

No se corrigió en código a propósito: ninguna lógica del lado del adaptador
puede separar ambos casos, porque Google devuelve exactamente la misma
respuesta. Tampoco sirve un `curl` de arranque como validación, por el mismo
motivo. La mitigación real es de despliegue: **tras cada cambio de llaves,
confirmar con un registro real desde el navegador** que el par site key +
secreto está bien emparejado. Es la única prueba concluyente.

### Pendiente de confirmación manual

Queda un único paso que no se puede automatizar sin resolver el widget: marcar
la casilla real en `/registro` y completar un registro. Eso confirma a la vez
que el par de llaves está bien emparejado y que `localhost` está en la lista de
dominios autorizados de la llave. Si el dominio falta, el widget muestra
`ERROR for site owner: Invalid domain for site key` en vez de la casilla.
