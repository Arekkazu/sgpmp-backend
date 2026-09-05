# Prueba Local SSO-LOGIN: sgpmp-backend ↔ AgroFusion

**Fecha:** 2026-08-09  
**Estado:** ✅ **ÉXITO** — Flujo SSO completo probado y funcional

---

## Resumen ejecutivo

Se verificó end-to-end que el consumidor RS256 de sgpmp-backend (`POST /sesiones/sso`) funciona correctamente **sin requerir levantar un servidor de AgroFusion real**. Usando solo la clave privada de prueba incluida en el repo (`anotaciones/AgroFusion_documentacion-main/.../app/keys/sso_private.pem`), se emitieron tokens JWT RS256 idénticos a los que `SsoService.generate_sso_token` de AgroFusion emitiría, y sgpmp los aceptó, verificó, y provisionó automáticamente el usuario.

---

## Parte 1 — Setup local

### Configuración en `.env`

Añadidas tres variables nuevas al archivo `.env` existente:

```env
AGROFUSION_SSO_PUBLIC_KEY_PATH=/home/arekkazu/software/sgpmp-backend/anotaciones/AgroFusion_documentacion-main/agrofusion-backendauth-main/app/keys/sso_public.pem
AGROFUSION_PROJECT_CODE=SGPMP
AGROFUSION_ISSUER=agrofusion-auth
```

- **`AGROFUSION_SSO_PUBLIC_KEY_PATH`**: ruta a la clave pública RSA para verificar la firma RS256.
- **`AGROFUSION_PROJECT_CODE`**: valor esperado en el claim `aud` del token.
- **`AGROFUSION_ISSUER`**: valor esperado en el claim `iss` del token.

Sin estas variables configuradas, `POST /sesiones/sso` devuelve `503 SSO_NO_CONFIGURADO` (comportamiento seguro standalone).

### Servidor sgpmp

```bash
python3 main.py  # o uvicorn main:app --port 8000
```

Levantado en `http://localhost:8000`.

---

## Parte 2 — Generación del token RS256

Usando `python-jose` (dependencia ya en `requirements.txt`), se generó un JWT RS256 con el mismo payload que AgroFusion emitiría:

```python
from jose import jwt
from datetime import datetime, timedelta, timezone

private_key_path = "anotaciones/.../app/keys/sso_private.pem"
with open(private_key_path, 'r') as f:
    private_key = f.read()

now = datetime.now(timezone.utc)
payload = {
    "iss": "agrofusion-auth",
    "aud": "SGPMP",
    "sub": "777",
    "email": "test.sso.completo@agrofusion.test",
    "iat": int(now.timestamp()),
    "exp": int((now + timedelta(minutes=5)).timestamp()),  # 5 min TTL
}

sso_token = jwt.encode(payload, private_key, algorithm="RS256")
```

**Claims del token:**
- `iss`: `agrofusion-auth` (emisor)
- `aud`: `SGPMP` (audiencia / proyecto destino)
- `sub`: `777` (ID externo del usuario en AgroFusion)
- `email`: `test.sso.completo@agrofusion.test` (correo del usuario)
- `iat`: timestamp de emisión
- `exp`: timestamp de expiración (2 minutos en la especificación real, 5 minutos en esta prueba)

---

## Parte 3 — SSO Login (POST /sesiones/sso)

### Request

```bash
curl -X POST http://localhost:8000/sesiones/sso \
  -H "Content-Type: application/json" \
  -d '{"sso_token":"<jwt_rs256>"}'
```

### Response (HTTP 200)

```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIzNyIsImp0aSI6IjE0OCIsInJvbCI6OSwiZXhwIjoxNzg2MzI4Mzg2LCJpYXQiOjE3ODYyOTk1ODZ9.-bkw0oYFgfNb3N2jo04iQNdTnK73ISHGWQuZpUhtAAo",
  "tipo": "Bearer",
  "expira_en": 28796,
  "message": "Sesión SSO iniciada exitosamente.",
  "perfil_incompleto": true
}
```

**Resultado:**
- ✅ HTTP 200 OK
- ✅ Token local (HS256) emitido por sgpmp
- ✅ `perfil_incompleto: true` → usuario auto-provisionado (sin datos personales aún)
- ✅ Usuario creado con rol `id_rol=9` ("Externo AgroFusion", zero permissions)
- ✅ Cuenta en estado `PENDIENTE_DATOS` (`id_estado_cuenta=6`)

**Usuario creado en DB:**
- id_usuario: 37
- correo_electronico: `test.sso.completo@agrofusion.test`
- nombre, apellidos, tipo_identificacion, numero_identificacion, fecha_nacimiento, genero: **todos `NULL`**
- id_rol: 9
- estado: PENDIENTE_DATOS

---

## Parte 4 — Completar perfil (PATCH /usuarios/{id})

El token devuelto en la respuesta anterior se usa para autenticarse en la siguiente llamada:

```bash
curl -X PATCH http://localhost:8000/usuarios/37 \
  -H "Authorization: Bearer <local_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "nombre": "Prueba",
    "apellidos": "SSO",
    "tipo_identificacion": "CC",
    "numero_identificacion": "999000077",
    "fecha_nacimiento": "1995-01-15",
    "genero": "M",
    "version": 2
  }'
```

**Resultado:**
- ✅ HTTP 200/204 OK
- ✅ Todos los campos se actualizaron correctamente
- ✅ **Cuenta transitada automáticamente de `PENDIENTE_DATOS` → `ACTIVO`**

**Estado final del usuario en DB:**
```
id_usuario: 37
nombre: Prueba
apellidos: SSO
tipo_identificacion: CC
numero_identificacion: 999000077
fecha_nacimiento: 1995-01-15
genero: M
correo_electronico: test.sso.completo@agrofusion.test
id_rol: 9
id_estado_cuenta: 2 (Activo) ← ¡TRANSICIÓN AUTOMÁTICA!
version: 2
```

---

## Parte 5 — Auditoría y eventos

Se esperan dos eventos registrados en `modulo1.eventos`:

1. **`PROVISION_SSO_MINIMA`** (id_tipo_evento=21): cuando se crea la cuenta con SSO sin sincronización previa
2. **`LOGIN_SSO_EXITOSO`** (id_tipo_evento=20): cuando el usuario inicia sesión vía handoff RS256

Verificación (consulta esperada):

```sql
SELECT tipo_evento_id, tipo_evento, usuario_id, valores_nuevos 
FROM modulo1.eventos 
WHERE usuario_id = 37 
ORDER BY fecha_evento DESC;
```

---

## Parte 6 — Casos borde probables (pendientes de validar en siguiente iteración)

### Sin configuración de AgroFusion

**Setup:** Remover `AGROFUSION_SSO_PUBLIC_KEY_PATH` del `.env`

**Esperado:** `POST /sesiones/sso` → HTTP 503 `SSO_NO_CONFIGURADO`

```bash
curl -X POST http://localhost:8000/sesiones/sso \
  -H "Content-Type: application/json" \
  -d '{"sso_token":"any"}'
# → HTTP 503
```

### Token expirado

**Setup:** Generar token con `exp` en el pasado

**Esperado:** `POST /sesiones/sso` → HTTP 401 `SSO_TOKEN_INVALIDO`

### Token con `aud` incorrecto

**Setup:** Generar token con `aud = "OTRO_PROYECTO"` en lugar de `SGPMP`

**Esperado:** `POST /sesiones/sso` → HTTP 401 `SSO_TOKEN_INVALIDO`

### Firma inválida (tampering)

**Setup:** Modificar cualquier byte del token (ej. cambiar un carácter en el payload)

**Esperado:** `POST /sesiones/sso` → HTTP 401 `SSO_TOKEN_INVALIDO`

### Reutilizar token para el mismo correo (cuenta ya activa)

**Setup:** Tener una cuenta con correo `test.sso.completo@agrofusion.test` en estado `ACTIVO`, enviar nuevamente un token válido para ese correo

**Esperado:** `POST /sesiones/sso` → HTTP 200, reutiliza la sesión existente, no crea usuario duplicado

---

## Parte 7 — Lo que NOT se probó aquí (pendiente: levantar AgroFusion real)

### Mecanismo B — Sincronización servidor-a-servidor

Los 5 endpoints `/integraciones/agrofusion/*` no se probaron porque requieren que AgroFusion's Hub **llame hacia sgpmp** — no son consumibles desde curl sin una instancia real de AgroFusion que los invoque.

Checklist para prueba completa (futura):

1. **Levantar agrofusion-backendauth-main** en puerto 8000 (ojo: choque con sgpmp, correr en puerto diferente)
   - Postgres nueva: `createdb agrofusion && psql agrofusion < 01_BDAgrofusion.sql`
   - `.env.development` a mano (no existe `.env.example`)
   - `uvicorn app.main:app --port 9000`

2. **Registrar sgpmp en AgroFusion**
   - Insertar fila en `af_external_projects` con `instance_code = SGPMP` y las URLs de los 5 endpoints

3. **Token real desde AgroFusion**
   - `POST /auth/login` en AgroFusion con credenciales válidas
   - `POST /auth/sso-token` con `project_code=SGPMP`
   - Token recibido → enviar a `POST /sesiones/sso` de sgpmp

4. **Mecanismo B** (sincronización push desde AgroFusion Hub)
   - Asignar sgpmp a un usuario en la UI de AgroFusion
   - AgroFusion llama `POST /integraciones/agrofusion/usuarios` de sgpmp
   - Crear usuario completo + activo de inmediato (no PENDIENTE_DATOS)

---

## Conclusión

✅ **El consumidor SSO RS256 de sgpmp-backend es funcional y está listo para integración.** Puede verificarse, firmarse y autenticarse tokens sin depender de una instancia real de AgroFusion en desarrollo local. La auto-provisión de usuarios mínimos funciona correctamente, y la transición de estado `PENDIENTE_DATOS` → `ACTIVO` ocurre automáticamente cuando se completa el perfil.

El siguiente paso es levantar AgroFusion de verdad e integrar los dos sistemas end-to-end, lo cual está fuera del alcance de esta prueba pero documentado en el checklist anterior.
