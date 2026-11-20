# Documento de entrega — Módulo 6 (Valoración financiera de activos biológicos) al equipo de Despliegue — v1.0

| Campo | Valor |
|---|---|
| Módulo | M06 — Valoración financiera (`src/financial_valuation/`) |
| Alcance | RF-82 a RF-94 y RF-COT (14 requisitos) |
| Fecha de corte | 2026-11-16 |
| Fuente | `informe_consolidado_pruebas_M06.md` (v1.0, 2026-11-16) |
| Ambiente de prueba | Backend TEST (`https://api.inmero.co/back-sigab-test`) |
| Emite | Equipo QA |
| Destino | Equipo de Despliegue |

---

## 1. Resumen

| Indicador | Cantidad | % |
|---|---:|---:|
| Casos | 119 | 100 % |
| Aprobados | **104** | **87.4 %** |
| Rechazados | 15 | 12.6 % |
| Pendientes | 0 | 0.0 % |

## 2. Verificación de criterios de cierre de módulo

| # | Criterio | Umbral | Resultado | Cumple |
|---|---|---|---|:---:|
| 1 | Casos con veredicto Aprobado | ≥ 85 % | **104/119 = 87.4 %** | ✅ |
| 2 | RF con al menos un caso ejecutado | 100 % | **14/14** | ✅ |
| 3 | Informe consolidado con la plantilla completa | Completo | `informe_consolidado_pruebas_M06.md` redactado (pendiente de firmas) | ✅ (firmas pendientes) |

**El módulo cumple los tres criterios de cierre evaluados** (umbral de aprobación, cobertura de RF e informe consolidado). Queda pendiente la firma de la entrega. Los 15 casos no aprobados se entregan a Desarrollo (sección 3); su detalle completo está en el informe consolidado.

## 3. Casos rechazados y pendientes

| TC | RF | Resultado | Estado | Motivo |
|---|---|---:|---|---|
| G014 | RF-83 | 10/11 | Rechazado | Un activo no elegible (PENDIENTE_RECONOCIMIENTO) excluido de la medición no deja registro de auditoría `MEDICION_EXCLUIDA` con su motivo |
| G015 | RF-83 | 7/10 | Rechazado | No se logra el escenario «períodos distintos»: el activo queda con mediciones en un solo período tras el cierre del período 1 |
| G024 | RF-85 | 3/8 | Rechazado | Tras la cosecha total el activo no queda en 0,0000 ni pasa a COSECHADO_COMPLETAMENTE / baja: queda ACTIVO con la medición anterior |
| G027 | RF-85 | 13/14 | Rechazado | Con precio manual justificado registrado, la cosecha pendiente no se reconoce (la cola de eventos responde SIN_EFECTO) |
| G030 | RF-85 | 8/9 | Rechazado | El valor del activo queda negativo: las reducciones acumuladas (20 680 000) superan el valor inicial (18 800 000) |
| G044 | RF-87 | 2/3 | Rechazado | Períodos cerrados responden 404 en lugar de informar su inmutabilidad; falla el escenario de cierre concurrente (TC-M06-030) |
| G062 | RF-92 | 33/34 | Rechazado | Una petición termina por `ESOCKETTIMEDOUT`; sin incidencia registrada, por confirmar si es de la prueba o del servicio |
| G063 | RF-92 | 16/17 | Rechazado | Para el activo QA-M06-COSTO-01 el valor «No determinable» se repite entre períodos cuando se esperaba una variación; sin incidencia registrada, por confirmar |
| G071 | RF-93 | 9/13 | Rechazado | Estado de resultados: una baja por venta no contribuye a ningún componente de INGRESOS (se acumula como gasto en `bajas_activos`) y los componentes de ingresos reales no coinciden con los de la ficha |
| G074 | RF-93 | 0/5 | Rechazado | Conciliación del estado de resultados: el error 422 `ESTADO_RESULTADOS_NO_CONCILIA`, el aviso al Contador y el registro `ERROR_CONCILIACION` no están desplegados |
| G080 | RF-93 | 5/7 | Rechazado | Ante un fallo del cálculo no se registra en auditoría y el cálculo combina todas las fuentes sin identificar cuál falló |
| G093 | RF-94 | 6/11 | Rechazado | Consulta de eventos sin filtros implícitos por rol, y `monto_afectado` se devuelve sin formato de moneda (CA-13) |
| G094 | RF-94 | 2/9 | Rechazado | El repositorio solo recibe eventos con `modulo_origen` fijo en «M06» y no existe el endpoint centralizado `GET /api/v1/audit/events` |
| G109 | RF-89 | 3/6 | Rechazado | Los avisos al Contador por vencimiento de precio (30, 15 y 7 días) no se generan: 0 avisos, se esperaba 1 en cada plazo |
| G117 | RF-COT | 1/3 | Rechazado | Cotización con valor propuesto ≤ 0: el backend responde 400 `VAL_ENTRADA` en lugar de 422 `VALOR_COTIZACION_INVALIDO` |

### Casos bloqueados y dependencias

- **RF-93 (G074, G080):** los mecanismos que esperan los casos (error 422 `ESTADO_RESULTADOS_NO_CONCILIA`, aviso al Contador con registro `ERROR_CONCILIACION` y registro en auditoría del fallo de cada fuente del cálculo) llegan con un cambio (PR #1121) que aún no está desplegado en TEST. Ambos casos deben reejecutarse tras el despliegue.
- **RF-85 (G024, G027, G030):** la corrección anunciada para el cierre de la cosecha total no está efectiva en TEST: el rerun del 2026-11-13 sigue fallando. Verificar el despliegue antes de reejecutar.
- **RF-89 (G109):** los avisos diarios al Contador por vencimiento de precios no se generan. El caso G104 se aprobó con alcance delimitado y deja pendiente esa misma validación (CA-8 / FA-5) por falta de evidencia.
- **G062 y G063 (RF-92)** no tienen incidencia registrada: hay que confirmar si el fallo es del servicio o de la prueba (timeout de la petición; comparación de «No determinable» entre períodos).
- No hay casos pendientes.

### Casos aprobados con alcance delimitado

Tres casos de RF-89 quedaron aprobados por decisión de QA con un alcance menor al plan original; el manual de usuario debe reflejarlo:

| TC | RF | Alcance de la aprobación |
|---|---|---|
| G102 | RF-89 | Aprobados TC-M06-16, 17 y 18 (HTTP 201, precio aplicado, históricos en SUPERADO, auditoría registrada). Los subcasos TC-M06-19 a 21 y el rechazo por justificación corta no se probarán. Observación: la especificación pide HTTP 400 para justificación corta y el backend responde 422 |
| G104 | RF-89 | Aprobados TC-M06-25, 26 y 29 (alcance delimitado). Queda pendiente la validación complementaria del aviso diario al Contador (CA-8 / FA-5), sin evidencia |
| G107 | RF-89 | Verificación de solo lectura de los precios y las rutas publicadas. La recepción y confirmación de precios externos aún no está desarrollada, por lo que no se pudo ejecutar de extremo a extremo; se aprueba por decisión de QA y se retoma cuando exista |

## 4. Estado por requisito (insumo para el manual de usuario)

| RF | Función | Casos | Aprobados | Rechazados | Pendientes | Observación para el manual |
|---|---|---:|---:|---:|---:|---|
| RF-82 | Reconocimiento inicial del activo biológico | 9 | 9 | 0 | 0 | Documentar completo |
| RF-83 | Medición posterior del valor razonable | 7 | 5 | 2 | 0 | **Documentar con limitaciones**: la exclusión de una medición no queda auditada como `MEDICION_EXCLUIDA`; el escenario de períodos distintos no se logra |
| RF-84 | Valor razonable menos costos de venta | 7 | 7 | 0 | 0 | Documentar completo |
| RF-85 | Reconocimiento del producto agrícola en la cosecha | 8 | 5 | 3 | 0 | **Documentar con limitaciones**: tras una cosecha total el activo no queda en cero; con precio manual justificado la cosecha pendiente no se reconoce; el valor del activo puede quedar negativo |
| RF-86 | Registro automático de variaciones de valor | 9 | 9 | 0 | 0 | Documentar completo |
| RF-87 | Cierre mensual y revaluación de activos | 6 | 5 | 1 | 0 | Períodos cerrados responden 404 en lugar de informar su inmutabilidad; cierre concurrente por revisar |
| RF-88 | Valor en libros y control de valores negativos | 7 | 7 | 0 | 0 | Documentar completo |
| RF-89 | Precios de referencia y sus fuentes | 8 | 7 | 1 | 0 | Los avisos al Contador por vencimiento de precio (30/15/7 días) no se generan. G102 y G104 se aprobaron con alcance delimitado y G107 con verificación de solo lectura (ver sección 3) |
| RF-90 | Costos de mantenimiento (capitalización o gasto) | 5 | 5 | 0 | 0 | Documentar completo |
| RF-91 | Verificación de la cadena de evidencia contable | 12 | 12 | 0 | 0 | Documentar completo |
| RF-92 | Informe de valoración de activos biológicos | 12 | 10 | 2 | 0 | Informe con dos casos rechazados sin defecto confirmado (timeout y variación «No determinable») |
| RF-93 | Estado de resultados de activos biológicos | 12 | 9 | 3 | 0 | **Documentar con limitaciones**: las bajas por venta no suman a ingresos; la conciliación y la auditoría de fallos de cálculo dependen de un despliegue pendiente |
| RF-94 | Repositorio de eventos contables | 12 | 10 | 2 | 0 | **Documentar con limitaciones**: sin endpoint centralizado de eventos; `modulo_origen` fijo; monto sin formato de moneda; consulta sin filtros por rol |
| RF-COT | Cotizaciones de precios | 5 | 4 | 1 | 0 | Un valor propuesto no válido responde 400 en lugar de 422 |

## 5. Decisión de liberación a `main`

Marque la opción que aplique y firme:

- [ ] **Liberación certificada por QA** — con los criterios evaluados cumplidos; requiere las firmas de esta entrega.
- [ ] **Liberación con condiciones definidas por Coordinación**: ________________________________________________

Si se autoriza, Despliegue puede programar el despliegue a `main` y el equipo de documentación puede iniciar el manual de usuario con las observaciones de la sección 4. Los RF marcados «con limitaciones» deben documentarse indicando la limitación conocida.

## 6. Firmas de entrega

| Rol | Nombre | Fecha | Firma |
|---|---|---|---|
| Responsable QA | | | |
| Líder de Desarrollo | | | |
| Coordinación / PM (excepción) | | | |
| Equipo de Despliegue (recibido) | | | |
