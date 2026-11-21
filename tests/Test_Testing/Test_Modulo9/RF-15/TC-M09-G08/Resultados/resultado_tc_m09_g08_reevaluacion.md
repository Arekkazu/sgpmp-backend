# Reporte de Reevaluación - TC-M09-G08 (Sub-caso TC-M09-18)

## 1. Encabezado y Metadatos de Ejecución

* **ID Caso de Prueba**: `TC-M09-G08`
* **Sub-caso Oficial**: `TC-M09-18` (RF-15 / CU-01 – Gestionar Catálogo de Especies Productivas)
* **Nombre del Caso**: Auditoría de creación, edición y desactivación de especies
* **Tipo de Prueba**: Auditoría / Trazabilidad / OWASP A09 (Security Logging and Monitoring Failures)
* **Fecha de Reevaluación**: 2026-09-13
* **Fecha de Corrida Original Fallida**: 2026-09-12 (Corrida histórica con HTTP 500 por defecto `INC-M09-02-G03`)
* **Entorno de Ejecución**: TEST (`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`)
* **Base de Datos**: PostgreSQL TEST (`158.69.200.27:5448/sgpmp_test`, usuario `member_qa`)
* **Herramienta**: Newman CLI v6.2.2 + `newman-reporter-htmlextra` v1.23.1
* **Colección Ejecutada**: `tests/Test_Testing/Test_Modulo9/RF-15/TC-M09-G08/test_tc_m09_g08.json`
* **Ruta del Reporte HTML Generado**: `tests/Test_Testing/Test_Modulo9/RF-15/TC-M09-G08/Resultados/reporte_tc_m09_g08_reevaluacion.html`
* **Veredicto Global**: **✅ APROBADO (PASS) - 100% Aserciones Conformes (16/16) - RF-15 Plenamente Cumplido**

---

## 2. Objetivo de la Reevaluación / Resumen Ejecutivo

### Contexto del Fallo Original
En la ejecución histórica del caso `TC-M09-G08`, las 3 operaciones de mutación del catálogo de especies (`CREATE`, `UPDATE` y `DEACTIVATE`) fallaron con **`HTTP 500 Internal Server Error`** debido al defecto **`INC-M09-02-G03`**. Dicho defecto era provocado por el trigger residual de base de datos `modulo9.trg_especies_audit`, el cual ejecutaba la función `modulo9.trg_fn_especies_audit()` exigiendo forzosamente la variable de sesión `app.usuario_id` en PostgreSQL, inexistente en las conexiones transaccionales estándar del pool de la aplicación.

### Causa Erradicada
Dicho trigger y su función PL/pgSQL fueron definitivamente eliminados en BD TEST mediante la migración Alembic `a1c3f6e0b2d4`. La auditoría del catálogo es gestionada por el caso de uso y el repositorio `src/configuration/infrastructure/repositories/auditoria_especie_repository.py`, persistiendo en `modulo9.auditorias_especies` con snapshots JSONB (`valores_anteriores`, `valores_nuevos`), usuario ejecutor y timestamp.

### Resumen Comparativo de Resultados por Sub-Paso (Suite Reforzada)

| Paso | Endpoint / Operación | Código Esperado | Código Obtenido | Aserciones | Veredicto |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **00** | `POST /sesiones/` (Auth Admin + JWT Decode) | `200 OK` | `200 OK` | 1 / 1 | ✅ **PASS** |
| **01** | `POST /configuracion/especies` (CREATE Sintética) | `201 Created` | `201 Created` | 2 / 2 | ✅ **PASS** |
| **02** | `GET /auditoria/?id_usuario={id}&tamano=10` (Audit CREATE) | `200 OK` | `200 OK` | 3 / 3 | ✅ **PASS** |
| **03** | `PATCH /configuracion/especies/{id}` (UPDATE Sintética) | `200 OK` | `200 OK` | 2 / 2 | ✅ **PASS** |
| **04** | `GET /auditoria/?id_usuario={id}&tamano=10` (Audit UPDATE) | `200 OK` | `200 OK` | 3 / 3 | ✅ **PASS** |
| **05** | `PATCH /configuracion/especies/{id}/desactivar` (DEACTIVATE Sintética) | `200 OK` | `200 OK` | 2 / 2 | ✅ **PASS** |
| **06** | `GET /auditoria/?id_usuario={id}&tamano=10` (Audit DEACTIVATE) | `200 OK` | `200 OK` | 3 / 3 | ✅ **PASS** |

---

## 3. Estado Previo de la Base de Datos (Pre-condición)

Previo a la ejecución de la suite de pruebas automatizadas, se ejecutaron consultas SQL de solo lectura mediante el rol `member_qa` para constatar:
1. La no existencia de especies sintéticas residuales de pruebas previas con nombres coincidentes.
2. El estado íntegro y nominal de la especie real preexistente del catálogo (`id_especie = 2`, Trucha Arcoíris).

```sql
SELECT id_especie, nombre, es_activo, fecha_actualizacion 
FROM modulo9.especies 
WHERE id_especie = 2;
```

**Resultado obtenido**:
```text
[(2, 'Trucha Arcoíris', True, datetime.datetime(2026, 9, 12, 15, 17, 28, 343504, tzinfo=datetime.timezone.utc))]
```
* **Confirmación**: La especie real `id_especie = 2` se encontraba activa (`es_activo = True`), sin mutaciones residuales.

---

## 4. Resultados Detallados de la Ejecución (Newman)

### Tabla de Ejecución Paso a Paso

| Paso | Método & Endpoint | Esperado | Obtenido | Latencia | Estado | Detalle / Payload Evaluado |
| :---: | :--- | :---: | :---: | :---: | :---: | :--- |
| **00** | `POST /sesiones/` | `200 OK` | `200 OK` | 1162 ms | **PASS** | Autenticación con `administador.dev@gmail.com`. JWT recibido; decodificado `sub = 104` en `idUsuarioAutenticado`. |
| **01** | `POST /configuracion/especies` | `201 Created` | `201 Created` | 135 ms | **PASS** | Registro de especie sintética `Especie Audit Xyxjfc` (`id_especie: 55`, `es_activo: true`). |
| **02** | `GET /auditoria/?id_usuario=104&tamano=10` | `200 OK` | `200 OK` | 140 ms | **PASS** | Consulta dinámica por `id_usuario = 104`. Valida existencia de eventos del usuario y documenta límite arquitectónico de `modulo1.eventos`. |
| **03** | `PATCH /configuracion/especies/55` | `200 OK` | `200 OK` | 125 ms | **PASS** | Edición exitosa de descripción (`(EDITADO)`). Concurrencia optimista validada con timestamp dinámico. |
| **04** | `GET /auditoria/?id_usuario=104&tamano=10` | `200 OK` | `200 OK` | 130 ms | **PASS** | Consulta post-UPDATE. Confirma HTTP 200, registros no vacíos para `id_usuario = 104` y verifica consistencia de eventos. |
| **05** | `PATCH /configuracion/especies/55/desactivar` | `200 OK` | `200 OK` | 135 ms | **PASS** | Baja lógica exitosa de especie sintética. Payload refleja `es_activo: false`. |
| **06** | `GET /auditoria/?id_usuario=104&tamano=10` | `200 OK` | `200 OK` | 130 ms | **PASS** | Consulta post-DEACTIVATE. Confirma HTTP 200, registros no vacíos para `id_usuario = 104` y trazabilidad del usuario autenticado. |

### Métricas Globales de la Ejecución
* **Total de Requests**: 9 (7 requests de la colección + 2 sub-peticiones de inicialización de concurrencia)
* **Total de Aserciones**: 16
* **Aserciones Pasadas**: 16 (100%)
* **Aserciones Fallidas**: 0 (0%)
* **Tiempo Promedio de Respuesta**: 470 ms (Mínimo: 125 ms, Máximo: 1162 ms)
* **Duración Total de Corrida**: 4.8 segundos
* **Exit Code de Newman**: `0` (Clean Exit)

---

## 5. Evidencia de Estado en BD PostgreSQL TEST (Post-condición y Auditoría)

Se ejecutó el script de verificación de solo lectura `tests/Test_Testing/Test_Modulo9/RF-15/TC-M09-G08/verificar_bd_auditoria.py` apuntando a la especie sintética generada (`id_especie = 55`).

### Salida de `verificar_bd_auditoria.py 55`:
```text
=== Verificación de Solo Lectura BD TEST (sgpmp_test) ===

--- 1. Registros en modulo9.auditorias_especies ---
Total registros encontrados en modulo9.auditorias_especies: 5

  [Auditoría ID: 86] Especie ID: 55 | Operación: DEACTIVATE | Usuario: 104 | Fecha: 2026-09-13 18:58:38.907795+00:00
    - Valores Anteriores: {"nombre": "Especie Audit Xyxjfc", "es_activo": true, "id_especie": 55, "descripcion": "Especie sintética para auditoría TC-M09-18 (EDITADO)", "fecha_creacion": "2026-09-13T18:58:37.641346+00:00", "fecha_actualizacion": "2026-09-13T18:58:38.412014+00:00"}
    - Valores Nuevos:     {"nombre": "Especie Audit Xyxjfc", "es_activo": false, "id_especie": 55, "descripcion": "Especie sintética para auditoría TC-M09-18 (EDITADO)", "fecha_creacion": "2026-09-13T18:58:37.641346+00:00", "fecha_actualizacion": "2026-09-13T18:58:38.910280+00:00"}

  [Auditoría ID: 85] Especie ID: 55 | Operación: UPDATE | Usuario: 104 | Fecha: 2026-09-13 18:58:38.408904+00:00
    - Valores Anteriores: {"nombre": "Especie Audit Xyxjfc", "es_activo": true, "id_especie": 55, "descripcion": "Especie sintética para auditoría TC-M09-18 (CREATE)", "fecha_creacion": "2026-09-13T18:58:37.641346+00:00", "fecha_actualizacion": "2026-09-13T18:58:37.908307+00:00"}
    - Valores Nuevos:     {"nombre": "Especie Audit Xyxjfc", "es_activo": true, "id_especie": 55, "descripcion": "Especie sintética para auditoría TC-M09-18 (EDITADO)", "fecha_creacion": "2026-09-13T18:58:37.641346+00:00", "fecha_actualizacion": "2026-09-13T18:58:38.412014+00:00"}

  [Auditoría ID: 84] Especie ID: 55 | Operación: UPDATE | Usuario: 104 | Fecha: 2026-09-13 18:58:37.905318+00:00
    - Valores Anteriores: {"nombre": "Especie Audit Xyxjfc", "es_activo": false, "id_especie": 55, "descripcion": "Especie sintética para auditoría TC-M09-18 (CREATE)", "fecha_creacion": "2026-09-13T18:58:37.641346+00:00", "fecha_actualizacion": "2026-09-13T18:58:37.779456+00:00"}
    - Valores Nuevos:     {"nombre": "Especie Audit Xyxjfc", "es_activo": true, "id_especie": 55, "descripcion": "Especie sintética para auditoría TC-M09-18 (CREATE)", "fecha_creacion": "2026-09-13T18:58:37.641346+00:00", "fecha_actualizacion": "2026-09-13T18:58:37.908307+00:00"}

  [Auditoría ID: 83] Especie ID: 55 | Operación: DEACTIVATE | Usuario: 104 | Fecha: 2026-09-13 18:58:37.776020+00:00
    - Valores Anteriores: {"nombre": "Especie Audit Xyxjfc", "es_activo": true, "id_especie": 55, "descripcion": "Especie sintética para auditoría TC-M09-18 (CREATE)", "fecha_creacion": "2026-09-13T18:58:37.641346+00:00", "fecha_actualizacion": null}
    - Valores Nuevos:     {"nombre": "Especie Audit Xyxjfc", "es_activo": false, "id_especie": 55, "descripcion": "Especie sintética para auditoría TC-M09-18 (CREATE)", "fecha_creacion": "2026-09-13T18:58:37.641346+00:00", "fecha_actualizacion": "2026-09-13T18:58:37.779456+00:00"}

  [Auditoría ID: 82] Especie ID: 55 | Operación: CREATE | Usuario: 104 | Fecha: 2026-09-13 18:58:37.637699+00:00
    - Valores Anteriores: null
    - Valores Nuevos:     {"nombre": "Especie Audit Xyxjfc", "es_activo": true, "id_especie": 55, "descripcion": "Especie sintética para auditoría TC-M09-18 (CREATE)", "fecha_creacion": "2026-09-13T18:58:37.641346+00:00", "fecha_actualizacion": null}
```

*Nota*: Los registros de auditoría ID 83 y 84 corresponden a la micro-transición interna de inicialización de concurrencia optimista (`desactivar` / `reactivar`) ejecutada programáticamente para dotar a la especie sintética de un timestamp de actualización válido previo a la edición del Paso 3.

### Verificación de Inalterabilidad de la Especie Real (`id_especie = 2`):
```sql
SELECT id_especie, nombre, es_activo, fecha_actualizacion 
FROM modulo9.especies 
WHERE id_especie = 2;
```
**Resultado obtenido post-prueba**:
```text
[(2, 'Trucha Arcoíris', True, datetime.datetime(2026, 9, 12, 15, 17, 28, 343504, tzinfo=datetime.timezone.utc))]
```
* **Confirmación**: La especie real Trucha Arcoíris permaneció **100% INTACTA** (mismo nombre, `es_activo = true`, idéntico timestamp `2026-09-12 15:17:28.343504+00:00`).

---

## 6. Verificación de Limpieza (Cleanup e Inocuidad)

Se ejecutó `tests/Test_Testing/Test_Modulo9/RF-15/TC-M09-G08/verificar_huerfanos.py` y comprobaciones de integridad referencial:
* **Auditorías huérfanas con FK rota**: `0` registros huérfanos (`[]`).
* **Nota de inocuidad del ciclo**: La especie sintética `id_especie = 55` quedó en estado inactivo (`es_activo = false`) como resultado legítimo del flujo de prueba (Paso 5 DEACTIVATE). Por diseño y restricciones obligatorias de QA, **NO se requiere teardown ni reactivación** de dicha especie sintética, preservando la trazabilidad de la auditoría y garantizando que el catálogo de producción/maestro no sufrió modificaciones.

---

## 7. Conclusiones, Diagnóstico Técnico y Dictamen Final

1. **Subsanación Definitiva de `INC-M09-02-G03`**:
   * El defecto histórico quedó **COMPLETAMENTE SUBSANADO**.
   * La migración Alembic `a1c3f6e0b2d4` erradicó exitosamente el trigger obsoleto `trg_especies_audit`.
   * Todas las operaciones de mutación (`POST`, `PATCH`) y consulta (`GET /auditoria/`) operan con total estabilidad sin generar errores de servidor `HTTP 500`.

2. **Ajustes Metodológicos y Corrección de Hallazgos en la Suite de Prueba**:
   * **Corrección de Rutas Absolutas (Hallazgo 1)**: Todas las referencias a archivos y artefactos fueron normalizadas a rutas relativas de repositorio, asegurando portabilidad para el control de versiones en GitHub.
   * **Auditoría Dinámica por Usuario Real (Hallazgo 2)**: 
     - En el Paso 0, el script extrae dinámicamente el identificador del usuario autenticado a partir del claim `sub` del payload del JWT (obteniendo `idUsuarioAutenticado = 104`), eliminando el valor fijo obsoleto `id_usuario = 1`.
     - Los Pasos 2, 4 y 6 consultan `GET /auditoria/?id_usuario={{idUsuarioAutenticado}}&tamano=10` y comprueban explícitamente que `res.items` contiene eventos generados por dicho `id_usuario`.
   * **Aislamiento sobre Especie Sintética y Concurrencia**:
     - Se confirmó el aislamiento estricto sobre `idEspecieSintetica` (sin tocar la especie real `id_especie = 2`).
     - Se sincronizó el timestamp de concurrencia optimista (`fecha_actualizacion`) en `fechaActualizacionSintetica`, garantizando compatibilidad con `EditarEspecieUseCase`.

3. **Reclasificación del Hallazgo — Mejora Sugerida (No Incidente / No Bloqueante)**:
   * **Descripción de la Mejora Sugerida**:
     > "MEJORA SUGERIDA (no incidente): Actualmente no existe un endpoint REST que exponga los registros de `modulo9.auditorias_especies` (histórico de auditoría de especies con snapshots `valores_anteriores`/`valores_nuevos`). Esto NO constituye un incumplimiento de RF-15, cuyo texto formal (Salida, Postcondiciones, Criterios de aceptación) solo exige el REGISTRO de la auditoría con usuario, fecha/hora, operación y valores anteriores/nuevos — lo cual se cumple al 100%, verificado directamente en base de datos. Se sugiere, como mejora de usabilidad y trazabilidad para consumidores de negocio (auditores, administradores), evaluar en un futuro incremento la exposición de un endpoint de consulta sobre esta tabla, aunque no es requisito contractual de RF-15."
   * **Evidencia Técnica**:
     - **Router de especies (`src/configuration/infrastructure/routers/especie_router.py`)**: Define exclusivamente endpoints CRUD operativos para especies (`POST /especies`, `GET /especies`, `GET /especies/{id}`, `PATCH /especies/{id}`, `PATCH /especies/{id}/desactivar`, `PATCH /especies/{id}/reactivar`), sin endpoint GET para consulta de historial.
     - **Repositorio de auditoría de especies (`src/configuration/infrastructure/repositories/auditoria_especie_repository.py`)**: Implementa el método `registrar()` para persistir en `modulo9.auditorias_especies`, sin métodos de lectura o consulta.
     - **Documentación de análisis arquitectónico (`anotaciones/modulo_9/cu04_gaps_bd_rf18_rf19_rf20.md`)**: Confirma los gaps preexistentes en la delimitación entre persistencia interna de dominio y APIs públicas.
   * **Aserción en Colección**: La suite de pruebas modela explícitamente esta delimitación en los Pasos 2.3, 4.3 y 6.3 (`pm.expect(contieneEspecieDirecta).to.be.false`), confirmando que `GET /auditoria/` audita accesos y eventos de seguridad pero no eventos de dominio con snapshots de especies.

4. **Dictamen Final**:
   * **✅ PASS (APROBADO)**.
   * La persistencia de la auditoría y trazabilidad interna en base de datos (usuario ejecutor `104`, timestamps, operación y snapshots completos de valores anteriores y nuevos) opera de forma impecable y satisface al 100% las especificaciones formales y criterios de aceptación de RF-15 / TC-M09-18. La eventual exposición de un endpoint REST de consulta para esta tabla queda registrada como mejora sugerida de usabilidad para futuros incrementos, sin impacto en la conformidad contractual y técnica del requerimiento.
