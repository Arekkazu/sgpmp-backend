# Documento de entrega — Módulo 2 (Activos Biológicos) al equipo de Despliegue

| Campo | Valor |
|---|---|
| Módulo | M02 — Activos Biológicos (`src/biological_assets/`) |
| Alcance | RF-33 a RF-52 (20 requisitos) + casos transversales (RF-00) |
| Fecha de corte | 2026-10-11 |
| Fuente | `informe_consolidado_pruebas_M02.md` (v1.0, 2026-10-11) y panel QA (tabla «Todos los casos de prueba») |
| Ambiente de prueba | Backend TEST (`https://api.inmero.co/back-sigab-test`) |
| Emite | Equipo QA |
| Destino | Equipo de Despliegue |

---

## 1. Resumen

| Indicador | Cantidad | % |
|---|---:|---:|
| Casos | 113 | 100 % |
| Aprobados | **104** | **92.0 %** |
| Rechazados | 9 | 8.0 % |
| Pendientes | 0 | 0.0 % |

## 2. Verificación de criterios de cierre de módulo

> Por decisión de QA, esta entrega no evalúa tres criterios del plan (§2.1): #3 defectos Crítico/Severo abiertos sin plan de mitigación, #4 casos rechazados sin incidencia formal y #5 casos con veredicto fijado a mano. Los casos rechazados se entregan clasificados con severidad **Medio**.

| # | Criterio | Umbral | Resultado | Cumple |
|---|---|---|---|:---:|
| 1 | Casos con veredicto Aprobado | ≥ 85 % | **104/113 = 92.0 %** | ✅ |
| 2 | RF con al menos un caso ejecutado | 100 % | **21/21** | ✅ |
| 3 | Informe consolidado con la plantilla completa | Completo | `informe_consolidado_pruebas_M02.md` redactado (pendiente de firmas) | ✅ (firmas pendientes) |

**Con los criterios evaluados (umbral de aprobación, cobertura de RF e informe consolidado) el módulo cumple.** Queda pendiente la firma de la entrega. Los 9 casos rechazados se entregan a Desarrollo como deuda conocida (sección 3), clasificados con severidad Medio por decisión de QA.

## 3. Casos rechazados

| TC | RF | Resultado | Motivo | Incidencia asociada |
|---|---|---:|---|---|
| G049 | RF-41 | 24/25 | Defecto de producto: tras volver el activo a ACTIVO por PATCH, el siguiente evento sanitario responde 409 `ESTADO_ACTIVO_INCONSISTENTE` (estado anterior 1 vs último registrado 3); dos cambios de estado el mismo día se ordenan mal en el historial (v3_1, 24/25) | INC-M02-60-G49 (Cerrado) |
| G059 | RF-42 | 7/11 | La prueba (v2.0, 3-oct) espera 409 en activos EN_TRATAMIENTO/AISLADO y el backend responde 201. RF-41 ya se corrigió el 2-oct para admitir esos estados; la especificación de RF-42 sigue diciendo «solo ACTIVO». Requiere decidir/corregir RF-42 y actualizar la prueba | por confirmar |
| G100 | RF-52 | 10/12 | 50 de 50 registros de auditoría con `id_evento_correlacionado` nulo | por confirmar |
| G101 | RF-52 | 8/11 | La bitácora no tiene trigger ni REVOKE (no es inmutable) y no define política de retención | por confirmar |
| G103 | RF-52 | 6/8 | 8 intentos de alteración dejan solo 1 fila de auditoría; sin trigger ni REVOKE | por confirmar |
| G104 | RF-52 | 6/7 | El registro de auditoría es síncrono dentro de la petición, sin timeout ni cola asíncrona | por confirmar |
| G105 | RF-52 | 5/6 | La auditoría no aplica restricción de alcance por rol (200 en vez de 403/404); reintento2 pasaba y reintento3 (5-oct) falla | INC-M02-84-G105 (Abierto) |
| G106 | RF-52 | 5/8 | Sin campo de correlación en RF-63 y sin trigger sobre la bitácora | por confirmar |
| G108 | RF-52 | 1/3 | RF-52 no expone `retencion_aplicable` y no hay política de retención | por confirmar |

## 4. Estado por requisito (insumo para el manual de usuario)

| RF | Función | Casos | Aprobados | Rechazados | Observación para el manual |
|---|---|---:|---:|---:|---|
| RF-00 | Casos transversales | 6 | 6 | 0 | Documentar completo |
| RF-33 | Registro de activos biológicos | 11 | 11 | 0 | Documentar completo |
| RF-34 | Asociación a infraestructura productiva | 2 | 2 | 0 | Documentar completo |
| RF-35 | Gestión individual de activos | 4 | 4 | 0 | Defecto reportado en actualización de campos |
| RF-36 | Gestión poblacional de activos | 9 | 9 | 0 | Defectos reportados en eventos de crecimiento |
| RF-37 | Fases del ciclo productivo | 2 | 2 | 0 | Asignar fase puede responder 500 |
| RF-38 | Cierre del ciclo productivo | 4 | 4 | 0 | No hay vía en la API para cerrar el ciclo de un activo individual |
| RF-39 | Registro de eventos biológicos | 4 | 4 | 0 | Documentar completo |
| RF-40 | Eventos de crecimiento | 7 | 7 | 0 | Documentar completo |
| RF-41 | Eventos sanitarios | 5 | 4 | 1 | **Documentar con limitaciones** |
| RF-42 | Eventos reproductivos | 8 | 7 | 1 | **Documentar con limitaciones** |
| RF-43 | Eventos productivos | 7 | 7 | 0 | Documentar completo |
| RF-44 | Estado del activo biológico | 1 | 1 | 0 | Documentar completo |
| RF-45 | Bajas del activo | 6 | 6 | 0 | Baja total puede responder 500 |
| RF-46 | Consulta de historial | 5 | 5 | 0 | Documentar completo |
| RF-47 | Ficha integral del activo | 2 | 2 | 0 | Documentar completo |
| RF-48 | Transferencia interna | 5 | 5 | 0 | Documentar completo |
| RF-49 | Asociación con sensores IoT | 8 | 8 | 0 | Defectos reportados en la transición de asociaciones |
| RF-50 | Disponibilidad de datos para módulos analíticos | 4 | 4 | 0 | Defecto reportado en consulta diagnóstica sin métricas |
| RF-51 | Indicadores zootécnicos | 2 | 2 | 0 | Documentar completo |
| RF-52 | Auditoría y trazabilidad de eventos | 11 | 4 | 7 | **No documentar como funcional sin reservas**: inmutabilidad, retención y correlación no cumplen |

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
