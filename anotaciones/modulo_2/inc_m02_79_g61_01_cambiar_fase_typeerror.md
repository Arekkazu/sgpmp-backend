# INC-M02-79-G61-01 — POST /{id_activo}/fases respondía 500 siempre (ya resuelto en `dev`)

**RF:** RF-37 (CU02) — Gestión de fases del ciclo productivo.
**Endpoint:** `POST /activos-biologicos/{id_activo}/fases`.

## Qué reportó QA

Cualquier intento de asignar/avanzar la fase productiva de un activo respondía `500 ERROR_INTERNO`, confirmado en múltiples activos y ciclos productivos distintos. Causa raíz señalada: `cambiar_fase_use_case.py:72` llamaba `self.repo.cerrar_gestion_activa(id_activo, ahora, dto.motivo_cambio or '')` con 3 argumentos, pero el puerto (`domain/repositories/activo_biologico_repository.py:56`) y su implementación exigen 4 (falta `usuario_id`) — `TypeError` de Python, no un error de base de datos. Bloquea en cascada RF-40 y RF-43, que dependen de tener una fase activa.

## Investigación (Paso 0)

Se verificó `cambiar_fase_use_case.py` en `dev` antes de tocar nada. La llamada ya pasa los 4 argumentos:

```python
self.repo.cerrar_gestion_activa(
    id_activo,
    ahora,
    dto.motivo_cambio or '',
    usuario.id_usuario,
)
```

`git blame` ubica el fix en el commit `24705314a` ("fix(rf37-rf38): enviar usuario al cerrar la fase anterior"), fechado **2026-09-11**, mergeado a `dev` vía **PR #253** ("fix(rf37-rf39): completar flujo de asignación de fases y cierre g35") — ya cerrado. Ese PR también agregó `tests/biological_assets/test_cambiar_fase_use_case.py` (193 líneas), que cubre explícitamente este caso: `test_avanzar_fase_cierra_la_anterior_con_el_usuario_responsable` verifica que `usuario_id` llega correctamente a `cerrar_gestion_activa`.

Mismo patrón que el resto de tickets de esta tanda de QA (`INC-M02-39-G27`, `INC-M02-40-G28`, `INC-M02-66-G90`): el reporte corrió contra `sgpmp_test`, una revisión anterior a `24705314a`/PR #253. **No se requiere cambio de código.**

## Pruebas

`tests/biological_assets/test_cambiar_fase_use_case.py` (ya en `dev`, sin cambios en este PR):

```
$ python -m pytest tests/biological_assets/test_cambiar_fase_use_case.py -q
...                                                                      [100%]
3 passed in 2.41s
```

## Fuera de alcance

Actualizar el contenedor de `sgpmp_test` a una revisión de `dev` posterior a `24705314a` (PR #253) — responsabilidad de despliegue/DevOps, no de este repositorio.
