# Documento de entrega — Módulo 3 (Telemetría IoT) al equipo de Despliegue — v1.0

| Campo | Valor |
|---|---|
| Módulo | M03 — Telemetría IoT (`src/telemetry/`) |
| Alcance | RF-53 a RF-63 (11 requisitos) |
| Fecha de corte | 2026-11-15 |
| Fuente | `informe_consolidado_pruebas_M03.md` (v1.0, 2026-11-15) |
| Ambiente de prueba | Backend TEST (`https://api.inmero.co/back-sigab-test`) |
| Emite | Equipo QA |
| Destino | Equipo de Despliegue |

---

## 1. Resumen

| Indicador | Cantidad | % |
|---|---:|---:|
| Casos | 103 | 100 % |
| Aprobados | **88** | **85.4 %** |
| Rechazados | 13 | 12.6 % |
| Pendientes | 2 | 1.9 % |

## 2. Verificación de criterios de cierre de módulo

| # | Criterio | Umbral | Resultado | Cumple |
|---|---|---|---|:---:|
| 1 | Casos con veredicto Aprobado | ≥ 85 % | **88/103 = 85.4 %** | ✅ |
| 2 | RF con al menos un caso ejecutado | 100 % | **11/11** | ✅ |
| 3 | Informe consolidado con la plantilla completa | Completo | `informe_consolidado_pruebas_M03.md` redactado (pendiente de firmas) | ✅ (firmas pendientes) |

**El módulo cumple los tres criterios de cierre evaluados** (umbral de aprobación, cobertura de RF e informe consolidado). Queda pendiente la firma de la entrega. Los 15 casos no aprobados se entregan a Desarrollo (sección 3); su detalle completo está en el informe consolidado.

## 3. Casos rechazados y pendientes

| TC | RF | Resultado | Estado | Motivo |
|---|---|---:|---|---|
| G056 | RF-56 | — | Pendiente | Sin veredicto: reintentos, backoff y cola de reenvío de paquetes de inferencia no implementados |
| G068 | RF-57 | 37/40 | Rechazado | No evalúa el valor contra umbrales y rangos: la severidad se copia de `severidad_edge` |
| G069 | RF-57 | 21/100 | Rechazado | Rechaza con 422 `REGLA_COMPUESTA_NO_ACTIVADA` toda lectura aislada fuera de banda |
| G070 | RF-57 | 9/10 | Rechazado | Alerta compuesta sin comprobar condición mínima (variables requeridas y THI) |
| G071 | RF-57 | 34/49 | Rechazado | Correlación de reglas (E14) no implementada; tipos de evento de bitácora no registrados |
| G072 | RF-57 | 55/56 | Rechazado | Espera 422 y el backend responde 200/201 |
| G074 | RF-57 | 16/79 | Rechazado | Dos eventos de IA del mismo activo dentro de la ventana generan dos alertas en vez de una |
| G075 | RF-57 | 38/45 | Rechazado | Reevaluación de alertas tras recuperación del motor IA (E3/E16/CA-6) no existe |
| G076 | RF-57 | 11/24 | Rechazado | Parámetro `umbral_confianza_edge_ia` no cargado en TEST: 503 `PARAMETRO_CONFIGURACION_AUSENTE` |
| G077 | RF-57 | 13/19 | Rechazado | La alerta no asocia el contexto del activo y no notifica al administrador |
| G078 | RF-57 | 90/104 | Rechazado | Listado de alertas responde 500 con filtros fuera de catálogo (debe ser 400) |
| G085 | RF-57 | 39/41 | Rechazado | Flujo E9 (variable sin umbrales) no implementado |
| G086 | RF-57 | 72/113 | Rechazado | No aplica la ventana de confirmación temporal |
| G124 | RF-59 | — | Pendiente | Diferido: la exportación PDF/Excel (RF-59) responde 503 porque el módulo de reportes aún no genera archivos |
| G167 | RF-62 | 23/32 | Rechazado | Defecto de producto: `posible_drift` mal calculado (oráculo 75 vs 100, 75 vs 90) en evaluación de calidad |

### Casos bloqueados y dependencias

- **RF-57** concentra 12 de los 13 rechazados: la generación de alertas copia la severidad enviada por el borde sin evaluar umbrales ni reglas compuestas. Es una deuda funcional de un mismo origen.
- **G056** depende de la política de reintentos y cola de reenvío hacia el motor IA. **G124** (exportación PDF/Excel) depende del módulo de reportes.

## 4. Estado por requisito (insumo para el manual de usuario)

| RF | Función | Casos | Aprobados | Rechazados | Pendientes | Observación para el manual |
|---|---|---:|---:|---:|---:|---|
| RF-53 | Recepción y almacenamiento de telemetría | 12 | 12 | 0 | 0 | Documentar completo |
| RF-54 | Buffer local y reenvío (store-and-forward) | 8 | 8 | 0 | 0 | Documentar completo |
| RF-55 | Detección de desviaciones en el borde (Edge) | 12 | 12 | 0 | 0 | Documentar completo |
| RF-56 | Envío de paquetes de inferencia al motor IA (M04) | 6 | 5 | 0 | 1 | **Documentar con limitaciones**: el envío de paquetes a IA hace un único intento síncrono, sin reintentos, backoff ni cola de reenvío; G056 sin veredicto |
| RF-57 | Generación y gestión de alertas ambientales | 15 | 3 | 12 | 0 | **Documentar con limitaciones graves**: no evalúa umbrales/rangos, reglas compuestas ni ventana de confirmación; no reevalúa alertas tras recuperación de la IA; el listado filtrado por valor fuera de catálogo responde 500 |
| RF-58 | Monitoreo ambiental en tiempo real | 9 | 9 | 0 | 0 | Defectos reportados en el panel: unidad sin sensores no se renderiza y estado vacío incorrecto |
| RF-59 | Historial de lecturas ambientales | 13 | 12 | 0 | 1 | Exportación PDF/Excel (G124) diferida: depende del módulo de reportes (503 `503`) |
| RF-60 | Detección de sensores sin reporte | 9 | 9 | 0 | 0 | Documentar completo |
| RF-61 | Asociación de lecturas a activo o lote | 6 | 6 | 0 | 0 | Documentar completo |
| RF-62 | Evaluación de calidad de datos del sensor | 8 | 7 | 1 | 0 | **Documentar con limitaciones**: `posible_drift` no se calcula como se espera y el proceso automático posterior al guardado no corre en TEST |
| RF-63 | Auditoría de telemetría y alertas | 5 | 5 | 0 | 0 | Documentar completo |

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
