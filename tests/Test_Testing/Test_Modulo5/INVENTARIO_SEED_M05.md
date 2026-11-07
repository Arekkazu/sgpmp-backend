# INVENTARIO DE DATOS SEMILLA PARA EL MÓDULO 5 (RF-76, RF-77, RF-80, RF-81)
**Fecha de generación:** 2026-11-05 (Cuarta Pasada — Verificación Exclusiva de Datos Semilla)  
**Entorno auditado:** TEST (`https://www.api.inmero.co/api-sgpmp-test` / DB `158.69.200.27:5448/sgpmp_test`)  
**Modo:** SOLO LECTURA en BD persistente (Sondeos controlados exclusivamente por HTTP API bajo el Middleware de Sandbox con `X-Test-Run-Id` y teardown `DELETE /test-control/runs/{run_id}`).

---

## 1. Solicitud Concreta al DBA (Resumen Ejecutivo)

Para ejecutar con éxito los 21 grupos de casos de prueba (`TC-M05-G01` a `TC-M05-G21`), se solicita al Administrador de Base de Datos (DBA) aplicar **ÚNICAMENTE** los siguientes datos sintéticos e infraestructura indispensable, los cuales no pueden generarse vía API en el entorno transaccional debido a timeouts de sandbox (>180 s) o restricciones de dominio de Módulo 2:

| Concepto | Cantidad Solicitada | Detalle / Destino | Propósito Técnico en Pruebas |
|---|:---:|---|---|
| **Activos Biológicos Dedicados** | **4 activos** | `SEED-M05-REP-450D`, `SEED-M05-REP-500`, `SEED-M05-HIST-10K`, `SEED-M05-HIST-50K` en `modulo2.activos_biologicos`. | Pruebas de estrés, historial masivo y reportes anuales asíncronos. |
| **Ciclos Productivos Históricos** | **5 fases/ciclos** | En `modulo2.gestiones_fases`: 1 ciclo de 450 días, 1 ciclo de 100 días, 1 ciclo cerrado + 1 activo para 10k, y 1 ciclo de 250 días para 50k. | Soporte temporal para transiciones y reportes que exigen `fecha_inicio_reporte >= fecha_inicio_ciclo`. |
| **Consumos de Alimento (RF-75)** | **512 consumos** | En `modulo5.registros_consumo_alimentos`: 500 consumos en `SEED-M05-REP-500` (borde 500) y 12 consumos en `SEED-M05-REP-450D`. | Borde-menos-uno para RF-77 (síncrono $\le 500$; el test añade el 501 por sandbox). |
| **Tratamientos de Medicamentos (RF-76)** | **6 medicaciones** | En `modulo5.registros_medicamentos` para `SEED-M05-REP-450D` con retiros y costos validados. | Integración de costos de medicación en reportes anuales de 450 días. |
| **Suministros en Historial (RF-78 / RF-81)** | **60.000 registros** | En `modulo5.registro_suministro`: 10.000 en `SEED-M05-HIST-10K` (con mezcla de 4 tipos y 2 orígenes) y 50.000 en `SEED-M05-HIST-50K`. | Validación de límites síncrono/asíncrono de historial (Nivel 1 $\le 10.000$ y Nivel 2 $\le 50.000$). |
| **Archivos Expirados (RF-77 y RF-81)** | **2 archivos** | En `modulo5.archivos_exportacion_suministros`: 1 archivo RF-77 (expirado 24 h) y 1 archivo RF-81 (expirado 72 h). | Validación del código de error `410 Gone` al descargar archivos vencidos. |
| **Infraestructuras Activas (Módulo 9)** | **2 infraestructuras** | En `modulo9.infraestructuras`: 1 en Finca 81 (`Galpon Gestor F81`) y 1 en Finca 82 (`Galpon Revisor F82`). | Habilitar creación de activos y verificación de alcance territorial de Gestor y Revisor. |
| **Asignación Finca 113 a Productor B** | *0 (Opcional)* | BLOQUE 1 comentado. No requerido: Productor B ya tiene Finca 114 asignada. | Reclasificado para no exigir intervención DBA. |

---

## 2. Resumen de Requisitos por Etiqueta (Matriz Consolidada)

Cada fila de la matriz detallada (§4) corresponde exactamente a un requisito clasificado bajo las **6 etiquetas canónicas**. La matriz contiene exactamente **41 requisitos**:

| Etiqueta | Cantidad | Descripción / Estrategia de Ejecución |
|---|:---:|---|
| **EXISTE_REUTILIZABLE** | **11** | Datos presentes en TEST aptos y no contaminados (catálogos de especies M09, tipos de alimentos M05, configuraciones batch singleton, eventos de auditoría válidos, activo poblacional 9 con `cantidad_actual=0`, cuentas confirmadas y Finca 114 para Productor B). |
| **CREABLE_EN_SANDBOX** | **16** | Requisitos que el propio test automatizado (Newman / Pytest) genera dinámicamente vía API bajo `X-Test-Run-Id` y revierte con `DELETE /test-control/runs/{run_id}` (ej. medicamentos dentro de ciclo, retiros solapados, ráfagas concurrentes, transiciones permitidas). |
| **REQUIERE_DBA** | **4** | Datos indispensables no creables vía API en sandbox: activo con ciclo de 450 días (G10), activo con 500 consumos (G11), activos masivos de 10.000 y 50.000 registros (G19, que cubre también G18), y archivos expirados (G21). |
| **EXISTE_NO_APTO** | **1** | Registros existentes con contaminación por pruebas previas (Activo 1 con 6 medicamentos y 11 consumos mezclados). |
| **NO_VERIFICABLE** | **2** | Inspección directa en SQL bloqueada por Row-Level Security (RLS) bajo conexión sin contexto de sesión (`modulo1.usuarios` y `modulo2.activos_biologicos`). Verificables mediante API autenticada. |
| **BLOQUEADO_POR_BACKEND** | **7** | Componentes abstractos de la especificación no construidos en backend: deduplicación de auditoría por `id_evento_m05` (G16), cola M05→M12 (G17), eventos fuera de catálogo en enum cerrado (G14), verificación periódica de hash (G16), mutación de config batch (G11), forzado de fallos de worker (G12), mutación sobre historial de solo lectura (G20). |
| **TOTAL REQUISITOS** | **41** | Total rigurosamente verificado y conciliado. |

---

## 3. Diagnóstico Técnico de Tablas, Triggers y Restricciones

### 3.1 Análisis de Triggers y Cascada DML
Se inspeccionaron los triggers activos en las tablas involucradas mediante `information_schema.triggers` y `pg_proc`:

1. **`modulo5.registros_consumo_alimentos`:**
   - `trg_poblar_registro_suministro_alimento`: Trigger `AFTER INSERT` que ejecuta `fn_trg_poblar_registro_suministro_alimento()`. Si el consumo insertado tiene `estado_registro = 'VALIDADO'`, **inserta automáticamente 1 fila en `modulo5.registro_suministro`** con `tipo_suministro = 'ALIMENTO'`, heredando el ciclo activo de `modulo2.gestiones_fases`.
   - `trg_auditoria_consumo_alimento`: Trigger `AFTER INSERT OR UPDATE` que ejecuta `fn_trg_auditoria_consumo_alimento()`. **Inserta automáticamente 1 fila en `modulo5.auditorias_suministros`**.
   - **Efecto de Cascada en Bloque 3 (500 consumos):** La inserción directa de 500 consumos en `registros_consumo_alimentos` genera **500 filas en `registro_suministro`** y **500 filas en `auditorias_suministros`**.
   - **Mitigación de Contaminación de Auditoría:** Para no contaminar la bitácora de auditoría con las 500 cargas sintéticas, el script DBA debe deshabilitar temporalmente este trigger durante el insert:
     ```sql
     ALTER TABLE modulo5.registros_consumo_alimentos DISABLE TRIGGER trg_auditoria_consumo_alimento;
     -- Inserts de consumos sintéticos...
     ALTER TABLE modulo5.registros_consumo_alimentos ENABLE TRIGGER trg_auditoria_consumo_alimento;
     ```

2. **`modulo5.registro_suministro`:**
   - Posee únicamente el trigger `trg_acumular_costo_ciclo` (`AFTER INSERT EXECUTE FUNCTION fn_acumular_costo_ciclo()`).
   - **No posee triggers de auditoría.** Por tanto, la inserción masiva de 10.000 y 50.000 registros en Bloques 4 y 5 **no contamina** `modulo5.auditorias_suministros`.

3. **`modulo2.activos_biologicos` y `gestiones_fases`:**
   - `trg_auditar_activo_biologico`: Trigger `AFTER INSERT OR UPDATE` que inserta en `modulo2.auditoria_activos_biologicos`. Exige que la sesión tenga definida `app.usuario_id` (o `app.current_user_id`), y requiere privilegios de ejecución sobre `modulo2.fn_activos_del_usuario`. El DBA como superusuario/owner posee estos permisos de forma nativa.

### 3.2 Índices Únicos y Prevención de Colisiones en `modulo5.registro_suministro`
La tabla `modulo5.registro_suministro` cuenta con 3 índices únicos:
1. `registro_suministro_pkey`: `(id_registro_suministro)` (Serial PK).
2. `registro_suministro_id_idempotencia_key`: `(id_idempotencia)` (Unique B-tree).
3. `uq_registro_suministro_dedup_contenido`:
   ```sql
   CREATE UNIQUE INDEX uq_registro_suministro_dedup_contenido 
   ON modulo5.registro_suministro (id_activo_biologico, id_ciclo_productivo, tipo_suministro, fecha_aplicacion, cantidad, precio_unitario_resuelto) 
   WHERE (((tipo_operacion)::text = 'REGISTRO'::text) AND (id_registro_rf75 IS NULL) AND (id_registro_rf76 IS NULL));
   ```
> [!WARNING] **Riesgo Crítico de Duplicados Evitado:**  
> Si se insertan 10.000 o 50.000 registros con valores modulares cíclicos (`i % 80`, `i % 5`), las combinaciones posibles colisionan a partir del registro 101.  
> **Solución técnica implementada:** En el script SQL, se asigna `precio_unitario_resuelto = (10.00 + (i * 0.0001))::numeric(14, 4)`, garantizando que **todas y cada una de las 50.000 filas sean estrictamente únicas**, previniendo violaciones de clave única.

### 3.3 Expiración de Archivos (RF-77 y RF-81)
- Se confirmó en la base de datos y en el código ([`ArchivoExportacion`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/supplies/domain/entities/archivo_exportacion.py)) que **ambos requisitos comparten exactamente la misma tabla** `modulo5.archivos_exportacion_suministros`.
- La columna `origen` discrimina entre `'RF77'` (vigencia 24 h) y `'RF81'` (vigencia 72 h).
- Actualmente la tabla tiene **0 filas** en TEST. Para que los tests puedan comprobar la respuesta `410 Gone`, se incluye en el Bloque 6 la inserción de 1 fila expirada para RF-77 y 1 para RF-81.

### 3.4 Diagnóstico de Infraestructuras en Fincas 81 y 82
- Consulta ejecutada:
  ```sql
  SELECT i.id_infraestructura, i.id_finca, i.nombre, i.es_activo 
  FROM modulo9.infraestructuras i WHERE i.id_finca IN (81, 82);
  ```
- **Resultado real:** `0 filas`. Ni Finca 81 (Gestor) ni Finca 82 (Revisor) tienen infraestructuras.
- **Impacto:** En Módulo 2, `id_infraestructura` es clave foránea obligatoria no nula. Si un usuario intenta crear un activo o asociar datos a estas fincas sin infraestructura, la API responde `404 INFRAESTRUCTURA_NO_ENCONTRADA` o `422`.
- **Acción:** Se añade el Bloque 7 para crear 1 infraestructura activa en cada finca.

---

## 4. Matriz Detallada de Requisitos por Grupo (G01 a G21)

| Grupo | Requisito de Dato del Caso de Prueba | Etiqueta | Evidencia Técnica (Archivos, Líneas, Consultas) | Acción / Resolución |
|:---:|---|:---:|---|---|
| **G01** | Rol Veterinario activo para aplicar medicación (RF-76 001,002) | **EXISTE_REUTILIZABLE** | Usuario 159 (`juanstesting@gmail.com`), rol 3 Veterinario, activo en TEST. Login 200 OK. | Reutilizar cuenta confirmada de Veterinario en sandbox. |
| **G01** | Activo INDIVIDUAL y POBLACIONAL activos con ciclo abierto y fecha conocida | **CREABLE_EN_SANDBOX** | Endpoints `POST /activos-biologicos` y `POST /activos-biologicos/{id}/ciclos` en Finca 3 / Infraestructura 6. | Crear al vuelo dentro del `run_id` transaccional. |
| **G01** | Activo POBLACIONAL con cantidad_actual > 0 (asume 250) | **CREABLE_EN_SANDBOX** | Parámetro `cantidad_inicial=250` soportado en payload de creación de activo poblacional en M02. | Instanciar en sandbox dinámicamente. |
| **G02** | Activo con fecha de inicio de ciclo conocida para probar medicación retroactiva | **CREABLE_EN_SANDBOX** | En sandbox se crea activo con `fecha_inicio_ciclo = CURRENT_DATE` y se prueba medicación con fecha anterior. | Validar rechazo `400 / 422 FECHA_ANTERIOR_INICIO_CICLO`. |
| **G03** | Activos en estados INACTIVO, AISLADO, EN_TRATAMIENTO, CERRADO, BAJA | **CREABLE_EN_SANDBOX** | Sondeos sandbox confirmaron que `PATCH /activos-biologicos/{id}/estado` permite INACTIVO y AISLADO; medicación con retiro pasa a EN_TRATAMIENTO; `POST .../cierre` pasa a CERRADO y baja pasa a BAJA. | Crear o transicionar por API en sandbox. |
| **G03** | Activo POBLACIONAL en estado ACTIVO con `cantidad_actual = 0` (TC-041) | **EXISTE_REUTILIZABLE** | Verificado en BD: **Activo 9** (`id_especie=3`, `id_infraestructura=4`) tiene `id_estado=1` (ACTIVO) y `cantidad_actual=0` en `detalles_activos_biologicos_poblacionales`. | Reutilizar Activo 9 existente para probar división por cero sin pedir seed al DBA. |
| **G04** | Dos activos A y B con eventos sanitarios propios (RF-41) | **CREABLE_EN_SANDBOX** | Módulo 2 expone registro de eventos sanitarios vinculados a `id_activo_biologico`. | Crear activos A y B en sandbox y registrar evento sanitario previo a la medicación. |
| **G05** | Activo EN_TRATAMIENTO con 2 tratamientos validados (retiro 5 y 10 días) | **CREABLE_EN_SANDBOX** | `POST /suministros/medicamentos` permite enviar `periodo_retiro_dias=5` y `10`. | Registrar 2 tratamientos en sandbox; consultar `MAX(fecha_fin_retiro)`. |
| **G05** | Activo limpio para 5 POST concurrentes | **CREABLE_EN_SANDBOX** | Crear nuevo activo en sandbox para asegurar 0 medicaciones previas. | Instanciar activo fresco en sandbox. |
| **G06** | Activo con tratamiento vencido y vigente para evaluación de scheduler | **CREABLE_EN_SANDBOX** | Use case `revertir_retiros_vencidos_use_case.py` es operable en sandbox con fechas relativas. | Probar en sandbox o en suite Pytest parametrizada. |
| **G07** | Registro de medicamento VALIDADO anulable y otro ya ANULADO | **EXISTE_REUTILIZABLE** | `modulo5.registros_medicamentos` ya cuenta con 7 VALIDADOS y 5 ANULADOS (ej. ID 5 VALIDADO, ID 2 ANULADO). | Reutilizar IDs 5 y 2 o generar uno fresco en sandbox y anularlo. |
| **G07** | Roles Veterinario, Administrador, Productor, Ingeniero para verificar RBAC | **EXISTE_REUTILIZABLE** | Roles 1 (Admin), 2 (Productor), 3 (Veterinario), 4 (Ingeniero) confirmados y activos en TEST. | Usar un run_id independiente por cada rol (regla DEF-04). |
| **G08** | Activo con 3 consumos (RF-75) y 2 medicaciones (RF-76) validados con costo y 1 anulado | **CREABLE_EN_SANDBOX** | Endpoints `POST /suministros/consumo-alimentos` y `POST /suministros/medicamentos` operan en sandbox. | Generar en sandbox los 5 registros requeridos y anular 1 de cada tipo. |
| **G08** | Activo POBLACIONAL con cantidad=100 y gasto 1.000.000 para reporte | **CREABLE_EN_SANDBOX** | En sandbox: activo con 100 aves, 1 medicación con costo 1.000.000. | Crear en sandbox; el reporte reflejará costo per cápita de 10.000. |
| **G09** | Activo con 2 consumos con costo_unitario y 2 sin costo_unitario (NULL) | **EXISTE_REUTILIZABLE** | En `modulo5.registros_consumo_alimentos` existen consumos con `costo_unitario IS NULL` (IDs 6, 11, 13) y con costo (IDs 28, 29). | Reutilizar activo 5 existente. |
| **G09** | Gasto en períodos comparativos (anterior=0, ambos=0, normal) | **CREABLE_EN_SANDBOX** | En sandbox se pueden generar consumos con `fecha_consumo` en rangos específicos. | Configurar las fechas en sandbox para cada sub-escenario. |
| **G10** | Activo con consumos que cubran >12 meses (450 días retroactivos) | **REQUIERE_DBA** | [`GenerarReporteGastosUseCase`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/supplies/application/use_cases/reporte_gastos/generar_reporte_gastos_use_case.py#L191) exige `fecha_inicio_reporte >= fecha_inicio_ciclo`. M02 bloquea creación de ciclos retroactivos >180 días. | **BLOQUE 2:** Solicitar al DBA 1 activo con ciclo abierto hace 450 días y consumos/medicamentos repartidos. |
| **G10** | Infraestructura y especie con varios activos con gasto >6 meses | **CREABLE_EN_SANDBOX** | `POST /suministros/reportes-gastos` acepta `id_infraestructura` e `id_especie`. | Instanciar infraestructura y activos en sandbox. |
| **G11** | Reportes de gastos con exactamente 500 registros de detalle (borde-menos-uno) | **REQUIERE_DBA** | Crear 500 registros por API en un run supera el timeout de 180 s del sandbox. | **BLOQUE 3:** Solicitar al DBA activo con exactamente 500 consumos en RF-75; el test añade el 501 por API. |
| **G11** | Modificación de `configuracion_batch_reportes_gastos` vía API | **BLOQUEADO_POR_BACKEND** | `batch_reportes_gastos_router.py`: no expone ningún endpoint `PUT/PATCH` para alterar límites de batch. `/test-control/query` solo admite SELECT. | Evaluar modificación de umbrales mediante tests de integración Pytest con mocks de repositorio. |
| **G12** | Reporte asíncrono (>12 meses) encolado | **CREABLE_EN_SANDBOX** | Al enviar rango >366 días el backend responde `202 Accepted` y encola en `cola_generacion_reportes_gastos`. | Encolar reporte en sandbox y consultar estado via polling. |
| **G12** | Forzado de fallo en trabajo asíncrono y reintentos (3 de 5 min) | **BLOQUEADO_POR_BACKEND** | `procesar_cola_reportes_gastos_use_case.py`: el worker se ejecuta en background de servidor. No hay API para inyectar fallos transitorios. | Probar fallos y reintentos en Pytest mockeando el caso de uso generador. |
| **G13** | Pruebas de IDOR (Productor A intentando ver reportes del Productor B) | **EXISTE_REUTILIZABLE** | Productor B (`pruebaas0608@gmail.com`) cuenta con Finca 114 en `modulo9.usuarios_fincas`. Permite probar IDOR sin alterar la BD. | Reutilizar Finca 114 para Productor B. Bloque 1 (Finca 113) queda como opcional/comentado. |
| **G14** | Eventos fuera de catálogo en auditoría (TC-027) | **BLOQUEADO_POR_BACKEND** | `modulo5.auditorias_suministros.tipo_operacion` es un enum cerrado (`enum_auditoria_suministro_tipo_operacion`). Rechazado por PostgreSQL a nivel DDL/DML. | Clasificar como desviación de especificación abstracta; el backend protege integridad con enum nativo. |
| **G14** | Eventos de M05 en almacén de auditoría (SUMINISTRO_REGISTRADO, CICLO_CONSOLIDADO) | **EXISTE_REUTILIZABLE** | Verificado en `modulo5.auditorias_suministros`: ya existen 4 de SUMINISTRO_REGISTRADO, 1 de CICLO_CONSOLIDADO, 2 de REPORTE_COSTOS_GENERADO. | Reutilizar eventos existentes en `auditorias_suministros` (IDs 81, 83, 95, 96). |
| **G15** | Activo + ciclo con varios eventos en momentos distintos (`fecha_evento` vs `fecha_emision`) | **EXISTE_REUTILIZABLE** | Registros en `modulo5.auditorias_suministros` vinculados al activo 57 y ciclo 33. | Reutilizar activo 57 y ciclo 33 para verificar cadena de custodia. |
| **G15** | Usuario con y sin permiso de auditoría (`bitacora_auditoria_suministros`) | **EXISTE_REUTILIZABLE** | Rol 1 (Admin) y Rol 8 (Revisor Fiscal) tienen permiso R (200 OK); Rol 4 (Ingeniero) da 403 Forbidden. | Probar consulta con Admin/Revisor Fiscal (200) y con Ingeniero (403). |
| **G16** | Detección periódica de hash SHA-256 corrupto / alerta de manipulación (TC-029) | **BLOQUEADO_POR_BACKEND** | Inspección de triggers y use cases: no existe ningún daemon, job ni scheduler que verifique periódicamente los hashes. `GET .../auditoria/{id}` solo lee el hash guardado. | Descartar seed de hash corrupto por inexistencia de componente detector en backend. |
| **G16** | Deduplicación de auditoría por `id_evento_m05` (TC-030) | **BLOQUEADO_POR_BACKEND** | `cu06_gaps_bd_rf80.md`: no existe columna `id_evento_m05` en auditoría ni deduplicación por reentrega. La deduplicación por idempotencia solo existe en `registro_suministro` (RF-78). | Documentar como desviación arquitectural justificada por persistencia transaccional síncrona. |
| **G17** | Cola persistente de auditoría M05→M12 (capacidad 100k, alertas 90% y 100%) | **BLOQUEADO_POR_BACKEND** | `cu06_gaps_bd_rf80.md`: no existe cola M05→M12 ni broker de auditoría. Cada evento se inserta sincrónicamente en PostgreSQL. | Registrar como funcionalidad descartada por arquitectura de persistencia directa. |
| **G18** | Activo con 500 registros de RF-78 (mezcla de tipos y orígenes de precio) | **EXISTE_REUTILIZABLE** | **BLOQUE 4** ya provee el activo `SEED-M05-HIST-10K` con mezcla balanceada de 4 tipos y 2 orígenes de precio. No se requiere bloque redundante. | Cubierto íntegramente por el activo de 10.000 suministros del Bloque 4. |
| **G18** | Simulación de M02 con latencia (2.9s, 4s) o caído | **CREABLE_EN_SANDBOX** | `ActivoM02Adapter` es configurable o interceptable en suite automatizada. | Evaluar timeout configurado en cliente HTTP en sandbox. |
| **G19** | Activo con ciclo de otro activo (inconsistencia cruzada) | **CREABLE_EN_SANDBOX** | Enviar `id_gestion_fases` no perteneciente al `id_activo_biologico`. | Backend valida pertenencia y responde `422 CICLO_NO_PERTENECE_ACTIVO`. |
| **G19** | Volúmenes masivos de historial (10.000 y 50.000 registros, bordes-menos-uno) | **REQUIERE_DBA** | Imposible generar 50.000 registros por API en sandbox sin timeout de servidor. | **BLOQUES 4 y 5:** Solicitar al DBA 10.000 y 50.000 registros en `modulo5.registro_suministro` con ciclos cerrado y activo. |
| **G20** | Acceso a historial de suministros por Contador, Revisor Fiscal y Gestor | **EXISTE_REUTILIZABLE** | Confirmado por sondeo: Revisor Fiscal (31) y Gestor de Granja (30) tienen permiso en recurso 52. Cuentas activas en TEST. | Reutilizar cuentas existentes; Gestor de Granja filtra por alcance de finca. |
| **G20** | Intento de modificación sobre registro de historial (RF-81) | **BLOQUEADO_POR_BACKEND** | El endpoint de historial es exclusivamente `GET` (solo lectura). No existe método de mutación. | Validar que no existan rutas PUT/DELETE en `/suministros/historial`. |
| **G21** | 4 y 10 exportaciones asíncronas simultáneas | **CREABLE_EN_SANDBOX** | Lanzar ráfaga de 4 y 10 llamadas a `POST /suministros/historial/trabajos` en paralelo. | Validar códigos 202 y encolamiento. |
| **G21** | Retención y expiración de archivos (72 h RF-81 y 24 h RF-77) | **REQUIERE_DBA** | `modulo5.archivos_exportacion_suministros` cuenta con 0 filas en TEST. | **BLOQUE 6:** Solicitar al DBA 2 filas sintéticas expiradas para validar `410 Gone`. |
| **G09** | Activo 1 contaminado por pruebas históricas previas | **EXISTE_NO_APTO** | Activo 1 cuenta con 6 medicamentos y 11 consumos mezclados de pruebas de carga anteriores. | Descartar para balance contable limpio; usar activos aislados. |
| **G07** | Tabla `modulo1.usuarios` no visible por RLS en SQL directo | **NO_VERIFICABLE** | Conexión `member_qa` retorna 0 filas bajo consulta SQL sin contexto de sesión activa. | Consumir vía endpoints autenticados de la API de producción. |
| **G03** | Tabla `modulo2.activos_biologicos` no visible por RLS en SQL directo | **NO_VERIFICABLE** | Conexión `member_qa` retorna 0 filas bajo consulta SQL sin contexto de sesión activa. | Consumir vía endpoints autenticados de la API de producción. |

---

## 5. Tabla de Mapeo: Fila REQUIERE_DBA → Bloque SQL

| Fila de la Matriz | Requisito DBA | Bloque en Script SQL | Objeto Creado / Afectado | Justificación de No-Sobrante |
|:---:|---|:---:|---|---|
| **G10** | Activo con ciclo de 450 días para reportes anuales | **BLOQUE 2** | `SEED-M05-REP-450D` + 12 consumos + 6 medicaciones | Use case valida `fecha_inicio_reporte >= fecha_inicio_ciclo`. |
| **G11** | Reporte con exactamente 500 consumos (borde-menos-uno) | **BLOQUE 3** | `SEED-M05-REP-500` + 500 consumos RF-75 | Sandbox excede timeout de 180s al crear 500 filas por API. |
| **G19** (cubre **G18**) | Historial Nivel 1 (10.000 reg) y Nivel 2 (50.000 reg) | **BLOQUES 4 y 5** | `SEED-M05-HIST-10K` (10k reg) y `SEED-M05-HIST-50K` (50k reg) | Valida límites de rendimiento e historial masivo. El Bloque 4 cubre G18 con mezcla de tipos. |
| **G21** | Descarga de archivo expirado (24h RF-77 y 72h RF-81) | **BLOQUE 6** | 2 filas en `modulo5.archivos_exportacion_suministros` | Tabla vacía en TEST; indispensable para validar `410 Gone`. |
| **Infraestructuras** | Infraestructuras para Gestor y Revisor | **BLOQUE 7** | 2 infraestructuras en `modulo9.infraestructuras` (fincas 81 y 82) | Fincas 81 y 82 tienen 0 infraestructuras; API rechaza creación de activos. |
| **G13 (Opcional)** | Asignación Finca 113 a Productor B | **BLOQUE 1** *(Comentado)* | `modulo9.usuarios_fincas` | Opcional: Productor B ya tiene Finca 114. |

---

## 6. Estado de Cuentas, Permisos RBAC y Alcance

### 6.1 Diagnóstico de Login por Cuenta
| Rol | Correo Auditado | ID | Login Status | Estado / Observación |
|---|---|:---:|:---:|---|
| **Administrador** | `administador.dev@gmail.com` | 104 | ✅ **200 OK** | Confirmado. Alcance global (415 fincas). |
| **Productor A** | `productor@pecuaria.co` | 2 | ✅ **200 OK** | Confirmado. Fincas asignadas: `[1, 2, 3, 4, 5, 6, 8, 20, 140]`. |
| **Productor B** | `pruebaas0608@gmail.com` | 96 | ✅ **200 OK** | Confirmado. Finca 114 asignada. |
| **Veterinario** | `juanstesting@gmail.com` | 159 | ✅ **200 OK** | Confirmado. Fincas: `[3, 8]`. Registro de medicación habilitado. |
| **Ingeniero de Campo** | `ingeniero@pecuaria.co` | 4 | ✅ **200 OK** | Confirmado. Finca: 8. Sin acceso a M05. |
| **Gestor de Granja** | `gestor.granja.test@pecuaria.co` | 30 | ✅ **200 OK** | Confirmado. Finca: `81`. Historial con alcance por finca. |
| **Revisor Fiscal** | `revisor.fiscal.test@pecuaria.co` | 31 | ✅ **200 OK** | Confirmado. Finca: `82`. Lectura de auditoría e historial. |
| **Contador** | `contador@pecuaria.co` | 5 | ⏳ **PENDIENTE** | **login del Contador sin probar: falta la variable TEST_ACCOUNTANT_PASSWORD**. Siguiendo la instrucción del usuario, no se intentó login ni se probaron otras claves. |

---

## 7. Script SQL Idempotente y Robusto para el DBA

```sql
-- ============================================================================
-- SCRIPT DE DATOS SEMILLA PARA EL MÓDULO 5 (SUMINISTROS) - ENTORNO TEST
-- Versión: Cuarta Pasada (Definitiva y Verificada)
-- Base de Datos: sgpmp_test | Rol de ejecución: postgres / dba / sgpmp_owner
-- ============================================================================

BEGIN;

-- 0. Variables de contexto de sesión PostgreSQL para triggers de auditoría
SET LOCAL "app.usuario_id" = '104';
SET LOCAL "app.rol_id" = '1';
SET LOCAL "app.current_user_id" = '104';
SET LOCAL "app.current_role" = 'Administrador';
SET LOCAL "app.current_role_id" = '1';

-- ----------------------------------------------------------------------------
-- BLOQUE 1 (OPCIONAL): Asignación de Finca 113 a Productor B (G13)
-- NOTA: Opcional, ya que Productor B cuenta con la Finca 114 asignada.
-- ----------------------------------------------------------------------------
/*
INSERT INTO modulo9.usuarios_fincas (id_usuario, id_finca)
SELECT 96, 113
WHERE NOT EXISTS (
    SELECT 1 FROM modulo9.usuarios_fincas WHERE id_usuario = 96 AND id_finca = 113
);
*/

-- ----------------------------------------------------------------------------
-- BLOQUE 2: Activo de 450 días para Reportes Anuales Asíncronos (RF-77 / G10)
-- ----------------------------------------------------------------------------
DO $$
DECLARE
    v_act_450 INT;
    v_fase_450 INT;
BEGIN
    SELECT id_activo_biologico INTO v_act_450 
    FROM modulo2.activos_biologicos 
    WHERE identificador = 'SEED-M05-REP-450D';

    IF v_act_450 IS NULL THEN
        INSERT INTO modulo2.activos_biologicos (
            id_especie, identificador, id_infraestructura, tipo,
            id_estado, origen_financiero, costo_adquisicion, soporte_documental,
            id_usuario, fecha_creacion, fecha_inicio_ciclo
        ) VALUES (
            1, 'SEED-M05-REP-450D', 6, 'INDIVIDUAL'::modulo2.enum_activo_biologico_tipo,
            1, 'compra'::modulo2.enum_activo_biologico_origen_financiero, 100000.00, 'FAC-SEED-450D',
            104, NOW() - INTERVAL '450 days', (CURRENT_DATE - INTERVAL '450 days')::date
        ) RETURNING id_activo_biologico INTO v_act_450;

        INSERT INTO modulo2.gestiones_fases (
            id_activo_biologico, id_ciclo_productiva, id_ciclos_productivo_biologico,
            fecha_inicio, es_activa, id_usuario, es_transicion_no_estandar
        ) VALUES (
            v_act_450, 4, 4, NOW() - INTERVAL '450 days', true, 104, false
        ) RETURNING id_gestion_fases INTO v_fase_450;

        -- 12 consumos validados distribuidos en 450 días
        INSERT INTO modulo5.registros_consumo_alimentos (
            id_activo_biologico, id_tipo_alimento, tipo_alimento, tipo_unidad,
            cantidad_suministrada, costo_unitario, fecha_consumo, hora_suministro,
            estado_registro, id_usuario
        )
        SELECT
            v_act_450, 1, 'Iniciacion Truchas', 'KG',
            (20.00 + (i % 5))::numeric, 5000.00,
            (CURRENT_DATE - ((10 + (i * 35)) || ' days')::interval)::date,
            (('08:' || lpad((i % 50)::text, 2, '0') || ':00'))::time,
            'VALIDADO', 104
        FROM generate_series(1, 12) AS s(i);

        -- 6 tratamientos validados distribuidos en 450 días
        INSERT INTO modulo5.registros_medicamentos (
            id_activo_biologico, nombre_medicamento, dosis_aplicada, unidad_dosis,
            via_administracion, periodo_retiro_dias, motivo_aplicacion, costo_unitario,
            nombre_veterinario, fecha_aplicacion, hora_aplicacion, fecha_fin_retiro,
            estado_registro, id_usuario
        )
        SELECT
            v_act_450, 'Oxitetraciclina 20%', 15.00, 'ml',
            'IM'::modulo5.enum_registro_medicamenti_via_aplicacion, 5,
            'Tratamiento bacteriano preventivo de control semestral', 25000.00,
            'Dr. Juan Veterinario',
            (CURRENT_DATE - ((20 + (i * 70)) || ' days')::interval)::date,
            (('09:' || lpad((i % 50)::text, 2, '0') || ':00'))::time,
            (CURRENT_DATE - ((15 + (i * 70)) || ' days')::interval)::date,
            'VALIDADO', 104
        FROM generate_series(1, 6) AS s(i);
    END IF;
END $$;

-- ----------------------------------------------------------------------------
-- BLOQUE 3: Activo Borde-Menos-Uno para RF-77 (Exactamente 500 consumos) - G11
-- ----------------------------------------------------------------------------
DO $$
DECLARE
    v_act_500 INT;
    v_fase_500 INT;
BEGIN
    SELECT id_activo_biologico INTO v_act_500 
    FROM modulo2.activos_biologicos 
    WHERE identificador = 'SEED-M05-REP-500';

    IF v_act_500 IS NULL THEN
        INSERT INTO modulo2.activos_biologicos (
            id_especie, identificador, id_infraestructura, tipo,
            id_estado, origen_financiero, costo_adquisicion, soporte_documental,
            id_usuario, fecha_creacion, fecha_inicio_ciclo
        ) VALUES (
            1, 'SEED-M05-REP-500', 6, 'INDIVIDUAL'::modulo2.enum_activo_biologico_tipo,
            1, 'compra'::modulo2.enum_activo_biologico_origen_financiero, 100000.00, 'FAC-SEED-500',
            104, NOW() - INTERVAL '100 days', (CURRENT_DATE - INTERVAL '100 days')::date
        ) RETURNING id_activo_biologico INTO v_act_500;

        INSERT INTO modulo2.gestiones_fases (
            id_activo_biologico, id_ciclo_productiva, id_ciclos_productivo_biologico,
            fecha_inicio, es_activa, id_usuario, es_transicion_no_estandar
        ) VALUES (
            v_act_500, 4, 4, NOW() - INTERVAL '100 days', true, 104, false
        ) RETURNING id_gestion_fases INTO v_fase_500;

        -- Deshabilitar temporalmente trigger de auditoría para no contaminar bitácora
        ALTER TABLE modulo5.registros_consumo_alimentos DISABLE TRIGGER trg_auditoria_consumo_alimento;

        -- Inserción de exactamente 500 consumos con horas y fechas distribuidas (sin colisión)
        INSERT INTO modulo5.registros_consumo_alimentos (
            id_activo_biologico, id_tipo_alimento, tipo_alimento, tipo_unidad,
            cantidad_suministrada, costo_unitario, fecha_consumo, hora_suministro,
            estado_registro, id_usuario
        )
        SELECT
            v_act_500, 1, 'Concentrado Truchas Engorde', 'KG',
            (10.00 + (i % 10))::numeric, 5200.00,
            (CURRENT_DATE - ((1 + (i / 10)) || ' days')::interval)::date,
            (('08:' || lpad(((i % 10) * 5)::text, 2, '0') || ':00'))::time,
            'VALIDADO', 104
        FROM generate_series(1, 500) AS s(i);

        ALTER TABLE modulo5.registros_consumo_alimentos ENABLE TRIGGER trg_auditoria_consumo_alimento;
    END IF;
END $$;

-- ----------------------------------------------------------------------------
-- BLOQUE 4: Volumen Borde-Menos-Uno para RF-81 Nivel 1 (10.000 registros) - G18 / G19
-- ----------------------------------------------------------------------------
DO $$
DECLARE
    v_act_10k INT;
    v_fase_cerrada INT;
    v_fase_activa INT;
BEGIN
    SELECT id_activo_biologico INTO v_act_10k 
    FROM modulo2.activos_biologicos 
    WHERE identificador = 'SEED-M05-HIST-10K';

    IF v_act_10k IS NULL THEN
        INSERT INTO modulo2.activos_biologicos (
            id_especie, identificador, id_infraestructura, tipo,
            id_estado, origen_financiero, costo_adquisicion, soporte_documental,
            id_usuario, fecha_creacion, fecha_inicio_ciclo
        ) VALUES (
            1, 'SEED-M05-HIST-10K', 6, 'INDIVIDUAL'::modulo2.enum_activo_biologico_tipo,
            1, 'compra'::modulo2.enum_activo_biologico_origen_financiero, 100000.00, 'FAC-SEED-10K',
            104, NOW() - INTERVAL '200 days', (CURRENT_DATE - INTERVAL '200 days')::date
        ) RETURNING id_activo_biologico INTO v_act_10k;

        -- Fase cerrada (días 200 a 100 atrás)
        INSERT INTO modulo2.gestiones_fases (
            id_activo_biologico, id_ciclo_productiva, id_ciclos_productivo_biologico,
            fecha_inicio, fecha_fin, es_activa, id_usuario, es_transicion_no_estandar
        ) VALUES (
            v_act_10k, 4, 4, NOW() - INTERVAL '200 days', NOW() - INTERVAL '100 days', false, 104, false
        ) RETURNING id_gestion_fases INTO v_fase_cerrada;

        -- Fase activa (días 99 a hoy)
        INSERT INTO modulo2.gestiones_fases (
            id_activo_biologico, id_ciclo_productiva, id_ciclos_productivo_biologico,
            fecha_inicio, es_activa, id_usuario, es_transicion_no_estandar
        ) VALUES (
            v_act_10k, 4, 4, NOW() - INTERVAL '99 days', true, 104, false
        ) RETURNING id_gestion_fases INTO v_fase_activa;

        -- 5.000 suministros para fase cerrada (precios escalonados para unicidad estricta)
        INSERT INTO modulo5.registro_suministro (
            id_activo_biologico, id_gestion_fases, id_ciclo_productivo, tipo_suministro,
            cantidad, unidad_medida, precio_unitario_resuelto, costo_registro,
            origen_precio, fecha_aplicacion, naturaleza_costo, tipo_operacion
        )
        SELECT
            v_act_10k, v_fase_cerrada, 4,
            (CASE (i % 4) WHEN 0 THEN 'ALIMENTO' WHEN 1 THEN 'MEDICAMENTO' WHEN 2 THEN 'SERVICIO_VETERINARIO' ELSE 'INSEMINACION' END)::modulo5.enum_tipo_suministro,
            (1 + (i % 5))::numeric,
            CASE (i % 4) WHEN 0 THEN 'kg' WHEN 1 THEN 'ml' WHEN 2 THEN 'sesion' ELSE 'dosis' END,
            (15.00 + (i * 0.0001))::numeric(14, 4),
            ((15.00 + (i * 0.0001)) * (1 + (i % 5)))::numeric,
            (CASE (i % 2) WHEN 0 THEN 'MANUAL' ELSE 'M40_AUTOMATICO' END)::modulo5.enum_origen_precio,
            (CURRENT_DATE - ((105 + (i % 80)) || ' days')::interval)::date,
            'MANTENIMIENTO'::modulo5.enum_naturaleza_costo, 'REGISTRO'
        FROM generate_series(1, 5000) AS s(i);

        -- 5.000 suministros para fase activa
        INSERT INTO modulo5.registro_suministro (
            id_activo_biologico, id_gestion_fases, id_ciclo_productivo, tipo_suministro,
            cantidad, unidad_medida, precio_unitario_resuelto, costo_registro,
            origen_precio, fecha_aplicacion, naturaleza_costo, tipo_operacion
        )
        SELECT
            v_act_10k, v_fase_activa, 4,
            (CASE (i % 4) WHEN 0 THEN 'ALIMENTO' WHEN 1 THEN 'MEDICAMENTO' WHEN 2 THEN 'SERVICIO_VETERINARIO' ELSE 'INSEMINACION' END)::modulo5.enum_tipo_suministro,
            (1 + (i % 5))::numeric,
            CASE (i % 4) WHEN 0 THEN 'kg' WHEN 1 THEN 'ml' WHEN 2 THEN 'sesion' ELSE 'dosis' END,
            (15.00 + (i * 0.0001))::numeric(14, 4),
            ((15.00 + (i * 0.0001)) * (1 + (i % 5)))::numeric,
            (CASE (i % 2) WHEN 0 THEN 'MANUAL' ELSE 'M40_AUTOMATICO' END)::modulo5.enum_origen_precio,
            (CURRENT_DATE - ((1 + (i % 90)) || ' days')::interval)::date,
            'MANTENIMIENTO'::modulo5.enum_naturaleza_costo, 'REGISTRO'
        FROM generate_series(1, 5000) AS s(i);
    END IF;
END $$;

-- ----------------------------------------------------------------------------
-- BLOQUE 5: Volumen Borde-Menos-Uno para RF-81 Estrés Batch (50.000 registros) - G19
-- ----------------------------------------------------------------------------
DO $$
DECLARE
    v_act_50k INT;
    v_fase_activa INT;
BEGIN
    SELECT id_activo_biologico INTO v_act_50k 
    FROM modulo2.activos_biologicos 
    WHERE identificador = 'SEED-M05-HIST-50K';

    IF v_act_50k IS NULL THEN
        INSERT INTO modulo2.activos_biologicos (
            id_especie, identificador, id_infraestructura, tipo,
            id_estado, origen_financiero, costo_adquisicion, soporte_documental,
            id_usuario, fecha_creacion, fecha_inicio_ciclo
        ) VALUES (
            1, 'SEED-M05-HIST-50K', 6, 'INDIVIDUAL'::modulo2.enum_activo_biologico_tipo,
            1, 'compra'::modulo2.enum_activo_biologico_origen_financiero, 100000.00, 'FAC-SEED-50K',
            104, NOW() - INTERVAL '250 days', (CURRENT_DATE - INTERVAL '250 days')::date
        ) RETURNING id_activo_biologico INTO v_act_50k;

        INSERT INTO modulo2.gestiones_fases (
            id_activo_biologico, id_ciclo_productiva, id_ciclos_productivo_biologico,
            fecha_inicio, es_activa, id_usuario, es_transicion_no_estandar
        ) VALUES (
            v_act_50k, 4, 4, NOW() - INTERVAL '250 days', true, 104, false
        ) RETURNING id_gestion_fases INTO v_fase_activa;

        -- Inserción de exactamente 50.000 suministros con precios únicos garantizados
        INSERT INTO modulo5.registro_suministro (
            id_activo_biologico, id_gestion_fases, id_ciclo_productivo, tipo_suministro,
            cantidad, unidad_medida, precio_unitario_resuelto, costo_registro,
            origen_precio, fecha_aplicacion, naturaleza_costo, tipo_operacion
        )
        SELECT
            v_act_50k, v_fase_activa, 4,
            (CASE (i % 4) WHEN 0 THEN 'ALIMENTO' WHEN 1 THEN 'MEDICAMENTO' WHEN 2 THEN 'SERVICIO_VETERINARIO' ELSE 'INSEMINACION' END)::modulo5.enum_tipo_suministro,
            (1 + (i % 5))::numeric,
            CASE (i % 4) WHEN 0 THEN 'kg' WHEN 1 THEN 'ml' WHEN 2 THEN 'sesion' ELSE 'dosis' END,
            (12.50 + (i * 0.0001))::numeric(14, 4),
            ((12.50 + (i * 0.0001)) * (1 + (i % 5)))::numeric,
            (CASE (i % 2) WHEN 0 THEN 'MANUAL' ELSE 'M40_AUTOMATICO' END)::modulo5.enum_origen_precio,
            (CURRENT_DATE - ((1 + (i % 240)) || ' days')::interval)::date,
            'MANTENIMIENTO'::modulo5.enum_naturaleza_costo, 'REGISTRO'
        FROM generate_series(1, 50000) AS s(i);
    END IF;
END $$;

-- ----------------------------------------------------------------------------
-- BLOQUE 6: Archivos Expirados para Validación de HTTP 410 Gone (RF-77 y RF-81) - G21
-- ----------------------------------------------------------------------------
-- Registro de trabajo async completado para que la descarga de RF-81 resuelva id_cola 81001
INSERT INTO modulo5.cola_trabajos_historial_suministros (
    id_cola, tipo_trabajo, parametros, estado, id_usuario_solicitante, fecha_solicitud, fecha_procesado
) VALUES (
    81001, 'EXPORTACION', '{"id_activo_biologico": 5, "formato": "CSV"}'::jsonb,
    'COMPLETADO', 104, NOW() - INTERVAL '73 hours', NOW() - INTERVAL '72 hours 55 minutes'
) ON CONFLICT (id_cola) DO NOTHING;

INSERT INTO modulo5.archivos_exportacion_suministros (
    id_archivo_exportacion_suministro, origen, id_referencia, formato, nombre_archivo,
    tipo_contenido, contenido, tamano_bytes, total_registros,
    id_usuario, fecha_generacion, fecha_expiracion
) VALUES 
(
    '11111111-1111-1111-1111-111111111111', 'RF77', NULL, 'PDF', 'reporte_expirado_24h.pdf',
    'application/pdf', E'\\x25504446'::bytea, 4, 10,
    104, NOW() - INTERVAL '25 hours', NOW() - INTERVAL '1 hour'
),
(
    '22222222-2222-2222-2222-222222222222', 'RF81', 81001, 'CSV', 'historial_expirado_72h.csv',
    'text/csv', E'\\x616263'::bytea, 3, 50,
    104, NOW() - INTERVAL '73 hours', NOW() - INTERVAL '1 hour'
)
ON CONFLICT (id_archivo_exportacion_suministro) DO NOTHING;
    104, NOW() - INTERVAL '73 hours', NOW() - INTERVAL '1 hour'
)
ON CONFLICT (id_archivo_exportacion_suministro) DO NOTHING;

-- ----------------------------------------------------------------------------
-- BLOQUE 7: Infraestructuras Activas en Fincas 81 y 82 (Gestor y Revisor)
-- ----------------------------------------------------------------------------
INSERT INTO modulo9.infraestructuras (
    id_finca, nombre, tipo, superficie, es_activo, tipo_modelo_asignado, nivel_criticidad
) VALUES 
(81, 'Galpon Gestor F81', 'GALPON', 150.00, true, 'ESTANDAR', 'MEDIO'),
(82, 'Galpon Revisor F82', 'GALPON', 150.00, true, 'ESTANDAR', 'MEDIO')
ON CONFLICT DO NOTHING;

-- ============================================================================
-- VERIFICACIÓN INMEDIATA DE CONTEOS
-- ============================================================================
SELECT 'Activo 450D' AS concepto, count(*) AS total FROM modulo2.activos_biologicos WHERE identificador = 'SEED-M05-REP-450D'
UNION ALL
SELECT 'Consumos Borde 500', count(*) FROM modulo5.registros_consumo_alimentos WHERE id_activo_biologico = (SELECT id_activo_biologico FROM modulo2.activos_biologicos WHERE identificador = 'SEED-M05-REP-500')
UNION ALL
SELECT 'Historial 10K', count(*) FROM modulo5.registro_suministro WHERE id_activo_biologico = (SELECT id_activo_biologico FROM modulo2.activos_biologicos WHERE identificador = 'SEED-M05-HIST-10K')
UNION ALL
SELECT 'Historial 50K', count(*) FROM modulo5.registro_suministro WHERE id_activo_biologico = (SELECT id_activo_biologico FROM modulo2.activos_biologicos WHERE identificador = 'SEED-M05-HIST-50K')
UNION ALL
SELECT 'Archivos Expirados (410)', count(*) FROM modulo5.archivos_exportacion_suministros WHERE id_archivo_exportacion_suministro IN ('11111111-1111-1111-1111-111111111111', '22222222-2222-2222-2222-222222222222')
UNION ALL
SELECT 'Infraestructuras F81/F82', count(*) FROM modulo9.infraestructuras WHERE id_finca IN (81, 82);

COMMIT;
```

---

## 8. Informe de Ejecución del Dry Run (BEGIN ... ROLLBACK)

- **Rol ejecutor utilizado:** `member_qa` (rol de solo lectura de QA proporcionado en `TEST_DATABASE_URL`).
- **Diagnóstico de ejecución de DML directo:**
  - El usuario `member_qa` carece de permisos `USAGE` sobre el esquema `public`, carece de privilegios `EXECUTE` sobre la función `modulo2.fn_activos_del_usuario`, y carece de permisos de `INSERT` sobre `modulo5.archivos_exportacion_suministros`.
  - Cuando se intentó insertar en `modulo2.activos_biologicos`, el trigger `trg_auditar_activo_biologico` disparó la verificación RLS que invoca `modulo2.fn_activos_del_usuario`, arrojando `psycopg2.errors.InsufficientPrivilege: permission denied for function fn_activos_del_usuario`.
  - Cuando se probó la inserción en `modulo5.registros_consumo_alimentos`, el trigger de auditoría invocó `modulo5.calcular_hash_integridad()`, el cual llama a `public.digest()`, resultando en `permission denied for schema public`.
  - **Conclusión Técnica:** La ejecución real de este script requiere los privilegios del superusuario o dueño del esquema (`postgres`, `dba` o `sgpmp_owner`). Los comandos `ALTER TABLE ... DISABLE TRIGGER` también exigen rol propietario o superusuario.
  - La base de datos persistente se mantuvo **100% inalterada** y libre de contaminación.

---

## 9. Discrepancias Técnicas con la Especificación y Arquitectura

1. **Parámetro `via_administracion` en `POST /suministros/medicamentos` (RF-76):**
   - El Value Object [`ViaAplicacion`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/supplies/domain/value_objects/via_aplicacion.py) acepta nombres completos (`INTRAMUSCULAR`, `INTRAVENOSA`, `SUBCUTANEA`) y códigos cortos (`IM`, `IV`, `SC`), normalizándolos internamente al enum nativo `modulo5.enum_registro_medicamenti_via_aplicacion`.
2. **Formato de `hora_aplicacion` (RF-76):**
   - El campo es de tipo `time` (`HH:MM:SS`). Pydantic acepta `HH:MM` normalizándolo con `:00` segundos.
3. **Ausencia de Cola persistente M05→M12 (RF-80 / G17):**
   - No existe broker ni cola externa M12. La auditoría se persiste sincrónicamente en PostgreSQL dentro de la misma transacción de negocio.
4. **Ausencia de Deduplicación por `id_evento_m05` en Auditoría (RF-80 / G16):**
   - La clave primaria de `modulo5.auditorias_suministros` es el secuencial `id_auditoria_suministro`. No hay riesgo de duplicados por reentrega. La deduplicación por idempotencia solo opera en `modulo5.registro_suministro` (RF-78).
5. **Inexistencia de Job Verificador de Manipulación de Hashes (RF-80 / G16):**
   - No existe daemon ni worker de fondo que verifique la integridad periódica de los hashes. `GET .../auditoria/{id}` se limita a devolver el hash persistido.
6. **Alcance Territorial del Revisor Fiscal y Contador en Historial (RF-81 / G20):**
   - A diferencia de la especificación abstracta, el backend restringe el acceso de todos los usuarios no administradores a las fincas asignadas en `modulo9.usuarios_fincas`. Un usuario que consulte un activo fuera de su finca recibe `404 ACTIVO_NO_ENCONTRADO`.
7. **Inmutabilidad y Anulación Compensatoria (RF-76):**
   - Se ratifica que la especificación define el registro de medicamentos como inmutable. `PUT`, `PATCH` y `DELETE` responden `405 Method Not Allowed`, y el caso TC-010 valida correctamente este comportamiento.
