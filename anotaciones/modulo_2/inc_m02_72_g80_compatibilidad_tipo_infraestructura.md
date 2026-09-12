# INC-M02-72-G80 — Transferencia permite mover bovino a infraestructura Estanque incompatible

**RF:** RF-48 — Registrar transferencia interna (CU10C)
**Endpoint:** `POST /activos-biologicos/{id_activo}/transferencias` y `GET .../transferencias/disponibles`

## Causa raíz (confirmada por QA en el propio reporte)

No existía ningún modelo de compatibilidad entre el tipo de infraestructura
(catálogo administrable `modulo9.tipos_area`: Corral, Estanque, Galpón,
Invernadero) y la especie del activo — la regla **C2** de RF-48. Ni el use case,
ni el listado de destinos disponibles, ni ningún trigger de BD la validaban.
Un bovino `INDIVIDUAL` se transfería sin rechazo a una infraestructura tipo
`Estanque`, quedando persistido como si fuera válido (movimiento, historial y
ocupación reales).

## Decisión de diseño

Se creó `modulo9.compatibilidades_tipo_area_especie` (FK a `modulo9.tipos_area`
y `modulo9.especies`, `uq_compatibilidad_tipo_area_especie` sobre el par) en vez
de:

- **Agregar una columna `categoria` a `modulo9.especies`** (ej. terrestre/acuático):
  hubiera sido un cambio más invasivo a una tabla ya usada por otros módulos, y
  no resuelve el caso real más simple que una tabla de asociación directa.
- **Un CHECK o trigger de BD codificando la regla**: la lista de tipos y especies
  compatibles es dato de negocio que crecerá (nuevas especies, nuevos tipos de
  infraestructura) — igual que RBAC en este proyecto, se prefiere una tabla
  administrable a lógica fija en código o en un CHECK.

**Semántica elegida — permisiva por defecto, restrictiva por configuración:**
si un `tipo_infraestructura` no tiene ninguna fila en la tabla, es compatible
con cualquier especie (sin regla definida todavía, no rompe infraestructuras
existentes sin clasificar). En cuanto existe al menos una fila para un tipo,
esa lista es la lista blanca completa para ese tipo. Evita tener que sembrar
compatibilidad para los 4 tipos × todas las especies de una sola vez.

## Qué se sembró

Solo el caso real confirmado por QA: `Estanque` es compatible únicamente con
las especies acuícolas ya existentes en el catálogo (`Trucha Arcoíris`,
`Camarón Blanco`, `Cachama Blanca`, `Mojarra Plateada`, `Tilapia`, `Tilapia Roja`).
El seed matchea por **nombre**, no por `id_especie` (los ids difieren entre
`sgpmp`/`pruebas` y el ambiente TEST real de QA) — si un nombre no existe en la
base donde corre la migración, simplemente no inserta esa fila, no falla.

`Corral`, `Galpón` e `Invernadero` quedan sin ninguna regla (compatibles con
cualquier especie) — no hay en este dev/pruebas ninguna clasificación de qué
especies corresponden a esos tipos. **Pendiente para quien administre el
ambiente TEST real de QA** (mismo patrón que INC-M02-90-G92/#241): sembrar ahí
las reglas reales para sus propias especies (bovino, aves, etc.) usando la
misma tabla — es dato de configuración, no requiere otra migración.

## Fix de código

- `InfraestructuraConsultaPort.es_tipo_compatible(tipo_infraestructura, id_especie)`
  (nuevo método del puerto ya existente, no un puerto nuevo).
- `InfraestructuraM09Adapter` lo implementa consultando la tabla nueva.
- `RegistrarTransferenciaUseCase.execute()`: nuevo paso `E-07b` (entre C1 especie
  y alcance por finca) que rechaza con `BusinessRuleError(INCOMPATIBILIDAD_TIPO_INFRAESTRUCTURA)`.
- `listar_infraestructuras_disponibles`: mismo filtro aplicado al listado, para
  que "disponible" siga implicando "transferible" (ya establecido por INC-M02-74-G80).

Sin cambios de contrato de respuesta (mismo shape JSON en ambos endpoints).

## Pruebas

- `tests/biological_assets/test_registrar_transferencia_c2_tipo_infraestructura.py`
  (nuevo, unitario con fakes): rechaza bovino→Estanque, permite pez→Estanque,
  filtra el listado.
- `tests/integration/test_inc_m02_72_g80_compatibilidad_tipo_infraestructura.py`
  (nuevo, contra Postgres real vía `TEST_DATABASE_URL`): valida el adapter y el
  seed real contra `pruebas` — bovino (`Miguel`, id 11) rechazado, `Tilapia`
  aceptada, tipo sin regla configurada (`Corral`) sigue sin restricción.
- Migración aplicada y verificada en `sgpmp` y `pruebas` (misma tabla, mismo seed).
- Suite completa `tests/`: 574 passed, 169 skipped (sin regresiones). Suite de
  integración completa contra `pruebas`: mismos 7 fallos preexistentes y no
  relacionados (gap de RBAC en `/configuracion/tipos-area` y dos casos de M01),
  confirmado reproduciéndolos también sin este cambio aplicado (`git stash`).
