# TC-M03-G181: Emisión Transversal de Eventos de Auditoría IoT (RF-63)

## 1. Identificación y Objetivos
- **Caso Maestro:** TC-M03-G181
- **Requisito Funcional:** RF-63 (Emisión Transversal desde RF-53 hasta RF-62)
- **Subcasos Evaluados:**
  - **TC-M03-347:** Invocación de operaciones de negocio mediante endpoints REST reales y verificación de la aparición de eventos en `GET /iot/auditoria`.
  - Verificación de la clasificación legal (`NIC41` con 5 años de retención para RF-53/RF-62, `TECNICO` con 1 año para RF-60).
  - Verificación de formato SHA-256 (64 hex).
  - Verificación SQL Solo Lectura de `componente_origen` (campo interno omitido en contrato REST).
- **Herramienta de Ejecución:** Newman + reporter htmlextra.
- **Entorno de Ejecución:** Sandbox transaccional con regla CERO DML.

---

## 2. Diagnóstico Técnico de Endpoints Emisores

| Requisito Funcional | Endpoint Emisor en Código | Tipo de Evento Emitido | Componente Interno | Clasificación | Retención |
|---|---|---|---|---|---|
| **RF-53** | `POST /iot/telemetria` | `EVALUACION_CALIDAD_COMPLETADA` (vía ingesta) | `ComponenteOrigen.RF53` / `RF62` | `NIC41` | 5 años |
| **RF-62** | `POST /iot/calidad/{id}/evaluar` | `EVALUACION_CALIDAD_COMPLETADA` | `ComponenteOrigen.RF62` | `NIC41` | 5 años |
| **RF-62** | `POST /iot/calidad/reevaluar` | `REEVALUACION_CALIDAD_SOLICITADA` | `ComponenteOrigen.RF62` | `NIC41` | 5 años |
| **RF-60** | `PATCH /iot/dispositivos/{id}/mantenimiento` | `TRANSICION_MANTENIMIENTO_MANUAL` | `ComponenteOrigen.RF60` | `TECNICO` | 1 año |

---

## 3. Estrategia para `componente_origen` (Campo Interno)
El esquema Pydantic `EventoAuditoriaIotSchema` omite intencionalmente `componente_origen` para cumplir con las especificaciones de seguridad de no fugar detalles de arquitectura interna al cliente HTTP.

Para verificar que el backend efectivamente guarda el componente emisor real:
- **Estrategia Elegida:** `[VERIFICACION SQL SOLO LECTURA]`
- **Mecanismo:** `POST /test-control/query` con sentencia `SELECT` estricta (sin DML):
  ```sql
  SELECT id_evento, tipo_evento, componente_origen, clasificacion_registro, retencion_aplicable
  FROM modulo3.bitacora_auditoria_iot
  WHERE id_evento = '...' LIMIT 1;
  ```
- **Ubicación en Suite:** Request `12-SQL-SELECT-Verificar-componente_origen` en [build_collection.cjs](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo3/RF-63/TC-M03-G181/build_collection.cjs).

---

## 4. Componentes Bloqueados (Broker MQTT / Workers Background)

| Componente | Tipo de Evento Documentado | Motivo de Bloqueo |
|---|---|---|
| **RF-54** | `BUFFER_ACTIVADO` | Depende de desconexión MQTT y almacenamiento local en firmware edge. |
| **RF-55** | `DESVIACION_DETECTADA` | Emitido por workers asíncronos de análisis de deriva en segundo plano. |
| **RF-56** | `PAQUETE_INFERENCIA_GENERADO` | Emitido por el módulo M04 de inferencia IA o colas de predicción. |
| **RF-57** | `ALERTA_GENERADA` | Depende del evaluador perimetral de umbrales en brokers de mensajería. |
| **RF-58** | Agregación de lecturas | Procesos batch fuera de interfaz REST síncrona. |
| **RF-59** | Calibración visión | Procesamiento de visión por computadora asíncrono. |
| **RF-60** | `DISPOSITIVO_SIN_SEÑAL` | Emitido por tarea periódica `_evaluar_dispositivos_periodicamente` tras heartbeat vencido. |
| **RF-61** | `VINCULACION_AUTOMATICA` | Emitido por worker edge RFID en segundo plano. |

Todos los subcasos bloqueados se documentan con `console.log` explicativo y **SIN** llamar a `pm.test`.
