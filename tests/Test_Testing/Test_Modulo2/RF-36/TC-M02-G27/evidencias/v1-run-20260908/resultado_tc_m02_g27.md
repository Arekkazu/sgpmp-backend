# INFORME DE RESULTADOS DE PRUEBAS DE SEGURIDAD (OWASP API TOP 10)
## CASO AGRUPADO: TC-M02-G27 (RF-36: Gestión Poblacional de Activos Biológicos)

- **Fecha de Ejecución**: 2026-09-08 / 2026-09-09
- **Entorno**: TEST (`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`)
- **Base de Datos**: PostgreSQL TEST (`158.69.200.27:5448/sgpmp_test`, usuario `member_qa`)
- **Herramienta**: Newman CLI v6.2.2 + Reporter `htmlextra`
- **Veredicto Global**: **FAIL PARCIAL (1 PASS, 1 FAIL — VULNERABILIDAD OWASP API1 BOLA DETECTADA)**

---

## 1. Resumen Ejecutivo de Resultados

| Sub-caso | Enfoque de Seguridad | Resultado Esperado | Resultado Obtenido | Veredicto |
| :--- | :--- | :--- | :--- | :---: |
| **TC-M02-057** | **OWASP API3: Mass Assignment** sobre `cantidad_inicial` | El backend ignora o rechaza la propiedad inyectada. `cantidad_inicial` permanece inalterada en BD y en la API. | `HTTP 400 Bad Request` en evento.<br>`GET` confirma `cantidad_inicial = 5` intacta.<br>BD confirma `cantidad_inicial = 5`. | **PASS** |
| **TC-M02-058** | **OWASP API1: BOLA** en consulta de lote de otra finca | `HTTP 403 Forbidden` o `404 Not Found`. Ningún dato del lote ajeno es expuesto al Productor. | `HTTP 200 OK`. El endpoint expone la información completa del lote ajeno (Finca 2) a un usuario sin asignación a dicha finca. | **FAIL (DEFECTO DE SEGURIDAD)** |

---

## 2. Datos de Prueba Utilizados

### 🌾 Entidades en Base de Datos:
1. **Lote Finca 1 (Control Positivo y Mass Assignment):**
   - **ID Activo:** `130`
   - **Especie:** `4` (*Cachama Blanca*)
   - **Infraestructura:** `3` (*Alevinera-01*) $\rightarrow$ Finca 1 (*Finca Acuícola El Remanso*).
   - **`cantidad_inicial`:** `5`
   - **`cantidad_actual`:** `5`

2. **Lote Finca 2 (Objetivo de Prueba BOLA):**
   - **ID Activo:** `8`
   - **Especie:** `3` (*Tilapia Roja*)
   - **Infraestructura:** `4` (*Canal-Trucha-01*) $\rightarrow$ Finca 2 (*Piscícola Los Esteros*).
   - **`cantidad_inicial`:** `8000`
   - **`cantidad_actual`:** `7650`

3. **Usuarios y Roles:**
   - **Admin:** `admin@pecuaria.co` (ID 1, Rol 1).
   - **Productor Evaluado:** `m2m.nuevo@ejemplo.com` (ID 35, Rol 2 Productor).

---

## 3. Detalle de Ejecución por Sub-caso

### 3.1. Sub-caso TC-M02-057: Mass Assignment sobre campo inmutable `cantidad_inicial`

- **Colección Postman**: `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G27/TC-M02-057.json`
- **Reporte HTML Generado**: `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G27/RESULTADOS/reporte_TC-M02-057.html`
- **Endpoint Objetivo**: `POST /activos-biologicos/130/eventos/crecimiento`
- **Payload con Intento de Mass Assignment**:
  ```json
  {
    "tipo_medicion": "PESO",
    "valor_medicion": 55.0,
    "unidad_medida": "g",
    "nuevo_peso_promedio": 55.0,
    "cantidad_medida": 5,
    "tipo_agregacion": "PROMEDIO",
    "fecha": "2026-09-09T02:00:00Z",
    "cantidad_inicial": 500
  }
  ```
- **Respuesta de la API**:
  - **Paso 1 (Inyección)**: `HTTP 400 Bad Request`
    - `error_code: "VAL_ENTRADA"`
    - El esquema DTO rechaza la presencia del campo no permitido o la inconsistencia en validación de evento.
  - **Paso 2 (Verificación GET /activos-biologicos/130)**:
    - `HTTP 200 OK`
    - `detalle_poblacional.cantidad_inicial`: `5` (inalterado, el valor inyectado `500` no fue aceptado ni propagado).
- **Aserciones Newman**:
  - `[PASS]` Checkpoint 0 - Autenticación exitosa (HTTP 200 OK)
  - `[PASS]` Respuesta del evento: Acepta ignorando campo extra (201) o rechaza por validación estricta (400/422)
  - `[PASS]` Código HTTP esperado: 200 OK al consultar activo
  - `[PASS]` Seguridad Mass Assignment: cantidad_inicial NO fue modificada por la inyección
- **Veredicto**: **PASS**.

---

### 3.2. Sub-caso TC-M02-058: BOLA en consulta de lote de otra granja

- **Colección Postman**: `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G27/TC-M02-058.json`
- **Reporte HTML Generado**: `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G27/RESULTADOS/reporte_TC-M02-058.html`
- **Usuario Autenticado**: `m2m.nuevo@ejemplo.com` (Rol Productor, sin pertenencia a Finca 2).
- **Paso 1 - Consulta a Lote Ajeno**: `GET /activos-biologicos/8` (Lote de Finca 2).
  - **Resultado Obtenido de la API**:
    - **Código HTTP**: `200 OK` ❌ *(Se esperaba `403 Forbidden` o `404 Not Found`)*
    - **Datos Expuestos**:
      ```json
      {
        "id_activo_biologico": 8,
        "id_especie": 3,
        "tipo": "POBLACIONAL",
        "identificador": null,
        "descripcion": "Lote de tilapia roja en estanque 1",
        "id_infraestructura": 4,
        "costo_adquisicion": "980000.0000",
        "atributos_dinamicos": {
          "estanque": "E1",
          "tipo_agua": "dulce",
          "cantidad_inicial": 1000,
          "soporte_documental": "factura_LOTEPEC001.pdf"
        },
        "id_estado": 5,
        "nombre_estado": "CERRADO",
        "detalle_poblacional": {
          "id_detalle": 3,
          "cantidad_inicial": 8000,
          "cantidad_actual": 7650,
          "peso_promedio": "0.480",
          "biomasa_total": "3672.000",
          "densidad": "25.000"
        }
      }
      ```
- **Aserciones Newman**:
  - `[PASS]` Checkpoint 0 - Autenticación exitosa como Productor (HTTP 200 OK)
  - `[FAIL]` Seguridad BOLA: Rechazar acceso a lote de otra finca (HTTP 403 Forbidden o 404 Not Found)
    - *expected [ 403, 404 ] to include 200*
  - `[FAIL]` No se expone información del lote ajeno
    - *VULNERABILIDAD BOLA DETECTADA: Se expusieron los datos del lote ajeno con HTTP 200*
  - `[PASS]` Control positivo: Lote accesible retorna HTTP 200 OK
- **Veredicto**: **FAIL (DEFECTO DE SEGURIDAD DETECTADO)**.

---

## 4. Auditoría y Verificación en Base de Datos (Solo Lectura)

Consulta ejecutada sobre PostgreSQL `sgpmp_test` para auditar la integridad del lote 130 tras el intento de Mass Assignment:

```sql
SELECT 
    a.id_activo_biologico, 
    d.cantidad_inicial, 
    d.cantidad_actual,
    d.peso_promedio,
    d.biomasa_total
FROM modulo2.activos_biologicos a
LEFT JOIN modulo2.detalles_activos_biologicos_poblacionales d 
    ON a.id_activo_biologico = d.id_activo_biologico
WHERE a.id_activo_biologico = 130;
```

### Resultado en BD:
```text
ID Activo: 130
Cantidad Inicial: 5
Cantidad Actual: 5
Peso Promedio: 55.0
Biomasa Total: 275.0
```

**Conclusión de BD**:
`cantidad_inicial` permaneció inmutable en `5` (el valor malicioso `500` nunca fue persistido). La base de datos mantiene total coherencia.

---

## 5. Análisis de Causa Raíz de la Vulnerabilidad BOLA (INC-SEC-M02-01)

### Descripción del Defecto:
El endpoint `GET /activos-biologicos/{id_activo}` únicamente evalúa permisos RBAC a nivel funcional (`recurso=29 (activo_biologico)`, `accion=2 (LEER)`). Al comprobar que el rol `Productor` cuenta con dicho permiso, el endpoint procede a retornar el activo solicitado **sin verificar si la infraestructura del activo pertenece a una finca asignada al usuario**.

### Evidencia en el Código Fuente:
En `src/biological_assets/infrastructure/routers/activo_biologico_router.py`:
```python
@router.get('/{id_activo}', response_model=ActivoBiologicoResponse, dependencies=[Depends(require_permission(_RECURSO, 2))])
def consultar_activo(
    id_activo: int,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> ActivoBiologicoResponse:
    ...
```
Aunque en ramas recientes se introdujo la resolución `ids_fincas_permitidas=_ids_fincas_alcance(db, usuario_actual)`, en el backend desplegado en el entorno **TEST**:
1. O bien el filtro no se encuentra desplegado en la versión activa del contenedor de TEST.
2. O el repositorio `SqlAlchemyActivoBiologicoRepository.obtener_por_id` no está restringiendo por la finca de la infraestructura asociada.

### Impacto de Seguridad:
- **Clasificación**: **Alta / Crítica (OWASP API1:2023 - Broken Object Level Authorization)**.
- **Consecuencia**: Un productor puede enumerar secuencialmente los IDs de activos biológicos (`1, 2, 3...`) y extraer inventarios, costos de adquisición de alevines, facturas de compra (`soporte_documental`), y densidades de producción de fincas competidoras.

---

## 6. Recomendaciones de Remediación

1. **Desplegar y Verificar RF-25 (Alcance por Finca):** Asegurar que la imagen del contenedor del backend TEST incorpore el adaptador `AlcanceFincaAdapter` sobre todos los endpoints de consulta de `activo_biologico_router.py`.
2. **Aplicar Rechazo Estricto (HTTP 403 / 404):** En `ConsultarActivoUseCase`, si el activo biológico pertenece a una infraestructura cuya finca no está en `ids_fincas_permitidas`, se debe lanzar `AuthorizationError(code="ACCESO_DENEGADO", message="No tiene autorización para consultar activos de esta finca")` (HTTP 403) o `NotFoundError` (HTTP 404) para evitar la fuga de información.
