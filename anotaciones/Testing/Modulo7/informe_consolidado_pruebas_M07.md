# Informe consolidado de pruebas — Módulo 7 (Integración contable con AgroFusión) — v1.0
## Resumen de resultados y entrega formal a Desarrollo

| Campo | Valor |
|---|---|
| Módulo | M07 — Integración contable (`src/accounting_integration/`) |
| Alcance | RF-95, RF-96, RF-97, RF-98, RF-101, RF-102, RF-AE01 y RF-AE02 (8 requisitos activos). RF-99 (Webhooks) está diferido y fuera de alcance |
| Período de ejecución | 2026-11-17 a 2026-11-21 |
| Fecha de corte del informe | 2026-11-21 |
| Ambiente | Backend TEST (`https://api.inmero.co/api-sgpmp-test`); los retests de RF-95, RF-98 y RF-101 corrieron contra el release `1.4.0-rc.80` |
| Herramientas | Newman/Postman, pytest, k6, Cypress (G036, pantalla de versiones) y runners propios con rollback en sandbox |
| Casos ejecutados | 54 de 54 (100 %) |
| Equipo QA | Julian Badillo (RF-95, RF-101), Juan Parra (RF-96, RF-97), Juan Esteban (RF-98), Laura López (RF-102), María José (RF-AE01 y RF-AE02) |
| Umbral de aceptación | **≥ 85 % de casos aprobados** |
| Fuente de datos | Panel QA (`QA-DASHBOARD-SGRPMP/`), evidencias en `tests/Test_Testing/Test_Modulo7/` e incidencias en `tests/Test_Testing/Test_Modulo7/incidencias/` y `anotaciones/modulo_7/` |

> Los conteos reflejan el estado del repositorio a la fecha de corte. Un caso reejecutado después puede cambiar de veredicto. Cuando un caso tiene varias corridas (V1, V2, V3), el veredicto vigente es el de la última.

---

## 1. Resumen ejecutivo

| Indicador | Cantidad | % |
|---|---:|---:|
| Casos | 54 | 100 % |
| Aprobados | **53** | **98.1 %** |
| Rechazados | 1 | 1.9 % |
| Pendientes | 0 | 0.0 % |

**El módulo supera el umbral de aprobación del 85 % (98.1 %).** Queda un caso rechazado, TC-M07-G035 (rendimiento y concurrencia de RF-97), por un defecto abierto de severidad Alta en TEST (INC-M07-376-G035). Su detalle está en la sección 4.

### Verificación de los criterios de salida

| # | Criterio | Umbral | Resultado | Cumple |
|---|---|---|---|:---:|
| 1 | Casos con veredicto Aprobado | ≥ 85 % | **53/54 = 98.1 %** | ✅ |
| 2 | RF con al menos un caso ejecutado | 100 % | **8/8** (RF-99 diferido, excluido) | ✅ |
| 3 | Informe consolidado con la plantilla completa | Completo | Este documento (pendiente de firmas) | ✅ (firmas pendientes) |

> Como en M06 y M09, este informe no evalúa el criterio de defectos Crítico/Severo sin plan de mitigación. El único defecto abierto con impacto en un caso es de severidad Alta y está en la sección 4.

---

## 2. Resultados por requisito

| RF | Título | Casos | Aprob. | Rech. | Pend. | % Aprob. | Veredicto |
|----|--------|------:|------:|-----:|-----:|--------:|-----------|
| RF-95 | Gateway de API REST del sistema | 6 | 6 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-96 | Transformadores de datos (Mappers) | 12 | 12 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-97 | Exportación de datos financieros al sistema externo | 12 | 11 | 1 | 0 | 92 % | ⚠️ Parcial |
| RF-98 | Gestión de versiones del contrato de integración | 6 | 6 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-101 | Gestión de credenciales y clientes externos | 6 | 6 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-102 | Auditoría y trazabilidad del módulo de integración | 7 | 7 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-AE01 y RF-AE02 | Consulta AAEF (validaciones y límites) y Anexo de mapeo | 5 | 5 | 0 | 0 | 100 % | ✅ Aprobado |
| **Total** | | **54** | **53** | **1** | **0** | **98.1 %** | |

RF-AE01 y RF-AE02 comparten carpeta de pruebas (`RF-AE01/`, casos G059 a G063): G059 y G060 cubren la consulta y sus validaciones, G061 los importes del Mapper de Compras, y G062 y G063 el ciclo de vida del Anexo de mapeo y su auditoría. RF-99 no tiene casos: el requisito está diferido sin receptor (RFC-017 D-17.8) y solo se confirma que no esté expuesto en TEST.

---

## 3. Cobertura y método

- **Evidencia por caso:** reporte de ejecución (HTML/JSON/XML) en `Resultados/` o `resultados/`. Las reevaluaciones guardan además un acta `.md` en `EvaluacionV2/` o `EvaluacionV3/`.
- **Escrituras en TEST:** los casos que crean o cambian datos (RF-98, RF-101, RF-AE02) se ejecutaron en un sandbox con `X-Test-Run-Id` y rollback al terminar (`DELETE /test-control/runs/{id}`), comparando el estado antes y después.
- **Reevaluaciones:** G036 a G040 (RF-98) y G002, G043 y G047 (RF-95 y RF-101) se rechazaron o fallaron en la primera corrida y se aprobaron tras la corrección. Su veredicto vigente es el de la última corrida.
- **Rendimiento (G035):** se usó k6 v1.6.1 contra TEST. JMeter no estuvo disponible.
- **Limitaciones de ambiente:** los datos de TEST cambian entre corridas por el trabajo de otros equipos (por ejemplo, las versiones de contrato vigentes), por lo que los runners eligen sus datos en vivo antes de escribir.

### Casos aprobados con alcance delimitado

| TC | RF | Alcance de la aprobación |
|---|---|---|
| G019 | RF-96 | Aprobado por prueba unitaria: el `LineType` ya se valida contra la matriz contable (`_exigir_catalogo()`). En los datos reales de TEST una fila comodín hace inalcanzable `LINETYPE_NO_CATALOGADO` (INC-M07-378-G019, de datos de prueba) |
| G025 | RF-97 | Las 10 aserciones pasan. Dos hallazgos quedan registrados: el `ExchangeId` real (`AF-SIGAB-AAAA-MM-nonce`) no coincide con la ficha, porque el formato lo exige SIGCON y debe actualizarse la ficha; y `SourceSystem.Environment` dice `DEV` en TEST (INC-M07-377-G025, abierta, de configuración de despliegue) |
| G027 | RF-97 | Aprobados los tres negativos de rango (422 `RANGO_NO_ALINEADO`, 422 de período abierto, 400 con rango invertido). No se verificaron la periodicidad trimestral ni el mes sin período abierto, porque TEST no tiene un titular con esa configuración |
| G035 | RF-97 | Rechazado (sección 4). Del caso solo se confirmó el aislamiento entre titulares y el determinismo del hash; no se confirmaron RNF-97.1 (2.000 facturas), RNF-97.7 (escalado) ni CA-14 (AgroFusión real) |
| G040 | RF-98 | Aprobado aceptando `VERSION_NO_REGISTRADA` y `VERSION_NO_ENCONTRADA` (decisión QA del 2026-11-18, observación OBS-G040-01) hasta que Análisis cambie el nombre del error en FA-7 |

---

## 4. Entrega a Desarrollo — registro de defectos

### 4.A — Casos rechazados (defectos abiertos)

| TC | RF | Responsable | Resultado | Motivo | Incidencia asociada | Severidad (QA) |
|---|---|---|---:|---|---|---|
| G035 | RF-97 | Juan Parra | 4/5 | Con 14 solicitudes concurrentes a `vista-previa` ya hay cola (~4 s) y con 15 o más casi todas expiran por timeout (a 20, respondió 200 el 0-15 % según la corrida). El caso exige que 20 concurrentes respondan en tiempo. Compatible con un pool de ~13-14 conexiones o recursos en el backend o la infraestructura de TEST; causa exacta sin identificar | INC-M07-376-G035 (Abierta) | Alta |

**Nota sobre el 4/5 del caso:** uno de los cinco chequeos del informe de G035 (`test_11_a_13_vus_responden_rapido_sin_cola`) es un `assert True` que no verifica nada; los aprobados reales son 3 de 5. El rechazo no cambia.

### 4.B — Casos aprobados por reevaluación

| TC | RF | Incidencia | Corrección | Veredicto vigente |
|---|---|---|---|---|
| G002 | RF-95 | INC-M07-375-G002 | Todo error trae `field` (#1169, dentro de #1190/#1189) | V2 20-nov, 62/62 |
| G043 | RF-101 | INC-M07-373-G043 | Nombre de cliente único: 409 `CLIENTE_DUPLICADO` (#1170, índice `uq_cliente_externo_nombre`) | V2 20-nov, 31/31 |
| G047 | RF-101 | INC-M07-374-G047 | Credenciales de los clientes 1 y 2 re-emitidas con bcrypt (corrección de datos del DBA) | V3 20-nov, 63/63 |
| G036 | RF-98 | INC-M07-372-G36 | `MAPPERS_INVALIDOS` en lugar de 400 `VAL_ENTRADA` (#1166, `5baa6e1f`) | V2 20-nov |
| G037 | RF-98 | INC-M07-373-G37 | Gracia mínima y por defecto configurables en la configuración del sistema (#1167, `0553cefd`) | V3 20-nov |
| G038 | RF-98 | INC-M07-374-G38 | Aviso al Administrador cuando se bloquea una activación (#1168, `0553cefd`) | V3 21-nov |
| G039 | RF-98 | INC-M07-375-G39 | Transiciones inválidas auditadas, `MODIFICACION_NO_PERMITIDA` y `REACTIVACION_NO_PERMITIDA` (#1175, `04bddac4` y `20b5f701`) | V2 21-nov |
| G058 | RF-102 | INC-M07-371-G58 | Retención de 5 y 10 años y archivado histórico de la auditoría (#1165) | Reevaluado y aprobado |
| G060 | RF-AE01 | INC-M07-377-G60 | `password` rechazado en la URL; el resumen se cuadra contra los documentos y bloquea el Anexo; `Lines` ausente da 422 en vez de `KeyError`; la query se omite del log de acceso (#1187, `f42865ce`) | Retest 21-nov, 7/7 |
| G061 | RF-AE02 | INC-M07-378-G61 | El Mapper de Compras rechaza importes de 0 o menores a 0,01 con `MAPPER_FALLIDO` (#1188, `e0e4ddb7`) | Retest 21-nov, 6/6 |
| G040 | RF-98 | — | Sin corrección de código: decisión QA sobre el código de error (ver sección 3) | V2 19-nov |

### 4.C — Casos bloqueados y dependencias

- **G035 (RF-97):** depende de Infraestructura o Desarrollo para eliminar el techo de concurrencia. Quedan además sin verificar RNF-97.1 (2.000 facturas, requiere un dataset sintético del DBA), RNF-97.7 (escalado a 2 y 4 instancias) y CA-14 (AgroFusión de pruebas, no confirmado disponible).
- **G027 (RF-97):** la periodicidad trimestral y el mes sin período abierto requieren un titular de prueba con esa configuración (DBA).
- **v3.1 del contrato con el Mapper `06`:** no se probó en TEST, porque el límite de 2 versiones vigentes lo impide; se verificó solo a nivel de unidad (G012). El contrato 3.1 se activa cuando SIGCON acepte el tipo 06.
- **RF-AE02, caso G064:** no está definido en el plan de casos; no hay prueba que ejecutar.
- **RF-99 (Webhooks):** diferido sin receptor; solo queda confirmar que no está expuesto en TEST (Laura López, pendiente de confirmar con los líderes).

### 4.D — Estado del registro de incidencias

| Incidencia | Caso | Severidad | Categoría | Estado |
|---|---|---|---|---|
| INC-M07-376-G035 | G035 | Alta | PERFORMANCE | **Abierta** (techo de concurrencia) |
| INC-M07-377-G025 | G025 | Baja | CONFIG_DESPLIEGUE | **Abierta** (`Environment` dice `DEV` en TEST; Infraestructura/DevOps) |
| INC-M07-378-G019 | G019 | Media | DATOS_PRUEBA | **Abierta** (comodín en la matriz contable de TEST; DBA) |
| INC-M07-371-G58, 372-G36, 373-G37, 374-G38, 375-G39 | G058, G036 a G039 | Baja a Media | Funcional | Cerradas con retest aprobado |
| INC-M07-373-G043, 374-G047, 375-G002 | G043, G047, G002 | Baja y Media | Funcional y datos | Cerradas con retest aprobado (20-nov, rc.80) |
| INC-M07-377-G60, 378-G61 | G060, G061 | Media | Seguridad y funcional | Cerradas con retest aprobado (21-nov) |

**Numeración por unificar.** Las incidencias de RF-95, RF-101, RF-97 y RF-96 se reportaron con consecutivo provisional (373 a 378) y chocan con los que el equipo usó para RF-98 y RF-AE01 (373 a 375, 377 y 378). Antes de publicarlas hay que confirmar con la líder de pruebas el consecutivo definitivo. El mismo problema aplica a INC-M07-377-G025 y a INC-M07-378-G019.

**Observaciones que no son incidencia** (decisiones de diseño por documentar en los RF; detalle en `tests/Test_Testing/Test_Modulo7/incidencias/observaciones_para_analisis_M07.md`): el token de canal se acepta hasta 30 s después de vencer (tolerancia de reloj); `GET /integraciones/agrofusion/roles` es público por contrato de AgroFusión; y el nombre del error de FA-7 de RF-98.

---

## 5. Condiciones de la entrega

1. **Se entrega a Desarrollo** el caso rechazado de la sección 4.A con su evidencia (`RF-97/TC-M07-G035/`, `incidencias/INC-M07-376-G035/`).
2. **Criterio de aceptación del módulo:** el umbral global (≥ 85 %) se cumple y todos los RF activos tienen casos ejecutados. El caso rechazado se entrega con severidad **Alta**. Resta obtener las firmas de este informe.
3. **Retorno esperado de Desarrollo:** rama o PR de corrección de INC-M07-376-G035 y confirmación de despliegue en TEST para que QA ejecute la retroprueba. No se cierra una incidencia sin retest.
4. **Acciones internas de QA antes de la certificación final:**
   - Unificar la numeración provisional de las incidencias con la líder de pruebas y publicarlas en GitHub y Taiga.
   - Reemplazar el `assert True` del informe de G035 por una verificación real, o marcarlo como informativo, y aclarar cuál es la corrida vigente (0/20 frente a 3/20).
   - Pedir al DBA el dataset de alto volumen y un titular trimestral, para los pendientes de la sección 4.C.
   - Obtener las firmas de la sección 6.
5. **Excepciones:** una excepción al umbral solo la autoriza Coordinación, y debe quedar registrada en el control de versiones de este informe.

---

## 6. Control del documento

| Versión | Fecha | Autor | Cambios |
|---|---|---|---|
| **1.0** | 2026-11-21 | Equipo QA | Primer informe consolidado de M07, con corte al 2026-11-21: 53/54 aprobados (98.1 %); un caso rechazado (G035) |

**Firmas de entrega**

| Rol | Nombre | Fecha | Firma |
|---|---|---|---|
| Responsable QA | | | |
| Líder de Desarrollo | | | |
| Coordinación / PM | | | |
