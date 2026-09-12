# RESULTADO — TC-M02-G95 (reformulado)

## 0. Resumen ejecutivo

| Dimensión | Resultado |
|---|---|
| VEREDICTO | **RECHAZADO** |
| TC-M02-309 | APROBADO: inexistencia confirmada, 404 semántico, sin dataset |
| TC-M02-310 | RECHAZADO: inconsistencia demostrada; retorna 200 y expone datos en lugar de 409 |
| TC-M02-311 | APROBADO: 200; activo correcto; API = BD = 250 kg |
| Solicitudes oficiales finales | 3/3; 17 assertions, 14 aprobadas y 3 fallidas, todas en 310 |
| Endpoint matriz | GET /activos-biologicos/{id_activo}/datos-analiticos |
| Endpoint ejecutado | GET /activos-biologicos/{id_activo}/datos-consolidados |
| Discrepancia matriz ↔ Swagger | SÍ |
| Principal utilizado | Usuario 35, m2m.nuevo@ejemplo.com, JWT oficial; READ comprobado con GET 200 |
| Escrituras funcionales QA | 0 |
| Equipo responsable del defecto | Desarrollo Backend |

## 1. Identificación

- Proyecto SGPMP, módulo 2, RF-50, CU12; responsable QA: Juan Esteban.
- Repositorio: https://github.com/Arekkazu/sgpmp-backend.git
- Rama: qa/juan-esteban-m02.
- HEAD: 41369ea4ab3948eacb1ab9b2d0549310e285eeae.
- Ambiente: TEST. Herramienta: colección Postman v2.1 ejecutada con Newman; reporters cli, json, htmlextra.
- Ventana de evidencia final UTC: 2026-09-10T23:34:06.380569+00:00 — 2026-09-10T23:34:13.756835+00:00.
- Finalización Colombia: 2026-09-10T18:34:13.756835-05:00.
- Estado inicial: múltiples archivos QA no versionados de otros casos; G95 solo tenía .gitkeep. No se modificaron archivos de otros casos.
- Últimos commits observados: 41369ea, a729fef, f707e8d, f51316f, d88af48.

## 2. Gate

| Gate | Evidencia |
|---|---|
| Repo y rama correctos | origin y rama coinciden |
| OpenAPI TEST | HTTP 200, consulta nueva |
| PostgreSQL | member_qa, SELECT 1 = 1, transaction_read_only = on |
| Endpoint RF-50 | summary vivo identifica explícitamente CU12 - RF-50 |
| Principal autorizado | Login oficial HTTP 200 y control READ HTTP 200; no se alteraron permisos |

Base: https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test

## 3. Resolución de contrato y cobertura

**DISCREPANCIA MATRIZ ↔ SWAGGER.** `/datos-analiticos` no aparece en OpenAPI; `/datos-consolidados` está identificado como “Exponer datos consolidados del activo biológico para módulos analíticos (CU12 - RF-50)”. Se conserva la ruta de matriz como referencia; la prueba usa el contrato desplegado.

La respuesta viva expone `metricas_actuales` en la raíz, no en `secciones.metricas_actuales`. La vista BD tiene `codigo`, no `identificador`; se usa `codigo AS identificador`. La consulta original dio UndefinedColumn y se corrigió tras inspeccionar el esquema: error de preparación, no del producto.

Consumidor técnico: usuario existente 35. Se obtuvo JWT nuevo por POST `/sesiones/` oficial y se comprobó READ. No se crearon usuarios ni permisos. No se verificó una identidad de servicio M04 utilizable; la cobertura literal M04 queda no demostrada y no se presenta este principal como M04. Los veredictos funcionales usan el consumidor autorizado permitido por el documento.

## 4. TC-M02-309

- ID 99999: SELECT devolvió 0 filas.
- GET `/activos-biologicos/99999/datos-consolidados?tipo_dato=todos&pagina=1&page_size=20`.
- Esperado/obtenido: 404 / 404.
- `error_code=ACTIVO_NO_ENCONTRADO`.
- Mensaje: “El activo biológico con ID 99999 no existe en los registros del sistema.”
- Sin dataset analítico, datos de otro activo ni detalles internos detectados.
- **APROBADO**, 4/4 assertions.

## 5. TC-M02-310

- Candidato redescubierto: 289, QAJE-DAT-INFRAINACT, ACTIVO.
- Infraestructura 49: `es_activo=false`.
- Historial 236: infraestructura 49; inicio 2026-06-01 08:00 UTC; `fecha_fin=null`.
- Gestión 68: ciclo 10; `es_activa=true`, `fecha_finalizacion=null`.
- Vista de cierres válidos: 0 filas para 289.
- GET `/activos-biologicos/289/datos-consolidados?tipo_dato=todos&pagina=1&page_size=20`.
- Esperado: 409 por inconsistencia jerárquica y ausencia de dataset.
- Obtenido: **200**, con identificador, infraestructura, fase activa, historial de fases y métricas (`peso_actual=180.0 kg`).
- No hay mensaje de inconsistencia. No se observó autocorrección funcional.
- **RECHAZADO**, 3 assertions fallidas: HTTP, ausencia de dataset y causa esperada. El control de ausencia de detalles internos sí pasó.

## 6. TC-M02-311 — Fuente BD y API

Se eligió 279 tras redescubrir los candidatos: tiene identificador inequívoco, cuatro eventos PESO positivos, ficha integral visible e infraestructura 48 activa. Se verificó de nuevo; no se asumió válido por ejecuciones históricas.

| Dato | BD | API |
|---|---|---|
| Activo | 279 | 279 |
| Identificador | QAJE-CREC-OK | QAJE-CREC-OK |
| Peso | 250.00 | 250.0 |
| Unidad | kg | kg |
| Fecha último peso | 2026-09-10 | 2026-09-10 |
| Cantidad | null | null |
| Biomasa | null | null |

Eventos PESO: 234, 232, 228, 227; todos 250.00 kg. Último: 234, 2026-09-10 08:33:36 UTC. Consulta de PESO <= 0: 0.

GET `/activos-biologicos/279/datos-consolidados?tipo_dato=metricas&pagina=1&page_size=20`: HTTP 200. Peso JSON numérico, finito y positivo; comparación numérica exacta con BD, unidad idéntica y fecha equivalente. No se detectaron NaN/Infinity, pesos negativos o IDs ajenos. Cantidad/biomasa null coherentes.

**APROBADO**, 9/9 assertions. No se buscó ni creó corrupción; no se esperó HTTP 500.

## 7. No mutación funcional y contabilidad

- SQL writes emitidos por QA: 0. Conexión protegida por default_transaction_read_only=on.
- POST/PUT/PATCH/DELETE del caso: 0. Las solicitudes oficiales son GET.
- Autenticación auxiliar: 3 POST oficiales `/sesiones/` durante la sesión; se cuentan aparte, no se ocultan como GET ni como cero tráfico POST total.
- GET de control: 3. GET oficiales: 3 finales más 3 de una corrida preliminar de la misma colección.
- La primera corrida Newman terminó; la consolidación Python falló por UnicodeEncodeError de consola. Se corrigió la codificación y se repitió la colección para completar evidencia antes/después. HTML/JSON conservan la corrida final; no se mezclan sus estadísticas con la preliminar.
- Hashes SHA-256 antes/después iguales para filas completas de activos 279/289, sus eventos, mediciones, historiales, fases e infraestructuras 48/49.
- Fuente de peso repetida e idéntica; consultas esenciales de 310 repetidas sin cambio. No se observó activación de infraestructura, cambio de asociación, cierre de historial o fase, ni alteración de peso.
- Límite: la igualdad compara los estados muestreados; no demuestra ausencia de cambios transitorios entre consultas ni cubre toda la BD.
- Auditoría automática RF50 observada: 3 registros en la ventana final. Es metadata generada por el sistema, no modificación funcional emitida por QA. Evidencia incluida en JSON.

## 8. Diagnóstico y atribución

310: clasificación **E — DEFECTO DEL SISTEMA**, integridad/flujo. Se descartaron candidato inexistente, infraestructura activa, relación cerrada, cierre válido, endpoint incorrecto, token inválido, falta de READ y fallo de proxy: BD demuestra el escenario; ruta OpenAPI inequívoca; respuesta de negocio 200; control autenticado 200. No es un 401/403 ni un error de path JSON.

El código local del HEAD revisado, `src/biological_assets/application/use_cases/gestion/consultar_datos_consolidados_use_case.py`, valida existencia y obtiene los datos; el repositorio consulta infraestructura sin filtro de actividad. Es una explicación compatible con lo observado. **Causa raíz desplegada no confirmada por QA**: no se verificó el SHA del servicio remoto.

Errores de preparación resueltos: columna `identificador` de la vista y codificación de consola (clasificación A). No afectan las assertions finales ni justifican el 200 de 310.

## 9. Hallazgos reportables

| Campo | Defecto 310 | Desalineación matriz/Swagger |
|---|---|---|
| Type | bug | task documental |
| Severity Taiga | Important | Minor |
| Priority | High | Low |
| Severidad interna | Severo | Bajo |
| Tiempo máximo | 1 día hábil | 3 días hábiles |
| Fecha límite propuesta (Colombia) | 2026-09-11 18:34 -05:00 | 2026-09-15 18:34 -05:00 |
| Equipo | Desarrollo Backend | Backend / responsable funcional |
| Impacto | Expone datos analíticos con jerarquía operativa inconsistente | Matriz apunta a ruta ausente |
| Reproducibilidad | Precondición y request conservados; fallo final 200 vs 409 | OpenAPI nuevo no incluye ruta de matriz |

Fechas calculadas desde la ejecución según los plazos internos del documento; propuestas QA, no compromisos aceptados por los equipos. Hallazgos preparados localmente, sin publicar tickets ni enviar mensajes.

## 10. Verificaciones V1–V26

| Verificaciones | Resultado |
|---|---|
| V1–V6 (309) | Cumplidas con consumidor técnico autorizado; M04 literal no demostrado |
| V7–V10 (310: precondición) | Cumplidas |
| V11–V13 (310: rechazo sin exposición) | Incumplidas |
| V14–V23 (311) | Cumplidas dentro de la respuesta de métricas recibida |
| V24 (cero escrituras funcionales QA) | Cumplida |
| V25 (sin cambios funcionales) | Cumplida en comparación antes/después del alcance descrito |
| V26 (evidencia consolidada) | Cumplida |

## 11. Reproducción y artefactos

1. Revalidar repo/rama, contrato TEST, usuario READ y precondiciones mediante los SELECT incluidos en `qa_evidence.queries` del JSON.
2. Actualizar id310, id311 y variables de fuente en la colección. No reutilizar el valor 250 ni IDs sin verificación nueva.
3. Inyectar token oficial en un entorno Postman privado o en memoria mediante Newman. La colección versionable deja token vacío; no pasar secretos literales al historial de consola.
4. Ejecutar la colección única con timeout 30000 ms. Conservar errores reales del producto; repetir los SELECT esenciales y contrastar fuente.
5. Generar reportes con redacción de credenciales **antes** de serializar (la corrida usa hook beforeDone). No exportar un environment con token real.

Archivos: `../test_tc_m02_g95.json`, `reporte_tc_m02_g95.html`, `reporte_tc_m02_g95.json` y este informe. JSON contiene respuestas y assertions Newman, consultas SQL y resultados consolidados, hashes antes/después y auditoría automática. HTML es el reporte htmlextra de la misma corrida. `.gitkeep` preexistente se conserva.

## 12. Veredicto final

**RECHAZADO.** 309 y 311 cumplen. 310 incumple el rechazo esperado ante inconsistencia jerárquica demostrada. Se requiere corrección de Desarrollo Backend y reejecución de G95; no hubo cambios productivos, de rama, commit, push, merge, migraciones ni deploy.
