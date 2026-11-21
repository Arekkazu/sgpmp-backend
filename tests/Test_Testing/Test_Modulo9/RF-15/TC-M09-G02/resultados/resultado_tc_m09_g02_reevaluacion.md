# INFORME DE RESULTADOS DE PRUEBAS DE ACEPTACIÓN — REEVALUACIÓN
## CASO AGRUPADO: TC-M09-G02 (RF-15: Catálogo de Especies Productivas — Validación de Campo "Nombre")

---

### 1. Encabezado y Metadatos de Ejecución

- **Fecha de Reevaluación**: 2026-09-13 (09:18 COT / 14:18 UTC)
- **Fecha de Corrida Previa**: 2026-09-05 (Aprox. - Ejecución inicial registrada en `reporte_tc_m09_g02.html`)
- **Entorno**: TEST (`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`)
- **Base de Datos**: PostgreSQL TEST (`158.69.200.27:5448/sgpmp_test`, usuario `member_qa` — **SOLO LECTURA**)
- **Herramienta**: Newman CLI v6.2.2 + Reporter `htmlextra`
- **Script Ejecutado**: `tests/Test_Testing/Test_Modulo9/RF-15/TC-M09-G02/test_tc_m09_g02.json`
- **Reporte HTML Generado**: `tests/Test_Testing/Test_Modulo9/RF-15/TC-M09-G02/Resultados/reporte_tc_m09_g02_reevaluacion.html`
- **Nota de Cambio de Credencial**: Se actualizó la credencial de autenticación del ítem `0. Auth` de `admin@pecuaria.co` (cuenta con `id_usuario = 1` en estado `Bloqueado` por exceso de intentos fallidos) a `administador.dev@gmail.com` (`id_usuario = 104`, `id_rol = 1`, estado `Activo`), validada con `HTTP 200 OK`.
- **Veredicto Global**: **✅ DEFECTO CORREGIDO — PASS COMPLETO (12/12 PETICIONES, 100% ASERCIONES APROBADAS)**

---

### 2. Objetivo de la Reevaluación y Resumen Ejecutivo

#### Contexto del Fallo Original:
En la corrida inicial de `TC-M09-G02`, los sub-casos de creación legítima (TC-M09-02 y TC-M09-03) y el sub-caso de duplicados (TC-M09-07) fallaban con `HTTP 500 Internal Server Error`. La causa raíz correspondió al defecto **`INC-M09-02-G02`**: la presencia de un trigger huérfano en base de datos (`modulo9.trg_especies_audit`, función `trg_fn_especies_audit()`) que exigía obligatoriamente la variable de sesión `app.usuario_id`. Dicho trigger fue formalmente eliminado del esquema TEST mediante la migración Alembic `alembic/versions/a1c3f6e0b2d4_rf15_eliminar_trigger_auditoria_especies_huerfano.py`.

#### Tabla Comparativa por Sub-caso:

| Sub-caso | Enfoque de Prueba | Código Esperado | Código Anterior | Código Reevaluación | Aserciones | Veredicto |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **0. Auth** | Autenticación administrador | 200 OK | 200 OK | **200 OK** | 1 / 1 | **PASS** |
| **1. TC-M09-02** | Límite inferior exacto (3 chars) | 201 Created | 500 Error | **201 Created** | 1 / 1 | **PASS** |
| **2. TC-M09-03** | Límite superior exacto (50 chars) | 201 Created | 500 Error | **201 Created** | 1 / 1 | **PASS** |
| **3. TC-M09-04** | Longitud menor a 3 caracteres | 400 Bad Request | 400 Bad Request | **400 Bad Request** | 1 / 1 | **PASS** |
| **4. TC-M09-05** | Longitud mayor a 50 caracteres | 400 Bad Request | 400 Bad Request | **400 Bad Request** | 1 / 1 | **PASS** |
| **5a. TC-M09-06** | Nombre omitido en payload | 400 Bad Request | 400 Bad Request | **400 Bad Request** | 1 / 1 | **PASS** |
| **5b. TC-M09-06** | Nombre con valor nulo (`null`) | 400 Bad Request | 400 Bad Request | **400 Bad Request** | 1 / 1 | **PASS** |
| **5c. TC-M09-06** | Nombre con espacios en blanco | 400 Bad Request | 400 Bad Request | **400 Bad Request** | 1 / 1 | **PASS** |
| **6. TC-M09-08** | Caracteres especiales o números | 400 Bad Request | 400 Bad Request | **400 Bad Request** | 1 / 1 | **PASS** |
| **7. TC-M09-07** | Nombre duplicado case-insensitive | 409 Conflict | 500 Error | **409 Conflict** | 1 / 1 | **PASS** |
| **8. Teardown 1** | Desactivar especie límite inferior | 200 OK | 400 Error | **200 OK** | 1 / 1 | **PASS** |
| **9. Teardown 2** | Desactivar especie límite superior | 200 OK | 400 Error | **200 OK** | 1 / 1 | **PASS** |

---

### 3. Estado Previo de la Base de Datos

Antes de ejecutar la colección Newman, se ejecutó una consulta de solo lectura contra `modulo9.especies`:

```sql
SELECT 
    COUNT(*) as total_especies,
    COUNT(*) FILTER (WHERE es_activo = true) as activas,
    COUNT(*) FILTER (WHERE es_activo = false) as inactivas,
    MAX(id_especie) as max_id
FROM modulo9.especies;
```

**Resultado obtenido antes de la corrida (2026-09-13 14:17 UTC)**:
```text
- Total especies registradas: 15
- Especies activas:           11
- Especies inactivas:          4
- ID máximo existente:        46
```

Se confirmó además que el trigger defectuoso `trg_especies_audit` no existía en `modulo9.especies` y que los triggers legítimos de formato (`trg_especies_nombre_formato`) y unicidad (`trg_especies_nombre_unique_ci`) estaban plenamente operativos.

---

### 4. Resultados Detallados de la Ejecución (Newman)

Se ejecutó la suite mediante el comando oficial:
```powershell
npx newman run tests/Test_Testing/Test_Modulo9/RF-15/TC-M09-G02/test_tc_m09_g02.json -r cli,htmlextra --reporter-htmlextra-export tests/Test_Testing/Test_Modulo9/RF-15/TC-M09-G02/Resultados/reporte_tc_m09_g02_reevaluacion.html
```

#### Paso a Paso de las 12 Peticiones:

| Paso | Método | Endpoint | Status Obtenido | Tiempo | Aserciones | Veredicto |
| :---: | :---: | :--- | :---: | :---: | :---: | :---: |
| **0** | `POST` | `/sesiones/` | 200 OK | 1985 ms | 1 / 1 | **PASS** |
| **1** | `POST` | `/configuracion/especies` (TC-M09-02: 3 chars `Mwi`) | 201 Created | 202 ms | 1 / 1 | **PASS** |
| **2** | `POST` | `/configuracion/especies` (TC-M09-03: 50 chars) | 201 Created | 133 ms | 1 / 1 | **PASS** |
| **3** | `POST` | `/configuracion/especies` (TC-M09-04: `<3` chars `Ab`) | 400 Bad Request | 203 ms | 1 / 1 | **PASS** |
| **4** | `POST` | `/configuracion/especies` (TC-M09-05: `>50` chars) | 400 Bad Request | 159 ms | 1 / 1 | **PASS** |
| **5a** | `POST` | `/configuracion/especies` (TC-M09-06: Omitido) | 400 Bad Request | 409 ms | 1 / 1 | **PASS** |
| **5b** | `POST` | `/configuracion/especies` (TC-M09-06: `null`) | 400 Bad Request | 128 ms | 1 / 1 | **PASS** |
| **5c** | `POST` | `/configuracion/especies` (TC-M09-06: `"   "`) | 400 Bad Request | 391 ms | 1 / 1 | **PASS** |
| **6** | `POST` | `/configuracion/especies` (TC-M09-08: `Bovino-123!`) | 400 Bad Request | 124 ms | 1 / 1 | **PASS** |
| **7** | `POST` | `/configuracion/especies` (TC-M09-07: Duplicado `MWI`) | 409 Conflict | 204 ms | 1 / 1 | **PASS** |
| **8** | `PATCH` | `/configuracion/especies/47/desactivar` (Teardown 1) | 200 OK | 124 ms | 1 / 1 | **PASS** |
| **9** | `PATCH` | `/configuracion/especies/48/desactivar` (Teardown 2) | 200 OK | 391 ms | 1 / 1 | **PASS** |

#### Métricas Consolidadas:
- **Peticiones Ejecutadas**: 12 / 12 (100%)
- **Aserciones Evaluadas**: 12 / 12 (100% exitosas, 0 fallidas)
- **Duración Total de Corrida**: 5.4 segundos
- **Tiempo de Respuesta Promedio**: 371 ms (mín: 124 ms, máx: 1985 ms)
- **Exit Code Newman**: `0` (Ejecución limpia sin errores)

#### Detalle de Sub-casos Previamente Fallidos:
- **Sub-caso 1 (TC-M09-02)**: Generó dinámicamente el nombre `'Mwi'`. Respondió `HTTP 201 Created` asignando `id_especie = 47`.
- **Sub-caso 2 (TC-M09-03)**: Generó dinámicamente un nombre de exactamente 50 caracteres (`'Especieproductivaparapruebasdecontrolquigxsaegptvv'`). Respondió `HTTP 201 Created` asignando `id_especie = 48`.
- **Sub-caso 7 (TC-M09-07)**: Envió el nombre `'MWI'` (mayúsculas de `'Mwi'`). Fue interceptado por el caso de uso y trigger con `HTTP 409 Conflict`, código de error `'ESPECIE_DUPLICADA'` y mensaje `"La especie 'MWI' ya se encuentra registrada en el catálogo."`.
- **Teardowns 1 y 2**: Al crearse exitosamente las especies 47 y 48, las variables `idEspecieMinima` e `idEspecieMaxima` fueron pobladas y los endpoints de desactivación respondieron `HTTP 200 OK` con `es_activo = false`.

---

### 5. Evidencia de Estado en BD PostgreSQL TEST

Consultas `SELECT` ejecutadas inmediatamente después de la corrida:

#### 1. Estado de Especies Creadas (IDs 47 y 48):
```sql
SELECT id_especie, nombre, descripcion, es_activo, fecha_creacion, fecha_actualizacion
FROM modulo9.especies
WHERE id_especie IN (47, 48)
ORDER BY id_especie ASC;
```
```text
- ID 47: 'Mwi' | es_activo = False | Creado: 2026-09-13 14:18:25 UTC | Actualizado: 2026-09-13 14:18:27 UTC
- ID 48: 'Especieproductivaparapruebasdecontrolquigxsaegptvv' | es_activo = False | Creado: 2026-09-13 14:18:25 UTC | Actualizado: 2026-09-13 14:18:28 UTC
```

#### 2. Comprobación de No Duplicidad (Sub-caso 7):
```sql
SELECT id_especie, nombre, es_activo 
FROM modulo9.especies 
WHERE LOWER(nombre) = 'mwi';
```
```text
Total filas encontradas: 1
- ID 47 | Nombre: 'Mwi' | es_activo = False
```
*(Confirmado: el intento de inserción de 'MWI' no persistió ninguna fila duplicada).*

#### 3. Auditoría en `modulo9.auditorias_especies`:
```sql
SELECT id_auditoria_especie, id_especie, id_usuario, tipo_operacion, fecha_gestion, valores_nuevos->>'es_activo' as estado
FROM modulo9.auditorias_especies
WHERE id_especie IN (47, 48)
ORDER BY id_auditoria_especie ASC;
```
```text
- ID 28 | Especie 47 | Usuario 104 | Operación: CREATE     | Fecha: 2026-09-13 14:18:25 UTC | Estado: True
- ID 29 | Especie 48 | Usuario 104 | Operación: CREATE     | Fecha: 2026-09-13 14:18:25 UTC | Estado: True
- ID 30 | Especie 47 | Usuario 104 | Operación: DEACTIVATE | Fecha: 2026-09-13 14:18:27 UTC | Estado: False
- ID 31 | Especie 48 | Usuario 104 | Operación: DEACTIVATE | Fecha: 2026-09-13 14:18:28 UTC | Estado: False
```

---

### 6. Verificación de Limpieza (Inocuidad Post-Prueba)

1. **Estado de Especies Temporales**: Ambas especies de prueba (IDs 47 y 48) quedaron formalmente en `es_activo = false` mediante los teardowns de la propia colección ejecutados a través de la API REST (`PATCH /configuracion/especies/{id}/desactivar`).
2. **Cero Mutaciones Destructivas Manuales**: No se requirió ni ejecutó ningún script SQL externo ni sentencias `DELETE`. Se mantuvo intacto el principio de base de datos *append-only* y la integridad referencial.
3. **Especies Activas Remanentes**: El número de especies activas en el catálogo se mantuvo exactamente en **11**, idéntico al estado previo a la ejecución.
4. **Detección de Huérfanos Anteriores**: Se identificó que de corridas previas de desarrollo/QA existen 3 especies de prueba activas (`ID 40: 'Bovino Qa Je'`, `ID 41: 'Ave Qa Je'`, `ID 44: 'Equino Test Qa'`). No fueron alteradas en esta reevaluación.

---

### 7. Conclusión y Dictamen Final

1. **Defecto INC-M09-02-G02**: **SUBSANADO Y TOTALMENTE CORREGIDO**. La eliminación del trigger huérfano permitió que los flujos de creación legítima (`HTTP 201`) y rechazo de duplicados (`HTTP 409`) operen conforme a la especificación de RF-15.
2. **Conformidad Contractual**: El endpoint `POST /configuracion/especies` cumple rigurosamente con todos los criterios de aceptación:
   - Admite nombres de 3 a 50 caracteres alfabéticos.
   - Rechaza nombres con longitud menor a 3 o mayor a 50 con `HTTP 400 VAL_ENTRADA`.
   - Rechaza nombres vacíos, nulos o con espacios en blanco con `HTTP 400 VAL_ENTRADA`.
   - Rechaza caracteres especiales y números con `HTTP 400 VAL_ENTRADA`.
   - Impide duplicidad insensible a mayúsculas/minúsculas con `HTTP 409 ESPECIE_DUPLICADA`.
3. **Persistencia de Casos Previos**: Los sub-casos 3, 4, 5a, 5b, 5c y 6 ratificaron su resultado **PASS**.
4. **Dictamen del Caso TC-M09-G02**: **APROBADO / CERRADO (CONFORME 100%)**.
5. **Observación para Siguientes Casos**: Se recuerda que se detectaron **85 archivos adicionales en `tests/Test_Testing/`** que aún referencian la credencial inactiva `admin@pecuaria.co`. Se recomienda actualizar masivamente dicha variable a `administador.dev@gmail.com` antes de ejecutar las reevaluaciones de los casos restantes.
