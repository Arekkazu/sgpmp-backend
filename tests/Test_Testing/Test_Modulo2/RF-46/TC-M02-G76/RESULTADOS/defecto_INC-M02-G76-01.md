# REPORTE DE DEFECTO FORMAL: INC-M02-G76-01
## Omisión de Mensaje Informativo en Respuesta de Historial con Filtro sin Resultados (Flujo E-04)

---

## 1. Estado del Defecto y Metadatos de Gestión

| Campo | Valor |
| :--- | :--- |
| **ID del Defecto:** | `INC-M02-G76-01` |
| **Estado Actual:** | **ABIERTO** |
| **Detectado por:** | Sebastián (QA) |
| **Asignado a:** | Equipo Backend (Módulo 2 - Activos Biológicos) |
| **Fecha de Reporte:** | 2026-09-09 |
| **Severidad:** | **Media** (No bloqueante, pero desviación de contrato funcional) |
| **Subcaso Asociado:** | `TC-M02-210` |
| **Requisito Funcional:** | RF-46 (CU10A - Historial de eventos del activo biológico, Flujo Alternativo E-04) |
| **Entorno Detectado:** | TEST (`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`) |
| **Fecha de Resolución Esperada:** | Pendiente despliegue de fix |
| **Re-test Ejecutado por:** | Pendiente hasta fix |
| **Aprobación Final:** | Pendiente |

---

## 2. Componentes Afectados en Código Fuente

- **Esquema Pydantic (Modelo de Respuesta):**  
  [`src/biological_assets/infrastructure/schema/activo_biologico_schema.py`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/biological_assets/infrastructure/schema/activo_biologico_schema.py)  
  *Clase afectada:* `HistorialActivoResponse` (líneas 254-260).
- **Router / Controlador FastAPI:**  
  [`src/biological_assets/infrastructure/routers/activo_biologico_router.py`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/biological_assets/infrastructure/routers/activo_biologico_router.py)  
  *Función afectada:* `consultar_historial` (líneas 929-965).

---

## 3. Descripción Detallada del Defecto

El subcaso de prueba **TC-M02-210** y la especificación de caso de uso CU10A (RF-46, Flujo Alternativo E-04) establecen explícitamente como criterio de aceptación contractual:
> *"HTTP 200 - mensaje informativo 'No se encontraron eventos para el activo [id] con los filtros aplicados...'. No se retorna error."*

Al ejecutar una consulta filtrada (por rango de fechas o categoría de evento) que no arroja registros para un activo existente, el endpoint responde con código `HTTP 200 OK`, `total_registros: 0` y `registros: []`. Sin embargo, **el endpoint no retorna el campo `mensaje` exigido por el flujo E-04**. 

El esquema Pydantic `HistorialActivoResponse` no define dicho atributo, por lo que la serialización de salida nunca puede incluir el texto exigido por la especificación. La prueba **FALLA** legítimamente en la aserción de presencia y contenido del mensaje.

---

## 4. Evidencia Técnica

### 4.1. Petición HTTP Enviada
```http
GET /activos-biologicos/130/historial?categoria_evento=BAJA HTTP/1.1
Host: sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io
Authorization: Bearer <token_admin>
```

### 4.2. Payload Real Recibido (TEST)
- **Código HTTP:** `200 OK`
```json
{
  "id_activo_biologico": 130,
  "total_registros": 0,
  "pagina_actual": 1,
  "total_paginas": 0,
  "registros_por_pagina": 20,
  "registros": []
}
```

### 4.3. Payload Esperado según Contrato Funcional RF-46 (Flujo E-04)
- **Código HTTP:** `200 OK`
```json
{
  "id_activo_biologico": 130,
  "total_registros": 0,
  "pagina_actual": 1,
  "total_paginas": 0,
  "registros_por_pagina": 20,
  "registros": [],
  "mensaje": "No se encontraron eventos para el activo 130 con los filtros aplicados."
}
```

### 4.4. Detalle del Fallo de Aserción en Newman
```text
# failure detail
1. AssertionError: [TC-M02-210] Mensaje informativo presente
   expected '' to include 'no se encontraron eventos'
   at assertion:3 in test-script
   inside "TC-M02-210 / TC-M02-210 - Consultar historial con filtro sin resultados (E-04)"
```
- **Reporte HTML de Evidencia:** [reporte_TC-M02-210.html](reporte_TC-M02-210.html)

---

## 5. Impacto en el Negocio y Consumidores de la API

Los consumidores de la API (frontend, aplicaciones móviles o servicios integradores) no reciben el mensaje informativo estipulado en la especificación y deben inferirlo client-side mediante comprobaciones heurísticas sobre `total_registros === 0`. Esto genera riesgo de inconsistencias en los textos presentados a los usuarios finales y viola el contrato de respuesta documentado en el caso de prueba.

---

## 6. Propuesta de Corrección para el Equipo Backend

1. **Agregar campo `mensaje` en el schema:**  
   En `src/biological_assets/infrastructure/schema/activo_biologico_schema.py`:
   ```python
   class HistorialActivoResponse(BaseModel):
       id_activo_biologico: int
       total_registros: int
       pagina_actual: int
       total_paginas: int
       registros_por_pagina: int
       registros: list[RegistroHistorialResponse]
       mensaje: Optional[str] = None  # <-- Campo agregado
   ```

2. **Asignar mensaje informativo en Router o Caso de Uso:**  
   En `src/biological_assets/infrastructure/routers/activo_biologico_router.py`:
   ```python
       mensaje_informativo = None
       if pagina_historial.total_registros == 0 and (fecha_inicio or fecha_fin or categoria_evento):
           mensaje_informativo = f"No se encontraron eventos para el activo {id_activo} con los filtros aplicados."

       return HistorialActivoResponse(
           id_activo_biologico=id_activo,
           total_registros=pagina_historial.total_registros,
           pagina_actual=pagina_historial.pagina_actual,
           total_paginas=pagina_historial.total_paginas,
           registros_por_pagina=pagina_historial.registros_por_pagina,
           registros=[_item_to_registro_response(it) for it in pagina_historial.items],
           mensaje=mensaje_informativo,
       )
   ```

3. **Actualizar los tests unitarios del módulo:**  
   Ajustar o ampliar las pruebas unitarias en `tests/` para validar que `mensaje` se puebla en respuestas sin registros y con filtros.

4. **Notificar cuando el fix esté desplegado en TEST:**  
   Coordinar con el equipo de QA para re-ejecutar inmediatamente el subcaso TC-M02-210.

---

## 7. Criterio de Cierre del Defecto

El defecto **INC-M02-G76-01** solo se considerará cerrado cuando se satisfagan los siguientes 4 puntos:

1. El fix esté desplegado y verificado en el entorno TEST.
2. El script `retest_tc_m02_210.ps1` retorne `5/5 PASSED` y código de salida `0` (Exit code 0).
3. El reporte HTML regenerado muestre las 5 aserciones exitosas sin ningún fallo.
4. QA apruebe formalmente el cierre del defecto.
