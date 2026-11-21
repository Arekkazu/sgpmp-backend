# Documento de entrega — Módulo 5 (Suministros) al equipo de Despliegue — v1.0

| Campo | Valor |
|---|---|
| Módulo | M05 — Suministros (`src/supplies/`) |
| Alcance | RF-74 a RF-81 (8 requisitos) |
| Fecha de corte | 2026-11-15 |
| Fuente | `informe_consolidado_pruebas_M05.md` (v1.0, 2026-11-15) |
| Ambiente de prueba | Backend TEST (`https://api.inmero.co/back-sigab-test`) |
| Emite | Equipo QA |
| Destino | Equipo de Despliegue |

---

## 1. Resumen

| Indicador | Cantidad | % |
|---|---:|---:|
| Casos | 44 | 100 % |
| Aprobados | **40** | **90.9 %** |
| Rechazados | 4 | 9.1 % |
| Pendientes | 0 | 0.0 % |

## 2. Verificación de criterios de cierre de módulo

| # | Criterio | Umbral | Resultado | Cumple |
|---|---|---|---|:---:|
| 1 | Casos con veredicto Aprobado | ≥ 85 % | **40/44 = 90.9 %** | ✅ |
| 2 | RF con al menos un caso ejecutado | 100 % | **8/8** | ✅ |
| 3 | Informe consolidado con la plantilla completa | Completo | `informe_consolidado_pruebas_M05.md` redactado (pendiente de firmas) | ✅ (firmas pendientes) |

**El módulo cumple los tres criterios de cierre evaluados** (umbral de aprobación, cobertura de RF e informe consolidado). Queda pendiente la firma de la entrega. Los 4 casos no aprobados se entregan a Desarrollo (sección 3); su detalle completo está en el informe consolidado.

## 3. Casos rechazados y pendientes

| TC | RF | Resultado | Estado | Motivo |
|---|---|---:|---|---|
| G002 | RF-74 | 114/116 | Rechazado | ICA crítico: el aviso «Urgencia ALTA» no llega al Veterinario/Productor, muestra id interno y valor crudo; 500 en el cálculo crítico |
| G007 | RF-74 | 5/8 | Rechazado | Batch ICA: un fallo técnico de BD se cuenta como procesado, no avisa al Administrador y el panel informa 0 pendientes |
| G031 | RF-78 | 3/4 | Rechazado | Costeo directo: esperas entre reintentos [1, 3] en vez de [1, 3, 5] s |
| G037 | RF-80 | 11/14 | Rechazado | Rechazos de negocio (409/422) de costeo, consolidado e historial no quedan en la bitácora de auditoría |

### Casos bloqueados y dependencias

Los 4 rechazados son defectos propios de Suministros, sin dependencias de otros módulos: manejo de fallos técnicos de BD (G007, G031), aviso de conversión crítica y error 500 en el cálculo (G002) y auditoría de rechazos de negocio (G037). No hay casos pendientes.

## 4. Estado por requisito (insumo para el manual de usuario)

| RF | Función | Casos | Aprobados | Rechazados | Pendientes | Observación para el manual |
|---|---|---:|---:|---:|---:|---|
| RF-74 | Índice de Conversión Alimenticia (ICA) y batch | 7 | 5 | 2 | 0 | **Documentar con limitaciones**: ICA con clasificación CRÍTICA responde 500 / el aviso «Urgencia ALTA» no llega al Veterinario; batch cuenta como procesado un fallo técnico de BD |
| RF-75 | Consumo de alimentos | 5 | 5 | 0 | 0 | Documentar completo |
| RF-76 | Aplicación de medicamentos | 7 | 7 | 0 | 0 | Documentar completo |
| RF-77 | Reporte de gastos acumulados | 6 | 6 | 0 | 0 | Documentar completo |
| RF-78 | Costeo directo por ciclo | 6 | 5 | 1 | 0 | Costeo directo: ante fallo de BD no se aplica la espera de 5 s entre reintentos |
| RF-79 | Provisión / consolidado de ciclo (NIC 41) | 5 | 5 | 0 | 0 | Documentar completo |
| RF-80 | Auditoría de suministros | 4 | 3 | 1 | 0 | **Documentar con limitaciones**: los rechazos de negocio de costeo directo (409), consolidado (409) e historial (422) no quedan en la bitácora |
| RF-81 | Historial y trazabilidad de suministros | 4 | 4 | 0 | 0 | Documentar completo |

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
