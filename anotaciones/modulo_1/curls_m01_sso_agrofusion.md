# Curls — SSO con AgroFusion (Módulo 1)

Base URL: `http://localhost:8000`. Referencia de diseño: `anotaciones/modulo_1/plan_sso_agrofusion.md`. Gaps de BD aplicados: `anotaciones/modulo_1/gaps_bd_sso_agrofusion.md`.

---

## Mecanismo A — Login SSO interactivo (`/sesiones/sso`)

Requiere `AGROFUSION_SSO_PUBLIC_KEY_PATH` y `AGROFUSION_PROJECT_CODE` configuradas; si no, responde `503 SSO_NO_CONFIGURADO` sin tocar la base de datos.

### Iniciar sesión vía SSO
```bash
curl -s -X POST http://localhost:8000/sesiones/sso \
  -H "Content-Type: application/json" \
  -d '{
    "sso_token": "<jwt_rs256_emitido_por_agrofusion>"
  }' | jq
```

**Respuesta esperada (200)**:
```json
{
  "token": "<jwt_sgpmp>",
  "tipo": "Bearer",
  "expira_en": 86400,
  "message": "Sesión SSO iniciada exitosamente.",
  "perfil_incompleto": false
}
```

Si el correo del token no existía en sgpmp, se provisiona una cuenta mínima (estado `Pendiente Datos`, `id_estado_cuenta=6`) y la respuesta trae `"perfil_incompleto": true`.

**Errores posibles**:
| Código HTTP | `code` | Causa |
|---|---|---|
| 503 | `SSO_NO_CONFIGURADO` | Integración deshabilitada en este despliegue (env vars ausentes) |
| 500 | `AGROFUSION_CLAVE_PUBLICA_NO_DISPONIBLE` | El path configurado no se pudo leer |
| 401 | `SSO_TOKEN_INVALIDO` | Firma RS256 inválida, `aud`/`iss` incorrectos, token expirado (TTL 2 min), o payload sin `sub`/`email` |
| 423 | `CUENTA_BLOQUEADA` | Cuenta existente bloqueada temporalmente por intentos fallidos de login normal |
| 403 | `CUENTA_DESHABILITADA` | Cuenta existente inactiva o eliminada |

### Completar perfil tras provisión mínima (`perfil_incompleto: true`)

Reutiliza el endpoint existente de edición de perfil — solo se puede enviar `tipo_identificacion`/`numero_identificacion`/`fecha_nacimiento`/`genero` mientras la cuenta está en `Pendiente Datos`. Al completarse los 4 campos (junto con `nombre`/`apellidos`, ya obligatorios en el DTO), la cuenta pasa a `Activo` automáticamente.

```bash
curl -s -X PATCH http://localhost:8000/usuarios/<ID_USUARIO> \
  -H "Authorization: Bearer <TOKEN_SSO_OBTENIDO_ARRIBA>" \
  -H "Content-Type: application/json" \
  -d '{
    "nombre": "Juan",
    "apellidos": "Pérez García",
    "tipo_identificacion": "CC",
    "numero_identificacion": "1234567890",
    "fecha_nacimiento": "1990-05-15",
    "genero": "M",
    "version": 1
  }' | jq
```

**Errores posibles**:
| Código HTTP | `code` | Causa |
|---|---|---|
| 403 | `SIN_PERMISO_CAMPOS_IDENTIFICACION` | Se envió alguno de esos 4 campos sin que la cuenta esté en `Pendiente Datos` |
| 412 | `CONFLICTO_CONCURRENCIA` | `version` no coincide con la versión actual del registro |
| 409 | `UNICIDAD` | `numero_identificacion` ya pertenece a otra cuenta |

### Verificar que el modo standalone no se afecta
```bash
# Sin las env vars de AgroFusion configuradas:
curl -isv -X POST http://localhost:8000/sesiones/sso -d '{"sso_token":"x"}'
# → 503 SSO_NO_CONFIGURADO

# El login normal debe seguir funcionando exactamente igual:
curl -s -X POST http://localhost:8000/sesiones/ \
  -H "Content-Type: application/json" \
  -d '{"correo_electronico":"usuario@ejemplo.com","contrasena":"Contrasena1!"}' | jq
```

---

## Mecanismo B — Sincronización servidor-a-servidor (`/integraciones/agrofusion`)

Requiere `AGROFUSION_HUB_CLIENT_ID`/`AGROFUSION_HUB_CLIENT_SECRET` configuradas; si no, el router ni siquiera se monta en `main.py` (404 en vez de 503 — no hay ruta que responder). Ninguno de estos endpoints usa `require_permission`: la confianza la da `client_id`/`client_secret`, verificado por `verify_agrofusion_client` (`src/shared/agrofusion_auth.py`) al inicio de cada handler.

### `GET_ROLES` — listar roles
```bash
curl -s -G http://localhost:8000/integraciones/agrofusion/roles \
  --data-urlencode "client_id=agrofusion" \
  --data-urlencode "client_secret=<secreto>" | jq
```

### `GET_AUTHORIZATION` — emitir token para un usuario existente
```bash
curl -s -X POST http://localhost:8000/integraciones/agrofusion/token \
  -H "Content-Type: application/json" \
  -d '{"client_id":"agrofusion","client_secret":"<secreto>","email":"usuario@ejemplo.com"}' | jq
```
**Respuesta (200)**: `{"access_token": "<jwt sgpmp normal>", "expires_in": 86400}`.

### `CREATE_USER` — alta completa, activa de inmediato
```bash
curl -s -X POST http://localhost:8000/integraciones/agrofusion/usuarios \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": "agrofusion",
    "client_secret": "<secreto>",
    "correo_electronico": "nuevo@ejemplo.com",
    "nombre": "Ana",
    "apellidos": "Pérez",
    "tipo_identificacion": "CC",
    "numero_identificacion": "123456",
    "fecha_nacimiento": "1990-01-01",
    "genero": "F",
    "rol_codigo": "Productor"
  }' | jq
```
`rol_codigo` debe matchear exactamente (case-insensitive) contra `modulo1.roles.nombre_rol` (ej. `"Productor"`, `"Veterinario"`); si no viene o no matchea ningún rol, cae al rol por defecto (`Usuario.ROL_PRODUCTOR`).

**Respuesta esperada**: `201`, cuenta `Activo` completa (sin flujo de activación por correo).

### `GET_USER` — existencia + estado + rol
```bash
curl -s -G http://localhost:8000/integraciones/agrofusion/usuarios/nuevo@ejemplo.com \
  --data-urlencode "client_id=agrofusion" \
  --data-urlencode "client_secret=<secreto>" | jq
```

### `CHANGE_USER_STATUS` — desactivar remotamente
```bash
curl -s -X PATCH http://localhost:8000/integraciones/agrofusion/usuarios/nuevo@ejemplo.com/estado \
  -H "Content-Type: application/json" \
  -d '{"client_id":"agrofusion","client_secret":"<secreto>","id_estado_cuenta":3,"motivo":"Usuario dado de baja en AgroFusion"}' | jq
```

**Errores posibles (los 5 endpoints)**:
| Código HTTP | `code` | Causa |
|---|---|---|
| 503 | `AGROFUSION_NO_CONFIGURADO` | Integración M2M deshabilitada en este despliegue |
| 401 | `CREDENCIALES_M2M_INVALIDAS` | `client_id`/`client_secret` no coinciden |
| 404 | `USUARIO_NO_ENCONTRADO` / `CUENTA_NO_ENCONTRADA` | No existe cuenta sgpmp para ese correo (`/token`, `/estado`) |
| 409 | `UNICIDAD` | Correo o número de identificación ya registrados (`CREATE_USER`) |
| 422 | `TRANSICION_INVALIDA` | Cambio de estado no permitido desde el estado actual |

No implementados en esta iteración: `ACTIVATE_ACCOUNT`, `UPDATE_USER`, `GET_TYPE_DOCUMENT` (ver `anotaciones/modulo_1/plan_sso_agrofusion.md`).
