# TC-M07-G037 — RECHAZADO

## Identificación

TC-M07-G037, que agrupa TC-M07-06, TC-M07-07 y TC-M07-08: valores límite del formato de versión del contrato AAEF y del período de gracia. RF-98 v1.2. Se apoya en la precondición de formato MAJOR.MINOR, la precondición de configuración del período de gracia en M09 (mínimo 30 y 90 por defecto), las restricciones 5.4 y 5.8 y RNF-98.10. La fila de la matriz se corrigió el 2026-11-18 para ajustarla al requerimiento. Versión 1, intento 1. RUN RUN-G037-V1-20261118-071829, ambiente TEST, autorización AUT-G037-V1-20261118. Actor: Administrador QA. Commit de TEST no consultado. Herramientas: Node v22.15.1 y Newman (código 0, 0 fallos). Cypress no aplica porque el grupo es solo de API. RUN oficial; 29 de 60 solicitudes.

## Resumen de veredictos

| Caso | Estado | Motivo |
|---|---|---|
| TC-M07-06 | APROBADO | Las siete versiones mal formadas se rechazaron sin crear contrato y la 4.0 se registró en PENDIENTE. |
| TC-M07-07 | RECHAZADO | Los valores de gracia se aplican bien (29 se rechaza, 30 se acepta y por defecto quedan 90), pero el período de gracia no se puede configurar en M09. |
| TC-M07-08 | APROBADO | La deprecación con 29 días se rechazó y la versión siguió ACTIVO; con 30 días pasó a DEPRECADO con la inactivación exactamente 30 días después. |

## Detalle por caso

### TC-M07-06 — Formato de la versión del contrato

- **Preparación:** el ejecutor leyó en TEST los anexos y las versiones. Eligió el anexo 2 (APROBADO) y comprobó que las versiones 4.0 a 4.3 no existían. Todas las peticiones llevaban un cuerpo válido (tipo MAJOR, Mappers COMPRAS, vigencia a 400 días y gracia de 90 días). Solo cambiaba la versión, para que el único motivo de rechazo fuera su formato.
- **Esperado:** la precondición del RF-98 exige que la versión siga el formato MAJOR.MINOR. El requerimiento no fija un código de error para este caso. Por eso cada valor mal formado debe rechazarse con un error de cliente (4xx) sin crear contrato, y la 4.0 debe registrarse en PENDIENTE.
- **Observado:** las siete versiones inválidas («4», «4.0.1», «v4.0», «4.x», «4.», «.4» y la cadena vacía) recibieron HTTP 400 con `error_code` VAL_ENTRADA en el campo `contrato_version`. El listado leído después de los siete intentos tenía exactamente las mismas versiones y estados que antes. La 4.0 se registró con HTTP 201 (id 10), en PENDIENTE y con 90 días de gracia, y apareció así en el listado.
- **Decisión: APROBADO.** El sistema solo admite versiones MAJOR.MINOR y no deja rastro de los intentos inválidos. El mensaje de detalle llega en inglés («String should match pattern …»); se anota en Observaciones porque el requerimiento no lo regula.

### TC-M07-07 — Período de gracia al registrar una versión MAJOR

- **Preparación:** se usaron la versión 4.1 para la gracia de 29 y de 30 días y la 4.2 para el valor por defecto, todo en el mismo RUN. El Administrador tiene permiso de lectura sobre la configuración global de M09, así que también se pudo consultar M09.
- **Esperado:** la restricción 5.8 impide una gracia menor de 30 días; el requerimiento no fija un código de error al registrar. Una gracia de 30 días se acepta y, si no se envía, se aplica el valor por defecto de 90. Además, la precondición del RF-98 y RNF-98.10 exigen que el período de gracia (mínimo y valor por defecto) sea configurable en M09.
- **Observado:**
  - Con 29 días, HTTP 400 VAL_ENTRADA en el campo `periodo_gracia_dias` («Input should be greater than or equal to 30»). La 4.1 no se creó.
  - Con 30 días, la 4.1 se registró (HTTP 201, id 11) en PENDIENTE con 30 días.
  - Sin el campo, la 4.2 se registró (HTTP 201, id 12) en PENDIENTE con 90 días.
  - La consulta de parámetros de M09 (`GET /configuracion/parametros`) respondió HTTP 200 con la configuración global activa (id 1): frecuencia de muestreo, heartbeat, umbral sin señal, estado y datos de la última actualización. No hay ningún campo del período de gracia de los contratos.
- **Decisión: RECHAZADO** por **INC-M07-G037-01**. Los tres valores se comportan como exige el requerimiento, pero el mínimo y el valor por defecto no se pueden configurar en M09, como pide RNF-98.10. Lo que se observa es un valor fijo, no uno configurado.

### TC-M07-08 — Período de gracia en la deprecación manual

- **Preparación:** la matriz pedía registrar y activar una 3.2 para deprecarla, pero eso es imposible en TEST: ya hay dos versiones vigentes (2.1 ACTIVO y 2.0 DEPRECADO) y una tercera activación superaría el límite de la restricción 5.3. Por eso se deprecó, dentro del RUN, la versión ACTIVO real: la 2.1 (id 3). El rollback la devolvió a ACTIVO.
- **Esperado:** con 29 días, la restricción 5.8 impide la deprecación y la versión sigue ACTIVO; el requerimiento no fija un código. Con 30 días, la versión pasa a DEPRECADO y su fecha de inactivación es la de deprecación más 30 días.
- **Observado:**
  - Con 29 días, HTTP 400 VAL_ENTRADA en el campo `dias_gracia` («Input should be greater than or equal to 30»). El listado posterior seguía mostrando la 2.1 como ACTIVO.
  - Con 30 días, HTTP 200: la 2.1 quedó en DEPRECADO con deprecación el 2026-11-18 a las 07:18:35.661952 UTC e inactivación el 2026-12-18 a las 07:18:35.661952 UTC, exactamente 30 días después. El listado posterior mostró la misma fecha de inactivación.
- **Decisión: APROBADO.** La deprecación respeta el mínimo de 30 días y calcula la inactivación con exactitud.

## Comprobaciones API

- TC-M07-06 / API / formato_1 a formato_7: APROBADO; 400 VAL_ENTRADA y ningún contrato creado; resultado.json.
- TC-M07-06 / API / registro_4_0: APROBADO; 201, PENDIENTE y 90 días; resultado.json.
- TC-M07-07 / API / gracia_29: APROBADO; 400 sin crear la 4.1; resultado.json.
- TC-M07-07 / API / gracia_30: APROBADO; 201 con 30 días; resultado.json.
- TC-M07-07 / API / gracia_defecto: APROBADO; 201 con 90 días; resultado.json.
- TC-M07-07 / API / m09_configurable: RECHAZADO; la configuración de M09 no expone el período de gracia; resultado.json y Newman.
- TC-M07-08 / API / deprecar_29: APROBADO; 400 y la versión sigue ACTIVO; resultado.json.
- TC-M07-08 / API / deprecar_30: APROBADO; DEPRECADO; resultado.json.
- TC-M07-08 / API / inactivacion_30: APROBADO; inactivación a +30 días exactos; resultado.json.

## Evidencias reales

resultado.json, preflight.json, contexto_operacion.json, newman/newman-G037.json y newman/newman-G037.html.

## Incidencias de producto

### INC-M07-G037-01 — El período de gracia de los contratos AAEF no se puede configurar en M09

**Requisito:** RF-98, precondición «Configuración del período de gracia (M09)»: debe existir una configuración válida del período de gracia para cambios MAJOR, con un mínimo de 30 días y un valor por defecto de 90. RNF-98.10: el período de gracia y las reglas de transición deben ser configurables desde M09. La restricción 5.8 repite que el período debe ser configurable en M09.

**Pasos para reproducir:** como Administrador (con permiso de lectura sobre `configuraciones_globales`), consultar `GET /configuracion/parametros` y buscar el período de gracia de los contratos AAEF. Después, registrar una versión MAJOR sin `periodo_gracia_dias` y observar que siempre queda en 90 días, y una con 29 días y observar que siempre se rechaza, sin que exista un valor configurado que lo determine.

**Esperado:** M09 expone el período de gracia (mínimo y valor por defecto) y permite configurarlo, y el registro y la deprecación de versiones usan esos valores.

**Obtenido:** la configuración de M09 solo expone frecuencia de muestreo, heartbeat, umbral sin señal, estado y datos de actualización, sin ningún campo de gracia. Aun así, el registro aplica 90 días por defecto y rechaza 29, y la deprecación rechaza 29, lo que indica valores fijos en lugar de configurables. La consulta de solo lectura a la BD de TEST (2026-11-18) tampoco encontró ningún parámetro de gracia en M09 ni en otras tablas de configuración.

**Causa probable (hipótesis a partir del código, sin confirmar en TEST):** los valores están fijados en el código y no se leen de la configuración.
- La entidad define las constantes `GRACIA_MINIMA_DIAS = 30` y `GRACIA_DEFECTO_DIAS = 90` (`src/accounting_integration/domain/entities/contrato.py:19-20`).
- El caso de uso las usa directamente al registrar (`src/accounting_integration/application/use_cases/contratos/gestionar_contratos_use_case.py:72-76`) y al deprecar (`contrato.py:78-84`).
- Los DTO repiten esos límites como literales: `periodo_gracia_dias` con `ge=30` (`src/accounting_integration/infrastructure/dto/m07_dto.py:101`) y `dias_gracia` con `ge=30` y valor por defecto 90 (`m07_dto.py:105-106`). Por eso el rechazo de 29 días llega como VAL_ENTRADA antes del caso de uso.
- La configuración global de M09 (`src/configuration/infrastructure/routers/configuracion_global_router.py:79-102` y su esquema de respuesta) no tiene ningún campo de gracia.
- En consecuencia, tampoco se puede dar el flujo FA-10 (bloquear la activación de una MAJOR si el período configurado es menor de 30 o no está definido), porque no existe un valor configurado que validar.

**Impacto y severidad:** MEDIA. Los valores que se aplican hoy coinciden con los del requerimiento (30 y 90), así que el comportamiento observado es correcto. Pero cambiarlos exige modificar el código y desplegar, en lugar de configurarlos en M09 como pide RNF-98.10, y FA-10 no se puede ejercer. Certeza de la discrepancia: CONFIRMADA en TEST (API pública y consulta de solo lectura a la BD). Causa raíz: hipótesis no verificada en la versión desplegada. Clasificación: DEFECTO_FUNCIONAL_CANDIDATO, porque se trata de una funcionalidad exigida que no existe.

**Primera atención:** Desarrollo, porque falta la configuración exigida en M09 y su uso en M07.

**Evidencias:** `resultado.json`: solicitud G037-021 (configuración de M09), G037-015 y G037-023 (rechazo de 29 días) y G037-019 (90 días por defecto); `newman/newman-G037.json` (lectura de la configuración de M09).

## Observaciones

- Los detalles de los rechazos por formato y por gracia llegan en inglés («String should match pattern …» e «Input should be greater than or equal to 30»), igual que la lista vacía de INC-M07-G036-01. El manejador de errores solo traduce algunos tipos de error de Pydantic (`src/shared/error_handlers.py:256-275` y `:303`). El RF-98 no regula el texto de estos mensajes, así que no se abre incidencia; se deja para revisión de Desarrollo junto con INC-M07-G036-01.
- La lectura de M09 devuelve el nombre de la persona que actualizó la configuración. Este informe no lo reproduce.

## Problemas técnicos y análisis de causas

Ninguno. El RUN se ejecutó al primer intento.

## Cierre y rollback

Al terminar se envió `DELETE /test-control/runs/RUN-G037-V1-20261118-071829`, que respondió HTTP 200. La lectura posterior, sin las cabeceras del RUN, mostró los mismos ids y estados de versiones que antes de empezar: la 2.1 volvió a ACTIVO y no quedaron la 4.0, 4.1, 4.2 ni 4.3. Rollback verificado. El único efecto persistente fue el inicio de sesión del Administrador QA anterior al RUN.

## Conclusión y acciones

El sistema aplica correctamente los valores límite de RF-98: solo admite versiones MAJOR.MINOR, exige al menos 30 días de gracia al registrar y al deprecar, usa 90 días por defecto y calcula con exactitud la fecha de inactivación. Lo que falla es que esos valores no se pueden configurar en M09 (INC-M07-G037-01, MEDIA). Acciones: derivar INC-M07-G037-01 a Desarrollo y reevaluar el grupo completo con una nueva autorización cuando informen la corrección.

## Historial del informe

Enmienda (2026-11-18): informe redactado con formato M06 y enmascarado el nombre de persona de la lectura de M09 (nombre_usuario → [NOMBRE]) en resultado.json y newman/; veredictos sin cambios. SHA-256 de resultado.json antes aa6111603b775ab2dedb94b801d0bf2e63e0d321ad0634d54a73151d369c7c05 y después 597d147e0497a310a67d191b18aa4e459329a280ed431de5b4e25c3b65e28e96.
