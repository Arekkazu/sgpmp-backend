# INFORME DE RESULTADOS DE PRUEBAS DE ACEPTACIÓN
## CASO AGRUPADO: TC-M02-G28 (RF-36: Gestión Poblacional & RF-48: Transferencia Interna)

- **Fecha de Ejecución**: 2026-09-08 / 2026-09-09
- **Entorno**: TEST (`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`)
- **Base de Datos**: PostgreSQL TEST (`158.69.200.27:5448/sgpmp_test`, usuario `member_qa`)
- **Herramienta**: Newman CLI v6.2.2 + Reporter `htmlextra`
- **Veredicto Global**: **FAIL PARCIAL (1 PASS, 2 FAIL — 2 DEFECTOS DE REGLA DE NEGOCIO DETECTADOS)**

---

## 1. Resumen Ejecutivo de Resultados

| Sub-caso | Enfoque de Prueba | Resultado Esperado | Resultado Obtenido | Veredicto |
| :--- | :--- | :--- | :--- | :---: |
| **TC-M02-200** | Rechazar transferencia a infraestructura inactiva | HTTP 400 Bad Request / 422 con código de error. Lote permanece en infraestructura origen (3). | `HTTP 400 Bad Request` (`INFRAESTRUCTURA_DESTINO_INVALIDA`). Lote verificado intacto en infraestructura 3. | **PASS** |
| **TC-M02-201** | Rechazar transferencia a infraestructura de otra finca | HTTP 400 Bad Request, 403 Forbidden o 422. Rechazo por frontera territorial entre fincas. | `HTTP 201 Created`. El backend permitió transferir el lote de Finca 1 a infraestructura de Finca 2 sin validar pertenencia. | **FAIL (DEFECTO DE NEGOCIO)** |
| **TC-M02-202** | Aceptar transferencia válida y verificar recálculo de densidad | HTTP 200/201. Activo trasladado a Estanque-01 (ID 1, 2500 m²). Densidad recalculada a `0.002` ($5 / 2500$). | `HTTP 201 Created`. Activo trasladado a ID 1, pero la densidad se mantuvo estática en `0.01` ($5 / 500$, no se recalculó). | **FAIL (DEFECTO ZOOTÉCNICO)** |

---

## 2. Datos de Prueba Utilizados

### 🐟 Lote de Activo Biológico Poblacional:
- **ID Activo:** `130`
- **Especie:** `4` (*Cachama Blanca*)
- **Estado:** `1` (*ACTIVO*)
- **Cantidad Actual:** `5`
- **Infraestructura Origen Inicial:** `3` (*Alevinera-01*, Finca 1, superficie = $500\text{ m}^2$, `es_activo = True`)
- **Densidad Inicial:** $0.01\text{ ind/m}^2$ ($5 / 500\text{ m}^2$)

### 🏢 Infraestructuras Involucradas (`modulo9.infraestructuras`):
1. **Infraestructura Origen (ID 3):**
   - Nombre: *Alevinera-01*
   - Finca: `1` (*Finca Acuícola El Remanso*)
   - Superficie: $500.00\text{ m}^2$
   - Estado: `es_activo = True`
2. **Infraestructura Inactiva (ID 10):**
   - Nombre: *Invernadero Norte*
   - Finca: `1` (*Finca Acuícola El Remanso*)
   - Estado: `es_activo = False`
3. **Infraestructura Otra Finca (ID 4):**
   - Nombre: *Canal-Trucha-01*
   - Finca: `2` (*Piscícola Los Esteros*)
   - Estado: `es_activo = True`
4. **Infraestructura Válida Misma Finca (ID 1):**
   - Nombre: *Estanque-01*
   - Finca: `1` (*Finca Acuícola El Remanso*)
   - Superficie: $2500.00\text{ m}^2$
   - Estado: `es_activo = True`

### 👤 Credenciales Utilizadas:
- **Usuario Administrador:** `admin@pecuaria.co` (`id_usuario = 1`)

---

## 3. Detalle de Ejecución por Sub-caso

### 3.1. Sub-caso TC-M02-200: Rechazar transferencia a infraestructura inactiva

- **Colección Postman**: `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G28/TC-M02-200.json`
- **Reporte HTML Generado**: `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G28/RESULTADOS/reporte_TC-M02-200.html`
- **Endpoint**: `POST /activos-biologicos/130/transferencias`
- **Payload Enviado**:
  ```json
  {
    "infraestructura_origen_id": 3,
    "infraestructura_destino_id": 10,
    "fecha_transferencia": "2026-09-08",
    "motivo_transferencia": "Prueba rechazo infraestructura inactiva TC-M02-200",
    "responsable_id": 1
  }
  ```
- **Respuesta Obtenida**:
  - **Código HTTP**: `400 Bad Request`
  - **Cuerpo JSON**:
    ```json
    {
      "error_code": "INFRAESTRUCTURA_DESTINO_INVALIDA",
      "message": "La infraestructura con id 10 no existe o no está activa.",
      "field": "infraestructura_destino_id",
      "timestamp": "2026-09-09T03:39:27.500918+00:00"
    }
    ```
- **Verificación de Estado del Lote (GET /activos-biologicos/130)**:
  - `HTTP 200 OK`
  - `id_infraestructura`: `3` (permanece inalterada).
- **Aserciones Newman**:
  - `[PASS]` Checkpoint 0 - Autenticación exitosa (HTTP 200 OK)
  - `[PASS]` Código HTTP esperado: 400 Bad Request (o 422)
  - `[PASS]` Mensaje de error indica que la infraestructura no existe o no está activa
  - `[PASS]` Código HTTP esperado: 200 OK
  - `[PASS]` El lote permanece en su infraestructura original
- **Veredicto**: **PASS**.

---

### 3.2. Sub-caso TC-M02-201: Rechazar transferencia a infraestructura de otra finca

- **Colección Postman**: `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G28/TC-M02-201.json`
- **Reporte HTML Generado**: `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G28/RESULTADOS/reporte_TC-M02-201.html`
- **Endpoint**: `POST /activos-biologicos/130/transferencias`
- **Payload Enviado**:
  ```json
  {
    "infraestructura_origen_id": 3,
    "infraestructura_destino_id": 4,
    "fecha_transferencia": "2026-09-08",
    "motivo_transferencia": "Prueba rechazo infraestructura otra finca TC-M02-201",
    "responsable_id": 1
  }
  ```
- **Respuesta Obtenida**:
  - **Código HTTP**: `201 Created` ❌ *(Se esperaba `400 Bad Request`, `403 Forbidden` o `422`)*
  - **Cuerpo JSON**:
    ```json
    {
      "id_movimiento": 20,
      "id_activo_biologico": 130,
      "infraestructura_origen": "Alevinera-01",
      "infraestructura_destino": "Canal-Trucha-01",
      "fecha_transferencia": "2026-09-08T00:00:00Z",
      "motivo_transferencia": "Prueba rechazo infraestructura otra finca TC-M02-201",
      "mensaje": "Transferencia registrada exitosamente. El activo fue transferido a Canal-Trucha-01 en fecha 2026-09-08."
    }
    ```
- **Verificación de Estado del Lote (GET /activos-biologicos/130)**:
  - `HTTP 200 OK`
  - `id_infraestructura`: `4` (El lote fue indebidamente reubicado a la Finca 2).
- **Aserciones Newman**:
  - `[PASS]` Checkpoint 0 - Autenticación exitosa (HTTP 200 OK)
  - `[FAIL]` Código HTTP esperado: Rechazo por infraestructura de otra finca (400, 403 o 422): `expected [ 400, 403, 422 ] to include 201`
  - `[FAIL]` Mensaje de error indica incompatibilidad de finca: `DEFECTO: El backend permitió transferir el lote a una infraestructura de otra finca con HTTP 201`
  - `[PASS]` Código HTTP esperado: 200 OK
  - `[FAIL]` El lote permanece en su infraestructura original (3): `expected 4 to deeply equal 3`
- **Veredicto**: **FAIL (DEFECTO DE NEGOCIO DEF-RF48-01)**.
- *Nota operativa*: Para continuar con el sub-caso TC-M02-202 en el orden previsto, el lote 130 fue retornado a su infraestructura de origen `3` (*Alevinera-01*) mediante la API.

---

### 3.3. Sub-caso TC-M02-202: Aceptar transferencia válida y verificar recálculo de densidad

- **Colección Postman**: `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G28/TC-M02-202.json`
- **Reporte HTML Generado**: `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G28/RESULTADOS/reporte_TC-M02-202.html`
- **Endpoint**: `POST /activos-biologicos/130/transferencias`
- **Payload Enviado**:
  ```json
  {
    "infraestructura_origen_id": 3,
    "infraestructura_destino_id": 1,
    "fecha_transferencia": "2026-09-08",
    "motivo_transferencia": "Transferencia válida a Estanque-01 con recálculo TC-M02-202",
    "responsable_id": 1
  }
  ```
- **Respuesta Obtenida (Paso 1 - Transferencia)**:
  - **Código HTTP**: `201 Created`
  - **Cuerpo JSON**:
    ```json
    {
      "id_movimiento": 22,
      "id_activo_biologico": 130,
      "infraestructura_origen": "Alevinera-01",
      "infraestructura_destino": "Estanque-01",
      "fecha_transferencia": "2026-09-08T00:00:00Z",
      "motivo_transferencia": "Transferencia válida a Estanque-01 con recálculo TC-M02-202",
      "mensaje": "Transferencia registrada exitosamente. El activo fue transferido a Estanque-01 en fecha 2026-09-08."
    }
    ```
- **Verificación de Estado y Métricas (Paso 2 - GET /activos-biologicos/130)**:
  - `HTTP 200 OK`
  - `id_infraestructura`: `1` (*Estanque-01*) $\rightarrow$ Reubicación física exitosa.
  - `cantidad_actual`: `5`
  - `densidad`: `0.01` ❌ *(Permaneció en el valor previo $5 / 500 = 0.01$. Se esperaba recálculo automático: $5 / 2500 = 0.002$)*.
- **Aserciones Newman**:
  - `[PASS]` Checkpoint 0 - Autenticación exitosa (HTTP 200 OK)
  - `[PASS]` Código HTTP esperado: 200 OK o 201 Created (transferencia exitosa)
  - `[PASS]` La respuesta confirma el traslado a la infraestructura destino
  - `[PASS]` Código HTTP esperado: 200 OK
  - `[PASS]` El lote fue asignado a la nueva infraestructura destino (ID 1: Estanque-01)
  - `[FAIL]` La densidad del lote se recalculó automáticamente con la nueva superficie (5 / 2500 = 0.002): `expected 0.01 to be close to 0.002 +/- 0.0001`
- **Veredicto**: **FAIL (DEFECTO ZOOTÉCNICO DEF-RF48-02)**.

---

## 4. Verificación en Base de Datos PostgreSQL (`sgpmp_test`)

Se ejecutó consulta directa de solo lectura (`SELECT`) a las tablas `modulo2.activos_biologicos`, `modulo2.detalles_activos_biologicos_poblacionales`, `modulo9.infraestructuras` y `modulo2.historial_infraestructura_activo`:

```sql
SELECT 
    a.id_activo_biologico,
    a.id_infraestructura,
    i.nombre AS nombre_infraestructura,
    i.superficie AS superficie_m2,
    a.id_estado,
    p.cantidad_actual,
    p.densidad
FROM modulo2.activos_biologicos a
JOIN modulo2.detalles_activos_biologicos_poblacionales p 
    ON a.id_activo_biologico = p.id_activo_biologico
JOIN modulo9.infraestructuras i 
    ON a.id_infraestructura = i.id_infraestructura
WHERE a.id_activo_biologico = 130;
```

### Resultado en Base de Datos:
```
id_activo_biologico: 130
id_infraestructura:  1
nombre_infra:        Estanque-01
superficie_m2:       2500.00
id_estado:           1 (ACTIVO)
cantidad_actual:     5
densidad:            0.01000000000000000000  <-- VALOR OBSOLETO (NO RECALCULADO)
```

### Historial de Movimientos de Infraestructura:
```
id_historial | id_infraestructura | fecha_inicio                  | fecha_fin
-------------+--------------------+-------------------------------+------------------------------
92           | 1 (Estanque-01)    | 2026-09-09 03:40:22.838424+00 | NULL (ACTUAL)
89           | 3 (Alevinera-01)   | 2026-09-09 03:40:06.800714+00 | 2026-09-09 03:40:22.838424+00
88           | 4 (Canal-Trucha)   | 2026-09-09 03:39:39.015639+00 | 2026-09-09 03:40:06.800714+00
```
*Interpretación*: La auditoría e historial de cambios de infraestructura en `modulo2.historial_infraestructura_activo` y la actualización de `id_infraestructura` en `modulo2.activos_biologicos` funcionan a la perfección. No obstante, la tabla hija de parámetros poblacionales (`modulo2.detalles_activos_biologicos_poblacionales`) fue totalmente ignorada durante la transacción de transferencia.

---

## 5. Fichas de Defectos Identificados

### 🐛 DEF-RF48-01: Ausencia de validación de frontera de finca en transferencia interna

- **Clasificación**: Regla de Negocio / Integridad Territorial
- **Severidad**: **Alta**
- **Archivo Afectado**: `src/biological_assets/application/use_cases/gestion/registrar_transferencia_use_case.py`
- **Descripción**: El caso de uso `RegistrarTransferenciaUseCase` implementa validaciones para:
  1. Coincidencia de infraestructura origen con la actual (`INFRAESTRUCTURA_ORIGEN_INCORRECTA`).
  2. Existencia y estado activo de infraestructura destino (`INFRAESTRUCTURA_DESTINO_INVALIDA`).
  3. Origen y destino distintos (`DESTINO_IGUAL_ORIGEN`).
  4. Compatibilidad de especie (`INCOMPATIBILIDAD_ESPECIE`).
  5. Capacidad máxima (`CAPACIDAD_EXCEDIDA`).
  
  **Deficiencia**: **Nunca valida que la infraestructura de destino pertenezca a la misma finca que la infraestructura de origen**. Según el RF-48 (Transferencia Interna), el movimiento solo está permitido entre infraestructuras de la misma unidad productiva/finca. Actualmente es posible transferir un lote de la Finca 1 a la Finca 2 sin restricción.
- **Recomendación de Código**:
  ```python
  # Validar que la infraestructura destino pertenezca a la misma finca que la origen
  infra_origen = self.infra_port.obtener_activa(dto.infraestructura_origen_id)
  if infra_origen and infra_destino.id_finca != infra_origen.id_finca:
      raise BusinessRuleError(
          code='TRANSFERENCIA_ENTRE_FINCAS_NO_PERMITIDA',
          message='La transferencia interna solo permite movimientos entre infraestructuras de la misma finca.',
          field='infraestructura_destino_id',
      )
  ```

---

### 🐛 DEF-RF48-02: Omisión de recálculo de densidad poblacional tras transferencia de lote

- **Clasificación**: Regla de Negocio / Parámetro Zootécnico (RF-36 & RF-48)
- **Severidad**: **Media**
- **Archivo Afectado**: `src/biological_assets/application/use_cases/gestion/registrar_transferencia_use_case.py` (Líneas 154-193)
- **Descripción**: Durante la ejecución de la transferencia, el caso de uso actualiza `activos_biologicos.id_infraestructura` y el historial, pero **no actualiza `modulo2.detalles_activos_biologicos_poblacionales`**. Cuando un activo es poblacional (`tipo == 'POBLACIONAL'`), la densidad poblacional debe ser recalculada de forma automática en función de la superficie de la nueva infraestructura receptora:
  $$\text{densidad} = \frac{\text{cantidad\_actual}}{\text{superficie\_destino}}$$
  Al omitirse este paso, el lote queda con una densidad zootécnica irreal e inconsistente con el espacio físico disponible.
- **Recomendación de Código**:
  ```python
  # Tras actualizar id_infraestructura en activos_biologicos:
  if activo.tipo == 'POBLACIONAL' and activo.detalle_poblacional:
      if infra_destino.superficie and infra_destino.superficie > 0:
          nueva_densidad = round(Decimal(activo.detalle_poblacional.cantidad_actual) / Decimal(infra_destino.superficie), 4)
          self.db.execute(
              text(
                  'UPDATE modulo2.detalles_activos_biologicos_poblacionales '
                  'SET densidad = :nueva_densidad '
                  'WHERE id_activo_biologico = :id'
              ),
              {'id': id_activo, 'nueva_densidad': nueva_densidad},
          )
  ```

---

## 6. Conclusión y Dictamen de Calidad

1. **TC-M02-200**: **PASS**. El backend protege correctamente la asignación de infraestructuras inactivas, respondiendo con `HTTP 400 Bad Request` y `INFRAESTRUCTURA_DESTINO_INVALIDA`.
2. **TC-M02-201**: **FAIL**. Se evidenció una brecha de negocio en el control de transferencias internas, permitiendo traslados de activos entre fincas distintas.
3. **TC-M02-202**: **FAIL**. Aunque el traslado físico y el historial se registran correctamente en la base de datos, el sistema carece de la lógica de sincronización zootécnica para recalcular la densidad poblacional en función de la nueva superficie.

Ambos defectos (`DEF-RF48-01` y `DEF-RF48-02`) han sido documentados con sus causas raíces a nivel de código fuente y base de datos para su correspondiente subsanación por el equipo de desarrollo.
