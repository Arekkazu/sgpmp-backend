# TASKS — Implementación SSO con AgroFusion

> **Estado: implementado y verificado end-to-end en dev (2026-08-08).** Checklist derivado de `anotaciones/modulo_1/plan_sso_agrofusion.md` (diseño) y del plan de ejecución acordado en sesión. Alcance: **Mecanismo A (login SSO interactivo) + Mecanismo B (sincronización servidor-a-servidor)**, solo backend.

Decisiones tomadas:
- Columnas `NOT NULL` de `modulo1.usuarios` afectadas por la provisión mínima SSO → **nullable** (no se inventan datos de identidad).
- El "completar perfil" de una cuenta `PENDIENTE_DATOS` se resuelve **extendiendo `EditarPerfilUseCase`/`EditarPerfilDTO`** existentes, no con un endpoint nuevo.
- El rol "Externo AgroFusion" nace **con cero permisos** en `modulo1.permisos`.
- Sin objeto `Settings` centralizado: se siguió el patrón existente de `os.getenv(...)` a nivel de módulo (como `src/shared/jwt.py`).

---

## Paso 0 — DB (MCP postgres)
- [x] `ALTER TABLE modulo1.usuarios` — 6 columnas nullable
- [x] `INSERT INTO modulo1.estados_cuentas` id=6 'Pendiente Datos'
- [x] `INSERT INTO modulo1.roles` 'Externo AgroFusion' (SQL directo) → `id_rol=9`
- [x] `INSERT INTO modulo1.tipos_eventos` x3 → `id_tipo_evento=20,21,22`
- [x] Documentado en `anotaciones/modulo_1/gaps_bd_sso_agrofusion.md`
- [x] **Gap adicional descubierto en verificación**: trigger `trg_validar_transicion_estado` en `modulo1.cuentas_usuarios` tenía su propia lista blanca de transiciones, independiente de la app — se corrigió para permitir `Pendiente Datos → (Activo, Eliminado)` (documentado en el mismo gaps doc, sección 6)

## Mecanismo A — Dominio
- [x] `Cuenta.ESTADO_PENDIENTE_DATOS`
- [x] `Usuario.crear_minimo_sso(...)`
- [x] `IdentidadFederada` VO
- [x] `SsoProviderPort`
- [x] `CuentaRepository.crear()` ganó un parámetro `id_estado_cuenta` opcional (para crear directo en `Pendiente Datos` sin pasar por el trigger de transición)

## Mecanismo A — Infraestructura y use case
- [x] `sesion_comun.py` (`verificar_estado_cuenta` + `emitir_sesion`)
- [x] Refactor `LoginUseCase` para usar `sesion_comun`
- [x] `AgroFusionSsoAdapter` (RS256)
- [x] `SsoLoginUseCase`
- [x] `SsoLoginDTO`, `LoginResponse.perfil_incompleto`
- [x] `POST /sesiones/sso` router

## Mecanismo A — Cerrar loop de perfil incompleto
- [x] `EditarPerfilDTO` +4 campos opcionales
- [x] `EditarPerfilUseCase`: guard `PENDIENTE_DATOS` + auto-transición a `ACTIVO` + `TRANSICIONES_VALIDAS[6]`

## Mecanismo A — Config
- [x] `.env.example`
- [x] `requirements.txt` (`cryptography` explícito)
- [x] `curls_m01_sso_agrofusion.md` — Mecanismo A

## Mecanismo B — Dominio
- [x] `RolRepository.obtener_por_nombre`
- [x] `Usuario.registrar_nuevo(id_rol opcional)`

## Mecanismo B — Infraestructura y use cases
- [x] `shared/agrofusion_auth.py`
- [x] `crear_usuario_agrofusion_use_case.py`
- [x] `emitir_token_agrofusion_use_case.py`
- [x] `cambiar_estado_usuario_agrofusion_use_case.py`
- [x] `agrofusion_dto.py` + `agrofusion_schema.py`
- [x] `agrofusion_integration_router.py` (5 endpoints)
- [x] `main.py` montaje condicional

## Mecanismo B — Config
- [x] `.env.example`
- [x] `curls_m01_sso_agrofusion.md` — Mecanismo B

## Cierre
- [x] `anotaciones/modulo_1/resumen_sso_agrofusion.md`
- [x] Verificación end-to-end manual (servidor real + DB dev real, no mocks):
  - [x] Apagado por defecto — sin env vars: `/sesiones/sso` → 503, `/integraciones/agrofusion/*` → 404 (router no montado), login normal intacto
  - [x] Mecanismo A camino mínimo — JWT RS256 real (keypair de prueba) → `perfil_incompleto=true`, 6 columnas NULL, rol 9, estado 6, confirmado en DB
  - [x] Cerrar el loop — PATCH con los 4 campos → cuenta pasó a `Activo` (confirmado en DB)
  - [x] Mecanismo A cuenta ya existente — segundo login SSO reutiliza el mismo `id_usuario`, `perfil_incompleto=false`
  - [x] Mecanismo B completo — `GET /roles`, `POST /usuarios` (rol_codigo resuelto correctamente), `GET /usuarios/{email}`, `POST /token` (JWT validado contra `/sesiones/me/permisos`), `PATCH /usuarios/{email}/estado`
  - [x] `client_secret` incorrecto → 401 (no 500)
  - [x] Bonus: cuenta desactivada vía Mecanismo B bloquea correctamente el login normal por contraseña (`CUENTA_DESHABILITADA`) — valida que `verificar_estado_cuenta` compartido funciona igual en los 3 flujos

**Bugs reales encontrados y corregidos durante la verificación** (no se habrían detectado sin probar contra la DB real):
1. Trigger de transición de estados no contemplaba `Pendiente Datos` — ver arriba.
2. `_valor_columna` en `EditarPerfilUseCase` no serializaba `fecha_nacimiento` (un `date` de Python) para el detalle JSONB de auditoría → `TypeError` al hacer `commit()`. Corregido con `.isoformat()`.

---

Referencia de diseño completa: `anotaciones/modulo_1/plan_sso_agrofusion.md`. Gaps de BD: `anotaciones/modulo_1/gaps_bd_sso_agrofusion.md`. Resumen de implementación: `anotaciones/modulo_1/resumen_sso_agrofusion.md`. Curls: `anotaciones/curls_m01_sso_agrofusion.md`.
