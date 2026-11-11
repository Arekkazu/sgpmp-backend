# Análisis previo — M06 RF-91 (trazabilidad) y RF-92 (revelaciones NIC 41)

| Campo | Valor |
|---|---|
| Fuente de casos | `RF-91_TC_Individuales_y_Agrupados.xlsx` (72 casos / 12 grupos) y `RF-92_TC_Individuales_y_Agrupados.xlsx` (84 casos / 12 grupos) |
| Código revisado | `origin/test` @ `e5d6934d` (2026-11-07, "Merge dev into test"), leído con `git show`, sin cambiar de rama |
| Guía de dominio | `writing-block.md` (Guía de preparación y validación — Finanzas y Suministros) |
| Plantilla seguida | `Test_Modulo9/RF-21/TC-M09-G58` (Postman + Newman, ficha + reporte HTML) |
| Fecha | 2026-11-07 |

## 1. Hallazgo principal: la matriz no describe la API real

La matriz se escribió sobre la especificación (`/api/v1/m06/entries/{id_asiento}/verify-chain`, `/disclosure-reports`, ...).
El código desplegado expone otra API, bajo el prefijo `/finanzas` (archivo `src/financial_valuation/infrastructure/routers/m06_router.py`):

### RF-91 — Trazabilidad

| Matriz (spec) | API real en `origin/test` | Nota |
|---|---|---|
| `POST /m06/entries/{id_asiento}/verify-chain` | `POST /finanzas/periodos/{id_periodo_contable}/trazabilidad` | Verifica **todas las líneas del período**, no un asiento. Solo períodos `ABIERTO`, si no 422 `PERIODO_NO_ABIERTO`. Permiso `trazabilidad_contable` E. |
| `GET /m06/entries/{id}/traceability-chain` | `GET /finanzas/lineas/{id_linea}/cadena` | Por **línea de asiento** (`id_linea_asiento_nic41`, entero, no UUID). 404 `LINEA_NO_ENCONTRADA`. Permiso R. |
| `POST /m06/entries/{id}/re-verify` | — (no existe) | La re-verificación es volver a llamar al POST del período: las líneas `PENDIENTE_TRAZABILIDAD` se reevalúan y las `VERIFICADO` se saltan. |
| `GET /m06/audit` (RF-94) | `GET /finanzas/auditoria?tipo_evento=CADENA_TRAZABILIDAD_VERIFICADA` | Payload: `resultado` (CADENA_COMPLETA / CADENA_INCOMPLETA), `tipo_evidencia`, `faltantes`, `nivel_fallo`. |
| `GET /m06/alerts` | — (no existe como endpoint) | Revisar con desarrollo dónde llega la alerta al Contador. |
| `POST /m06/periods/{id}/close` | `POST /finanzas/periodos/{id}/cierre` (+ `GET .../prevalidacion`) | El cierre llama al verificador (RF-87 paso 3). |
| `POST /m06/periods/{id}/exclusions` | — | La exclusión se decide dentro del cuerpo del cierre (`CierreDTO`). |
| `GET /m08/audit/traceability/{id}` | — (M08 no está en este repo) | Casos del Auditor externo bloqueados. |
| `.../verify-chain-bulk` | Es el mismo POST del período | — |

**Entradas que la matriz supone y la API no recibe.** `tipo_evidencia_origen`, `ids_lectura_iot`, `id_evento_biologico` e `id_lote` **no se envían**: el backend los deduce de la línea (`tabla_origen`, `tipo_evidencia`). Por eso TC-91-047, 048 y 059 no aplican tal como están redactados. Su intención (no aceptar tipos fuera del enumerado ni cadenas mal tipificadas) se prueba en la capa de dominio con pytest.

**Regla real de niveles** (`src/financial_valuation/domain/services/trazabilidad.py`, función pura `verificar_cadena`):

| Tipo de evidencia | Eslabones exigidos |
|---|---|
| IOT_DIRECTO | origen, evento_m02, lecturas_nic41, precio_documentado |
| REGISTRO_MANUAL | origen, evento_m02, precio_documentado |
| VARIACION_PRECIO | origen, precio_documentado |
| EVENTO_SANITARIO | origen, evento_sanitario |
| CIERRE_PERIODO | origen, cierre, precio_documentado |

Un eslabón "no aplica" (`None`) no se exige. Nivel 1 = lecturas `apto_para_nic41` del dispositivo del activo entre 24 h antes y 1 h después del evento (`trazabilidad_repository.py`).

### RF-92 — Revelaciones

| Matriz (spec) | API real en `origin/test` | Nota |
|---|---|---|
| `POST /m06/disclosure-reports` | `POST /finanzas/periodos/{id}/revelaciones` | Solo períodos `CERRADO`, si no 422 `PERIODO_NO_CERRADO`. Exige compromisos, pignorados o `declaracion_sin_novedad=true`, si no 422 `REVELACIONES_MANUALES_REQUERIDAS`. Con alertas de consistencia exige `justificacion_inconsistencias` ≥ 20 caracteres, si no **409** `ALERTA_CONSISTENCIA`. |
| `GET /m06/disclosure-reports/{id_version}` | `GET /finanzas/revelaciones/{id_informe}` y `GET /finanzas/periodos/{id}/revelaciones` (versiones) | 404 `INFORME_NO_ENCONTRADO`. |
| `.../approve` y `.../reject` | `POST /finanzas/revelaciones/{id}/resolucion` con `{"aprobar": bool, "razon_rechazo": str}` | Rechazo exige razón ≥ 20 caracteres (`RAZON_RECHAZO_OBLIGATORIA`). Solo sobre `BORRADOR` (`INFORME_NO_EDITABLE`). |
| `.../download` | `GET /finanzas/revelaciones/{id}/descarga?formato=pdf\|excel` | Solo `APROBADO`/`ARCHIVADO`. |
| `.../consistency-check` | — (no existe) | La consistencia se calcula dentro de la generación (alertas `rollforward` con tolerancia **±1 COP**, no ±0,01 como dice la matriz). |
| `GET /m08/reports/{id}` | — | Bloqueado (M08). |
| `tipo_periodo`, `formato_salida`, `filtro_especie` | No son entradas del API | El tipo sale del período y el formato de la descarga. TC-92-040, 041 (en parte), 042 y 082 no aplican tal como están redactados. |

**Versión real del informe**: `{AAAA}-{M##|Q#|A}-V{n}` (ej. `2026-M10-V1`), donde `n` es un **número sin dos dígitos**. La matriz (TC-92-056…) espera `V01`: es una posible discrepancia a confirmar contra el RF.

**Roles con permiso** (migración `c4d81e6f2a95`):

| Recurso | Contador (5) | Administrador (1) | Revisor Fiscal (8) | Productor (2) | Externo AgroFusion (auditor externo) |
|---|---|---|---|---|---|
| `trazabilidad_contable` (96) | R, E | R | R | — | — |
| `revelaciones_nic41` (97) | C, R, U | — | R | R | — |

Corrección (2026-11-07): la primera versión de esta tabla daba lectura de revelaciones al Administrador y no al Productor; es al revés. Contraste con la especificación (`ESPECIFICACION_REQUERIMIENTOS_COMPLETA.xlsx`, hoja Módulo 6):
- RF-92 Salida 3: el informe APROBADO está disponible para Contador, Auditor y **Productor** (coincide con el código).
- La guía de Finanzas da lectura de Finanzas al **Administrador**; el código no le da lectura de revelaciones (discrepancia guía ↔ código, TC-92-083).
- RF-91 y RF-92 (Actores) dan al **auditor externo** lectura de la cadena de períodos CERRADOS y de informes APROBADOS/ARCHIVADOS (y descarga de copias aprobadas) a través de M08; en este backend el rol Externo AgroFusion no tiene ningún permiso de M06 (TC-91-061, TC-92-071).

## 2. Viabilidad por grupo

Las 24 carpetas existen (`Test_Modulo6/RF-91/TC-M06-G01…G12` y `RF-92/TC-M06-G01…G12`), cada una con `ficha.md`, colección Postman y `resultados/`. Las peticiones marcadas **[escritura]** solo corren con `--env-var permitir_escritura=SI`.

Leyenda:
- **API**: ejecutable con Postman/Newman contra TEST.
- **API+datos**: ejecutable si existe o se siembra el escenario en TEST.
- **pytest**: lógica de dominio, se puede probar en local con la función pura o con mocks.
- **Bloqueado**: falta el endpoint, el módulo o la herramienta.

Carpetas con la misma estructura que `Test_Modulo9/RF-21/TC-M09-G58`: `Test_Modulo6/RF-XX/TC-M06-G<nn>/` con `ficha.md`, `tc_m06_g<nn>.postman_collection.json` y `resultados/resultado_TC-M06-G<nn>.html`. El número `<nn>` es el del grupo TCG de la matriz (RF-91 TCG-09 → `RF-91/TC-M06-G09`; RF-92 TCG-07 → `RF-92/TC-M06-G07`); la carpeta `RF-XX` distingue los grupos que comparten número.

### RF-91

| Carpeta | TCG | Tema | Viabilidad | Comentario |
|---|---|---|---|---|
| G01 | TCG-01 | Cadena IOT_DIRECTO completa | API+datos | Requiere un período ABIERTO con una línea IOT_DIRECTO cuyo activo tenga dispositivo y lecturas apto_para_nic41. **Escribe en TEST**: necesita sandbox o autorización. |
| G02 | TCG-02 | Cardinalidad de lecturas (1 de 3, 0 de 3, etc.) | pytest + API+datos | Regla "al menos una" = `count(*) > 0` en SQL. La variante "lectura inexistente" no aplica (los IDs no se envían). |
| G03 | TCG-03 | Matriz de niveles por tipo | **pytest** | `verificar_cadena` es Python puro: se cubren los 5 tipos en local sin TEST. |
| G04 | TCG-04 | Coherencia semántica | pytest + API+datos | El SQL valida evento ↔ activo de la línea; **no compara fechas lectura/evento/variación** ni galpón en POBLACIONAL (posibles hallazgos TC-91-023/024/025/026). |
| G05 | TCG-05 | Precio de referencia y fuente | API+datos | Exige evidencia no vacía y justificación si ESTIMADA. **No** comprueba "aprobación del Contador" (posible hallazgo TC-91-029/030). |
| G06 | TCG-06 | Auditorías de módulos fuente (RF-52/63/73) | Revisar | El repositorio no consulta RF-52, RF-63 ni RF-73: solo eventos M02 y sanitarios. Posible hallazgo o cambio de alcance. |
| G07 | TCG-07 | Re-verificación de pendientes | API+datos | Mismo POST del período. Escribe en TEST. |
| G08 | TCG-08 | Indisponibilidad de fuente ≠ eslabón ausente | Bloqueado | Todo es SQL en la misma BD: no hay llamada remota que simular (sin WireMock/Toxiproxy). Una caída de BD está prohibida en TEST. |
| **G09** | TCG-09 | Estados y contrato de entrada | **API (sin escritura)** | |
| G10 | TCG-10 | Cierre, exclusión, inmutabilidad | API+datos | La parte "período cerrado no se re-verifica" se cubre en RF-91/G09 sin escribir. |
| G11 | TCG-11 | Escala y control de acceso | API (roles) + Bloqueado (M08) | La parte de roles se cubre en RF-91/G09 sin escribir. |
| G12 | TCG-12 | Rendimiento y retención | k6 (con autorización) | Carga sobre TEST compartido: pedir visto bueno antes. |

### RF-92

| Carpeta | TCG | Tema | Viabilidad | Comentario |
|---|---|---|---|---|
| G01 | TCG-01 | Informe BORRADOR con 9 secciones | API+datos | Necesita un período CERRADO. Escribe un BORRADOR. |
| G02 | TCG-02 | Separación TB / precio | API+datos | Lectura del `contenido.parr_40…` y `parr_51…`. |
| G03 | TCG-03 | Métodos y supuestos | API+datos | `niif13_93_metodos_y_supuestos` devuelve el texto "datos insuficientes" globalmente, no por activo (posible hallazgo de granularidad). |
| G04 | TCG-04 | Cuadre del rollforward | API+datos + hoja de cálculo | Tolerancia real ±1 COP. |
| G05 | TCG-05 | Precios y activos al costo | API+datos | `rango_valor_razonable` es siempre "No determinable" (comparar con el ¶54 y el RF-88). |
| G06 | TCG-06 | Entradas manuales y riesgos | API+datos | Validación de la combinación contradictoria (`declaracion_sin_novedad=true` + compromisos) no está en el DTO (posible hallazgo TC-92-033/034). |
| **G07** | TCG-07 | Bloqueos y contrato de entrada | **API (sin escritura)** | |
| G08 | TCG-08 | Consistencia y justificación | API+datos | 409 `ALERTA_CONSISTENCIA` (la matriz esperaba otro flujo; confirmar código esperado). |
| G09 | TCG-09 | Secciones BLOQUEADAS | Revisar | El constructor no marca secciones BLOQUEADAS; posible hallazgo. |
| G10 | TCG-10 | Versionado y aprobación | API+datos | Formato `V1` vs `V01`. |
| G11 | TCG-11 | Inmutabilidad, descarga, acceso | API + SQL (con permiso) | Parte de roles en RF-92/G07. |
| G12 | TCG-12 | PDF/A-1, Excel UPRA, rendimiento | veraPDF + k6 | Herramientas fuera del stack actual: declarar o instalar. |

## 3. Posibles hallazgos ya visibles en el código (pendientes de confirmar ejecutando)

| Caso | Observación | Dónde |
|---|---|---|
| TC-92-043 | `CompromisoDTO.monto_estimado` no tiene restricción `> 0`: un monto negativo pasa la validación. **G07 (RF-92) lo prueba sin escribir**. | `m06_dto.py` |
| TC-91-045 / TC-92-039 | Un período inexistente responde 422 (`PERIODO_NO_ABIERTO` / `PERIODO_NO_CERRADO`), no 404. La matriz acepta 404 o 422: **no es defecto**, pero el mensaje dice "no abierto" en vez de "no existe". | use cases RF-91 y RF-92 |
| TC-91-024…026 | No hay validación temporal lectura ≤ evento ≤ variación. | `trazabilidad_repository.py` |
| TC-91-029/030 | Precio ESTIMADA solo exige justificación, no aprobación del Contador. | `trazabilidad_repository.py` |
| TC-91-031…034 | No se consultan RF-52, RF-63 ni RF-73. | `trazabilidad_repository.py` |
| TC-92-056 | Versión `V1` en lugar de `V01`. | `reportes.py` |

Ninguno es todavía una incidencia: según el plan de pruebas §6, primero se ejecuta y se descarta el falso positivo.

## 4. Preguntas para el responsable QA o desarrollo

1. ¿URL vigente de TEST? La colección G58 usa `…sslip.io/api-sgpmp-test` y `cypress.config.cjs` usa `https://api.inmero.co`.
2. ¿Cuentas de prueba de Contador, Administrador, Productor, Veterinario y **Revisor Fiscal**, vinculadas a una finca con titular (NIT + DV)?
3. ¿Hay períodos contables ABIERTO, EN_CIERRE y CERRADO en TEST? Sin ellos las pruebas que dependen del estado se omiten.
4. ¿Está habilitado el sandbox (`ENABLE_TEST_SANDBOX`, cabecera `X-Test-Run-Id`) para los grupos que escriben (RF-91 G01 y G07, RF-92 G01…)?
5. Las dos matrices numeran sus grupos desde TCG-01: ¿basta con la carpeta `RF-91`/`RF-92` para distinguir, por ejemplo, `TC-M06-G07` de cada RF en el panel QA?
6. Los casos que dependen de la especificación y no de la API (inputs que no existen, M08): ¿se marcan "No aplica — diseño distinto" o se piden a desarrollo?
