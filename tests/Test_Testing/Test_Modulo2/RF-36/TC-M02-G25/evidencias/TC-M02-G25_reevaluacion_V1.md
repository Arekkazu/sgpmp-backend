# INFORME DE RESULTADOS DE PRUEBAS DE ACEPTACIÓN
## CASO AGRUPADO: TC-M02-G25 (RF-36: Gestión Poblacional de Activos Biológicos)

- **Fecha de Ejecución**: 2026-09-08 / 2026-09-09
- **Entorno**: TEST (`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`)
- **Base de Datos**: PostgreSQL TEST (`158.69.200.27:5448/sgpmp_test`, usuario `member_qa`)
- **Herramienta**: Newman CLI v6.2.2 + Reporter `htmlextra`
- **Veredicto Global**: **FAIL PARCIAL (1 PASS, 1 FAIL — DEFECTO DETECTADO)**

---

## 1. Resumen Ejecutivo de Resultados

| Sub-caso | Objetivo de la Prueba | Resultado Esperado | Resultado Obtenido | Veredicto |
| :--- | :--- | :--- | :--- | :--- |
| **TC-M02-051** | Rechazar cantidad actual negativa (Baja parcial > existencia) | `HTTP 400` / `422`<br>Rechazo por cantidad superior a existencia. Lote intacto. | `HTTP 422 Unprocessable Entity`<br>`CANTIDAD_BAJA_SUPERIOR_EXISTENCIA`<br>Lote intacto (existencia = 5). | **PASS** |
| **TC-M02-052** | Rechazar densidad superior a la máxima por especie | `HTTP 409 Conflict`<br>*"La densidad del lote supera el máximo permitido para la especie"*. Lote intacto. | `HTTP 201 Created`<br>El backend **no valida densidad máxima**, persiste el evento y actualiza biomasa y peso. | **FAIL (DEFECTO)** |

---

## 2. Datos del Lote de Prueba (Activo Biológico Poblacional)

- **ID Activo**: `130`
- **Especie**: `4` (*Cachama Blanca*)
- **Infraestructura**: `3` (*Alevinera-01*, superficie = 500 m²)
- **Tipo de Activo**: `POBLACIONAL`
- **Estado Inicial**: `1` (`ACTIVO`)
- **Cantidad Inicial / Actual**: `5` individuos
- **Fase Productiva Activa**: `Fase juvenil cachama` (`id_gestion_fases = 35`, ciclo `4`)

---

## 3. Detalle de Ejecución por Sub-caso

### 3.1. Sub-caso TC-M02-051: Rechazar cantidad_actual negativa (Baja Excesiva)

- **Colección Postman**: `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G25/TC-M02-051.json`
- **Reporte HTML Generado**: `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G25/RESULTADOS/reporte_TC-M02-051.html`
- **Endpoint**: `POST /activos-biologicos/130/eventos/baja`
- **Payload Enviado**:
  ```json
  {
    "tipo_baja": "VENTA",
    "fecha_baja": "2026-09-08",
    "motivo_baja": "Prueba de validación de baja superior a existencia",
    "cantidad_afectada": 10,
    "responsable_id": 1
  }
  ```
- **Respuesta de la API**:
  - **Código HTTP**: `422 Unprocessable Entity`
  - **Cuerpo JSON**:
    ```json
    {
      "error_code": "CANTIDAD_BAJA_SUPERIOR_EXISTENCIA",
      "message": "La cantidad a dar de baja (10) es superior a la existencia actual del lote (5).",
      "fields": [
        {
          "field": "cantidad_afectada",
          "message": "La cantidad a dar de baja (10) es superior a la existencia actual del lote (5)."
        }
      ],
      "timestamp": "2026-09-09T01:51:01.117702+00:00"
    }
    ```
- **Métricas Newman**:
  - Peticiones: 2 / 2 ejecutadas
  - Aserciones: **3 / 3 PASSED (100%)**
  - Fallas: 0
- **Veredicto**: **PASS**

---

### 3.2. Sub-caso TC-M02-052: Rechazar densidad superior a la máxima por especie

- **Colección Postman**: `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G25/TC-M02-052.json`
- **Reporte HTML Generado**: `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G25/RESULTADOS/reporte_TC-M02-052.html`
- **Endpoint**: `POST /activos-biologicos/130/eventos/crecimiento`
- **Payload Plano Enviado (según DTO `RegistrarEventoCrecimientoDTO`)**:
  ```json
  {
    "tipo_medicion": "PESO",
    "valor_medicion": 50,
    "unidad_medida": "kg",
    "nuevo_peso_promedio": 55,
    "cantidad_medida": 250,
    "tipo_agregacion": "PROMEDIO",
    "fecha": "2026-09-09T02:05:38Z"
  }
  ```
- **Respuesta Real de la API**:
  - **Código HTTP Obtenido**: `201 Created` *(Esperado: 409 Conflict)*
  - **Cuerpo JSON**:
    ```json
    {
      "evento": {
        "id_eventos": 126,
        "id_activo_biologico": 130,
        "fecha": "2026-09-09T02:05:38Z",
        "descripcion": null,
        "id_usuario": 1,
        "crecimiento": {
          "tipo_medicion": "PESO",
          "valor_medicion": "50.00",
          "unidad_medida": "kg",
          "tipo_agregacion": "PROMEDIO",
          "frecuencia": null,
          "nuevo_peso_promedio": "55.0000",
          "cantidad_medida": 250
        },
        "baja": null,
        "sanitario": null,
        "productivo": null,
        "reproductivo": null
      },
      "fase_avanzada": false
    }
    ```
- **Métricas Newman**:
  - Peticiones: 2 / 2 ejecutadas
  - Aserciones: **1 PASSED / 2 FAILED**
    - `1. Código HTTP esperado: 409 Conflict` → **FAILED** (`expected response to have status code 409 but got 201`)
    - `2. Mensaje de error contiene rechazo por superación de densidad` → **FAILED** (`expected undefined to be true`)
- **Veredicto**: **FAIL (DEFECTO IDENTIFICADO)**

---

## 4. Verificación de Impacto en Base de Datos TEST (Solo Lectura)

Consulta ejecutada tras la prueba:
```sql
SELECT a.id_activo_biologico, a.tipo, a.id_estado, 
       d.cantidad_inicial, d.cantidad_actual, d.densidad, d.biomasa_total, d.peso_promedio, d.peso_promedio_inicial
FROM modulo2.activos_biologicos a
LEFT JOIN modulo2.detalles_activos_biologicos_poblacionales d 
  ON a.id_activo_biologico = d.id_activo_biologico
WHERE a.id_activo_biologico = 130;
```

**Resultado en BD**:
- `cantidad_actual`: **5**
- `densidad`: **0.01000000000000000000** *(Calculada como 5 / 500 = 0.01)*
- `biomasa_total`: **275.00** *(5 individuos * 55 kg nuevo peso promedio)*
- `peso_promedio`: **55.00**
- Eventos registrados en `modulo2.eventos_activos` para el activo 130: **3 eventos** (fueron persistidos debido al código 201).

---

## 5. Análisis de Causa Raíz y Hallazgos Técnicos

### 1. Defecto Funcional INC-M02-01 (Ausencia de Regla de Negocio de Densidad Máxima):
- En el código fuente de `RegistrarEventoCrecimientoUseCase` (`src/biological_assets/application/use_cases/gestion/registrar_evento_crecimiento_use_case.py`), **no existe ninguna lógica que consulte la densidad máxima de la especie ni que compare la densidad proyectada**.
- El método de dominio `activo.aplicar_evento_crecimiento()` solo ejecuta:
  ```python
  dp.peso_promedio = nuevo_peso_promedio
  cantidad_actual = Decimal(str(dp.cantidad_actual or 0))
  dp.biomasa_total = cantidad_actual * nuevo_peso_promedio
  if superficie and superficie > 0:
      dp.densidad = cantidad_actual / superficie
  ```
- Como `cantidad_medida` (250) es solo un campo descriptivo del muestreo y no altera `dp.cantidad_actual` (5), el lote simplemente recalcula su densidad como 5 / 500 = 0.01 y persiste el evento con `HTTP 201 Created`.
- **Recomendación**: Implementar en `RegistrarEventoCrecimientoUseCase` o en `ParametrosEspeciePort` la consulta de la densidad máxima de la especie configurada en Módulo 9, y lanzar `ConflictError('DENSIDAD_MAXIMA_SUPERADA', 'La densidad del lote supera el máximo permitido para la especie')` cuando la densidad calculada supere el umbral.

### 2. Defecto Técnico en Asignación de Fases (RF-37):
- Durante la preparación del entorno, se detectó un error en `src/biological_assets/application/use_cases/gestion/cambiar_fase_use_case.py` (línea 72):
  `self.repo.cerrar_gestion_activa(id_activo, ahora, dto.motivo_cambio or '')`
  Dicho método requiere 4 argumentos posicionales (`id_activo, fecha_fin, motivo, usuario_id`), por lo que llamar al endpoint `POST /activos-biologicos/{id}/fases` causaba `TypeError` (`HTTP 500 Internal Server Error`).
- Se corrigió en el código local pasando `usuario.id_usuario`.
