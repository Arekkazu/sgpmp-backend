# RF-12 — Resumen de implementación

Issue #1605 · PR #49 · rama `feature/rf12-permiso-identificacion-completa-alembic`

Siembra el permiso que faltaba para ver el número de identificación completo, y cierra
los tres flujos alternos de RF-12 que seguían sin implementar.

---

## 1. El permiso que faltaba

### El gap

Se comprobó en `origin/dev`, en el historial remoto y por consulta de solo lectura a
`sgpmp` (la base de dev) que no existía la combinación RBAC necesaria: en
`modulo1.permisos` estaban las acciones 1, 2, 3 y 4 sobre el recurso `usuarios`, y
ninguna con `id_accion = 5`. En la práctica, nadie podía ver el documento completo.
No se aplicaron cambios manuales a desarrollo.

El caso de uso ya consultaba esta capacidad:

| Elemento | Valor |
|---|---:|
| Administrador | `id_rol = 1` |
| Usuarios | `id_recurso = 1` |
| Ejecutar | `id_accion = 5` (`E`) |

Los tres IDs se verifican contra sus catálogos antes de sembrar el permiso.

### La migración

La migración Alembic `f2c84d91a6e7_rf12_permiso_identificacion_completa.py` inserta
exclusivamente:

```text
admin_ejecutar_identificacion_completa
rol=1, recurso=1, acción=5, activo=true
```

La operación es idempotente: si la combinación ya está activa no la duplica; si
existe inactiva y no es un registro administrativo protegido, la reactiva. No
concede esta capacidad a Productor, Veterinario ni otros roles.

El `downgrade` conserva el registro. Esto es intencional porque los triggers
`trg_proteger_permisos_admin_delete` y
`trg_proteger_permisos_admin_update` definen los permisos `admin_*` como
permanentes e inmutables. Intentar eliminarlo o desactivarlo rompería una regla
de integridad vigente en la base.

### Aplicación

La aplica el workflow `.github/workflows/migration-db.yml` (`alembic upgrade head`)
al mergear a `dev`. No se sembró a mano en `sgpmp`.

La revisión cuelga de `e7b31f4a6c20`, la cabeza real de `dev`. La rama la había
encadenado a `d4e2f8a15c9b`, que era la cabeza cuando se creó pero quedó 7 revisiones
atrás; eso dejaba dos cabezas y hacía fallar `alembic upgrade head` con *Multiple head
revisions are present* — justo el comando que corre ese workflow.

```bash
alembic heads   # -> f2c84d91a6e7 (una sola)
```

### Verificación en BD

```sql
SELECT
    p.id_permiso,
    p.nombre,
    r.nombre_rol,
    re.nombre_recurso,
    a.codigo,
    p.es_activo
FROM modulo1.permisos AS p
JOIN modulo1.roles AS r ON r.id_rol = p.id_rol
JOIN modulo1.recursos AS re ON re.id_recurso = p.id_recurso
JOIN modulo1.acciones AS a ON a.id_accion = p.id_accion
WHERE p.id_rol = 1
  AND p.id_recurso = 1
  AND p.id_accion = 5;
```

Debe retornar una sola fila activa. El Administrador verá la identificación
completa y los actores sin esa combinación seguirán recibiéndola enmascarada.



---

## 2. Flujo alterno — fallo al validar el permiso

RF-12 pide que, si no se puede verificar el permiso, se aplique el enmascaramiento por
defecto "priorizando la privacidad sobre la visualización". El código anterior dejaba
propagar la excepción, así que un servicio de permisos caído tumbaba la consulta entera
con un 500 en vez de servirla enmascarada.

`_puede_ver_identificacion_completa()` envuelve la consulta y retorna `False` ante
cualquier fallo.

El mismo método exige además `permiso.es_activo`. Hacía falta porque
`PermisoRepository.buscar()` **no** filtra por ese campo, a diferencia de
`require_permission` en `src/shared/rbac.py`: sin la condición, un permiso desactivado
seguiría concediendo el número completo. El filtro no se puede añadir dentro de
`buscar()` porque `AsignarPermisoUseCase` lo usa para detectar duplicados antes de
insertar y necesita ver también los inactivos.

---

## 3. Flujo alterno — patrón de consulta inusual (429)

RF-12 exige cortar con `429` cuando un mismo actor consulta fichas "en un lapso de
tiempo extremadamente corto (posible extracción masiva o scraping)". No existía rate
limiting en esta vista.

No hizo falta infraestructura nueva: esta vista **ya registraba** un evento de auditoría
tipo 18 en cada consulta, así que la ventana se cuenta sobre esos eventos. Es el mismo
patrón que ya usaba `SolicitarRecuperacionUseCase` con
`contar_solicitudes_recuperacion_por_ip` para RF-08/09.

- `EventoRepository.contar_consultas_detalle_usuario(id_usuario, desde)` — nuevo método
  del puerto y su implementación SQLAlchemy. Lo resuelve el índice ya existente
  `ix_eventos_usuario_fecha (id_usuario, fecha_evento DESC)`: **cero DDL**.
- El conteo filtra `resultado = exitoso`. Es necesario, no cosmético: el intento
  bloqueado se registra como evento fallido, y si contara también esos, cada reintento
  alimentaría la ventana y el bloqueo no expiraría nunca.
- Al alcanzar el umbral se registra el evento fallido con
  `motivo = "PATRON_CONSULTA_INUSUAL"` — es la "alerta de seguridad" que pide el RF,
  sobre la auditoría inmutable que ya existe — y se hace `commit()` **antes** de lanzar,
  porque si no la alerta se perdería al cerrarse la sesión sin confirmar.
- El corte es por actor, no global: un administrador no bloquea a otro.

Umbral y ventana son constantes de módulo, para calibrarlas sin tocar lógica:

```python
MAX_CONSULTAS_DETALLE_POR_VENTANA = 20
VENTANA_CONSULTAS_MINUTOS = 1
```

Veinte fichas por minuto no las abre nadie navegando a mano; un scraper cruza el umbral
de inmediato. Si en operación resultan estrechas o anchas, se ajustan ahí.

---

## 4. Flujo alterno — auditoría no disponible

RF-12 exige bloquear la visualización si no se puede auditar el acceso. Eso ya ocurría
—el use case hacía `rollback` y relanzaba—, pero la excepción cruda daba un 500 genérico
en vez del contrato del RF. Ahora se traduce a `InfrastructureError`:

```json
{
  "error_code": "AUDITORIA_NO_DISPONIBLE",
  "message": "Error de seguridad: No se pudo garantizar la trazabilidad de la consulta. La visualización de datos sensibles ha sido bloqueada preventivamente."
}
```

---

## Archivos tocados

| Archivo | Cambio |
|---|---|
| `alembic/versions/f2c84d91a6e7_…py` | semilla del permiso; `down_revision` reencadenado |
| `…/use_cases/usuarios/consultar_detalle_usuario_use_case.py` | enmascarado defensivo, `es_activo`, 429, 500 de auditoría |
| `…/domain/repositories/evento_repository.py` | `contar_consultas_detalle_usuario` (puerto) |
| `…/infrastructure/repositories/evento_repository.py` | implementación del conteo |
| `…/infrastructure/routers/usuarios_routers.py` | `429` en `responses` |
| `tests/identity_access/test_rf12_permiso_identificacion_completa.py` | 8 casos |
| `tests/integration/test_rf12_permiso_identificacion_integration.py` | 2 casos |

---

## Pruebas

Suite completa contra la base `pruebas`: **186 pasan, 7 se saltan, 0 fallan**. Los 6
fallos de módulo 9 que reportaba la descripción del PR no se reproducen.

```bash
TEST_DATABASE_URL=postgresql://…/pruebas python -m pytest tests/ -q
```

Cubierto: permiso concedido / ausente / inactivo, verificación de permiso que revienta,
umbral alcanzado y justo por debajo, auditoría caída, migración aplicada dos veces contra
Postgres real, y que el evento de bloqueo no realimente su propia ventana.
