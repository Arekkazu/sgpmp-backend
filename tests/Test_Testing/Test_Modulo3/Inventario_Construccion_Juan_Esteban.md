# Inventario de construcción QA — Módulo 03 — Juan Esteban

**Fecha de corte:** 2026-10-17 · **Fase:** construcción terminada · **Ejecución funcional:** NO REALIZADA en ningún grupo.

**Fuente oficial:** `Casos_Prueba(Modulo3 Agrupado).csv`, filtrada por `Responsable = Juan Esteban`: **31 grupos y 65 casos originales**, todos de CU04:
- G87–G110 (RF-58): 24 grupos y 48 casos. G110 está asignado a RF-58 y RF-59.
- G120 y G124–G129 (RF-59): 7 grupos y 17 casos.

## Criterios de este inventario

| Columna | Origen |
| --- | --- |
| **Agente** | Lo documentado en los informes de cierre de las sesiones de construcción y en las asignaciones del responsable QA. Ningún archivo de los grupos registra autoría; si no hay constancia, se indica **NO DOCUMENTADO**. |
| **Validaciones documentadas** | Las cifras que constan en los informes de cierre de Claude Code. Para los demás grupos no hay resultados registrados: **NO DOCUMENTADO**. |
| **Barreras y versionado** | Inspección estática hecha el 2026-10-17: presencia de la comprobación de `QA_AUTORIZADO` en el ejecutor, de una barrera propia en la colección (`BLOQUEO_*` o `skipRequest`) y en el spec de Cypress, y de la lógica `RESULTADOS` / `EvaluacionVN`. No se ejecutó ningún script de los grupos que no construyó Claude Code. |
| **Sintaxis** | `node --check` sobre todos los `.mjs`, `.cjs` y `.js` de los 31 grupos (no ejecuta código): **todos correctos**. |

## 1. Trazabilidad

| Grupo | Casos originales | RF / CU | Objeto (matriz) | Agente | Ejecutor principal | Herramientas |
| --- | --- | --- | --- | --- | --- | --- |
| G87 | 168, 177, 178 | RF-58 / CU04 | Última lectura válida ante datos anómalos | Claude Code | `RF-58/TC-M03-G87/ejecutar_tc_m03_g87.mjs` | Node, Newman, Cypress |
| G88 | 169, 170, 171, 172, 180, 266 | RF-58 / CU04 | Semáforo según umbrales de M09 | Claude Code | `RF-58/TC-M03-G88/ejecutar_tc_m03_g88.mjs` | Node, Newman, Cypress |
| G89 | 173, 174 | RF-58 / CU04 | Semáforo según severidad de alertas | Claude Code | `RF-58/TC-M03-G89/ejecutar_tc_m03_g89.mjs` | Node, Newman |
| G90 | 175, 176 | RF-58 / CU04 | Sensor sin señal (GRIS) y persistencia de alertas | NO DOCUMENTADO | `RF-58/TC-M03-G90/ejecutar_tc_m03_g90.mjs` | Node, Newman, Cypress |
| G91 | 179, 194 | RF-58 / CU04 | Resincronización y actualización automática | NO DOCUMENTADO | `RF-58/TC-M03-G91/ejecutar_tc_m03_g91.mjs` | Node, Newman, Cypress |
| G92 | 181, 182, 183 | RF-58 / CU04 | Estado general de la unidad (peor semáforo, paginación) | NO DOCUMENTADO | `RF-58/TC-M03-G92/ejecutar_tc_m03_g92.mjs` | Node, Newman |
| G93 | 184 | RF-58 / CU04 | Unidad sin datos en GRIS | Construcción inicial: Codex. Corrección autorizada: Claude Code | `RF-58/TC-M03-G93/ejecutar_tc_m03_g93.mjs` | Node, Newman, Cypress |
| G94 | 185 | RF-58 / CU04 | Usuario sin unidades asignadas | NO DOCUMENTADO | `RF-58/TC-M03-G94/ejecutar_tc_m03_g94.mjs` | Node, Newman, Cypress |
| G95 | 186 | RF-58 / CU04 | Expiración de sesión durante el monitoreo | NO DOCUMENTADO | `RF-58/TC-M03-G95/ejecutar_tc_m03_g95.mjs` | Node, Cypress |
| G96 | 187 | RF-58 / CU04 | Catálogo de conectividad ONLINE/OFFLINE/SIN_SEÑAL | Construcción inicial: Codex. Reconstrucción autorizada: Claude Code | `RF-58/TC-M03-G96/ejecutar_tc_m03_g96.mjs` | Node, Newman |
| G97 | 188, 189, 190, 210 | RF-58 / CU04 | Vistas y payloads por rol | Construcción inicial: Codex. Reconstrucción y correcciones: Claude Code | `RF-58/TC-M03-G97/ejecutar_tc_m03_g97.mjs` | Node, Newman, Cypress |
| G98 | 191 | RF-58 / CU04 | Panel de alertas por severidad | NO DOCUMENTADO | `RF-58/TC-M03-G98/ejecutar_tc_m03_g98.mjs` | Node, Newman |
| G99 | 192, 193 | RF-58 / CU04 | Dashboard de solo lectura y semáforo en backend | Codex (asignación QA) | `RF-58/TC-M03-G99/ejecutar_tc_m03_g99.mjs` | Node, Newman, Cypress, BD solo lectura |
| G100 | 195 | RF-58 / CU04 | Throttling visual | Codex (asignación QA) | `RF-58/TC-M03-G100/ejecutar_tc_m03_g100.mjs` | Node, Newman, Cypress |
| G101 | 196, 197, 198, 199, 200 | RF-58 / CU04 | Niveles de degradación de latencia | Codex (asignación QA) | `RF-58/TC-M03-G101/ejecutar_tc_m03_g101.mjs` | Node, Newman, Cypress |
| G102 | 201, 202, 213 | RF-58 / CU04 | Límite de 50 sensores por vista y segmentación hasta 200 | Claude Code | `RF-58/TC-M03-G102/ejecutar_tc_m03_g102.mjs` | Node, Newman, Cypress |
| G103 | 203 | RF-58 / CU04 | Carga inicial < 1 s con 50 sensores | Claude Code | `RF-58/TC-M03-G103/ejecutar_tc_m03_g103.mjs` | Node, Newman |
| G104 | 204 | RF-58 / CU04 | Vista usable a 360 px | Claude Code | `RF-58/TC-M03-G104/ejecutar_tc_m03_g104.mjs` | Node, Cypress |
| G105 | 205 | RF-58 / CU04 | Interpretación ≤ 5 s por un Productor (manual) | Claude Code | `RF-58/TC-M03-G105/ejecutar_tc_m03_g105.mjs` | Node (sesión moderada) |
| G106 | 206 | RF-58 / CU04 | Disponibilidad ≥ 99,0 % | Claude Code | `RF-58/TC-M03-G106/ejecutar_tc_m03_g106.mjs` | Node (sonda) |
| G107 | 207, 208, 209 | RF-58 / CU04 | RBAC/BOLA del dashboard y bitácora de denegaciones | Claude Code | `RF-58/TC-M03-G107/ejecutar_tc_m03_g107.mjs` | Node, Newman |
| G108 | 211 | RF-58 / CU04 | Token válido en los endpoints de monitoreo | NO DOCUMENTADO | `RF-58/TC-M03-G108/ejecutar_tc_m03_g108.mjs` | Node, Newman |
| G109 | 212 | RF-58 / CU04 | Cifrado del canal (TLS) | NO DOCUMENTADO | `RF-58/TC-M03-G109/ejecutar_tc_m03_g109.mjs` | Node (sonda TLS) |
| G110 | 263 | RF-58, RF-59 / CU04 | Coherencia entre monitoreo e historial | NO DOCUMENTADO | `RF-58/TC-M03-G110/ejecutar_tc_m03_g110.mjs` | Node, Newman, BD |
| G120 | 241, 242, 243 | RF-59 / CU04 | Sincronización desde el buffer local | Codex (asignación QA) | `RF-59/TC-M03-G120/ejecutar_tc_m03_g120.mjs` | Node |
| G124 | 249, 250, 254 | RF-59 / CU04 | Exportación PDF y Excel, estructura y volumen | Codex (asignación QA) | `RF-59/TC-M03-G124/ejecutar_tc_m03_g124.mjs` | Node, validación de archivo |
| G125 | 251, 252, 253, 265 | RF-59 / CU04 | Reglas y errores de la exportación | Codex (asignación QA) | `RF-59/TC-M03-G125/ejecutar_tc_m03_g125.mjs` | Node, validación de archivo |
| G126 | 255 | RF-59 / CU04 | La consulta del historial no modifica datos | Claude Code | `RF-59/TC-M03-G126/ejecutar_tc_m03_g126.mjs` | Node, Newman, BD solo lectura |
| G127 | 256 | RF-59 / CU04 | Auditoría de consultas y exportaciones | Claude Code | `RF-59/TC-M03-G127/ejecutar_tc_m03_g127.mjs` | Node, Newman |
| G128 | 257 | RF-59 / CU04 | Token válido en historial y exportación | Claude Code | `RF-59/TC-M03-G128/ejecutar_tc_m03_g128.mjs` | Node, Newman |
| G129 | 258, 259, 260, 261 | RF-59 / CU04 | Autorización por granja, recurso y rol | Claude Code | `RF-59/TC-M03-G129/ejecutar_tc_m03_g129.mjs` | Node, Newman (matriz parametrizada) |

Los casos se citan con su número; el identificador completo es `TC-M03-<número>`.

## 2. Estado técnico

| Grupo | Validación local (archivos) | Resultados documentados (local / unitarias) | Barrera ejecutor / colección / Cypress | Reutilización V1–Vn | README |
| --- | --- | --- | --- | --- | --- |
| G87 | `--validar-local`, `validar_local_g87.mjs`, `--verificar-spec` | 94/94 · 44/44 · spec descubierto sin red | sí / sí / sí | sí | sí |
| G88 | `--validar-local`, `validar_local_g88.mjs`, `--verificar-spec` | 110/110 · 45/45 · spec descubierto sin red | sí / sí / sí | sí | sí |
| G89 | `--validar-local`, `validar_local_g89.mjs` | 65/65 · 41 pruebas | sí / sí / n.a. | sí | sí |
| G90 | `validar_local_g90.mjs` | NO DOCUMENTADO | sí / sí / sí | sí | sí |
| G91 | `validar_local_g91.mjs` | NO DOCUMENTADO | sí / sí / sí | sí | sí |
| G92 | `validar_local_g92.mjs` | NO DOCUMENTADO | sí / sí / n.a. | sí | sí |
| G93 | `--validar-local`, `validar_local_g93.mjs` | 31/31 · 8/8 | sí / sí / sí | sí | sí |
| G94 | `validar_local_g94.mjs` | NO DOCUMENTADO | sí / **no** (sin barrera propia en la colección) / sí | sí | sí |
| G95 | `validar_local_g95.mjs` | NO DOCUMENTADO | sí / n.a. / sí | sí | sí |
| G96 | `--validar-local`, `validar_local_g96.mjs` | 23/23 · 9/9 | sí / sí / n.a. | sí | sí |
| G97 | `--validar-local`, `validar_local_g97.mjs`, `--verificar-spec` | 28/28 · 14/14 · spec descubierto sin red | sí / sí / sí | sí | sí |
| G98 | `validar_local_g98.mjs` | NO DOCUMENTADO | sí / sí / n.a. | sí | sí |
| G99 | `validar_local_g99.mjs` | NO DOCUMENTADO | sí / sí / sí | sí | **no** |
| G100 | `validar_local_g100.mjs` | NO DOCUMENTADO | sí / sí / sí | sí | **no** |
| G101 | `validar_local_g101.mjs` | NO DOCUMENTADO | sí / sí / sí | vía la base de G100 (estático) | **no** |
| G102 | `--validar-local`, `validar_local_g102.mjs`, `--verificar-spec` | 33/33 · 15/15 · spec descubierto sin red | sí / sí / sí | sí | sí |
| G103 | `--validar-local`, `validar_local_g103.mjs` | 26/26 · 7/7 | sí / sí / n.a. | sí | sí |
| G104 | `--validar-local`, `validar_local_g104.mjs`, `--verificar-spec` | 29/29 · 11/11 · spec descubierto sin red | sí / n.a. / sí | sí | sí |
| G105 | `--validar-local`, `validar_local_g105.mjs` | 14/14 · 6/6 | sí / n.a. / n.a. | sí | sí |
| G106 | `--validar-local`, `validar_local_g106.mjs` | 15/15 · 7/7 | sí / n.a. / n.a. | sí | sí |
| G107 | `--validar-local`, `validar_local_g107.mjs` | 24/24 · 9/9 | sí / sí / n.a. | sí | sí |
| G108 | NO DOCUMENTADO (sin archivo propio) | NO DOCUMENTADO | sí / sí / n.a. | sí (base `qa_lote6_base.mjs`) | **no** |
| G109 | NO DOCUMENTADO | NO DOCUMENTADO | sí / n.a. / n.a. | vía la base de G108 (estático) | **no** |
| G110 | NO DOCUMENTADO | NO DOCUMENTADO | sí / sí / n.a. | vía la base de G108 (estático) | **no** |
| G120 | `validar_local_g120.mjs` | NO DOCUMENTADO | sí / n.a. / n.a. | vía la base de G108 (estático) | **no** |
| G124 | `validar_local_g124.mjs` | NO DOCUMENTADO | sí / n.a. / n.a. | vía la base de G108 (estático) | **no** |
| G125 | `validar_local_g125.mjs` | NO DOCUMENTADO | sí / n.a. / n.a. | vía la base de G108 (estático) | **no** |
| G126 | `--validar-local`, `validar_local_g126.mjs` | 23/23 · 7/7 | sí / sí / n.a. | sí | sí |
| G127 | `--validar-local`, `validar_local_g127.mjs` | 24/24 · 7/7 | sí / sí / n.a. | sí | sí |
| G128 | `--validar-local`, `validar_local_g128.mjs` | 24/24 · 8/8 | sí / sí / n.a. | sí | sí |
| G129 | `--validar-local`, `validar_local_g129.mjs` | 28/28 · 11/11 | sí / sí / n.a. | sí | sí |

**Barreras verificadas en ejecución** (no solo por inspección), según los informes de cierre:
- **Newman contra loopback con 0 peticiones:** G87–G89, G93, G96, G97, G102, G103, G107 y G126–G129.
- **`--ejecutar` sin autorización con código 2 y sin RESULTADOS:** todos los grupos de Claude Code.
- **Barrera del spec de Cypress, ejecutada en local sin red:** G87, G88, G97, G102 y G104.

## 3. Acoplamientos entre carpetas (riesgo de reutilización)

Algunos ejecutores importan módulos de otras carpetas. Modificar el grupo de origen afecta a los dependientes.

| Grupo | Importa de |
| --- | --- |
| G100 | `TC-M03-G99/ejecutar_tc_m03_g99.mjs` |
| G101 | `TC-M03-G100/qa_lote5_base.mjs` y `TC-M03-G99/ejecutar_tc_m03_g99.mjs` |
| G109, G110 | `TC-M03-G108/qa_lote6_base.mjs` |
| G120 (RF-59) | `../../RF-58/TC-M03-G108/qa_lote6_base.mjs` (cruza de RF-59 a RF-58) |
| G124 | `TC-M03-G120/rf59_base.mjs` |
| G125 | `TC-M03-G120/rf59_base.mjs` y `TC-M03-G124/validadores.mjs` |

**Copias locales:** los grupos de Claude Code usan copias por carpeta: `g87_lib.mjs` (G87–G92) y `monitoreo_lib.mjs` (G102–G107 y G126–G129). Sus versiones difieren a propósito:
- **G102 y G104:** con la corrección de Cypress y `--verificar-spec`.
- **G103:** sin modificar; su función de Cypress está latente y sin uso.
- **G105–G107 y G126–G129:** con la invocación de Cypress corregida, aunque no la usan.

## 4. Grupos con documentación incompleta

| Situación | Grupos |
| --- | --- |
| **Sin README** | G99, G100, G101, G108, G109, G110, G120, G124 y G125 |
| **Sin resultados de validación documentados** | G90, G91, G92, G94, G95, G98, G99, G100, G101, G108, G109, G110, G120, G124 y G125 |
| **Agente no documentado** | G90, G91, G92, G94, G95, G98, G108, G109 y G110 |
| **Sin archivo de validación local propio** | G108, G109 y G110 |
| **Colección sin barrera propia** | G94 (depende solo de la barrera del ejecutor) |

Antes de V1 conviene que el responsable de cada grupo documente al menos el resultado de `--validar-local` y de sus pruebas unitarias.
