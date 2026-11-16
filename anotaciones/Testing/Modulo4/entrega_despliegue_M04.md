# Documento de entrega — Módulo 4 (Predicción y Motor IA) al equipo de Despliegue — v1.0

| Campo | Valor |
|---|---|
| Módulo | M04 — Predicción / Motor IA (`src/prediction/`) |
| Alcance | RF-64 a RF-73 (10 requisitos) |
| Fecha de corte | 2026-11-15 |
| Fuente | `informe_consolidado_pruebas_M04.md` (v1.0, 2026-11-15) |
| Ambiente de prueba | Backend TEST (`https://api.inmero.co/back-sigab-test`) |
| Emite | Equipo QA |
| Destino | Equipo de Despliegue |

---

## 1. Resumen

| Indicador | Cantidad | % |
|---|---:|---:|
| Casos | 60 | 100 % |
| Aprobados | **51** | **85.0 %** |
| Rechazados | 8 | 13.3 % |
| Pendientes | 1 | 1.7 % |

## 2. Verificación de criterios de cierre de módulo

| # | Criterio | Umbral | Resultado | Cumple |
|---|---|---|---|:---:|
| 1 | Casos con veredicto Aprobado | ≥ 85 % | **51/60 = 85.0 %** | ✅ |
| 2 | RF con al menos un caso ejecutado | 100 % | **10/10** | ✅ |
| 3 | Informe consolidado con la plantilla completa | Completo | `informe_consolidado_pruebas_M04.md` redactado (pendiente de firmas) | ✅ (firmas pendientes) |

**El módulo cumple los tres criterios de cierre evaluados** (umbral de aprobación, cobertura de RF e informe consolidado). Queda pendiente la firma de la entrega. Los 9 casos no aprobados se entregan a Desarrollo (sección 3); su detalle completo está en el informe consolidado.

## 3. Casos rechazados y pendientes

| TC | RF | Resultado | Estado | Motivo |
|---|---|---:|---|---|
| G018 | RF-66 | 3/4 | Rechazado | Endpoint de inferencia inexistente (rutas candidatas devuelven 404/405) |
| G024 | RF-66 | 3/4 | Rechazado | Bloqueo: sin dataset etiquetado de 4 clases ni nodo Edge aislable para medir F1/recall y disponibilidad |
| G029 | RF-68 | 27/28 | Rechazado | Con densidad inválida responde 400 y no usa el histórico de ocupación de 30 días |
| G030 | RF-68 | 96/97 | Rechazado | No aplica la cobertura mínima de inferencias (55 % corre normal; 45 % corre sin Fs) |
| G032 | RF-68 | 36/37 | Rechazado | Recálculo dentro de 5 s responde 429; modo MVP inexistente (422 `MODO_EJECUCION_INVALIDO`) |
| G034 | RF-68 | 69/72 | Rechazado | Cuenta salidas de otros lotes y el resultado de contagio no aparece en el historial |
| G082 | RF-73 | — | Pendiente | Sin veredicto: carpeta sin evidencia ejecutada |
| G084 | RF-73 | 3/7 | Rechazado | Pipeline de reentrenamiento y scheduler de degradación no implementados (3 subcasos fallan) |
| G092 | RF-73 | 1/4 | Rechazado | Cadenas causales y filtro `correlacion_id` no disponibles (RF-66 sin productores) |

### Casos bloqueados y dependencias

- **RF-66 (G018, G024)**: falta el endpoint de inferencia en línea y los insumos de validación (dataset etiquetado, nodo Edge aislable).
- **RF-68 (G029, G030, G032, G034)**: reglas del modelo de contagio por ajustar (cobertura mínima, histórico de densidad, modo MVP, aislamiento por lote).
- **RF-73 (G084, G092, G082)** depende de RF-66 y del reentrenamiento (RF-71), aún sin implementar.

## 4. Estado por requisito (insumo para el manual de usuario)

| RF | Función | Casos | Aprobados | Rechazados | Pendientes | Observación para el manual |
|---|---|---:|---:|---:|---:|---|
| RF-64 | Catálogo de patologías | 4 | 4 | 0 | 0 | Documentar completo |
| RF-65 | Configuración del motor IA | 3 | 3 | 0 | 0 | Documentar completo |
| RF-66 | Inferencia de patologías en tiempo real | 4 | 2 | 2 | 0 | **Documentar con limitaciones**: el endpoint de inferencia en línea no existe en la API (rutas candidatas 404/405); G024 bloqueado por falta de dataset etiquetado y nodo Edge aislable |
| RF-67 | Historial de diagnósticos | 2 | 2 | 0 | 0 | Documentar completo |
| RF-68 | Modelo de riesgo de contagio | 8 | 4 | 4 | 0 | **Documentar con limitaciones**: no aplica cobertura mínima de inferencias, no usa densidad histórica cuando la densidad es inválida, limita recálculo a 5 s, no hay modo MVP y cuenta salidas de otros lotes |
| RF-69 | Validación y versionado de modelos IA | 8 | 8 | 0 | 0 | Documentar completo |
| RF-70 | Actualización OTA del modelo en el borde | 2 | 2 | 0 | 0 | Documentar completo |
| RF-71 | Reentrenamiento del modelo | 9 | 9 | 0 | 0 | Pipeline de reentrenamiento no implementado en backend: confirmar alcance con Desarrollo antes de documentar |
| RF-72 | Retroalimentación clínica del veterinario | 9 | 9 | 0 | 0 | Documentar completo |
| RF-73 | Auditoría del motor de predicción | 11 | 8 | 2 | 1 | **Documentar con limitaciones**: la auditoría de reentrenamiento y cadena causal depende de RF-66/RF-71, no implementados; filtro `correlacion_id` incompleto; G082 sin veredicto |

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
