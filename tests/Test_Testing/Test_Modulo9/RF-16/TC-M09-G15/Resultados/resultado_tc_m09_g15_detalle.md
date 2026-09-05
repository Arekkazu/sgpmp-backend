# Informe Técnico Detallado: TC-M09-G15 & Defecto de Integridad INC-M09-03

## 1. Introducción y Alcance de las Pruebas

Este documento constituye la evaluación técnica exhaustiva del grupo de pruebas **TC-M09-G15** (sub-casos **TC-M09-36**, **TC-M09-37** y **TC-M09-38**), cuyo propósito según el requisito **RF-16 (CU-02 — Configurar Parámetros Productivos y Sanitarios por Especie)** es verificar que el sistema impida la desactivación lógica de etapas productivas, patologías y métricas que se encuentren en uso o asociadas a activos biológicos, eventos sanitarios o eventos productivos.

---

## 2. Descripción de Sub-casos y Métodos de Verificación

### Sub-caso TC-M09-36: Desactivación de Etapa Productiva con Activos Asociados
* **Objetivo:** Garantizar que el sistema bloquee con `HTTP 422` la desactivación de una etapa productiva si existen activos biológicos o ciclos asociados a la misma (regla FA-03).
* **Método de Verificación:** Pruebas E2E en vivo mediante colección Newman contra la API de TEST (`PATCH /configuracion/ciclos/10/desactivar`) y verificación posterior de estado en base de datos PostgreSQL TEST vía conexión de solo lectura (`member_qa`).
* **Etapa Objetivo:** *Fase juvenil cachama* (`id_ciclo_biologico = 10`, `id_especie = 4`), la cual registra **1 referencia activa** en la vista `modulo9.vw_rf16_dependencias_ciclos` derivada de `modulo9.ciclos_productivos_biologicos`.
* **Resultado de Ejecución:**
  * Status Code HTTP: **`422 Unprocessable Entity`**
  * Body de Error: `{"error_code": "ETAPA_CON_ACTIVOS", "message": "No es posible desactivar la etapa 'Fase juvenil cachama'. Existen activos biológicos actualmente en esta fase del ciclo. Debe trasladarlos de etapa antes de proceder."}`
  * Verificación en BD (`verificar_bd_ciclo10.py`): Confirmado `es_activo = True` para la etapa 10. La etapa permaneció protegida e intacta.
  * **Veredicto:** 🟢 **PASSED (Comportamiento correcto)**.

---

### Sub-caso TC-M09-37: Desactivación de Patología por Especie con Eventos Sanitarios Asociados
* **Objetivo:** Verificar que el sistema bloquee con `HTTP 422` la desactivación de una patología referenciada en el historial clínico o eventos sanitarios de activos (regla FA-04).
* **Método de Verificación:** Auditoría estática de código fuente y arquitectura de componentes. **No se ejecutó la llamada HTTP real en el servidor de TEST** para evitar la desactivación irreversible de la única patología activa registrada.
* **Aclaración sobre Datos en BD:** La tabla `modulo2.eventos_sanitarios` en BD TEST registra actualmente **0 filas**. No obstante, el análisis de código demostró concluyentemente que, incluso si existiesen datos en `modulo2`, el endpoint respondería `HTTP 200 OK` desprotegiendo la entidad.
* **Resultado de Inspección de Código:**
  * Endpoint Router: [`src/configuration/infrastructure/routers/patologia_router.py`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/configuration/infrastructure/routers/patologia_router.py#L129)
  * Inyección de Dependencia: Instancia hardcodeada de `StubDependenciaPatologiaAdapter()`.
  * Código de la Clase: [`src/configuration/infrastructure/adapters/dependencia_patologia_stub.py`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/configuration/infrastructure/adapters/dependencia_patologia_stub.py#L14-L17)
    ```python
    class StubDependenciaPatologiaAdapter(DependenciaPatologiaPort):
        def tiene_dependencias_activas(self, id_patologia: int) -> bool:
            return False  # Retorna False incondicionalmente
    ```
* **Veredicto:** 🔴 **VULNERABLE (Defecto Activo INC-M09-03)**.

---

### Sub-caso TC-M09-38: Desactivación de Métrica Productiva con Eventos Productivos Asociados
* **Objetivo:** Verificar que el sistema bloquee con `HTTP 422` la desactivación de una métrica referenciada por registros de eventos productivos o mediciones (regla FA-09).
* **Método de Verificación:** Auditoría estática de código fuente y arquitectura de componentes. **No se ejecutó la llamada HTTP real en el servidor de TEST** para preservar la integridad del catálogo activo de métricas.
* **Aclaración sobre Datos en BD:** La tabla `modulo2.eventos_productivos` en BD TEST registra actualmente **0 filas**. La vulnerabilidad fue identificada mediante revisión de código sin requerir inyección de datos en Módulo 2.
* **Resultado de Inspección de Código:**
  * Endpoint Router: [`src/configuration/infrastructure/routers/metrica_router.py`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/configuration/infrastructure/routers/metrica_router.py#L140)
  * Inyección de Dependencia: Instancia hardcodeada de `StubDependenciaMetricaAdapter()`.
  * Código de la Clase: [`src/configuration/infrastructure/adapters/dependencia_metrica_stub.py`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/configuration/infrastructure/adapters/dependencia_metrica_stub.py#L13-L16)
    ```python
    class StubDependenciaMetricaAdapter(DependenciaMetricaPort):
        def tiene_dependencias_activas(self, id_metrica_produccion: int) -> bool:
            return False  # Retorna False incondicionalmente
    ```
* **Veredicto:** 🔴 **VULNERABLE (Defecto Activo INC-M09-03)**.

---

## 3. Matriz Comparativa de Defectos Identificados

A continuación se realiza el contraste formal entre los dos hallazgos críticos detectados durante la evaluación del Módulo 9:

| Atributo | Defecto INC-M09-02-G03 | Defecto INC-M09-03 (NUEVO) |
| :--- | :--- | :--- |
| **Nombre del Hallazgo** | Fallo del trigger de auditoría de BD por falta de `app.usuario_id` | Omisión de validación de integridad referencial por adaptadores Stub |
| **Capa Afectada** | Base de Datos (PL/pgSQL Trigger `modulo9.trg_especies_audit`) | Capa de Aplicación / Infraestructura FastAPI (`StubAdapters`) |
| **Severidad** | **Crítica (Bloqueo de Operaciones)** | **Alta / Crítica (Vulnerabilidad de Integridad)** |
| **Comportamiento ante Operación** | Arroja `HTTP 500 Internal Server Error` impidiendo la escritura (bloqueante). | Responde `HTTP 200 OK` permitiendo la operación ilegítima (destructivo silencioso). |
| **Componentes Concretos** | • `modulo9.trg_especies_audit`<br>• `modulo9.trg_fn_especies_audit()` | • [`StubDependenciaPatologiaAdapter`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/configuration/infrastructure/adapters/dependencia_patologia_stub.py#L14)<br>• [`StubDependenciaMetricaAdapter`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/configuration/infrastructure/adapters/dependencia_metrica_stub.py#L13) |
| **Impacto de Negocio** | Bloquea totalmente la creación, edición y desactivación de especies en el entorno TEST. | Permite que un usuario desactive patologías o métricas activamente utilizadas en historiales clínicos o registros productivos, corrompiendo la consistencia del dominio. |

---

## 4. Causa Raíz e Inconsistencia de Datos en BD TEST

1. **Causa Raíz de INC-M09-03:** En la fase de construcción de la arquitectura hexagonal para el Módulo 09, se definieron los puertos de dominio `DependenciaPatologiaPort` y `DependenciaMetricaPort`. Ante la falta de integración con los servicios de Módulo 04 (Predicciones / Salud) y Módulo 02 (Gestión Productiva), se crearon adaptadores stub temporales que retornan `False` por defecto. Sin embargo, dichos stubs fueron inyectados directamente en los routers expuestos a producción/TEST sin mecanismos de salvaguarda o verificación de esquema.
2. **Razonamiento sobre Datos en BD TEST:** En la base de datos de TEST, las tablas `modulo2.eventos_sanitarios` y `modulo2.eventos_productivos` no poseen filas asociadas. Generar registros sintéticos en `modulo2` para intentar "forzar" la prueba en vivo habría introducido riesgos colaterales con el patrón de trigger roto `INC-M09-02` existente en las tablas de `modulo2`. Por ello, la identificación mediante auditoría de código representa la evidencia técnica más sólida, segura y definitiva.

---

## 5. Recomendaciones Técnicas de Corrección

1. **Para TC-M09-37 (Patologías):**
   * Crear la vista SQL `modulo9.vw_rf16_dependencias_patologias` que realice el conteo de referencias en `modulo2.eventos_sanitarios` y `modulo4.alertas_patologicas`.
   * Reemplazar `StubDependenciaPatologiaAdapter` en [`patologia_router.py`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/configuration/infrastructure/routers/patologia_router.py#L129) por `SqlAlchemyDependenciaPatologiaRepository(db)` que ejecute la consulta sobre dicha vista.
2. **Para TC-M09-38 (Métricas):**
   * Crear la vista SQL `modulo9.vw_rf16_dependencias_metricas` que realice el conteo de referencias en `modulo2.eventos_productivos` y `modulo5.mediciones_incrementales`.
   * Reemplazar `StubDependenciaMetricaAdapter` en [`metrica_router.py`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/configuration/infrastructure/routers/metrica_router.py#L140) por `SqlAlchemyDependenciaMetricaRepository(db)` que ejecute la consulta sobre dicha vista.
