# Resumen — SSO con AgroFusion (Mecanismo A + Mecanismo B)

Implementado y verificado end-to-end en dev el 2026-08-08, sobre `feature/sso-login`. Diseño completo en `plan_sso_agrofusion.md`, gaps de BD en `gaps_bd_sso_agrofusion.md`, curls en `../curls_m01_sso_agrofusion.md`, checklist de ejecución en `TASKS_sso_agrofusion.md`.

## Qué se implementó

**Mecanismo A — login SSO interactivo** (`POST /sesiones/sso`): verifica un JWT RS256 de 2 minutos TTL emitido por `backendauth` de AgroFusion (`audience`/`issuer` validados explícitamente, a diferencia del antipatrón observado en `backendint`). Si el correo no existe en sgpmp, provisiona una cuenta mínima (`Usuario.crear_minimo_sso`) con los 6 campos personales en `NULL` y la cuenta en estado nuevo `Pendiente Datos`; el usuario la completa reutilizando el endpoint existente de edición de perfil (`PATCH /usuarios/{id}`, extendido con 4 campos opcionales), que la transiciona a `Activo` automáticamente al completarse.

**Mecanismo B — sincronización servidor-a-servidor** (`/integraciones/agrofusion/*`, 5 endpoints): autenticación M2M por `client_id`/`client_secret` (`secrets.compare_digest`), sin RBAC de sgpmp. Permite al Hub de AgroFusion listar roles, emitir tokens sin contraseña, crear usuarios completos y activos de inmediato, consultar estado y desactivar cuentas remotamente. `ACTIVATE_ACCOUNT`/`UPDATE_USER`/`GET_TYPE_DOCUMENT` quedaron fuera de esta iteración (documentado como decisión, no como pendiente).

Ambos mecanismos son **aditivos**: sin las variables de entorno de AgroFusion configuradas, `/sesiones/sso` responde `503` sin tocar la DB y `/integraciones/agrofusion/*` ni siquiera se monta en `main.py`. El login y RBAC normales de sgpmp no cambiaron de comportamiento.

## Decisiones de diseño no obvias

- **6 columnas de `modulo1.usuarios` pasaron a nullable** (`tipo_identificacion`, `numero_identificacion`, `nombre`, `apellidos`, `fecha_nacimiento`, `genero`) en vez de inventar datos de identidad para la provisión mínima. `uq_usuario_numero_identificacion` sigue siendo segura porque Postgres permite múltiples `NULL` en una `UNIQUE`.
- **`sesion_comun.py`** (nuevo módulo compartido) extrae la verificación de estado de cuenta y la emisión de sesión/JWT, reusadas por `LoginUseCase` (contraseña), `SsoLoginUseCase` (RS256) y `EmitirTokenAgroFusionUseCase` (M2M) — evita triplicar esa lógica.
- **El rol "Externo AgroFusion" (`id_rol=9`) nace con cero permisos**, aplicado por SQL directo (no vía la API de roles, cuyo stored procedure exige ≥1 permiso). Un usuario con este rol puede loguearse y ver/editar su propio perfil, pero cualquier endpoint RBAC-protegido le da 403 hasta que complete su perfil o un admin lo reasigne.
- **`rol_codigo` de AgroFusion se resuelve por match exacto (case-insensitive) contra `modulo1.roles.nombre_rol`**, con fallback al rol productor si no matchea — no hay un catálogo de mapeo fijo porque los roles no son fijos en este sistema (ver CLAUDE.md).

## Gaps de BD encontrados solo al probar contra la DB real (no visibles por inspección de esquema)

1. **Trigger `trg_validar_transicion_estado`** en `modulo1.cuentas_usuarios` mantenía su propia lista blanca de transiciones de estado, independiente del `TRANSICIONES_VALIDAS` de la aplicación — rechazaba cualquier transición hacia/desde `Pendiente Datos`. Corregido agregando `Pendiente Datos → (Activo, Eliminado)` a la lista blanca. Además, `CuentaRepository.crear()` ganó un parámetro `id_estado_cuenta` opcional para que la provisión mínima SSO inserte directo en `Pendiente Datos` (el trigger solo dispara en `UPDATE`, no en `INSERT`), evitando necesitar también `Pendiente → Pendiente Datos` en la lista blanca.
2. **Serialización JSONB del detalle de auditoría**: `EditarPerfilUseCase` no serializaba `fecha_nacimiento` (un `date` de Python) al registrar el evento, causando `TypeError` en el `commit()`. Corregido en `_valor_columna` con `.isoformat()`.

Ambos se descubrieron ejecutando el flujo real contra Postgres (servidor levantado + JWT RS256 real firmado con un keypair de prueba), no habrían aparecido con solo inspección de esquema o revisión de código.

## Verificación realizada

Servidor real + DB dev real (sin mocks): apagado por defecto, provisión mínima SSO, cierre del loop de perfil incompleto con transición automática a `Activo`, reutilización de cuenta en segundo login SSO, los 5 endpoints de Mecanismo B (incluyendo que el JWT emitido por `POST /token` funciona como un JWT normal contra `/sesiones/me/permisos`), rechazo de credenciales M2M inválidas (401, no 500), y confirmación cruzada de que una cuenta desactivada vía Mecanismo B bloquea el login normal por contraseña. Detalle completo en `TASKS_sso_agrofusion.md`.

Quedaron dos usuarios de prueba en dev (`sso.nuevo@ejemplo.com`, `m2m.nuevo@ejemplo.com`) — no se pudieron eliminar porque referencian filas en `modulo1.eventos`, inmutable por diseño (ver `gaps_bd_sso_agrofusion.md`).

## Pendiente / fuera de alcance

- Mecanismos `ACTIVATE_ACCOUNT`, `UPDATE_USER`, `GET_TYPE_DOCUMENT` de la integración con AgroFusion.
- Rate limiting en `POST /sesiones/sso` y `/integraciones/agrofusion/token` (el plan de diseño lo sugiere con el mismo patrón de `SolicitarRecuperacionUseCase`, no implementado en esta iteración).
- Prerrequisitos del lado de AgroFusion (registrar sgpmp como proyecto externo, entregar `sso_public.pem`, configurar plantillas REST) — fuera del control de este repo, ver `plan_sso_agrofusion.md`.
