# TC-M02-G77 — Consolidación de la ficha integral del activo

**CU-10B · RF-47 — Ficha Integral del Activo Biológico.**

| Campo | Valor |
|---|---|
| Sub-casos | (TC-M02-127) Ficha completa · (TC-M02-128) Sección vacía · (TC-M02-129) Fallo parcial de módulo fuente · (TC-M02-130) Advertencia de inconsistencia |
| Tipo | Funcional / Integración |
| Herramienta | Frontend / API — Cypress + Postman (ejecutado solo API — ver nota) |
| Endpoint | `GET /activos-biologicos/{id_activo}/ficha-integral` |
| Responsable | Juan Manuel · Prioridad Media |

## Resultado vigente (2026-09-26): 12/13 assertions — TC-M02-127 sigue FAIL en TEST, pero ya corregido en `dev` (pendiente de despliegue)

La colección se re-ejecutó **sin cambios** (sigue siendo de solo lectura: activos existentes 5, 10 y 8).

| Sub-caso | Resultado (2026-09-26) |
|---|---|
| TC-M02-127 — Ficha completa | **FAIL en TEST**: secciones 1-7 presentes, pero la respuesta no trae `accesos_directos` (Sección 8) |
| TC-M02-128 — Sección vacía | PASS: `eventos_sanitarios = []`, ficha 200 |
| TC-M02-129 — Fallo parcial de módulo fuente | Corregido en código y desplegado; sigue sin forzarse en vivo (ver abajo) |
| TC-M02-130 — Advertencia de inconsistencia | PASS: activo 8 `CERRADO` con fase activa, 200 con advertencia |

### TC-M02-127: la Sección 8 está implementada en `dev`, pero no desplegada en TEST

- `9528c8c3 feat(m02): agregar accesos directos y densidad real a la ficha integral (RF-47)` (2026-09-24) agrega
  `accesos_directos` (historial, registrar evento, cambiar estado, registrar baja, filtrados por el permiso de cada
  endpoint) al schema de respuesta.
- TEST se despliega desde la rama `test` (`.github/workflows/migrate-test.yml`), y ese commit **está en `origin/dev`
  pero todavía no en `origin/test`** (verificado con `git merge-base --is-ancestor`). La respuesta en vivo de
  `GET /activos-biologicos/5/ficha-integral` no trae la clave.
- No es un defecto nuevo de código sino una promoción pendiente de `dev` → `test`. La assertion ya exige el campo,
  así que el caso pasará sin cambios cuando se despliegue.

### TC-M02-129: fallo parcial ya manejado por sección

`4f63a9dc fix(rf47): una seccion que no carga ya no tumba la ficha integral` (ya en `origin/test`) envuelve cada
sección en `_seccion()` (`consultar_ficha_integral_use_case.py`): cada una carga en su propio savepoint y, si falla,
la ficha responde 200 con `advertencias` = "La sección {nombre} no pudo cargarse en este momento." en vez de 500.
Cubierto por tests unitarios del repo (`test_rf47_seccion_caida_no_tumba_la_ficha` en
`tests/biological_assets/test_gaps_flujo_alterno_m02.py`, `test_vista_base_caida_no_tumba_la_ficha` en
`test_rf47_ficha_integral.py`), no ejecutados en esta sesión (importan `fcntl`, que no existe en Windows). Forzar el
fallo en vivo sigue requiriendo romper una vista compartida de TEST, así que no se hizo. El texto exacto del RF
("Información no disponible. [Actualizar]") es responsabilidad del frontend.

Evidencia: `RESULTADOS/TC-M02-G77_resultado.html` (Newman htmlextra, 2026-09-26).

---

## Histórico (2026-09-19): 3/4 sub-casos PASS, 1 FAIL confirmado (falta la Sección 8), 1 no reproducible en vivo sin riesgo

**13/14 assertions PASS.** Re-confirmado hoy, mismo resultado exacto que las ejecuciones anteriores (2026-09-09 y
2026-09-15) — este caso solo hace `GET /ficha-integral` sobre activos ya existentes, no crea nada, así que nunca
dependió de la regresión de migración que afectó a otros casos de este módulo (ver `RESULTADOS/TC-M02-G77_resultado.html`).

### Datos usados: reales, ya existentes en TEST — no se creó nada nuevo

Para TC-M02-127, TC-M02-128 y TC-M02-130 se usaron activos **ya existentes** en el entorno compartido (5, 10 y 8),
en vez de crear datos nuevos: el escenario de TC-M02-130 (activo en `CERRADO`/`BAJA` con una fase productiva **aún
activa**) ya existe de forma natural en TEST — se encontró consultando la base de datos (solo lectura) antes de
diseñar el caso, sin necesidad de construir la inconsistencia artificialmente. Reutilizar datos reales evita crear
más activos de prueba de los estrictamente necesarios.

### TC-M02-127 — FAIL confirmado: no existe la Sección 8 (accesos directos)

La respuesta de `GET /ficha-integral` **no tiene ningún campo** de "accesos directos" — ni la entidad `FichaIntegral`
(`domain/entities/activo_biologico.py`) ni el schema de respuesta lo declaran. Las 7 secciones restantes
(identificación, estado/fase, ubicación, datos biológicos, eventos recientes, indicadores, datos de lote) sí están
presentes y se verificaron una por una. Esto coincide con un gap ya documentado en la auditoría del módulo
(`anotaciones/modulo_2/estado.md`, RF-47): *"No existe la Sección 8 (Accesos directos) en absoluto... Gap real, no
cosmético."* Esta ejecución lo confirma en vivo contra TEST.

### TC-M02-128 — PASS a nivel de API; el texto "Sin información registrada" es responsabilidad del frontend

`eventos_sanitarios` se devuelve como un arreglo vacío `[]`, sin error ni sección omitida — el contrato de datos
correcto para que el frontend renderice el mensaje. **No se verificó el renderizado visual real** ("Sin información
registrada" en pantalla) porque esta sesión trabajó contra el backend vía API; verificar el texto exacto en la UI
requiere una prueba Cypress contra el frontend desplegado, fuera del alcance de esta ejecución.

### TC-M02-129 — no se pudo forzar un fallo real sin arriesgar romper una vista compartida

Se consultó la ficha integral de 4 activos distintos (incluyendo uno con indicadores poblados) y en ningún caso
`vw_rf47_indicadores_zootecnicos_activo` falló — no hay forma de "apagar RF-51 temporalmente" sin modificar un
objeto de base de datos compartido por todos los usuarios de TEST, algo que esta sesión decidió no hacer por el
riesgo que implica para el resto del equipo. Por lectura de código sí se confirma el gap que este sub-caso busca
detectar: `_indicadores()` (y las demás funciones de sección) en `consultar_ficha_integral_use_case.py` **no tienen
ningún `try/except` individual** — si esa consulta fallara, la excepción se propagaría sin control y probablemente
tumbaría toda la ficha (500), en vez de mostrar "Información no disponible. [Actualizar]" solo en esa sección como
exige el RF. Ya señalado en la auditoría del módulo: *"Sin manejo granular de fallo parcial por sección."* No se
marca como incidente nuevo — ya estaba documentado — pero se confirma que sigue vigente en el código actual.

### TC-M02-130 — PASS completo

Activo 8 (CERRADO, fase "Ciclo completo mojarra 2025-A" aún activa): la ficha se muestra completa (200), con la
advertencia exacta y el resto de secciones cargadas con normalidad — comportamiento correcto y ya bien
implementado.

### Entorno

- Backend TEST: `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`.
- Cuenta: `admin.test@sgpmp.com.co`. Activos usados (ya existentes, no creados por esta sesión): `5`, `10`, `8`.
- Newman 6.2.2 + htmlextra 1.23.1. Fecha de ejecución: 2026-09-19.

### Cómo re-ejecutar

```bash
cd tests/Test_Testing/Test_Modulo2/RF-47/TC-M02-G77
newman run TC-M02-G77.postman_collection.json -r cli,htmlextra \
  --reporter-htmlextra-export RESULTADOS/TC-M02-G77_resultado.html \
  --suppress-exit-code
```

Esta colección es de solo lectura — no crea ni modifica ningún dato, solo consulta activos ya existentes en TEST.
