# Implementación de los RFC vigentes — RFC-006, RFC-009, RFC-011 (y RFC-008)

Fecha: 2026-10-05 · Rama `feature/rfc006-rfc009-rfc011` en **sgpmp-backend** y en **sgpmp-frontend**
(mismo nombre en los dos repos) · Migración Alembic `cf12e716a4ec`.

Fuentes: `anotaciones/RFC/` y las fichas de `anotaciones/Requerimientos/` (M03, M04, M09).
Curls: `anotaciones/modulo_9/curls_m09_rfc006_rfc009_rfc011.md` y
`anotaciones/modulo_4/curls_m04_rfc009_taxonomia_paradigma.md`.

---

## 1. Estado de cada RFC

| RFC | Estado del comité | Qué se hizo en esta rama |
|---|---|---|
| RFC-005 (RF-108 recomendación de plantillas) | Pendiente de ratificación | **Nada.** Sin ficha propia, y el propio RFC pide definir pesos, fórmula y desempate antes de implementar. |
| RFC-006 (RF-24 v1.1) | Aprobado | **Implementado completo.** |
| RFC-007 (RF-22 v1.1 / RF-49 v1.2) | Aprobado | **Nada: ya estaba en dev** (backend #304, frontend #227, mergeados el 2026-10-03). |
| RFC-008 (RF-57 v1.1 / CU-03) | Aprobado, sin cambio de código | Solo un test de regresión (TC-M03-040): CERRADA → 422 `TRANSICION_INVALIDA`. |
| RFC-009 (taxonomía de M04 + RF-20) | Aprobado 2026-10-02 | **Implementada la parte de Desarrollo** (M09 RF-15/RF-20; M04 RF-65/69/70/73). Lo de IA queda fuera (§5). |
| RFC-011 (capa de visión) | Aprobado 2026-10-02 | **Implementada la parte de M09** (RF-21/RF-22). M03 y la parte de visión de RF-24 quedan fuera (§5). |

---

## 2. Qué se implementó

### RFC-006 — RF-24 v1.1: auditar los intentos de calibración rechazados

- Cada rechazo de `POST /configuracion/sensores/{id}/calibrar` queda en el historial de RF-10
  (`modulo1.eventos`) con `resultado = FALLIDO`, `modulo = MODULO9` y el tipo de evento nuevo
  **29 `CALIBRACION_RECHAZADA`** (categoría MODIFICACION). Lleva IP, user-agent, sesión, hash SHA-256 y,
  en `detalle`, sensor, dispositivo, área, código HTTP, código de error y motivo.
- Rechazos cubiertos: 404 (sensor/dispositivo inexistente, punto 4 del RFC recomendado por Análisis),
  422 (dispositivo inactivo, sensor de otro dispositivo), 400 (área incorrecta, no numérico, fuera de rango)
  y **403**. El 403 lo lanza `require_permission` antes del use case, así que se audita en una
  dependencia propia del endpoint que reutiliza la misma compuerta RBAC.
- **Best-effort**: si la escritura del evento falla, se registra en el log y el rechazo conserva su 4xx.
- El repositorio de eventos de RF-10 recibe un `modulo` opcional (default `MODULO1`); la verificación de
  integridad ya usaba el módulo guardado, así que los eventos anteriores siguen siendo íntegros.

### RFC-009 — M09

- **RF-15**: `especies.tipo_modelo` = familia de modelo de IA de la especie (opcional; uno de los 5 asignables).
- **RF-20 v1.1**:
  - `especie_id` obligatorio en el registro y la edición del área; `tipo_modelo_asignado` es opcional.
  - Coherencia especie ↔ modelo: el modelo debe ser la familia de la especie, y `MODELO_RIESGO_CONTAGIO`
    nunca es asignable (422 `INCOHERENCIA_ESPECIE_MODELO`).
  - Especie inexistente o inactiva → 422 `ESPECIE_INVALIDA`.
  - No se cambia la especie ni el modelo si el área tiene activos vigentes de otra especie
    (422 `AREA_CON_ACTIVOS_DE_OTRA_ESPECIE`, con cantidad y especie en el mensaje).
  - Nuevo `PATCH /configuracion/infraestructuras/{id}/reactivar`, auditado como UPDATE.

### RFC-009 — M04

- **Taxonomía**: 6 `tipo_modelo` en 3 paradigmas (`src/shared/tipo_modelo.py`, compartido por M04 y M09).
  La respuesta incluye `paradigma`, que se deriva del tipo.
- **RF-65 v2.0**:
  - INDIVIDUAL/META: conservan `umbral_riesgo_alto` y `umbral_alerta_critica` (0.50–0.95, con orden).
  - POBLACIONAL: usa `umbral_score_anomalia` (0–1, sin orden) y `versiones_activas_por_componente`
    (un mapa componente → versión) en lugar de `id_version_modelo_activa`.
  - La compatibilidad de la versión vinculada (4.e) se valida por la llave (`tipo_modelo`, `componente`).
  - La BD lo respalda con `ck_configuracion_motor_umbrales_por_paradigma`.
- **RF-69 v2.0**:
  - Las versiones POBLACIONAL exigen `componente` ∈ {DETECTOR, SEGUIMIENTO, METRICAS, ANOMALIAS}.
  - Se validan con métricas poblacionales en vez de F1/recall.
  - Solo puede haber una versión ACTIVO por (`tipo_modelo`, `componente`), tanto en la activación como en
    la BD (índice único parcial `uq_version_modelo_activa_tipo_componente`).
- **RF-70 v2.0**: `componente` en `despliegues_ota`, expuesto en las consultas.
- **RF-73 v2.0**: los campos mínimos de `VERSION_APROBADA/RECHAZADA` dependen del paradigma:
  - supervisados: `f1_score_global` y `recall_clase_riesgo_alto`;
  - POBLACIONAL: `calibracion_completada` y las dos tasas.

### RFC-011 — M09

- **RF-21 v2.0**: `tipos_dispositivo_iot.categoria` (SENSOR | CAMARA), sembrada con el tipo `CAMARA_VISION`.
  - Una cámara exige `resolucion` (ANCHOxALTO), `fps` (1–60) y `area_cobertura_m2` (> 0); si falta o es
    inválido responde 400 `ATRIBUTOS_VISION_INVALIDOS`, con el campo indicado.
  - En un SENSOR esos tres atributos se ignoran.
  - Una cámara no admite sensores escalares (422 `CAMARA_SIN_SENSORES`).
- **RF-22 v1.2**: la asociación cámara → área es el `id_infraestructura` del dispositivo, que ya era N:1.
  Varias cámaras en un área funcionan sin cambios; quedó cubierto por un test.

### Frontend (misma rama)

- Áreas: selector de especie (obligatorio). El de modelo de IA solo ofrece la familia de la especie, con
  un aviso si la especie no tiene familia. Hay columna "Modelo IA" y botón de reactivar.
- Especies: selector "Familia de modelo de IA".
- Dispositivos: si el tipo es CAMARA aparecen resolución, FPS y área de cobertura; un error 400 del
  backend se muestra en el campo correspondiente.
- M04:
  - Los 6 tipos en las pestañas del motor; el formulario se adapta al paradigma (umbral de anomalía y una
    versión por componente si es POBLACIONAL).
  - Componente y paradigma en modelos y OTA; métricas poblacionales en el detalle.
  - Caché offline adaptada.

---

## 3. Base de datos — migración `cf12e716a4ec` (requiere autorización del DBA antes de mergear)

- `modulo1.tipos_eventos`: tipo 29 `CALIBRACION_RECHAZADA`.
- `modulo4.enum_tipo_modelo`: los valores viejos **se renombran**, así que las filas existentes siguen
  apuntando al mismo valor sin tocar datos:
  - `ESPECIES_PEQUEÑAS` → `MODELO_AVES`
  - `ESPECIES_MEDIANAS` → `MODELO_ESPECIES_MEDIANAS`
  - `ESPECIES_GRANDES` → `MODELO_ESPECIES_GRANDES`
  - `CONTAGIO` → `MODELO_RIESGO_CONTAGIO`

  Además se agregan `MODELO_PORCINOS` y `MODELO_ACUICULTURA`.
- `configuraciones_motor_ia`:
  - Los umbrales de riesgo pasan a nullable y se agregan `umbral_score_anomalia` y
    `versiones_activas_por_componente`, con los CHECK correspondientes.
  - La configuración que existía en DEV (`ESPECIES_PEQUEÑAS`, ahora POBLACIONAL) pasa su
    `umbral_riesgo_alto` a `umbral_score_anomalia`.
- `versiones_modelos`: `componente`, `metricas_poblacionales` e índice único parcial (tipo, componente) para ACTIVO.
- `despliegues_ota`: `componente`.
- `especies.tipo_modelo` e `infraestructuras.tipo_modelo_asignado` (CHECK con los 5 asignables).
- `tipos_dispositivo_iot.categoria` y el tipo `CAMARA_VISION`; `dispositivos_iot.resolucion`, `fps` y
  `area_cobertura_m2` con sus CHECK.

Verificación: upgrade, downgrade y upgrade otra vez sobre un Postgres 17 desechable construido desde cero.
También se probaron los repositorios contra esa BD (mapeo ORM, CHECK, índice único, SQL del adaptador de M02
y hash del evento 29). No se aplicó DDL a DEV ni a TEST.

**El despliegue de backend y frontend debe ser conjunto**: el frontend anterior envía `ESPECIES_PEQUEÑAS`,
que ahora es 422.

---

## 4. Supuestos tomados (decisiones que la ficha deja abiertas; validar con Análisis)

1. **"Familia de modelo de la especie" (RF-20)**: la ficha la exige, pero ningún RF la define. Se guarda
   en `especies.tipo_modelo`, la configura el Administrador en RF-15, y la coherencia es igualdad. Una
   especie sin familia no admite un área con modelo asignado.
2. **`especie_id` obligatorio**: se exige en el DTO, pero la columna sigue nullable porque las 12 áreas de
   DEV no tienen especie. Esas áreas pasan a necesitar especie en su próxima edición.
3. **Métricas POBLACIONAL (RF-69/73)**: los nombres son `calibracion_completada`,
   `tasa_falsos_positivos_rutina` y `tasa_deteccion_eventos_clinicos`. La aprobación depende solo de
   `calibracion_completada` porque la ficha no fija umbrales para las tasas. `umbral_score_anomalia` usa
   el rango 0–1.
4. **`ESPECIES_PEQUEÑAS` → `MODELO_AVES`**: era lo que el eje por tamaño agrupaba como "pequeñas".
5. **Campos que no aplican al paradigma** (por ejemplo, umbrales de riesgo en un modelo POBLACIONAL) se
   descartan en lugar de rechazarse, con el mismo criterio que RF-16 y RF-21.
6. **Reactivar un área** usa la acción D (4), igual que reactivar una finca, así que no hizo falta tocar RBAC.
7. **Cámara con sensores**: la ficha declara la restricción pero no el flujo alterno; se eligió 422
   `CAMARA_SIN_SENSORES`.

---

## 5. NO implementado — corresponde a otro alcance (IoT / IA / Análisis), no a Desarrollo backend-frontend

| RF | Qué falta | Por qué no es de esta rama | Responsable |
|---|---|---|---|
| **RF-53 v2.0** (M03) | Recibir observaciones estructuradas de visión (vector de comportamiento) | El esquema del vector (contrato ET-01) no existe en ningún repo ni en la ficha | Diseño / AIoT |
| **RF-55 v2.0** (M03) | Procesamiento de visión en el Edge, anomalías no supervisadas, latencia por ventana | Es firmware Edge (`EDGE-FIRMWARE-SGPMP`) más modelos de visión por especie entrenados con datasets propios | AIoT |
| **RF-56 v2.0** (M03) | Tipo de dato estructurado y `area_id` en el sobre de transporte | Contrato Edge ↔ broker (`BROKER-MQTT-SGPMP`); depende de ET-01 | AIoT |
| **RF-60 v1.3** (M03) | Heartbeat de CAMARA y distinguir "sin señal" de "sin detección válida" | La ficha no da el intervalo, y la distinción la tiene que emitir el Edge | AIoT + Análisis |
| **RF-62 v2.0** (M03) — *bloqueante de RF-71* | Índice de calidad de visión → `apto_para_ia`; `apto_para_nic41 = false` | No están definidos la fórmula ni los pesos sobre `cobertura_ventana`, `n_tracks_perdidos`, `fps_efectivo` y `estado_calibracion` | Análisis / AIoT |
| **RF-24 v2.0** (parte de visión) | Calibración de línea base por visión y "tres auditorías automáticas" | La ficha solo tiene el bloque de actualización; no dice qué son ni cómo se calculan | Análisis / AIoT |
| **RF-66 v2.0** (M04) | Inferencia por `tipo_modelo_asignado` del área y rama POBLACIONAL (score de anomalía) | El motor de inferencia no vive en el backend. Lo que necesita de M09 ya está listo: `tipo_modelo_asignado`, más sensor/cámara → área | AIoT / IA |
| **RF-68 v1.1** (M04) | `definicion_fs` e `id_area_productiva` en la salida de riesgo de contagio | RF-68 no está implementado en el backend (la pantalla es un mock) | IA |
| **RF-71 v2.0** (M04) | `CALIBRACION_EN_SITIO`, trigger de degradación poblacional, CA-15 solo INDIVIDUAL | El reentrenamiento es el proceso externo RF-71 (la pantalla es un mock). El backend ya acepta registrar versiones POBLACIONAL por componente | IA |
| **RF-73** (resto) | Campos mínimos por paradigma de `REENTRENAMIENTO_COMPLETADO` y `DEGRADACION_DETECTADA` | Los emite RF-71, que no existe; se agregan cuando haya emisor | IA |
| **RF-70** (despliegue OTA) | Que el despliegue OTA real cargue `componente` | El backend solo consulta despliegues; quien los crea (Edge/broker) debe llenar la columna. La unicidad (tipo, componente) ya la garantiza la BD | AIoT |
| **RF-67 v1.1 / RF-72 v1.1** | — | Sin cambio de código: el historial ya tolera una salida sin patología (payload libre) y RF-72 es una aclaración de alcance | — |
| **RFC-005 / RF-108** | Recomendación de plantillas | El comité no lo ha ratificado y no hay ficha ni definición del ranking | Análisis / Comité |

Mientras RF-53/55/56/62 no existan, los tres modelos POBLACIONAL tienen taxonomía, configuración y
versionado listos, pero **no hay dato de entrada**: no son operables de punta a punta (RFC-009 §4.6).

---

## 6. Hallazgos laterales

1. **RF-69 roto en DEV (anterior a esta rama, no corregido)**: `modulo4.versiones_modelos.umbral_clasificacion`
   es `numeric(5,4)` con default `70.00`, que no cabe. Cualquier INSERT que no envíe ese valor falla por
   overflow, y el use case no lo envía, así que hoy **ninguna versión se puede registrar**. Hay que decidir si
   el valor es una fracción (0.70) o un porcentaje (y cambiar el tipo); requiere una migración autorizada
   por el DBA.
2. `versiones_modelos.nombre_version` es `varchar(40)` en BD, pero el ORM decía `String(100)`; se alineó el
   ORM. Con los nombres nuevos, el nombre generado pasaba de 40 caracteres, así que se le quitó el prefijo
   `MODELO_` y la fecha pasó a `aammdd`. Ampliar la columna obligaría a recrear 6 vistas de M04.
3. **RF-73 corregido de paso**: los eventos `VERSION_*` siempre se guardaban como `AUDITORIA_EVENTO_INVALIDO`,
   porque el payload no traía `id_version`, `f1_score_global` ni `id_version_nueva`.
4. RF-21 v2.0 pide 422 para un tipo de dispositivo inexistente, pero el código devuelve 404
   `TIPO_DISPOSITIVO_NO_ENCONTRADO`. No se corrigió (fuera de los RFC).
5. Frontend, `MotorView`: todas las pestañas aparecían seleccionadas porque la variable del `map` tapaba
   el estado (`tipo === tipo`). Corregido.
6. Cambiar la familia de modelo de una especie no revalida las áreas que ya tienen un modelo asignado; la
   ficha no lo define.

---

## 7. Pruebas

- Backend, unitarias:
  - Nuevas: `tests/test_registrar_calibracion_use_case.py` (ampliado),
    `tests/configuration/test_rf20_rfc009_especie_modelo_area.py`,
    `tests/configuration/test_rf21_rfc011_camara.py`,
    `tests/prediction/test_rfc009_taxonomia_paradigma.py` y
    `tests/telemetry/test_rfc008_tc_m03_040_ciclo_vida_alerta.py`.
  - Suite completa: **1152 pasan**. Los 2 que fallan (`test_sin_token_es_401` de RF-25 y RF-29) ya
    fallaban en `dev`.
- Backend, integración: el mismo conjunto de fallos que `dev` en la misma BD (17 y 3 errores de
  datos/entorno); sin regresiones.
- Frontend: vitest con **56 archivos y 345 tests**, todos en verde, y `tsc --noEmit` limpio. Nuevos:
  `MotorConfigForm.test.tsx`, `DispositivoModal.test.tsx` y casos de especie/modelo en
  `InfraestructuraSection.test.tsx`.
