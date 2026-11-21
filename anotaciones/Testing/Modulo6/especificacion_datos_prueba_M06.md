# Datos de prueba que necesita QA en TEST — M06 RF-91 (trazabilidad) y RF-92 (revelaciones)

| Campo | Valor |
|---|---|
| Para | Responsable de insertar datos en TEST |
| Ambiente | `https://api.inmero.co/api-sgpmp-test` |
| Pruebas que lo usan | `tests/Test_Testing/Test_Modulo6/RF-91/TC-M06-G47…G58` y `RF-92/TC-M06-G59…G70` |
| Fecha | 2026-11-07 |

## Por qué hace falta

En la ejecución del 2026-11-07 se omitieron la mayoría de las pruebas porque TEST no tiene los datos que necesitan:

- Los 6 períodos contables tienen `numero_id_tributaria = null`: **no hay titular tributario** (NIT + DV).
- El período ABIERTO 1 tiene **0 líneas de asiento** NIC 41. Nunca se ha verificado su trazabilidad.
- Los períodos CERRADOS 2, 3, 4 y 5 no tienen **ningún informe de revelaciones**.
- No hay **ningún período EN_CIERRE**.

## Reglas generales

1. **Creen los datos usando la aplicación siempre que se pueda** (pantallas o API con el rol indicado), no con SQL directo. Así quedan las líneas de asiento, auditorías, hashes y procesos de fondo como los genera el sistema. Usen SQL solo donde este documento lo indica.
2. **Todo en una finca y un titular dedicados a QA.** Así nada se mezcla con otros datos. Sugerencia: finca `QA-M06`, titular `NIT 900000001-5` (o el que acepte la validación del DV).
3. **Nombren lo que creen con el prefijo `QA-M06-`** (activos, precios, descripciones) para encontrarlo después.
4. **Después de cada hecho en Activos biológicos esperen al menos 1 minuto**: el proceso de fondo es el que crea la medición y la línea de asiento (guía de Finanzas, §3). El Contador puede forzarlo con «Calcular medición ahora».
5. **No corrijan el período 2.** Está CERRADO sin `fecha_cierre` y con eso se reproduce la incidencia del 500 al recerrar (INC-M06-01-054). Déjenlo así hasta que desarrollo cierre la incidencia.
6. **Al terminar, envíen a QA los identificadores** de la tabla de la sección 8.

## 1. Cuentas (ya existen; solo verificar)

| Rol | Correo | Qué verificar |
|---|---|---|
| Contador | contador@gmail.com | **Vinculado a la finca QA-M06.** Si no lo está, las listas salen vacías sin error. |
| Administrador | admin.rol@gmail.com | Ve todas las fincas. |
| Productor | productor@gmail.com | Vinculado a la finca QA-M06. |
| Veterinario | veterinario@gmail.com | Vinculado a la finca QA-M06 (registra eventos sanitarios y medicamentos). |
| Revisor Fiscal | revisor.fiscal@gmail.com | Vinculado a la finca QA-M06. |
| Externo AgroFusion (auditor externo) | externo.agrofusion@gmail.com | Vinculado a la finca QA-M06. |

## 2. Datos base de Finanzas (en este orden; guía de Finanzas §2)

| # | Dato | Detalle | Dónde |
|---|---|---|---|
| 2.1 | **Titular tributario** | Finca QA-M06 con NIT y DV válidos. Sin esto no se abre ningún período ni hay reconocimiento. | Configuración → Fincas |
| 2.2 | **Configuración contable** | Periodicidad de cierre **MENSUAL**, umbral de desviación de precio y días de aviso de vencimiento. | Finanzas → Configuración (Administrador o Contador) |
| 2.3 | **Parámetros por especie** | Bovino: clasificación PRODUCCION, precio **por kilogramo**. Ave (pollo de engorde): CONSUMO, **por cabeza**. Ambas con **porcentajes de costos de venta**. | Finanzas → Configuración → Especies |
| 2.4 | **Matriz contable completa** | Cuentas débito y crédito para **todos** los hechos (reconocimiento, variación por transformación biológica, variación por precio, baja, producto agrícola, costos). Si falta alguna, las líneas quedan «Sin cuenta contable» y el cierre se bloquea. | Finanzas → Configuración → Matriz |
| 2.5 | **Precios de mercado** | Ver tabla 2.5. Todos con fecha de vigencia **anterior** a los hechos (un precio con fecha futura queda «Programado»). | Finanzas → Precios (Contador) |

### 2.5 Precios

| Precio | Especie | Fuente | Evidencia | Justificación | Para |
|---|---|---|---|---|---|
| QA-M06-P1 | Bovino | MERCADO_ACTIVO | Sí (texto o soporte) | — | Líneas normales (TC-91-027) |
| QA-M06-P2 | Ave | UPRA | Sí | — | Activos poblacionales (TC-91-028) |
| QA-M06-P3 | Bovino | ESTIMADA | Sí | ≥ 50 caracteres | Precio estimado (TC-91-029/030). Registrarlo **después** de P1 para que sea el vigente en una de las mediciones; si no se puede, avisar. |

## 3. Activos biológicos (M02) en la finca QA-M06

Todos con reconocimiento inicial **confirmado** en Finanzas (RF-82) por el Contador, salvo que se diga lo contrario.

| Activo | Tipo | Especie | Requisitos | Para |
|---|---|---|---|---|
| QA-M06-BOV-01 | INDIVIDUAL | Bovino | Origen compra con costo y soporte; **dispositivo IoT de peso asociado**; peso inicial. | Cadena IOT_DIRECTO completa (CA-1, CA-9 individual) |
| QA-M06-BOV-02 | INDIVIDUAL | Bovino | Igual que BOV-01, con su propio dispositivo. | Lecturas no aptas (CA-4) |
| QA-M06-BOV-03 | INDIVIDUAL | Bovino | Sin dispositivo IoT. | REGISTRO_MANUAL |
| QA-M06-BOV-04 | INDIVIDUAL | Bovino | Con dispositivo. Tendrá un **evento sanitario**. | EVENTO_SANITARIO |
| QA-M06-AVE-01 | POBLACIONAL (cantidad, p. ej. 500) | Ave | En el galpón **QA-M06-G1**, con **sensor ambiental** en ese galpón. | CA-9 poblacional |
| QA-M06-AVE-02 | POBLACIONAL | Ave | En el galpón **QA-M06-G2** (otro galpón, con su propio sensor). | Coherencia de galpón (TC-91-023) |
| QA-M06-COSTO-01 | INDIVIDUAL | Una especie **sin precio de mercado** (o sin precio vigente) | Origen compra **con costo documentado**. Debe quedar **valorado por costo** (aparece en «Valoración sin mercado»). | Párr. 54 (TC-92-027) |

## 4. RF-91 — Período ABIERTO con líneas de asiento

Un período **ABIERTO** del titular QA-M06 (se abre solo con el primer hecho contable, por ejemplo el primer reconocimiento confirmado). Dentro de él tiene que haber **líneas de asiento NIC 41 de los 5 tipos de evidencia**, completas e incompletas.

### 4.1 Lecturas IoT (M03)

| Dispositivo | Lecturas | `apto_para_nic41` | Momento | Para |
|---|---|---|---|---|
| Peso de BOV-01 | 3 | **1 true, 2 false** | Dentro de las 24 h **anteriores** al pesaje | CA-3 (TC-91-005) |
| Peso de BOV-02 | 3 | **las 3 false** | Dentro de las 24 h anteriores al pesaje | CA-4 / FA-1 (TC-91-008) |
| Ambiental del galpón G1 | 3 | 1 o más true | 24 h antes del pesaje de AVE-01 | CA-9 (TC-91-057) |
| Ambiental del galpón G2 | 3 | true | Momento del pesaje de AVE-02 | Lectura de otro galpón (TC-91-023, ver 4.3) |

Si las lecturas no se pueden crear por API, se insertan en `modulo3.telemetrias` con `id_dispositivo_iot`, `timestamp_captura` y `apto_para_nic41`.

### 4.2 Hechos que generan las líneas (por la aplicación)

| Hecho | Activo | Tipo de evidencia esperado | Resultado esperado al verificar |
|---|---|---|---|
| Pesaje con el dispositivo | BOV-01 | IOT_DIRECTO | VERIFICADO (cadena completa) |
| Pesaje con el dispositivo | BOV-02 | IOT_DIRECTO | PENDIENTE_TRAZABILIDAD, nivel 1 |
| Pesaje manual | BOV-03 | REGISTRO_MANUAL | VERIFICADO |
| Evento sanitario (Veterinario) y deterioro en Finanzas (Contador) | BOV-04 | EVENTO_SANITARIO | VERIFICADO |
| Registro de un **nuevo precio** para Bovino (sin evento) | — | VARIACION_PRECIO | VERIFICADO |
| Pesaje (crecimiento de lote) | AVE-01 | IOT_DIRECTO | VERIFICADO |
| Consumo de alimento y medicamento (Productor o Veterinario) | BOV-01 | — | Deben aparecer en Costos (para TC-91-071, **no** deben generar línea de trazabilidad si son servicio veterinario o inseminación) |
| Servicio veterinario o inseminación | BOV-03 | — | No genera línea de asiento (TC-91-071) |

**Con un ejemplo de cada fila basta.** Lo importante es que existan líneas de los 5 tipos: IOT_DIRECTO, REGISTRO_MANUAL, VARIACION_PRECIO, EVENTO_SANITARIO y CIERRE_PERIODO. La de CIERRE_PERIODO aparece al cerrar un período, así que la cubre la sección 5.

### 4.3 Casos de incoherencia (requieren SQL; hacerlos en líneas **adicionales**, no en las anteriores)

| Caso | Cómo prepararlo | Para |
|---|---|---|
| Evento ajeno | Una línea de BOV-03 cuyo evento de origen sea **otro evento real de BOV-01** (cambiar el evento referenciado en el origen de la línea). | TC-91-020 / CA-7 |
| Lecturas de otro activo | Lecturas aptas del dispositivo de BOV-01 vinculadas al pesaje de un bovino sin dispositivo. | TC-91-022 |
| Galpón distinto | Pesaje de AVE-02 sustentado con la lectura ambiental del galpón **G2** cuando el activo está en **G1** (o al revés). | TC-91-023 |
| Lectura posterior al evento | Lectura apta con `timestamp_captura` **1 día después** del evento. | TC-91-024 |
| Evento posterior a la variación | Evento con fecha posterior a la variación de valor razonable que lo usa. | TC-91-025 |

Si alguno no se puede preparar sin romper la integridad de la base, avisen y se acuerda otra forma de prepararlo; el caso no se reporta como bloqueado por falta de datos.

### 4.4 No verificar el período

**No ejecuten la verificación de trazabilidad del período** («Verificar trazabilidad» o `POST /finanzas/periodos/{id}/trazabilidad`): esa es justamente la prueba de QA (RF-91 TC-M06-G47 y TC-M06-G53). Dejen las líneas en VERIFICACION_PENDIENTE.

## 5. RF-92 — Período CERRADO con informes de revelaciones

### 5.1 Período CERRADO de QA

Un período **MENSUAL** del titular QA-M06, cerrado **con el flujo normal** (Finanzas → Cierre, Contador, autorizando las exclusiones si las pide). El cierre genera solo el estado de resultados y la primera versión del informe en BORRADOR. Antes de cerrar, el período debe tener:

| Movimiento | Activo | Para |
|---|---|---|
| Compra (reconocimiento con costo) | BOV-01 | Rollforward: compras (TC-92-019) |
| Nacimiento dentro del período (cría registrada en M02 y reconocida) | Nuevo `QA-M06-BOV-05` | Activo sin valor inicial (TC-92-020) |
| Baja o muerte dentro del período | BOV-03 | Activo sin valor al cierre (TC-92-021) |
| Variación positiva por transformación biológica (pesaje con más peso) | BOV-01 | Párr. 40a (TC-92-008) |
| Variación **negativa** por precio (precio nuevo más bajo) | Bovino | Signo conservado y partidas compensadas (TC-92-009/010) |
| Producción o cosecha (producto agrícola) | AVE-01 o el que aplique | Rollforward: cosechas (TC-92-019) |
| Evento sanitario | BOV-04 | Sección de riesgos sanitarios (TC-92-035) |
| Activo valorado por costo | COSTO-01 | Párr. 54 (TC-92-027) |
| Dos especies (Bovino y Ave) | — | Agregación por especie (TC-92-023) |

### 5.2 Informes en los 4 estados (en ese período, con el Contador)

| Orden | Acción | Estado final | Para |
|---|---|---|---|
| 1 | El cierre deja la versión 1 en BORRADOR. **Aprobarla.** | V1 APROBADO | — |
| 2 | Generar otra versión («sin novedad») y **aprobarla**. | V2 APROBADO, V1 pasa a **ARCHIVADO** | TC-92-059, 065 |
| 3 | Generar otra versión y **rechazarla** con una razón de al menos 20 caracteres. | V3 **RECHAZADO** | TC-92-062, 069 |
| 4 | Generar otra versión y **dejarla sin resolver**. | V4 **BORRADOR** | TC-92-007, 063, 068 |

Al generar las versiones 2, 3 y 4, si el sistema pide justificar inconsistencias, usen un texto de al menos 20 caracteres (por ejemplo «QA M06: inconsistencia conocida, se continúa para pruebas»).

### 5.3 Período con alertas de consistencia (opcional)

Un segundo período CERRADO donde el rollforward **no cuadre** (por ejemplo, un ajuste por SQL al valor de cierre de un activo de más de 1 COP) y un informe generado con justificación. Sirve para TC-92-044, 046 y 050. Si es complicado, se omite y QA lo marca como bloqueado.

## 6. Período EN_CIERRE (solo SQL)

EN_CIERRE es un estado de paso que dura lo que dura el cierre, así que no se puede dejar por la aplicación. Si se acepta tocarlo por SQL:

- Creen **otro** período del titular QA-M06 (no usen los de las secciones 4 y 5) y pongan `estado = 'EN_CIERRE'` en `modulo6.periodos_contables`.
- Sirve para TC-91-044 y TC-92-038: verificar o generar el informe sobre ese período debe responder 422.
- Si no se acepta, avisen y se acuerda otra forma de prepararlos; no se reportan como bloqueados por falta de datos.

## 7. Sandbox con rollback

Para las pruebas marcadas **[escritura]** (verificar trazabilidad, generar y aprobar informes), QA necesita saber:

1. Si `ENABLE_TEST_SANDBOX=true` está activo en TEST.
2. Cómo se abre una ejecución con la cabecera `X-Test-Run-Id` (secreto o endpoint de inicio) y que el cierre es `DELETE /test-control/runs/{id}`.

Con eso las colecciones pueden escribir dentro del sandbox y todo se revierte al final. Sin el sandbox, las pruebas de escritura solo se ejecutan con autorización de Coordinación.

## 8. Qué devolver a QA

| Dato | Valor |
|---|---|
| NIT y DV del titular QA-M06 | |
| `id_periodo_contable` del período ABIERTO (sección 4) | |
| `id_periodo_contable` del período CERRADO (sección 5) | |
| `id_periodo_contable` del período EN_CIERRE (sección 6), si se creó | |
| `id_periodo_contable` del período con alertas (5.3), si se creó | |
| `id_activo_biologico` de BOV-01 a BOV-05, AVE-01, AVE-02 y COSTO-01 | |
| `id_informe` de V1 (ARCHIVADO), V2 (APROBADO), V3 (RECHAZADO) y V4 (BORRADOR) | |
| Casos de 4.3 o 6 que no se pudieron preparar | |
| Datos del sandbox (sección 7) | |

Con los identificadores de los períodos, QA ejecuta las colecciones indicando esos períodos (`--env-var periodo_abierto_qa=…`, `periodo_cerrado_qa=…`, `periodo_en_cierre_qa=…`).
