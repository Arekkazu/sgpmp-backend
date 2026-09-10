# TC-M02-G33 — BLOQUEO: mismo defecto de RF-37 ya documentado en TC-M02-G23 (RF-35), más un gap estructural nuevo

## 1. Bloqueo compartido — INC-M02-37-01 (ya documentado, re-confirmado aquí)

`POST /activos-biologicos/{id}/fases` responde **500** para cualquier activo/ciclo válido. Causa raíz **confirmada
por código** (no es una hipótesis): `cambiar_fase_use_case.py:72` llama
`self.repo.cerrar_gestion_activa(id_activo, ahora, dto.motivo_cambio or '')` con 3 argumentos, pero
`activo_biologico_repository.py:386` exige 4 (`def cerrar_gestion_activa(self, id_activo, fecha_fin, motivo,
usuario_id)`) — falta `usuario_id` en la llamada → `TypeError` no controlado.

Detalle completo, con el mismo bug reproducido sobre 9 combinaciones distintas de activo/ciclo en la sesión
anterior: `tests/Test_Testing/Test_Modulo2/RF-35/TC-M02-G23/NOTA_BLOQUEO.md`. **Re-confirmado aquí** el
2026-09-10 sobre un activo nuevo (id 201, especie 2/Trucha) con el ciclo productivo documentado para esa misma
especie (`id_ciclo_productiva=2`):

```
POST /activos-biologicos/201/fases {"id_ciclo_productiva":2,"motivo_cambio":"..."}
→ HTTP 500 {"error_code":"ERROR_INTERNO","message":"Ocurrió un error interno..."}
```

**Fix (una línea, sin tocar otra lógica):**
```python
# cambiar_fase_use_case.py:72
self.repo.cerrar_gestion_activa(id_activo, ahora, dto.motivo_cambio or '', usuario.id_usuario)
```

Reportado como incidente: **INC-M02-37-01** (Crítico, Desarrollo, mismo día).

## 2. Gap adicional, específico de TC-M02-042 — no depende del bug anterior

`CambiarFaseDTO` (`src/biological_assets/infrastructure/dto/cambiar_fase_dto.py`) declara únicamente
`id_ciclo_productiva`, `motivo_cambio` y `fecha_inicio`. **No existe** `confirmacion_no_estandar` ni
`fase_destino_id`. Enviarlos no produce error (Pydantic los descarta, `extra='ignore'` por defecto de `BaseDTO`) —
el use case (`CambiarFaseUseCase.execute()`) siempre calcula la siguiente fase de forma automática
(`fase_siguiente_idx = len(gestiones_en_ciclo)`), sin ninguna rama para saltar a una fase específica ni para
registrar una confirmación explícita.

Consecuencia: **incluso corrigiendo INC-M02-37-01, TC-M02-042 no puede pasar** — el concepto de "transición no
estándar con confirmación" que pide el RF y este caso de prueba no tiene ninguna vía de entrada en la API actual.
Ya señalado en `anotaciones/modulo_2/estado.md` (RF-37): *"El modelo de 'fase destino + confirmación de transición
no estándar' del RF no está implementado"*.

**Para desbloquear (requiere diseño, no es un fix de una línea):**
1. Agregar `fase_destino_id: Optional[int]` y `confirmacion_no_estandar: bool = False` a `CambiarFaseDTO`.
2. En `CambiarFaseUseCase.execute()`, si `fase_destino_id` viene informado y no coincide con la siguiente fase
   secuencial: exigir `confirmacion_no_estandar=True` (rechazar con 409 si no viene) y usar el índice de
   `fase_destino_id` dentro de `ciclo.fases` en vez de `fase_siguiente_idx` calculado automáticamente.
3. Registrar la confirmación explícita en `motivo_cambio` o en un campo dedicado del historial, para que quede
   "evidencia de la confirmación en el historial" como exige el resultado esperado del caso.

## Cómo re-verificar

Tras el fix de INC-M02-37-01:
```bash
newman run "tests/Test_Testing/Test_Modulo2/RF-37/TC-M02-G33/TC-M02-G33.postman_collection.json" \
  -r cli,htmlextra --folder "1. TC-M02-039 - Registrar cambio de fase estandar valido"
```
debería pasar de 500 a 201. El paso "3" (TC-M02-042) seguirá en 500/ignorando los campos hasta que se implemente
el punto 2 de la lista anterior.
