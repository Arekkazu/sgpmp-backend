# Verificación en vivo RF-93/RF-94 (Módulo 6) contra TEST

**Fecha:** 2026-11-12
**Herramienta:** Newman/Postman (`tc_m06_rf93_rf94_live.postman_collection.json`)
**Entorno:** TEST (`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`)

## Por qué esta colección

Las 24 pruebas `pytest` de RF-93/RF-94 (carpetas `RF-93/TC-M06-G71..G82` y `RF-94/TC-M06-G83..G94`,
renombradas por el equipo de desarrollo el 2026-11-08 desde su numeración original G01-G12/13-24) corren
100% en local, sin base de datos — usan `MagicMock` e inspección de código fuente. Confirman la AUSENCIA
o presencia de código Python, pero son ciegas a cualquier control implementado a nivel de PostgreSQL.

Al actualizar el checkout contra `origin/test` (2026-11-11/12) apareció la migración
`alembic/versions/4fa0e24ea021_rls_modulo_06.py` (RLS Módulo 6, 2026-11-07, autor SamuelPR21): Row-Level
Security sobre las 25 tablas de `modulo6`, como "segunda línea de defensa del RBAC: por rol y por estado
del período contable". Esto puede cambiar el comportamiento real sin que ningún `pytest` lo detecte.

## Hallazgo principal confirmado aquí

**INC-M06-006 (TC-M06-G11, RF-93) queda CORREGIDO** — no por el código Python de la aplicación (que
sigue, verificado, sin ninguna validación de `estado` en `obtener_estado()`), sino por la política RLS
`pol_estado_resultados_periodo_select` sobre `modulo6.estados_resultados_periodo`:

```
estado_resultados:R AND (VISION_COMPLETA OR estado = 'APROBADO')
```

Confirmado con el ciclo completo en TEST:
- Un estado `GENERADO` (id_estado=38, período 219) responde `404 ESTADO_RESULTADOS_NO_ENCONTRADO` tanto
  para Productor como para Revisor Fiscal (ninguno tiene "visión completa").
- Se aprobó deliberadamente el estado `id_estado=32` (período 253, NIT 901458732) como Contador — acción
  autorizada explícitamente por el usuario en esta sesión, dado que es irreversible (el trigger de
  inmutabilidad de M06 solo permite la transición GENERADO→APROBADO).
- Tras la aprobación, el mismo Productor obtiene `200` tanto en la consulta como en la descarga del estado
  — confirma que la RLS libera el acceso exactamente cuando `estado = 'APROBADO'`, y que "exportar" sigue
  siendo la misma acción RBAC que "consultar" (ya no es un problema: ambas quedan correctamente gateadas).

**Importante:** `id_estado=32` quedó `APROBADO` de forma permanente en TEST. Esta colección ya no puede
reproducir el ciclo GENERADO→APROBADO completo con ese id; solo la mitad "ya aprobado". Si se necesita
repetir el ciclo completo, usar otro `id_estado` todavía en `GENERADO` (verificar primero con el Contador).

## Actualización 2026-11-13 — respuesta de Análisis/Diseño sobre los hallazgos "para análisis"

El equipo de Análisis/Diseño respondió sobre los 7 TC que seguían en rojo por "para análisis"
(G74, G80, G85, G86, G88, G89, G90). Resultado tras incorporar la respuesta:

- **G85, G86, G88, G89, G90 → NO SON DEFECTOS, cerrados.** Se decidió mantener la auditoría de
  RF-94 en la misma transacción que la operación auditada (RF-86, RNF de Fiabilidad). Por esa
  decisión no aplican la asincronía (G85), la validación de "evento recibido de un emisor
  externo" (G86), ni el fallback local/HASH_CALCULO_FALLIDO (G89/G90). G88 se deja como está:
  RF-94 solo exige cortar a 64 KB y marcar el truncado, y eso se cumple. Los 33 pytest de estos
  5 TC se convirtieron de `pytest.fail()` a `assert` y pasan 100%.
- **Falso positivo corregido en G90:** 2 subtests venían pasando en verde por error -- coincidían
  con la aparición literal de `"FALLBACK"` en `m06_router.py` como valor del filtro de consulta
  `origen_registro: Optional[Literal["REPOSITORIO", "FALLBACK"]]` de `GET /finanzas/auditoria`
  (un filtro, no un mecanismo implementado). Corregido para excluir ese uso.
- **G74, G80 → resueltos en diseño, pendientes de despliegue a TEST (PR #1121).** El mecanismo
  real de conciliación no usa `/reconciliation-check` ni `/alerts`: la verificación corre en la
  propia generación del estado (`422 ESTADO_RESULTADOS_NO_CONCILIA`, con detalle de qué
  variación/producto agrícola falta y de qué activo), se registra `ERROR_CONCILIACION` en la
  bitácora de RF-94 y se avisa al Contador. Mientras el PR #1121 no se despliegue, el código de
  este checkout sigue sin ese mecanismo -- los 7 pytest afectados se mantienen en rojo, pero con
  el mensaje reclasificado a "PENDIENTE DE DESPLIEGUE" (no "hallazgo sin solución"). Re-verificar
  tras el despliegue (el equipo de desarrollo avisará antes).

## Actualización 2026-11-14 — rol Auditor confirmado en vivo

El usuario proporcionó una cuenta real del rol Auditor (`auditor.rol@gmail.com`, `id_rol=81`), creado por
el DBA en TEST el 2026-11-13 (issue #1087, INC-M06-361-G93b). Confirmado en vivo:
- Login funciona; el rol tiene acceso real a `GET /finanzas/auditoria`, `/finanzas/activos` y
  `/finanzas/lineas` — más permisos de los que la migración `810b1e4eb4f9` por sí sola otorgaría (el DBA
  configuró el RBAC completo al crear el rol, no solo lo automático de esa migración).
- **El mismo hueco de alcance por período/titular (INC-M06-012) también afecta al Auditor**: puede
  consultar auditoría de un período de un titular (NIT) sin ninguna relación con él, igual que
  Contador/Revisor Fiscal — confirma que el gap es transversal a los 3 roles con acceso, no solo a 2.
- El Auditor **no** tiene permiso sobre `estado_resultados` (403) — consistente con su alcance (auditoría +
  reconocimiento + trazabilidad, no Estado de Resultados); no es un hallazgo, es el diseño esperado.

## Otros hallazgos reconfirmados en código corriendo

- **INC-M06-003 (G04, RF-93):** `GET /finanzas/reconciliation-check` y `GET /finanzas/alerts` siguen sin
  existir (404) — no hay mecanismo de conciliación/alerta.
- **INC-M06-012 (TC23, RF-94) — rol Auditor: CERRADO** (ver arriba); **alcance por período/titular: SIGUE
  ABIERTO** — Revisor Fiscal, Auditor (y por extensión Contador) pueden consultar auditoría de un período
  de un titular distinto al suyo sin ningún filtro.
- **INC-M06-013 (TC24, RF-94):** en `formato=TECNICO`, el campo `modulo` del evento es siempre `"M06"` y
  `origen_registro` siempre `"REPOSITORIO"` — confirma que no existe repositorio centralizado cross-módulo
  ni mecanismo de fallback real. `GET /api/v1/audit/events` sigue sin existir (404).

## Cómo correrlo

```powershell
cd tests/Test_Testing/Test_Modulo6/RF-93-94-Verificacion-Live
npx newman run tc_m06_rf93_rf94_live.postman_collection.json `
  -r cli,htmlextra --reporter-htmlextra-export resultados/resultado_live_rf93_rf94.html
```

No requiere `permitir_escritura` como variable porque el único paso de escritura real (aprobar
`id_estado=32`) ya se ejecutó y es irreversible; de aquí en adelante la colección es de solo lectura.
