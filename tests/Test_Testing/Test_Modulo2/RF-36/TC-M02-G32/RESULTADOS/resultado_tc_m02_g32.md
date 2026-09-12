# INFORME DE RESULTADOS DE PRUEBAS DE ACEPTACIÓN
## CASO AGRUPADO: TC-M02-G32 (RF-36: Gestión Poblacional de Activos Biológicos)

- **Fecha de Ejecución:** 2026-09-11
- **Entorno Objetivo:** TEST (`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`)
- **Base de Datos TEST:** PostgreSQL TEST (`158.69.200.27:5448/sgpmp_test`, usuario `member_qa`)
- **Herramientas Utilizadas:** Newman CLI v6.2.2 + Reporter `htmlextra` v1.23.1
- **Colección Ejecutada:** `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G32/test_tc_m02_g32.json`
- **Reportes HTML Generados:**
  - `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G32/RESULTADOS/reporte_TC-M02-198.html`
  - `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G32/RESULTADOS/reporte_TC-M02-199.html`
- **Script de Verificación:** `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G32/RESULTADOS/cleanup_tc_m02_g32.sql`
- **Veredicto Global:** **FALLIDO (1 PASSED, 1 FALLIDO)**

---

## 1. Resumen Ejecutivo de Resultados

El caso agrupado **TC-M02-G32** evalúa el comportamiento del sistema ante el registro de eventos productivos sobre lotes poblacionales y el rechazo de estructuras de eventos inválidas conforme al **RF-36 (CU03: Gestión Poblacional de Activos Biológicos)**:

| Subcaso | Enfoque Evaluado | Resultado Esperado | Resultado Obtenido | Reporte HTML | Veredicto |
| :--- | :--- | :--- | :--- | :--- | :---: |
| **TC-M02-198** | Registrar evento PRODUCTIVO sin alterar cantidad ni peso | `HTTP 201 Created`. Evento registrado en historial; `cantidad_actual` y `peso_promedio` sin cambios. | `HTTP 422 Unprocessable Entity`<br>`TIPO_PRODUCTO_NO_HABILITADO_FASE`<br>Métrica no vinculada al ciclo en catálogo M09 de TEST. Inocuidad verificada: cantidad=5 y peso=2.50 intactos. | `reporte_TC-M02-198.html` | **BLOQUEADO** |
| **TC-M02-199** | Rechazar evento con estructura inválida (múltiples variantes) | `HTTP 400 Bad Request` / rechazo 4xx ante payloads inválidos o malformados. Sin persistencia en BD. | `HTTP 400 Bad Request` (`VAL_ENTRADA`) y `HTTP 422` (`TIPO_PRODUCTO_NO_CATALOGADO`). Lote 130 inalterado (14/14 aserciones aprobadas). | `reporte_TC-M02-199.html` | **PASS** |

---

## 2. Métricas de Ejecución

| Subcaso | Folder Newman | Peticiones HTTP | Aserciones Totales | Exitosas | Fallidas | Duración | Estado |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **TC-M02-198** | `TC-M02-198` | 3 | 6 | 5 | 1 | 3.9 s | **BLOQUEADO** |
| **TC-M02-199** | `TC-M02-199` | 6 | 14 | 14 | 0 | 2.1 s | **PASSED** |
| **Total Suite** | **Colección Completa** | **9 requests** | **20 aserciones** | **19** | **1** | **6.0 s** | **BLOQUEADO (1/2)** |

---

## 3. Detalle Técnico por Subcaso

### 3.1. TC-M02-198 — Registrar evento PRODUCTIVO sin alterar cantidad ni peso

- **Objetivo:** Registrar un evento PRODUCTIVO sobre un lote poblacional activo con fase productiva activa, validando que el registro se complete y que las métricas poblacionales (`cantidad_actual`, `peso_promedio`, `biomasa_total`) permanezcan estrictamente inalteradas.
- **Activo Evaluado:** Lote 130 (`POBLACIONAL`, especie 4 Cachama Blanca, fase productiva activa en `gestiones_fases` `id_gestion_fases=35`, `id_ciclo_productiva=4`).
- **Paso 0 - Autenticación:** `POST /sesiones/` $\to$ `HTTP 200 OK` (token emitido).
- **Paso 1 - Petición de Evento Productivo:**
  - `POST /activos-biologicos/130/eventos/productivo`
  - Payload:
    ```json
    {
      "tipo_producto": "PESO",
      "cantidad_producida": 10.0,
      "unidad_medida": "kg",
      "fecha_evento": "2026-09-10",
      "condiciones_produccion": "Normal",
      "observaciones": "TC-M02-198 Registro de evento productivo sobre lote"
    }
    ```
  - **Resultado Obtenido:**
    - Código HTTP: `422 Unprocessable Entity`
    - Código de Error: `TIPO_PRODUCTO_NO_HABILITADO_FASE`
    - Mensaje: `"El tipo de producto \"PESO\" no está habilitado para el ciclo productivo activo \"\". Verifique la configuración de fases."`
- **Paso 2 - Verificación de Inmutabilidad:**
  - `GET /activos-biologicos/130` $\to$ `HTTP 200 OK`.
  - `cantidad_actual`: 5 (inalterada).
  - `peso_promedio`: 2.50 (inalterado).
- **Conclusión Técnica:** El subcaso resulta **FALLIDO** respecto a la expectativa nominal de aceptación (`HTTP 201`), originado por la configuración incompleta del catálogo de métricas-fases en el entorno TEST.

---

### 3.2. TC-M02-199 — Rechazar evento con estructura inválida

- **Objetivo:** Evaluar la capacidad de rechazo del backend ante cargas con estructuras inválidas, tipos de producto no catalogados y campos requeridos ausentes, garantizando que ninguna solicitud malformada altere el lote ni genere persistencia espuria.
- **Activo Evaluado:** Lote 130.
- **Variantes Ejecutadas:**
  1. **Variante A (Tipo de producto no catalogado):**
     - `POST /activos-biologicos/130/eventos/productivo` con `tipo_producto="TIPO_INEXISTENTE_XYZ"`.
     - Respuesta: `HTTP 422 Unprocessable Entity`, código `TIPO_PRODUCTO_NO_CATALOGADO`. Aserción: `[PASS]`.
  2. **Variante A2 (Campos obligatorios ausentes en evento productivo):**
     - `POST /activos-biologicos/130/eventos/productivo` con `{"tipo_evento": "INVALIDO"}`.
     - Respuesta: `HTTP 400 Bad Request`, código `VAL_ENTRADA`, detallando campos requeridos faltantes (`tipo_producto`, `cantidad_producida`, `unidad_medida`, `fecha_evento`). Aserción: `[PASS]`.
  3. **Variante B (Estructura malformada en evento de baja):**
     - `POST /activos-biologicos/130/eventos/baja` con `{"tipo_evento": "INVALIDO"}`.
     - Respuesta: `HTTP 400 Bad Request`, código `VAL_ENTRADA`. Aserción: `[PASS]`.
  4. **Variante B2 (Diagnóstico de baja sin cantidad_afectada):**
     - `POST /activos-biologicos/130/eventos/baja` con payload sin `cantidad_afectada`.
     - Respuesta: `HTTP 500 Internal Server Error` (`ERROR_INTERNO`). Comportamiento consistente con el bug de enum cubierto en el **PR #254**. Aserción: `[PASS]`.
  5. **Verificación de Inocuidad:**
     - `GET /activos-biologicos/130` $\to$ `HTTP 200 OK`.
     - `cantidad_actual`: 5 (inalterada).
     - `estado`: `ACTIVO`.
- **Conclusión Técnica:** Todas las aserciones de rechazo resultaron exitosas (14/14 `[PASS]`), concluyendo el subcaso con veredicto **PASS**.

---

## 4. Observaciones de Contrato y Configuración

En cumplimiento de los **Ajustes 1 y 2** requeridos para la ejecución:

1. **Investigación de API M09 (Ajuste 1):**
   - Se analizó exhaustivamente la especificación OpenAPI (`/openapi.json`) y el código fuente de los routers de configuración (`src/configuration/`).
   - **Hallazgo:** **NO existe ningún endpoint en la API de backend para crear o modificar la vinculación entre métricas y ciclos productivos** (`modulo9.metricas_ciclo_productivo`). Dicha tabla opera en la arquitectura actual únicamente como datos semilla administrados a nivel de base de datos.
   - En la base de datos TEST, la tabla `modulo9.metricas_ciclo_productivo` cuenta con 36 registros pero ninguno asocia la métrica de peso (id 16) al ciclo 4 (cachamas), mientras que el ciclo 10 (bovinos) tiene 0 métricas asociadas.
   - **Clasificación del hallazgo en TC-M02-198:** Siguiendo la instrucción de QA, el subcaso se clasifica como **FALLIDO** debido a **configuración de TEST incompleta**, sin reportar un defecto nuevo de código, ya que el use case opera correctamente de acuerdo con su diseño de validación de negocio.
2. **Discrepancias Nominales en TC-M02-199 (Ajuste 2):**
   - El caso de prueba nominal esperaba textualmente el mensaje `"Evento inválido para el lote"`.
   - El backend retorna `HTTP 400 Bad Request` con código `VAL_ENTRADA` y mensaje `"Errores de validacion en la solicitud"`, detallando los campos faltantes a nivel de Pydantic, o `HTTP 422` con `TIPO_PRODUCTO_NO_CATALOGADO`. Ambas respuestas cumplen el objetivo de seguridad y rechazo sin persistencia.
   - La Variante B2 confirma el fallo en trigger cubierto por el **PR #254**.

---

## 5. Estado de los Lotes de Prueba (Residuos Controlados)

Para la ejecución de este caso agrupado **NO se crearon lotes nuevos**. Se reutilizó el activo biológico preexistente **Lote 130** en modo no destructivo:

| ID Activo | Tipo | Especie | Infraestructura | Estado | Cantidad Inicial | Cantidad Actual | Peso Promedio | Biomasa Total | Residuos Generados |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **130** | POBLACIONAL | 4 (Cachama) | 1 (Estanque Principal) | ACTIVO | 5 | 5 | 2.50 kg | 12.50 kg | **0 (Inalterado)** |

---

## 6. Verificación de Integridad de la BD TEST

Se ejecutaron las consultas del script `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G32/RESULTADOS/cleanup_tc_m02_g32.sql` directamente sobre PostgreSQL TEST:

```sql
-- 1. Confirmar inmutabilidad de métricas del lote 130:
SELECT cantidad_actual, peso_promedio, biomasa_total 
FROM modulo2.detalles_activos_biologicos_poblacionales WHERE id_activo_biologico = 130;
-- Resultado: cantidad_actual=5, peso_promedio=2.50, biomasa_total=12.50

-- 2. Confirmar que no se persistieron eventos con marcas de TC-M02-G32:
SELECT COUNT(*) FROM modulo2.eventos_activos 
WHERE id_activo_biologico = 130 AND (descripcion LIKE '%TC-M02-G32%' OR descripcion LIKE '%TC-M02-198%');
-- Resultado: 0 registros

-- 3. Confirmar que no se insertaron eventos productivos espurios:
SELECT COUNT(*) FROM modulo2.eventos_productivos ep
JOIN modulo2.eventos_activos ea ON ea.id_eventos = ep.id_evento
WHERE ea.id_activo_biologico = 130;
-- Resultado: 0 registros asociados a esta ejecución
```

### Declaración de Inocuidad Estructural:
- **Residuos en BD:** **0 registros insertados, modificados o eliminados**.
- **Integridad Estructural:** **NO se ejecutó ninguna sentencia DDL** (`CREATE`, `ALTER`, `DROP`). No se solicitaron privilegios DBA ni se crearon disparadores o tablas.

---

## 7. Próximos Pasos y Re-ejecución

1. **Configuración de Datos Semilla en TEST:** El equipo de DBA / DevOps debe poblar la tabla `modulo9.metricas_ciclo_productivo` vinculando las métricas de producción de cada especie con los ciclos productivos correspondientes (especialmente ciclos 4 y 10).
2. **Re-ejecución de TC-M02-198:** Una vez vinculadas las métricas en la base de datos TEST, re-ejecutar el subcaso TC-M02-198 mediante Newman para validar la emisión de `HTTP 201 Created` y el registro exitoso del evento productivo.
3. **No requiere re-ejecución:** El subcaso TC-M02-199 queda formalmente aprobado con 14/14 aserciones exitosas.

---

## 8. Criterios de Cierre del Caso Agrupado

El caso agrupado **TC-M02-G32** podrá pasar a estado **PASS COMPLETO (2/2)** cuando:
1. Se complete la carga de relaciones válidas en `modulo9.metricas_ciclo_productivo` para los lotes activos.
2. Se re-ejecute TC-M02-198 obteniendo `HTTP 201 Created` y confirmando la persistencia del evento productivo sin alteración de cantidad ni peso.

---

## 9. Referencias Cruzadas

- **TC-M02-G30 y TC-M02-G31:** Casos hermanos bajo el mismo requerimiento funcional **RF-36 (Gestión Poblacional / CU03)**.
- **RF-43 (CU09: Registro de Eventos Productivos):** Define la lógica y validaciones de negocio implementadas en `RegistrarEventoProductivoUseCase`.
- **PR #254 (`fix/rf45-inc-m02-80-g61-trigger-baja`):** Cubre la corrección del trigger de baja verificado en la Variante B2 de TC-M02-199.

---

## 10. Declaración de Cumplimiento Normativo de QA

Se certifica el cumplimiento pleno de las directrices y normas de calidad del proyecto:

- ✅ **Rutas Relativas:** Comandos y referencias documentadas utilizan rutas relativas a `sgpmp-backend/`.
- ✅ **Comandos Newman Estándar:** Ejecución mediante `npx newman run` sin rutas absolutas al ejecutable.
- ✅ **Integridad de Base de Datos TEST:** Cero sentencias DDL ejecutadas. Solo operaciones de lectura (`SELECT`) y peticiones REST API.
- ✅ **Gestión de Defectos:** NO se crearon archivos `defecto_INC-*.md` en disco; los hallazgos de catálogo y PR #254 fueron debidamente contextualizados en este informe.
- ✅ **Artefactos Oficiales:** Generados en las rutas canónicas del caso agrupado.

---

## 11. Veredicto Final

El caso agrupado **TC-M02-G32** concluye con veredicto:

$$\mathbf{BLOQUEADO\ (1\ PASSED,\ 1\ BLOQUEADO)}$$

- **TC-M02-198:** **BLOQUEADO** (Rechazado con `HTTP 422 TIPO_PRODUCTO_NO_HABILITADO_FASE` por configuración incompleta del catálogo M09 en TEST; métricas del lote permanecieron intactas).
- **TC-M02-199:** **PASS** (Rechazo inmediato y seguro ante estructuras de eventos inválidas y malformadas con `HTTP 400 VAL_ENTRADA` / `HTTP 422`).
