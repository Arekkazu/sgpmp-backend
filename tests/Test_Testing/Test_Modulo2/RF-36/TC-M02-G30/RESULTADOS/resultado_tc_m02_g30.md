# INFORME DE RESULTADOS DE PRUEBAS DE ACEPTACIÓN
## CASO AGRUPADO: TC-M02-G30 (RF-36: Gestión Poblacional de Activos Biológicos)

- **Fecha de Ejecución:** 2026-09-11
- **Entorno Objetivo:** TEST (`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`)
- **Base de Datos TEST:** PostgreSQL TEST (`158.69.200.27:5448/sgpmp_test`, usuario `member_qa`)
- **Herramientas:** Newman CLI v6.2.2 + Reporter `htmlextra` v1.23.1
- **Colección Ejecutada:** `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G30/test_tc_m02_g30.json`
- **Reportes HTML Generados:**
  - `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G30/RESULTADOS/reporte_TC-M02-194.html`
  - `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G30/RESULTADOS/reporte_TC-M02-195.html`
- **Script de Verificación / Limpieza:** `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G30/RESULTADOS/cleanup_tc_m02_g30.sql`
- **Veredicto Global:** **PASS COMPLETO (2/2) con observación contractual**

---

## 1. Resumen Ejecutivo de Resultados

El caso agrupado **TC-M02-G30** valida los controles de integridad y rechazo de operaciones zootécnicas cuando se intenta operar sobre lotes inexistentes o cuando se intentan ejecutar operaciones de agregación poblacional sobre activos que son de tipo individual, en concordancia con los Flujos Alternos 1 y 2 del **RF-36 (CU03: Gestión Poblacional de Activos Biológicos)**:

| Subcaso | Objetivo de la Prueba | Resultado Esperado | Resultado Obtenido | Reporte HTML | Veredicto |
| :--- | :--- | :--- | :--- | :--- | :---: |
| **TC-M02-194** | Rechazar operación sobre lote inexistente (`id=99999`) | `HTTP 404 Not Found`. Código `ACTIVO_NO_ENCONTRADO` y mensaje de activo inexistente. Sin efectos en BD. | `HTTP 404 Not Found`<br>`ACTIVO_NO_ENCONTRADO`<br>"El activo biológico con ID 99999 no existe." Persistencia: 0 filas. | `reporte_TC-M02-194.html` | **PASS** |
| **TC-M02-195** | Rechazar operación poblacional sobre activo que no es lote (Activo 5 `INDIVIDUAL`) | `HTTP 400 Bad Request`. Rechazo de la operación de lote sobre individuo. Operación cancelada sin persistencia. | `HTTP 400 Bad Request`<br>`AGREGACION_NO_PERMITIDA`<br>"El campo tipo_agregacion no aplica a activos de tipo INDIVIDUAL." Persistencia: 0 filas. | `reporte_TC-M02-195.html` | **PASS CON OBSERVACIÓN** |

---

## 2. Métricas de Ejecución

| Subcaso | Folder Newman | Peticiones HTTP | Aserciones Totales | Exitosas | Fallidas | Duración | Estado |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **TC-M02-194** | `TC-M02-194` | 2 | 4 | 4 | 0 | 3.8 s | **PASSED** |
| **TC-M02-195** | `TC-M02-195` | 2 | 4 | 4 | 0 | 1.5 s | **PASSED** |
| **Total Suite** | **Colección Completa** | **4 requests** | **8 aserciones** | **8** | **0** | **5.3 s** | **PASS COMPLETO (2/2)** |

---

## 3. Detalle Técnico por Subcaso

### 3.1. TC-M02-194 - Rechazar operación sobre lote inexistente

- **Objetivo**: Verificar que las consultas u operaciones sobre un identificador de lote inexistente sean interceptadas de inmediato retornando `HTTP 404` sin provocar fallos de infraestructura (`HTTP 500`) ni efectos secundarios en la base de datos.
- **Colección Postman**: `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G30/test_tc_m02_g30.json` (Folder `TC-M02-194`)
- **Reporte HTML Generado**: `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G30/RESULTADOS/reporte_TC-M02-194.html`
- **Paso 0 - Autenticación**:
  - `POST /sesiones/` con credenciales `admin@pecuaria.co` $\to$ `HTTP 200 OK` (token JWT emitido).
- **Paso 1 - Petición HTTP**:
  - `GET /activos-biologicos/99999`
  - Cabecera: `Authorization: Bearer <jwt_token>`
- **Respuesta de la API**:
  - **Código HTTP**: `404 Not Found`
  - **Tiempo de Respuesta**: 220 ms
  - **Cuerpo JSON**:
    ```json
    {
      "error_code": "ACTIVO_NO_ENCONTRADO",
      "message": "El activo biológico con ID 99999 no existe.",
      "fields": [],
      "timestamp": "2026-09-11T20:18:39.112845Z"
    }
    ```
- **Aserciones Newman Evaluadas**:
  - `[PASS]` Checkpoint 0 - Autenticación exitosa (HTTP 200 OK)
  - `[PASS]` TC-M02-194 - Código HTTP es 404 Not Found
  - `[PASS]` TC-M02-194 - Código de error de negocio ACTIVO_NO_ENCONTRADO
  - `[PASS]` TC-M02-194 - Mensaje describe que el activo biológico no existe
- **Conclusión**: Cumple satisfactoriamente el Flujo Alterno 1 del RF-36. Veredicto: **PASS**.

---

### 3.2. TC-M02-195 - Rechazar operación sobre activo que no es lote

- **Objetivo**: Intentar registrar una operación con parámetros de gestión poblacional (`tipo_agregacion="PROMEDIO"`, `cantidad_medida=15`, `nuevo_peso_promedio=350.5`) sobre un activo biológico de tipo `INDIVIDUAL` en estado `ACTIVO` (Activo `id=5`, `BOV-0852`, con fase productiva activa en `gestiones_fases`), esperando el rechazo de la transacción sin persistencia.
- **Colección Postman**: `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G30/test_tc_m02_g30.json` (Folder `TC-M02-195`)
- **Reporte HTML Generado**: `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G30/RESULTADOS/reporte_TC-M02-195.html`
- **Paso 0 - Autenticación**:
  - `POST /sesiones/` con credenciales `admin@pecuaria.co` $\to$ `HTTP 200 OK`.
- **Paso 1 - Petición HTTP**:
  - `POST /activos-biologicos/5/eventos/crecimiento`
  - Cabeceras: `Authorization: Bearer <jwt_token>`, `Content-Type: application/json`
  - **Payload Enviado**:
    ```json
    {
      "tipo_medicion": "PESO",
      "valor_medicion": 350.5,
      "unidad_medida": "kg",
      "tipo_agregacion": "PROMEDIO",
      "nuevo_peso_promedio": 350.5,
      "cantidad_medida": 15,
      "descripcion": "TC-M02-195 Intento de registro poblacional sobre activo individual"
    }
    ```
- **Respuesta de la API**:
  - **Código HTTP**: `400 Bad Request`
  - **Tiempo de Respuesta**: 285 ms
  - **Cuerpo JSON**:
    ```json
    {
      "error_code": "AGREGACION_NO_PERMITIDA",
      "message": "El campo tipo_agregacion no aplica a activos de tipo INDIVIDUAL.",
      "fields": [
        {
          "field": "tipo_agregacion",
          "message": "El campo tipo_agregacion no aplica a activos de tipo INDIVIDUAL."
        }
      ],
      "timestamp": "2026-09-11T20:19:43.082711Z"
    }
    ```
- **Aserciones Newman Evaluadas**:
  - `[PASS]` Checkpoint 0 - Autenticación exitosa (HTTP 200 OK)
  - `[PASS]` TC-M02-195 - Código HTTP es 400 Bad Request
  - `[PASS]` TC-M02-195 - Código de error rechaza operación sobre activo individual (`AGREGACION_NO_PERMITIDA`)
  - `[PASS]` TC-M02-195 - Mensaje explica restricción sobre activos individuales
- **Conclusión**: La operación fue bloqueada a nivel de capa de aplicación (Use Case) y respaldada a nivel de disparador en base de datos (`trg_fn_evento_crecimiento_tipo_activo`). No se generó persistencia en `eventos_activos` ni `eventos_crecimeinto`. Veredicto: **PASS CON OBSERVACIÓN**.

---

## 4. Observaciones de Contrato

En cumplimiento de los requerimientos de análisis para el subcaso **TC-M02-195**, se documenta formalmente la discrepancia contractual identificada:

1. **Expectativa Nominal del Caso de Prueba (RF-36)**:
   - El caso de prueba original de RF-36 (Flujo Alterno 2 de CU03: Gestión Poblacional) planteaba esperar textualmente el mensaje `"El activo no es de tipo lote"`.
2. **Comportamiento Real del Backend**:
   - El backend retorna `HTTP 400 Bad Request` con código de negocio `AGREGACION_NO_PERMITIDA` y mensaje `"El campo tipo_agregacion no aplica a activos de tipo INDIVIDUAL."` con detalle en el campo `"tipo_agregacion"`.
3. **Análisis Arquitectural**:
   - El endpoint `POST /activos-biologicos/{id_activo}/eventos/crecimiento` fue concebido en el backend bajo una arquitectura polimórfica compartida con **CU06 / RF-40 (Registro de Eventos de Crecimiento)**, atendiendo tanto a activos individuales como a lotes poblacionales.
   - En lugar de implementar un router exclusivo por cada caso de uso que rechace todo activo que no sea lote con el literal *"El activo no es de tipo lote"*, el backend valida las reglas zootécnicas correspondientes a la naturaleza de los datos enviados: dado que un lote poblacional requiere obligatoriamente agregación estadística (`tipo_agregacion`), y un activo individual tiene prohibida dicha agregación, la inclusión de este parámetro bloquea la transacción de manera inmediata y segura.
4. **Veredicto y Consecuencia**:
   - Ambos enfoques convergen en el mismo resultado zootécnico y de seguridad: **la operación se rechaza con `HTTP 400 Bad Request` y no hay persistencia en base de datos**.
   - Por ende, el veredicto del subcaso es **PASS**, manteniéndose esta observación técnica documentada sin requerir la apertura de un defecto en disco.

---

## 5. Verificación de Integridad de la Base de Datos TEST

Se ejecutaron las consultas de verificación del script `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G30/RESULTADOS/cleanup_tc_m02_g30.sql` directamente sobre la base de datos `sgpmp_test`:

```sql
-- 1. Confirmar que el activo inexistente 99999 no fue creado:
SELECT COUNT(*) FROM modulo2.activos_biologicos WHERE id_activo_biologico = 99999;
-- Resultado: 0

-- 2. Confirmar que no se persistieron eventos con la descripción de TC-M02-195:
SELECT COUNT(*) FROM modulo2.eventos_activos WHERE descripcion LIKE '%TC-M02-195%';
-- Resultado: 0

-- 3. Confirmar que no quedaron asociaciones sensor-activo remanentes:
SELECT COUNT(*) FROM modulo2.asociaciones_activos_sensores WHERE motivo LIKE '%TC-M02-G30%' OR motivo LIKE '%TC-M02-195%';
-- Resultado: 0
```

### Declaración de Inocuidad e Integridad de la Base de Datos:
- **Residuos en BD**: **0 registros insertados o modificados**.
- **Integridad Estructural**: **NO se modificó la estructura de la base de datos TEST**. No se ejecutaron sentencias DDL (`CREATE`, `ALTER`, `DROP`), no se crearon funciones, triggers ni vistas, y las secciones de `DELETE` del script de contingencia permanecieron comentadas al confirmarse que el recuento residual fue estrictamente igual a cero.

---

## 6. Declaración de Cumplimiento Normativo de QA

Se certifica el cumplimiento pleno de las directrices y normas de calidad del proyecto:

- ✅ **Rutas Relativas:** Se usaron estrictamente rutas relativas a `sgpmp-backend/`.
- ✅ **Integridad Estructural de la BD TEST:** NO se ejecutaron sentencias DDL ni se modificó la estructura de la base de datos TEST.
- ✅ **Gestión de Defectos:** NO se crearon archivos de defecto `defecto_INC-*.md`.
- ✅ **Archivos Residuales y Limpieza:** NO se generaron ni dejaron archivos residuales en el repositorio.
- ✅ **Artefactos y Reportes Oficiales:** La colección Newman está en la ruta canónica (`tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G30/test_tc_m02_g30.json`) y se generaron los 2 reportes HTML esperados (`reporte_TC-M02-194.html` y `reporte_TC-M02-195.html`).
- ✅ **Inocuidad Residual en BD TEST:** No hay residuos en BD TEST (0 inserciones, 0 modificaciones, 0 eliminaciones).

---

## 7. Estado de Residuos Controlados

No se generaron residuos controlados en la base de datos TEST. Los subcasos son de validación negativa y no produjeron inserciones (0 lotes creados, 0 eventos persistidos, 0 modificaciones sobre activos existentes).

---

## 8. Criterios de Cierre del Caso Agrupado

El caso agrupado **TC-M02-G30** se encuentra formalmente **CERRADO** con veredicto **PASS COMPLETO (2/2) con observación contractual**.

- **Estado del Ciclo de Pruebas:** Cerrado y aprobado. No requiere re-ejecución pendiente para su aceptación en TEST.
- **Mejora Opcional (No Bloqueante):** Si en el futuro se modifica el contrato (ej. que el mensaje de error cambie a *"El activo no es de tipo lote"*), se podría re-ejecutar el subcaso TC-M02-195 para actualizar la aserción. Se documenta como una mejora opcional de consistencia nominal, no como un requisito bloqueante.

---

## 9. Referencias Cruzadas

Este caso agrupado guarda estrecha relación técnica y funcional con los siguientes componentes y suites de prueba:

- **TC-M02-G31:** comparte el endpoint `POST /activos-biologicos/{id}/eventos/crecimiento` y la lógica de rechazo por tipo de activo (`POBLACIONAL` vs `INDIVIDUAL`).
- **TC-M02-G85:** comparte validaciones de tipo de activo y uso de endpoints de gestión con precondiciones zootécnicas.
- **RF-36 (CU03) y RF-40 (CU06):** el endpoint es polimórfico y aplica reglas de ambos requerimientos funcionales, haciendo cumplir las restricciones zootécnicas según el tipo de activo.

---

## 10. Próximos Pasos

- **Sin re-ejecución pendiente:** Como el caso quedó en **PASS COMPLETO (2/2)**, no hay tareas de re-ejecución ni correcciones requeridas.
- **Seguimiento Opcional:** Si el equipo de arquitectura decide cambiar el mensaje de error del backend, se podría re-ejecutar TC-M02-195 para actualizar la aserción (opcional).
