# SEG-M02-01 [RF-52] — Resumen

Issue #265 · rama `fix/seg-m02-01-auditoria-fallos-silenciosos`

`src/biological_assets/` tenía 30 bloques `except Exception: pass` alrededor
de escrituras a la bitácora RF-52, en 18 casos de uso. Un fallo al escribir
el evento de auditoría se descartaba sin dejar rastro: la operación de
negocio respondía `200`/`201` con normalidad y nadie se enteraba de que el
evento correspondiente nunca se persistió.

## Decisión: opción (a) — la operación continúa, el fallo queda en log

RF-52 restricción 3 ("Sin Impacto en el Flujo Operativo") ya establece que un
fallo de auditoría no debe bloquear los demás RF de M02, salvo que el propio
RF defina lo contrario explícitamente (el propio documento cita como único
ejemplo RF-49). Revertir 12 casos de uso de escritura para hacer la bitácora
transaccional con la operación de negocio (opción b) es un cambio de
comportamiento mucho más amplio que "dejar de descartar en silencio" — se
deja fuera de este PR (ver sección "Fuera de alcance" abajo).

Se elige (a) para los 30 sitios, sin distinguir escritura de consulta: el
modo de fallo y el remedio son idénticos en ambos casos (no perder rastro,
no bloquear la respuesta), así que tratarlos distinto no aporta nada —
la decisión es la misma y ahora es explícita.

## El fix: un helper, no 30 parches

En vez de repetir logging + fallback en los 30 sitios, se centraliza en
`src/biological_assets/application/use_cases/_registrar_evento_bitacora.py`:

```python
def registrar_evento_bitacora(bitacora_repo, db, evento: EventoAuditoria) -> None:
    if bitacora_repo is None:
        return
    try:
        bitacora_repo.registrar(evento)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("Fallo al registrar evento de auditoría RF-52: ...", exc_info=True)
        _escribir_fallback(evento, exc)  # logs/audit_fallback_M02_YYYYMMDD.log
```

Mismo mecanismo (log ERROR + archivo de fallback local) que ya usa
`src/prediction/infrastructure/repositories/evento_auditoria_m04_repository.py`
para el mismo problema en M04 — no se inventó un patrón nuevo. El archivo de
fallback es lo que responde al criterio de aceptación "existe una forma de
detectar estos fallos sin revisar logs a mano": una línea JSON por fallo,
contable con `grep`/`wc -l` sin necesitar acceso a la base de datos que
falló.

Los 30 sitios pasaron de:

```python
if self.bitacora_repo:
    try:
        self.bitacora_repo.registrar(EventoAuditoria(...))
        self.db.commit()
    except Exception:
        pass
```

a:

```python
registrar_evento_bitacora(self.bitacora_repo, self.db, EventoAuditoria(...))
```

Ningún kwarg de `EventoAuditoria(...)` cambió — es un reemplazo mecánico del
try/except por la llamada al helper. Cuando el bloque llevaba un
`self.db.rollback()` de la operación de negocio antes del intento de
auditoría (la rama de fallo), ese rollback se conserva intacto — es distinto
del rollback interno del helper, que solo protege su propio intento de
escritura.

`_auditoria_rechazos.py` no se tocó: sus dos `except Exception:` no están en
los 30 (uno ya lleva un comentario justificando por qué se descarta —
enriquecer con datos del activo, no la escritura de auditoría en sí — y el
otro hace `db.rollback()`, no `pass`).

## Verificación

- `grep -rn "except Exception:" src/biological_assets/application/use_cases/ -A1 | grep -B1 "pass$"` → sin resultados.
- `tests/biological_assets/test_registrar_evento_bitacora.py` (nuevo): sin
  `bitacora_repo` no hace nada; escritura exitosa comitea; escritura que
  falla NO propaga la excepción, hace rollback, deja un `logger.error` y una
  línea en `logs/audit_fallback_M02_*.log` con `tipo_evento`,
  `id_activo_biologico`, `id_usuario_responsable` y el error — 3/3 pasan.
- `pytest tests/ -q`: 633 passed, 180 skipped, **2 failed** — ambos en
  `test_registrar_transferencia_use_case.py`
  (`test_endpoint_fecha_futura_responde_422_con_campo_y_mensaje` y
  `test_fecha_actual_conserva_el_flujo_existente`), confirmados
  **preexistentes en `dev`** corriéndolos con este cambio revertido
  (`git stash`) antes de tocar nada — no los causó este PR.

## Fuera de alcance (para Análisis/Desarrollo)

RF-52 restricción 3 cita a RF-49 (`asociar_sensor_activo_use_case.py`) como
el único RF que debería revertir su operación si la auditoría no está
disponible. Hoy no lo hace: la asociación sensor→activo se comitea en su
propia transacción, y el evento `ASOCIACION_IOT_CREADA` es un best-effort
posterior. Hacerlo estrictamente transaccional (una sola escritura atómica
asociación+bitácora) es un cambio de arquitectura mayor que "dejar de
descartar en silencio" y no estaba entre los criterios de aceptación de este
issue — se deja documentado para una decisión aparte.
