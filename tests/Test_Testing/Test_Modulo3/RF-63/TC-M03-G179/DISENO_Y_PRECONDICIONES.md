> **Actualización 2026-10-26 — versión de solo lectura.** La colección `test_tc_m03_g179.json` ya no crea finca, dispositivo ni sensor ni genera eventos, y este documento describe el diseño anterior. Motivos: (1) los eventos de auditoría (RF-63) se emiten de forma asíncrona *después del commit* y el sandbox nunca confirma, así que dentro de él no se generan; (2) el sandbox deja `now()` de la BD congelado al inicio, por lo que una lectura con hora actual responde `ERROR_TIEMPO`; (3) la ingesta solo acepta lecturas posteriores a la asociación del sensor, lo que impide usar fechas pasadas con un sensor nuevo; (4) el sistema no permite la transición manual ACTIVO → EN_MANTENIMIENTO. Ahora las pruebas consultan la bitácora tal como está y toman de ella los ids que necesitan. También se corrigió: `verificar-integridad` exige `fecha_desde` y `fecha_hasta` (ventana de 30 min; máximo 50 000 eventos) y `rf_origen` usa el formato `RF62` (no `RF-62`). Los códigos 422 que algunas aserciones esperan para validación de entrada (`por_pagina` > 200, UUID malformado) no los define el RF-63 y hoy el sistema responde 400; se dejaron sin cambiar para que la discrepancia siga visible.

# TC-M03-G179: Clasificación NIC41 vs. TECNICO y Retención Legal en Auditoría IoT (RF-63)

## 1. Identificación y Objetivos
- **Caso Maestro:** TC-M03-G179
- **Requisito Funcional:** RF-63 (Clasificación de Eventos y Retención Legal)
- **Subcasos Evaluados:**
  - **TC-M03-342:** Filtro por `clasificacion_registro` (`NIC41` con `retencion_aplicable=5`, `TECNICO` con `retencion_aplicable=1`). Inyección de evento ambiguo marcada como `[BLOQUEADO]`.
  - **TC-M03-344 (Positivo NIC41):** Verificación de eventos emitidos por componentes NIC41 (`RF-62`: `EVALUACION_CALIDAD_COMPLETADA` y `REEVALUACION_CALIDAD_SOLICITADA`). Verificación de que `clasificacion_registro === 'NIC41'` y `retencion_aplicable === 5`. Subcasos `RF-56` y `RF-61` marcados como `[BLOQUEADO]`.
  - **TC-M03-345 (Negativo TECNICO):** Verificación de eventos emitidos por componentes técnicos (`RF-60`: `TRANSICION_MANTENIMIENTO_MANUAL`). Verificación de que `clasificacion_registro === 'TECNICO'` y `retencion_aplicable === 1`. Subcasos `RF-54`, `RF-55`, `RF-57`, `RF-58`, `RF-59` y `DISPOSITIVO_SIN_SEÑAL` marcados como `[BLOQUEADO]`.
- **Herramienta de Ejecución:** Newman + reporter htmlextra.
- **Entorno de Ejecución:** Sandbox transaccional con regla CERO DML.

---

## 2. Regla de Negocio y Clasificación en Código

En [evento_auditoria_iot.py:18-35](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/telemetry/domain/entities/evento_auditoria_iot.py#L18):
```python
_COMPONENTES_NIC41 = {
    ComponenteOrigen.RF53,  # Captura / Validación
    ComponenteOrigen.RF56,  # Paquete de Inferencia
    ComponenteOrigen.RF61,  # Vinculación de Lectura
    ComponenteOrigen.RF62,  # Calidad del Dato
}

def clasificar_componente(componente: Optional[ComponenteOrigen]) -> tuple[ClasificacionRegistro, int]:
    if componente is None:
        return ClasificacionRegistro.NIC41, 5  # Ambiguo por defecto
    if componente in _COMPONENTES_NIC41:
        return ClasificacionRegistro.NIC41, 5
    return ClasificacionRegistro.TECNICO, 1
```

---

## 3. Matriz de Clasificación de Componentes y Emisores

| RF-Emisor | Componente Origen | Clasificación Esperada | Clasificación Observada en Sandbox | Retención (Años) | Método de Generación API | Estado |
|---|---|---|---|---|---|---|
| **RF-62** | `ComponenteOrigen.RF62` | `NIC41` | `NIC41` | 5 | `POST /iot/telemetria/batch` / `POST /iot/calidad/{id}/evaluar` | Verificado |
| **RF-62** | `ComponenteOrigen.RF62` | `NIC41` | `NIC41` | 5 | `POST /iot/calidad/reevaluar` | Verificado |
| **RF-60** | `ComponenteOrigen.RF60` | `TECNICO` | `TECNICO` | 1 | `PATCH /iot/dispositivos/{id}/mantenimiento` | Verificado |
| **RF-53** | `ComponenteOrigen.RF53` | `NIC41` | N/A (bitácora ingest) | 5 | `POST /iot/telemetria` escribe en `bitacora_ingest_iot` | Documentado |
| **RF-56** | `ComponenteOrigen.RF56` | `NIC41` | N/A | 5 | Generado por motor de IA / M04 asíncrono | `[BLOQUEADO]` |
| **RF-61** | `ComponenteOrigen.RF61` | `NIC41` | N/A | 5 | Worker RFID / Edge asíncrono | `[BLOQUEADO]` |
| **RF-54** | `ComponenteOrigen.RF54` | `TECNICO` | N/A | 1 | Broker MQTT / Gateway offline | `[BLOQUEADO]` |
| **RF-55** | `ComponenteOrigen.RF55` | `TECNICO` | N/A | 1 | Worker de detección de desvíos | `[BLOQUEADO]` |
| **RF-57** | `ComponenteOrigen.RF57` | `TECNICO` | N/A | 1 | Motor de alertas / regla de umbral | `[BLOQUEADO]` |
| **RF-58** | `ComponenteOrigen.RF58` | `TECNICO` | N/A | 1 | Procesamiento de agregaciones | `[BLOQUEADO]` |
| **RF-59** | `ComponenteOrigen.RF59` | `TECNICO` | N/A | 1 | Calibración automática de visión | `[BLOQUEADO]` |
| **RF-60** | `ComponenteOrigen.RF60` | `TECNICO` | N/A | 1 | `DISPOSITIVO_SIN_SEÑAL`: background task | `[BLOQUEADO]` |
| **Ambiguo** | `None` | `NIC41` | N/A | 5 | No existe endpoint para forzar None | `[BLOQUEADO]` |

---

## 4. Hallazgos y Motivos de Bloqueo
1. `[BLOQUEADO]`: El backend no provee endpoints REST síncronos para emitir directamente eventos de `RF-54` (buffer activado), `RF-55` (desviación detectada), `RF-56` (paquete de inferencia), `RF-57` (alerta generada), ni `RF-61` (vinculación automática edge). Estos componentes dependen de colas de mensajes MQTT o workers de fondo independientes.
2. `[BLOQUEADO]`: No existe endpoint de inyección para eventos ambiguos (sin `componente_origen`), dado que todos los casos de uso implementados asignan de forma explícita su respectivo enum `ComponenteOrigen`.
3. Todos los subcasos bloqueados se documentan con `console.log` explicativo y **SIN** llamar a `pm.test` para preservar la integridad del reporte del escáner QA.
