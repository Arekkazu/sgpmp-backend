# RF-12 — Permiso de identificación completa y cierre de flujos alternos

Issue #1605 · PR #49 · rama `feature/rf12-permiso-identificacion-completa-alembic`

Documento de trabajo: se va cerrando a medida que avanza la implementación.
El resumen definitivo queda en `resumen.md` de esta misma carpeta.

---

## Alcance

1. Sembrar el permiso que deja al Administrador ver el número de identificación
   completo (el alcance literal de la issue, 1 pt).
2. Cerrar los dos flujos alternos de RF-12 que el PR daba por hechos sin estarlo:
   429 por patrón de consulta inusual, y enmascaramiento defensivo cuando la
   verificación del permiso falla.
3. Cerrar también el FA de auditoría no disponible, que devolvía un 500 genérico
   en vez del contrato del RF.

---

## Revisión del PR #49 — qué estaba bien

- [x] La semilla apunta a la combinación correcta: Administrador `id_rol=1`,
      Usuarios `id_recurso=1`, Ejecutar `id_accion=5`. Es exactamente la que
      `ConsultarDetalleUsuarioUseCase` ya consultaba; no hizo falta tocar el use case
      para esto.
- [x] Los tres catálogos se validan antes de insertar, y las tres validaciones
      pasan contra la BD real (`roles.id_rol=1` → `Administrador`,
      `recursos.id_recurso=1` → `usuarios`, `acciones.id_accion=5` → `E`).
- [x] `ON CONFLICT (id_rol, id_recurso, id_accion)` coincide con la restricción real
      `uq_permiso_unico`.
- [x] `trg_proteger_permisos_admin_insert` deja pasar un permiso `admin_*` solo si el
      rol es Administrador — el INSERT es válido.
- [x] `downgrade()` vacío bien justificado: `trg_proteger_permisos_admin_delete` y
      `_update` hacen la fila indeleteable e inmutable.
- [x] El gap era real: verificado por `SELECT` que en `modulo1.permisos` existían las
      acciones 1, 2, 3 y 4 sobre el recurso 1, y ninguna con `id_accion = 5`.

## Revisión del PR #49 — hallazgos a corregir

- [x] **BLOQUEANTE.** La migración `f2c84d91a6e7` colgaba de `d4e2f8a15c9b`, que ya
      no es la cabeza de `dev` (`e7b31f4a6c20`) — la rama se creó cuando lo era y
      `dev` avanzó 7 revisiones. Tras el merge quedaban dos cabezas y
      `alembic upgrade head` falla con *Multiple head revisions are present*, que es
      justo lo que corre `migration-db.yml` contra la BD de dev. Es el mismo fallo
      del PR #48.
- [x] El PR marcaba RF-12 como ✅ 100% con dos flujos alternos del RF sin implementar
      (429 y enmascaramiento defensivo). Se implementaron en vez de recortar el estado.
- [x] `PermisoRepository.buscar()` no filtra `es_activo`, a diferencia de
      `require_permission`: un permiso desactivado seguía concediendo el número
      completo. El filtro no puede ir en `buscar()` porque `AsignarPermisoUseCase`
      lo usa para detectar duplicados; va en el use case.
- [x] El test unitario afirmaba sobre el texto del archivo de migración, incluido
      `down_revision`. Se quitó esa aserción: rompía con el reencadenado y no probaba
      comportamiento.
- [x] El doc del PR decía haber consultado `sgpmp_dev`; la base de dev es `sgpmp`.
- [x] `tests/integration/conftest.py` añade `pruebas-integrador` a la allowlist de
      bases de prueba. Ajeno a RF-12 pero inocuo y ya documentado en el README: se
      conserva tal cual.

---

## Implementación

### Migración

- [x] `down_revision` → `"e7b31f4a6c20"`. El SQL del `upgrade()` no se tocó.
- [x] `alembic heads` devuelve una sola cabeza, `f2c84d91a6e7`.

### FA — fallo al validar el permiso → enmascarar, no 500

- [x] `_puede_ver_identificacion_completa()`: `try/except` alrededor de la consulta
      del permiso; ante cualquier fallo, enmascara.
- [x] Se exige además `permiso.es_activo`.

### FA — patrón de consulta inusual → 429

- [x] Puerto e implementación de `contar_consultas_detalle_usuario`, calcado de
      `contar_solicitudes_recuperacion_por_ip` (el rate limiting que ya existía en el
      repo para RF-08/09). Sin infraestructura nueva ni DDL.
- [x] La ventana se cuenta sobre los eventos de auditoría tipo 18 que esta misma
      vista ya registraba, filtrando `resultado = exitoso`.
- [x] El intento bloqueado se registra como evento fallido (la alerta de seguridad
      que pide el RF) y se hace `commit` antes de lanzar el 429.
- [x] Umbral y ventana como constantes de módulo, calibrables sin tocar lógica.
- [x] `429` documentado en los `responses` del endpoint.

### FA — auditoría no disponible → 500 con contrato propio

- [x] El fallo al registrar la auditoría se traduce a `InfrastructureError`
      `AUDITORIA_NO_DISPONIBLE` con el mensaje del RF. El acceso ya quedaba bloqueado;
      lo que faltaba era el contrato de respuesta.

### Tests

- [x] 8 casos unitarios: permiso concedido/ausente, permiso inactivo, verificación
      que revienta, umbral alcanzado, umbral justo por debajo, auditoría caída, y la
      forma de la migración.
- [x] 2 casos de integración: la migración aplicada dos veces contra Postgres real
      (idempotencia + exclusividad del Administrador), y el recorrido de 429 con la
      comprobación de que el evento de bloqueo no realimenta su propia ventana.

### Documentación

- [x] Carpeta `rf12_permiso_identificacion_completa/` con `checklist.md` y `resumen.md`.
- [x] `estado_M01.md` y `ESTADO_BACKEND.md` actualizados.

---

## Verificación ejecutada

- [x] `alembic heads` → `['f2c84d91a6e7']`, una sola cabeza.
- [x] `alembic upgrade e7b31f4a6c20:head --sql` → una única revisión pendiente desde
      el estado actual de la BD de dev.
- [x] Suite completa contra la base `pruebas`: **186 pasan, 7 se saltan, 0 fallan**.
      Los 6 fallos de módulo 9 que reportaba el PR no se reproducen.
- [x] La fila **no** se aplicó a mano en `sgpmp`: la aplica `migration-db.yml` al
      mergear a `dev`.
