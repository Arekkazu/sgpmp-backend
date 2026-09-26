# TC-M02-G33 — [RESUELTO 2026-09-19] INC-M02-37-01, más un gap estructural que sigue vigente

## 1. Bloqueo compartido — INC-M02-37-01 [RESUELTO]

> **Actualización 2026-09-19:** confirmado resuelto en TEST. `cambiar_fase_use_case.py` ya pasa `usuario.id_usuario`
> como 4to argumento a `cerrar_gestion_activa`. `POST /activos-biologicos/{id}/fases` responde `201` para
> TC-M02-039. Se conserva el detalle original abajo como registro histórico.

`POST /activos-biologicos/{id}/fases` respondía **500** para cualquier activo/ciclo válido. Causa raíz **confirmada
por código** (no fue una hipótesis): `cambiar_fase_use_case.py:72` llamaba
`self.repo.cerrar_gestion_activa(id_activo, ahora, dto.motivo_cambio or '')` con 3 argumentos, pero
`activo_biologico_repository.py:386` exige 4 (`def cerrar_gestion_activa(self, id_activo, fecha_fin, motivo,
usuario_id)`) — faltaba `usuario_id` en la llamada → `TypeError` no controlado.

Detalle completo, con el mismo bug reproducido sobre 9 combinaciones distintas de activo/ciclo en la sesión
anterior: `tests/Test_Testing/Test_Modulo2/RF-35/TC-M02-G23/NOTA_BLOQUEO.md`.

Reportado como incidente: **INC-M02-37-01** (Crítico, Desarrollo).

## 2. Gap adicional, específico de TC-M02-042 — [RESUELTO 2026-09-26, con un defecto residual]

> **Actualización 2026-09-26:** `fase_destino_id`/`confirmacion_no_estandar` ya están implementados (`15c4611e`,
> llegó con el merge de `dev`). El salto confirmado se acepta y respeta el destino (`paso_actual=3`). Queda un
> defecto residual, documentado en `README.md`: `es_transicion_no_estandar` no se persiste en
> `modulo2.gestiones_fases`, así que el historial (`GET .../fases`) lo muestra siempre en `false`. Se conserva el
> detalle original abajo como registro histórico.

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

## Cómo re-verificar tras implementar el punto 2

```bash
newman run "tests/Test_Testing/Test_Modulo2/RF-37/TC-M02-G33/TC-M02-G33.postman_collection.json" \
  -r cli,htmlextra --reporter-htmlextra-export RESULTADOS/TC-M02-G33_resultado.html
```

El paso "3" (TC-M02-042) pide `fase_destino_id=3` (saltar directo a la fase 3, saltando la 2) con
`confirmacion_no_estandar=true`, y hoy (2026-09-19) sigue devolviendo `paso_actual=2` — confirma que el campo se
ignora y el sistema siempre avanza secuencial. El día que se implemente el punto 2 de la lista anterior, la
respuesta debería traer `paso_actual=3` y este assert pasará automáticamente.
