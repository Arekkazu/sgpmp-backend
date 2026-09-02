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
| 503 | `CAPTCHA_SERVICIO_NO_DISPONIBLE` | Secreto ausente/inválido, red, timeout o respuesta no confiable |

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
