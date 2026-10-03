# INC-M02-89-G83 — E-05 no distingue destino inexistente de destino inactivo (mejora de usabilidad)

**RF:** RF-48 — Transferencia Interna de Activos Biológicos (CU10C).
**Endpoint:** `POST /activos-biologicos/{id_activo}/transferencias`.
**Caso QA:** `TC-M02-308` (grupo `TC-M02-G83`) — observación, no defecto funcional.

## Qué reportó QA

`E-05` (`INFRAESTRUCTURA_DESTINO_INVALIDA`) devuelve el mismo mensaje genérico ("La infraestructura con id N no existe o no está activa.") tanto cuando la infraestructura destino no existe (`TC-M02-308-A`, id `99999`) como cuando existe pero está inactiva (`TC-M02-308-B`, id `50`, `es_activo=false`). QA es explícito: "el comportamiento coincide con la matriz actual y no constituye un defecto funcional" — se registra únicamente como mejora de usabilidad, sin impacto en aplicación de la regla, persistencia, seguridad o el veredicto de `G83`.

## Fix

Nuevo método en el puerto `InfraestructuraConsultaPort`: `existe(id_infraestructura) -> bool`, que verifica existencia sin importar el estado activo (a diferencia de `obtener_activa`, que devuelve `None` tanto si no existe como si está inactiva y no permite distinguir). Implementado en `InfraestructuraM09Adapter.existe()` con un simple `db.get(...) is not None`.

`RegistrarTransferenciaUseCase._execute()`, en `E-05`: cuando `infra_destino is None`, se llama `self.infra_port.existe(dto.infraestructura_destino_id)` para elegir el mensaje:

- Existe pero inactiva → `"La infraestructura con id {id} se encuentra inactiva."`
- No existe → `"La infraestructura con id {id} no existe."`

El `error_code` (`INFRAESTRUCTURA_DESTINO_INVALIDA`) y el `field` no cambian — solo el texto del mensaje.

**Nota de secuencia con `INC-M02-88-G83`:** ese ticket (aún no mergeado a `dev` al momento de este PR) cambia `E-05` de `ValidationError` (400) a `BusinessRuleError` (422); este PR se hizo sobre `origin/dev` limpio (sin ese cambio todavía) y por lo tanto sigue usando `ValidationError` — el mensaje diferenciado aplica igual sin importar cuál PR se mergee primero; si hay conflicto de merge entre ambos, es solo en la línea de la clase de excepción, trivial de resolver.

## Pruebas

`tests/biological_assets/test_registrar_transferencia_mensaje_destino_inactivo.py` (nuevo, 2 casos):

- Destino inexistente (`99999`) → mensaje `"...no existe."` (reproduce `TC-M02-308-A`).
- Destino existente pero inactivo (`50`) → mensaje `"...se encuentra inactiva."` (reproduce `TC-M02-308-B`).

Suite completa sin regresiones: 660 passed (658 previos + 2 nuevos), mismos 2 fallos preexistentes en `test_registrar_transferencia_use_case.py` (no relacionados).

## Fuera de alcance

Nada más — este ticket es puramente de redacción de mensaje, sin cambios de regla de negocio, código de error ni status HTTP.
