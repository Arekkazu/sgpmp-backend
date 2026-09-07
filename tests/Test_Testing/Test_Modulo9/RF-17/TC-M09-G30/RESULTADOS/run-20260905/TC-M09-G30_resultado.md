# TC-M09-G30 — RESULTADO

## DECISIÓN GENERAL

**BLOCKED — AUDITORÍA NO EXPUESTA/NO VERIFICABLE EN TEST. HALLAZGO REPORTABLE A DESARROLLO BACKEND.**

El caso original `TC-M09-64` no consumió ninguna de sus dos escrituras
funcionales. La revisión de contrato obligatoria demostró que RF-17 registra
auditoría de umbrales, pero TEST no ofrece una API para consultar el registro
por su `id_umbral_ambiental` ni correlacionar de forma inequívoca los eventos
`CREATE` y `UPDATE` con las operaciones que habría ejecutado esta corrida.

| Caso | Resultado | Motivo | ¿Reportar a Desarrollo? |
| --- | --- | --- | --- |
| TC-M09-64 | **BLOCKED — AUDITORÍA NO EXPUESTA/NO VERIFICABLE EN TEST** | `CONTRACT_REQUIREMENT_MISMATCH`: la auditoría RF-17 existe en el modelo persistente, pero no tiene endpoint de consulta específico ni integración con los eventos que expone D09. | **Sí — Desarrollo Backend (Configuration/RF-17 y Auditoría/D09).** |

## Contrato de auditoría verificado

El Administrador real de TEST fue autenticado una vez y confirmado por
`GET /usuarios/me`: `id_usuario=1`, rol `Administrador`, con coincidencia del
actor solicitado. Sus permisos reales habilitan D09 `(recurso 6, acción 2)` y
los tres permisos de umbrales requeridos: crear `(20,1)`, consultar `(20,2)` y
modificar `(20,3)`.

`GET /auditoria/` respondió `200` y usa los filtros `id_usuario`,
`tipo_evento`, `categoria`, fechas y paginación. Su evento publicado contiene
usuario, `fecha_evento`, tipo, módulo, detalle e integridad; no expone
`id_umbral_ambiental`, un recurso RF-17 o un filtro por ese ID. El catálogo de
D09 respondió `200` con 24 tipos, ninguno asociado a “umbral”.

En contraste, RF-17 persiste de forma append-only en
`modulo9.auditorias_umbrales_ambientales`, con `id_umbral_ambiental`,
`id_usuario`, `tipo_operacion`, `valores_anteriores`, `valores_nuevos` y
`fecha_gestion`. `RegistrarUmbralUseCase` registra `CREATE` y
`EditarUmbralUseCase` registra `UPDATE` mediante
`SqlAlchemyAuditoriaUmbralRepository`. Ninguno de ambos casos de uso emplea
`SqlAlchemyEventoRepository`, que es la fuente de `GET /auditoria/`; tampoco
hay router o endpoint OpenAPI de consulta para la tabla de auditoría de
umbrales.

La evidencia sanitizada está en
[contrato-auditoria.json](contrato-auditoria.json).

## AUDITORÍA VERIFICADA

| Operación | Recurso/ID | Usuario | Fecha/hora | Valores | Evento encontrado | Coincide |
| --- | --- | --- | --- | --- | --- | --- |
| Creación | No ejecutada para no consumir una escritura sin mecanismo de correlación | Administrador autenticado (id 1) | N/A | N/A | No verificable por API | N/A |
| Modificación | No ejecutada; depende de creación correlacionable | Administrador autenticado (id 1) | N/A | N/A | No verificable por API | N/A |

## BEFORE / AFTER

No aplica. No se creó ni modificó un umbral: efectuar `POST` y `PATCH` sin una
consulta capaz de vincular su ID con los eventos RF-17 produciría evidencia
funcional que no puede satisfacer TC64 y agotaría de forma irreversible el
presupuesto máximo de dos escrituras.

## Datos y ejecución

- Fecha/hora del discovery: `2026-09-05T20:08:48-05:00`.
- Backend TEST: `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`.
- Frontend TEST: `https://sigab-frontendtest-6aqrny-d2b730-158-69-200-27.sslip.io`.
- Backend local: rama `qa/juan-esteban-m09`, SHA
  `adc3932b9f0293a76ebec7e89ed877274791b6a1`.
- Frontend local: rama `qa/juan-esteban-m09`, SHA
  `966621df4e2c6a1f2c9233ea5ebefbb9e3bc2f56`.
- SHA desplegado en TEST no confirmado.
- Newman `6.2.2` y `newman-reporter-htmlextra` `1.23.1` están disponibles.
  No se ejecutó Newman ni se creó HTML porque el bloqueo de contrato se
  identificó antes de las escrituras funcionales.
- POST funcionales de umbral: `0`; PATCH funcionales de umbral: `0`; SQL write:
  `0`; consultas PostgreSQL: `0`.
- El único POST realizado fue el login de identidad requerido. Token, cabeceras
  de autorización, cookies y contraseña se mantuvieron solo en memoria y no
  aparecen en los artefactos.

## Origen y acción

| Producto | Automatización/prueba | Entorno | Bloqueo | Acción |
| --- | --- | --- | --- | --- |
| **Sí: defecto de contrato y observabilidad API.** | No. | No: API, identidad y D09 respondieron correctamente. | Sí: el defecto impide ejecutar el oráculo completo de TC64. | **REPORTAR A DESARROLLO BACKEND.** |

Debe reportarse a **Desarrollo Backend**, responsable de Configuration/RF-17 y
Auditoría/D09. El defecto es que el producto persiste los datos de auditoría de
umbrales pero no proporciona la interfaz API requerida para consultarlos y
correlacionarlos. No se asigna a Despliegue: el OpenAPI de TEST muestra el mismo
vacío contractual que el código revisado. Tampoco se asigna a DBA: el modelo
RF-17 declara la tabla y todos los campos necesarios, sin evidencia de fallo de
esquema, conexión, permisos o disponibilidad de PostgreSQL.

No se creó un ticket, conforme al alcance. Una vez Desarrollo exponga o integre
la consulta, se podrá realizar una nueva corrida controlada de `1 CREATE + 1
UPDATE` con correlación real. PostgreSQL no se usó como sustituto porque el
objetivo exige evidencia consultable mediante API.

## DEFECTO DETECTADO

- **ID:** Pendiente de asignación según Registro de Errores vigente.
- **TC / RF:** `TC-M09-64` / `RF-17`.
- **Título:** La auditoría de umbrales ambientales RF-17 no es consultable ni
  correlacionable mediante la API D09.
- **Responsable:** Desarrollo Backend — Configuration/RF-17 y Auditoría/D09.
- **Actor validado:** Administrador de TEST, `id_usuario=1`.
- **Pasos de reproducción:**
  1. Autenticar como Administrador y confirmar permisos de umbrales y auditoría.
  2. Consultar `GET /auditoria/` y `GET /auditoria/catalogo/tipos-evento`.
  3. Revisar el contrato OpenAPI y los casos de uso RF-17 de creación y edición.
  4. Intentar definir la correlación exigida por TC64 para
     `id_umbral_ambiental`, `CREATE` y `UPDATE`.
- **Esperado:** una API D09 o RF-17 debe permitir recuperar el evento de
  auditoría por el recurso creado/modificado, incluyendo actor, fecha/hora,
  operación y valores registrados.
- **Obtenido:** D09 publica eventos globales sin filtro ni campo de
  `id_umbral_ambiental`; su catálogo no incluye evento de umbral. RF-17 escribe
  `modulo9.auditorias_umbrales_ambientales` de forma aislada y no expone un
  endpoint para consultarla.
- **Persistencia:** el modelo RF-17 sí declara los campos necesarios; el fallo
  es de exposición/integración del contrato API, no de evidencia de escritura
  fallida en la base de datos.
- **Reproducibilidad:** reproducible con OpenAPI TEST y revisión del código de
  la rama evaluada, sin crear datos ni modificar infraestructura.
- **Evidencia:** [contrato-auditoria.json](contrato-auditoria.json).
- **Severidad:** Pendiente de validar contra Registro de Errores vigente.
- **Tiempo máximo / fecha límite:** Pendiente.

## Seguridad y límites respetados

- No se modificó código funcional, dependencias, infraestructura, migraciones,
  Docker, configuración de TEST ni datos directamente en PostgreSQL.
- No se manipularon registros de auditoría ni se eliminaron/restauraron datos.
- No se ejecutaron G22–G29, G31 ni G32; G22 quedó expresamente fuera de alcance.
- No se usó Cypress. No hubo commit, push, pull, merge ni cambio de rama.
- Los artefactos nuevos de esta ejecución se mantienen exclusivamente en
  `sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-17/TC-M09-G30/`.

## Git final

Ambos repositorios siguen en `qa/juan-esteban-m09`, con SHA
`adc3932b9f0293a76ebec7e89ed877274791b6a1` en backend y
`966621df4e2c6a1f2c9233ea5ebefbb9e3bc2f56` en frontend. `git diff --stat`
está vacío en ambos. Se preservaron los artefactos untracked externos G24–G29
en backend; los de frontend G22 y G28 permanecen fuera de alcance y no fueron
considerados por G30. El detalle de `status`, `diff --stat` y `ls-files` está
en [git-final.json](git-final.json). No hubo operaciones de escritura Git.

La ejecución se detiene para revisión humana.
