# DIAGNÓSTICO PREVIO — TC-M06-G97

**Caso:** Validación de la depreciación lineal según la vida útil configurada del activo  
**Escenarios:** TC-M06-08 (vida útil ausente → HTTP 422) · TC-M06-09 (12.000.000 / 6 años = 2.000.000 anual)  
**RF / CU:** RF-88 · M09 · CU07  
**Fecha:** 2026-11-13  
**Alcance:** solo lectura (código `origin/test`, OpenAPI TEST, documentación del lote #1036)  
**Sin escrituras:** sin POST/PUT/PATCH/DELETE · sin commit/push · sin alterar activos/periodos  

---

## Dictamen final

### **BLOQUEADO**

No existe en el backend desplegado (ni en el contrato OpenAPI de TEST) un **endpoint específico de cálculo de depreciación** que permita:

1. rechazar con **HTTP 422** el cálculo cuando falta la vida útil (TC-M06-08), ni  
2. devolver/verificar en una sola operación la **depreciación lineal anual** de $2.000.000 para costo $12.000.000 y vida útil 6 años (TC-M06-09).

El cierre del issue **#969** / integración del **PR #1036** **no** añadió esa capacidad. La propia nota del lote declara **#969 no resuelto en código**.

---

## 1. Estado de disponibilidad del endpoint RF-88 (cálculo de depreciación)

| Pregunta | Hallazgo |
|---|---|
| ¿Hay ruta cuyo path contenga `depreci`? | **No** (OpenAPI TEST 200, inventario exhaustivo) |
| ¿Algún summary/description OpenAPI menciona depreciación? | **0** coincidencias |
| ¿Existe POST/GET de “calcular depreciación”? | **No** |
| ¿Dónde se calcula hoy? | Dominio `valor_por_costo` + efecto colateral de `POST /finanzas/periodos/{id}/cierre` (`_depreciar`) |

**Conclusión:** la ficha exige un endpoint de cálculo/validación de depreciación; ese contrato **sigue pendiente**. No se inventaron ni se sustituyeron rutas.

---

## 2. Evidencia de revisión del PR #1036

**Merge en integración:** `375883d3` — *Merge PR #1036 (fix/lote-qa-2026-11-09-luis)*  

**Documento del lote:** `anotaciones/lote_qa_2026_11_09.md` (`e0c86e27`):

> **#969 (INC-M06-282-G69, endpoints no disponibles).** El issue no dice qué RF ni qué rutas faltan para los dos escenarios de G69. Hay que pedirle a QA la lista de solicitudes que intentó ejecutar.

| Aspecto | En #1036 |
|---|---|
| Issues RF-88 corregidos | **#968** (alerta `VALOR_LIBROS_AJUSTADO_A_CERO`) — **no** #969 |
| #969 | Listado bajo **«No resueltas en código»** |
| Migración RF-88 del lote | `c6e8a0b2d453` (solo tipo de evento de auditoría de valor en libros) |
| Archivos RF-88 tocados | `nic41.py` (+`valor_libros_calculado`), deterioro, cierre (alerta), auditoría, test integración G68-07 |

**Nota de renumeración:** el bloqueo original se registró como **G69** (TC-M06-08/09); en la reorganización de carpetas pasó a **TC-M06-G97**. Misma descripción funcional; carpeta actual: `RF-88/TC-M06-G97/` (solo `.gitkeep` + este diagnóstico).

---

## 3. Rutas identificadas (relacionadas, no equivalentes al AC)

Consulta OpenAPI TEST `GET https://api.inmero.co/api-sgpmp-test/openapi.json` → **200**.

| Método y ruta | Rol real | ¿Cubre G97? |
|---|---|---|
| `GET /finanzas/activos/{id}` | Historial financiero / valor en libros ya persistido | **No** calcula depreciación bajo demanda |
| `GET /activos-biologicos/{id}` | Ficha M02 del activo | Apoyo; **no** calcula depreciación RF-88 |
| `GET /finanzas/activos/{id}/simulacion` | Simula **valor razonable** RF-84 | **No** es depreciación |
| `PUT /finanzas/configuracion/especies/{id_especie}` | Guarda clasificación, categoría y `vida_util_meses` | Configura vida útil; **no** calcula |
| `GET /finanzas/configuracion` | Lee parámetros de especies (incl. vida útil) | Lectura de config |
| `GET /finanzas/reconocimientos/propuestas/{id}` | Propuesta con posibles `bloqueos` | Puede reportar `VIDA_UTIL_NO_CONFIGURADA` al modelo de costo; **no** es “calcular depreciación” ni garantiza HTTP 422 del AC-08 |
| `POST /finanzas/reconocimientos/{id}` | Confirma reconocimiento | Escritura; no es el cálculo anual del AC-09 |
| `POST /finanzas/periodos/{id}/cierre` | Cierra periodo y **deprecia** activos a costo | Escritura masiva; no recibe costo/vida del escenario; no responde 422 por vida útil ausente |

Ninguna de estas rutas es el endpoint específico pendiente que la ficha asocia a RF-88 para G97.

---

## 4. Validaciones de vida útil

### Dónde se configura y almacena

- **Por especie (M06):** `modulo6.parametros_contables_especies.vida_util_meses` vía `PUT /finanzas/configuracion/especies/{id_especie}` (`GuardarParametroEspecieUseCase`).  
- **DTO:** `ParametroEspecieDTO.vida_util_meses` es **opcional** (`gt=0`, `le=1200`); required solo `clasificacion`.  
- Al reconocer por costo, la vida útil se copia a la valoración (`valoraciones_por_costos.vida_util_meses`).  
- Cambio posterior de vida útil: aplica a depreciaciones **siguientes**, no recalcula las ya registradas (comentario RF-88 R3 en el use case).

### Escenario “vida útil ausente” (TC-M06-08)

| Mecanismo | Comportamiento | ¿HTTP 422 del AC? |
|---|---|---|
| Propuesta de reconocimiento → modelo de costo | `bloquear("VIDA_UTIL_NO_CONFIGURADA", …)` si no hay `vida_util_meses` | Es un **bloqueo de propuesta** (lectura GET); no es un endpoint de cálculo de depreciación con 422 documentado para ese caso |
| Cierre `_depreciar` | Usa `costo.vida_util_meses or 1` | **No rechaza**: si falta, asume **1 mes** y deprecia |
| Endpoint dedicado “calcular depreciación” | **No existe** | Imposible cumplir el AC-08 tal como está escrito |

**Conclusión 08:** la validación de vida útil obligatoria existe para **entrar al modelo de costo en reconocimiento**, no como rechazo 422 de un cálculo de depreciación. El cierre **no** implementa el 422 esperado.

---

## 5. Implementación del cálculo lineal

### Dominio (sí implementado)

```text
valor_por_costo(costo, vida_util_meses, meses, deterioro)
depreciacion = min(costo, costo × meses / vida_util_meses)   # q4
```

- Método: línea recta **por meses**, no un servicio “depreciación anual” expuesto por API.  
- Tope: no supera el costo.  
- Usado por el cierre (`_depreciar`) y reportes (revelaciones: método «Línea recta»).

### Relación con TC-M06-09 ($12.000.000 / 6 años = $2.000.000)

| Expectativa de la ficha | Comportamiento real |
|---|---|
| Depreciación **anual** 2.000.000 | El sistema acumula por **meses** de vida útil |
| Vida útil “6 años” | El parámetro es `vida_util_meses` → equivaldría a **72** meses |
| Un GET/POST de cálculo que devuelva 2.000.000 | **No existe** |
| Verificación vía cierre | Haría falta un activo a costo 12M, vida 72, y **12 meses/cierres** para acercarse a 2M de depreciación del año (y el cierre escribe sobre todo el NIT) |

Incluso con dominio correcto, **no hay forma API de solo lectura** de ejecutar el escenario 09 tal como está formulado.

---

## 6. Disponibilidad en TEST

| Chequeo | Resultado |
|---|---|
| OpenAPI TEST | **200** · sin rutas de depreciación |
| Endpoint de cálculo RF-88 en TEST | **Ausente** |
| Lectura de config/activos | Posible vía GET (no ejercida con autenticación en esta fase para no alterar sesiones) |
| Escritura / cierre / deterioro | **No ejecutados** (restricción) |

El cierre del #969 **no** implica disponibilidad del endpoint en TEST: el lote documentó que #969 no se resolvió.

---

## 7. Dependencias para preparar los dos escenarios

### TC-M06-08 (si existiera el endpoint)

- Activo/especie **sin** `vida_util_meses` (o valoración sin vida útil).  
- Hoy: preparar eso implicaría **no** poder confirmar reconocimiento por costo, o manipular datos; además el “cálculo” no tiene ruta.  
- **Detenerse:** no hay operación autorizada de solo lectura que demuestre el 422 del AC.

### TC-M06-09

- Especie con `vida_util_meses = 72` (6 años) vía PUT config (**escritura**, afecta toda la especie).  
- Activo con costo depreciable 12.000.000, reconocimiento `VALORACION_POR_COSTO`.  
- Verificación del monto anual: o bien endpoint de cálculo (inexistente), o múltiples cierres (**escritura**, impacto amplio).  

**Dependencia bloqueante común:** falta el contrato API de cálculo/consulta puntual de depreciación alineado a los AC. Hasta que Desarrollo lo exponga (o Análisis redefina los AC sobre cierre/propuesta), **no** se pueden ejecutar 08/09 sin sustituir el objeto de prueba.

---

## 8. Diferencias: implementado vs exigido por la ficha

| Exigencia G97 | Estado actual |
|---|---|
| Endpoint RF-88 de depreciación | **No existe** |
| 08 → HTTP 422 si falta vida útil al calcular | Solo bloqueo en propuesta de costo; cierre usa `or 1` |
| 09 → resultado anual 2.000.000 verificable por API | Dominio mensual; sin endpoint de resultado anual |
| Apoyo `GET /activos-biologicos/{id}` | Existe; no calcula depreciación |
| #969 cerrado vía #1036 | **#969 explícitamente no resuelto en código** del lote |
| Carpeta G97 con colección/ficha | Solo `.gitkeep` (+ este diagnóstico) |

---

## 9. Relación hallazgo ↔ criterios de aceptación

| Criterio | Componente | ¿Demostrable por API hoy? |
|---|---|---|
| 08 Rechazo por vida útil ausente (422) | Endpoint de cálculo (pendiente) | **No** |
| 09 Depreciación lineal anual 2.000.000 | Endpoint de cálculo o consulta (pendiente); dominio sí | **No** por API; dominio solo en unidad/integración |
| Configuración de vida útil (M09/M06) | `PUT .../configuracion/especies/{id}` | Sí configurar (escritura); no cumple el AC de cálculo |

---

## Evidencias concretas

1. OpenAPI TEST: HTTP 200; **0** paths `*depreci*`; **0** summaries con “depreci”.  
2. `anotaciones/lote_qa_2026_11_09.md`: **#969 no resuelto**.  
3. Código `origin/test`: `valor_por_costo` (línea recta mensual); `_depreciar` con `vida_util_meses or 1`; `VIDA_UTIL_NO_CONFIGURADA` en propuesta de costo.  
4. Antecedente QA (G69→G97): catálogo y evaluación previa ya concluyeron ausencia de endpoint; reevaluación post-#1036 **confirma** que no se añadió.

---

## Próximo paso (requiere autorización)

No ejecutar escenarios 08/09. Opciones a escalar:

1. **Desarrollo:** exponer operación RF-88 de cálculo/validación de depreciación (con 422 si falta vida útil y respuesta con monto lineal).  
2. **Análisis:** redefinir AC de G97 sobre flujos reales (propuesta + cierre), aceptando que no hay cálculo anual en un solo request.  
3. Tras (1) o (2), nueva evaluación de disponibilidad y autorización de ejecución funcional.

**Estado del caso permanece BLOQUEADO** hasta disponer de ruta o criterios alineados. No se marca APROBADO ni se ejecutan pruebas funcionales en esta etapa.
