# RF-62 — Motor de calidad, sigma cero y notificaciones pendientes · INC-M03-104-G165

Fecha: 2026-10-26. Autor de cabeceras verificado mediante git config user.name: Leandro.

Referencia: [issue #632](https://github.com/Arekkazu/sgpmp-backend/issues/632), TC-M03-G165 y documentos RF-53/RF-62 y AIOT-DEV-03 aportados por el usuario.

## Resultado

Se corrigió el outlier estadístico con sigma cero y el bloqueo de calidad causado por una severidad de alerta de drift no definida. Se verificaron los descuentos compuestos, el historial de reevaluaciones y la inmutabilidad del origen.

**664 pruebas distintas aprobadas, 0 fallidas y 0 omitidas:** 618 de tests/telemetry, 41 de integración contra dev y 5 del flujo combinado con la dependencia de snapshot de #626 aplicada únicamente a PostgreSQL local. No se suman repeticiones ni corridas interrumpidas.

| Caso | Índice | Clasificación | Apto IA | Apto NIC-41 |
|---|---:|---|---|---|
| Base | 100 | APTO | true | true |
| 318a: outlier + drift ~7 % + gap 25 min | 60 | APTO_CON_RESERVA | true | false |
| 318b: congelado moderado + drift ~15 % | 40 | APTO_CON_RESERVA | true | false |
| 318c: congelado crítico + salto con sigma cero | 0 | NO_APTO | false | false |
| 320: congelado moderado + outlier + gap 25 min | 35 | NO_APTO | false | false |

Los casos usan N=20, M=5, k=3, P=5, umbral de drift 5 % y muestreo 10 min. Las pruebas de motor preparan las lecturas históricas mediante INSERT de fixture, con su snapshot explícito; no presentan esa preparación como validación de ingesta.

## Base y alcance confirmado

Se ejecutó git fetch origin dev, se actualizó dev con fast-forward y se creó una rama nueva desde esa base:

- Rama: fix/inc-m03-104-g165-motor-calidad-rf62.
- Base verificada: 18b4ce67e8d23ed57fdfd108d44e0c2601e66604.
- Las ramas de #625 y #626 no forman parte de sus commits.

El usuario confirmó expresamente dos decisiones:

1. Conservar DEV-02: telemetrias es inmutable y la aptitud oficial se consulta en telemetria_calidad. El punto 4 del reporte no se implementa como UPDATE del origen.
2. Persistir la evaluación cuando falta una severidad aprobada de drift y dejar la alerta pendiente en auditoría. Se mantienen las alertas de congelamiento y el rollback ante fallos reales.

## Revisión de las manifestaciones reportadas

| Manifestación | Diagnóstico sobre dev actualizado | Tratamiento |
|---|---|---|
| No aplicar drift | El motor calcula y descuenta drift cuando recibe el snapshot. dev y la función oficial inspeccionada todavía lo omiten en la ingesta | Dependencia #626, no duplicada en esta rama; validación del motor con snapshot y del flujo combinado local |
| No aplicar gap | DEV-43 ya consulta timestamps, frecuencia y periodos de RF-60; los casos con gap de 25 min sí descuentan 10 puntos | Pruebas de contrato y PostgreSQL; se conserva la regla vigente |
| Sigma cero | El guard sigma > 0 omite un salto aunque se cumpla la desigualdad estadística | Corrección del motor y evidencia JSON finita |
| Una sola evaluación tras POST | El repositorio hace INSERT, y el caso de uso supera la anterior si existe; la ingesta B+ no garantiza que su etapa asíncrona haya terminado antes del POST | Se ejecuta la etapa RF-62 real del worker antes de reevaluar y se comprueban cadenas de dos y tres filas |
| UPDATE de aptitud en telemetrias | Contradice AIOT-DEV-03, DEV-02 y el trigger RF-53 | Se conserva el origen completo y la evaluación vigente como fuente oficial, confirmado por el usuario |

El XML adjunto comprueba magnitud_drift_porcentaje dentro de flags_detectados.posible_drift, no dentro de parametros_aplicados. Se conserva esa ubicación del contrato.

La aptitud para índices 60 y 40 es IA=true y NIC-41=false según la tabla de RF-62; no se convierte ambos indicadores a false para esas clasificaciones.

## Causa raíz y cambios de producción

### Outlier con sigma cero

La desigualdad es abs(valor-media) > k*sigma. Con sigma=0, un valor distinto de la media sí cumple la condición. El cálculo ya no se omite por la ausencia de dispersión.

Para una serie de veinte valores 20 y una lectura 26:

- Se conserva congelado CRITICO (-90).
- Se activa outlier estadístico (-20).
- El índice satura en 0.
- magnitud_desviacion es null porque el z-score no está definido; se guardan sigma_cero=true y desviacion_absoluta=6.
- No se generan Infinity/NaN ni se inventa una versión de límite físico.

También se comprueban un salto negativo y el valor igual a la media, que no debe activar outlier. El fallback por límite físico versionado se conserva.

### Drift significativo sin severidad aprobada

El motor ya detectaba drift, pero GenerarAlertaCalidadUseCase lanzaba SEVERIDAD_DRIFT_NO_CONFIGURADA cuando su magnitud superaba el umbral significativo y no encontraba una severidad aprobada. Esa excepción revertía la evaluación.

Con el alcance confirmado, el servicio devuelve un aviso pendiente con anomalía, motivo y magnitud. El evaluador lo incorpora a accion_detallada.notificaciones_pendientes del evento EVALUACION_CALIDAD_COMPLETADA, con resultado PARCIAL, dentro de la misma transacción que la calidad y la sustitución de la anterior.

No se inventa una alerta ni su severidad. La alerta MODERADO de congelamiento del caso 318b sí se conserva. Los errores de repositorio, de auditoría o de confirmación siguen propagándose y revirtiendo los cambios.

## Historial, transacciones y arquitectura

Se preserva Router → caso de uso → puertos → repositorios/adaptadores. No se añade SQL al dominio ni commits a los repositorios.

Una reevaluación crea otra fila. La nueva apunta a la anterior mediante id_evaluacion_superada; la anterior queda SUPERADA con motivo. No se añade un enlace inverso que genere ciclos. Con tres evaluaciones se verifica exactamente una VIGENTE y dos SUPERADA, preservando los snapshots históricos.

La prueba postcommit ejecuta el componente real del worker con identidad de servicio existente y rol sgpmp_app, antes de invocar POST /iot/calidad/{id}/evaluar. Se distinguen una primera evaluación y una reevaluación; no se crean filas ficticias para satisfacer el conteo.

La inyección de un fallo después de insertar una evidencia real comprueba rollback de la nueva evaluación, de la transición de la anterior y de la auditoría, así como reintento exitoso. Las regresiones existentes comprueban también concurrencia y deduplicación de alertas.

## BD, RBAC y migraciones

Se inspeccionaron columnas, tipos, PK/FK, índices, triggers, RLS, migraciones y permisos antes de modificar producción. La base local sgpmp_g165_test se construyó desde cero con Alembic hasta 30168ab97bd4.

En sgpmp_dev se verificó transaction_read_only=on. No se ejecutaron DDL/DML ni solicitudes POST contra la base oficial. Se observaron los triggers de inmutabilidad activos y el esquema de calidad con FK al historial. La lectura de permisos y alembic_version oficial fue rechazada con 42501; no se presenta como ausencia de permisos ni como certificación de la revisión desplegada.

RLS/FORCE están activos en sensores. telemetrias y telemetria_calidad no tienen RLS en el esquema observado; no se les atribuye esa garantía ni se cambia aquí. En la base local se verificaron los permisos RBAC del recurso 38 y el rol de API sin superusuario ni BYPASSRLS.

Esta corrección no añade migración: las columnas y contratos requeridos ya existen. Se mantienen restricciones, triggers, identidad RLS y use_insertmanyvalues=False.

## Dependencia de ingesta #626

La inspección de pg_proc confirma que fn_ingesta_telemetria en dev y en la BD oficial aún no guarda parametros_calibracion. Por ello el despliegue del flujo completo necesita la corrección previamente entregada:

- Rama: fix/inc-m03-123-g167-alta-sensor-rf62.
- Commit: 96b23b8ef46b30dad0c3601979786f366b00f7e2.
- Migración: 8d13c7e9a624.

Después de validar los 41 casos de motor/historial sobre la base de dev sin esa dependencia, se exportó la migración exacta del commit anterior a .pytest_cache y se aplicó únicamente a la base local mediante Operations. No se copió a la rama ni se modificó su alembic_version para simular integración.

Se ejecutaron cinco variantes desde sensor → asociación → calibración → ingesta → calidad/detalle, incluyendo ganancia decimal, ausencia de calibración, recalibración histórica y drift significativo. Se usaron las pruebas de #626 exportadas temporalmente, ampliadas con offset 4 y el descuento correspondiente. Estas cinco pruebas se reportan separadas: demuestran compatibilidad local combinada, no una dependencia ya fusionada o desplegada.

## Pruebas y evidencia

| Grupo | Aprobadas | Fallidas | Omitidas |
|---|---:|---:|---:|
| tests/telemetry: pruebas unitarias y contratos HTTP | 618 | 0 | 0 |
| PostgreSQL real sobre migraciones de dev: motor, historial, rollback, seguridad y concurrencia | 41 | 0 | 0 |
| Flujo HTTP completo con #626 aplicada solo localmente | 5 | 0 | 0 |
| **Total distinto** | **664** | **0** | **0** |

Los ocho casos nuevos de integración HTTP usan JWT y TEST_ROL_APP=sgpmp_app. El setup SQL y las aserciones administrativas emplean la conexión del fixture. Las regresiones existentes conservan sus propios fixtures; no se presentan todas como peticiones bajo el rol de API. No se usó broker MQTT real.

Evidencias ignoradas en .pytest_cache:

- g165_unit_antes.xml: 5 fallos y 6 aprobadas antes de la corrección; reproduce sigma cero y el bloqueo por severidad.
- g165_unit_final.xml: 618 aprobadas.
- g165_pg_inicial.xml: 37 aprobadas y 4 detenidas por destinos ORM no registrados en el fixture HTTP acotado.
- g165_pg_repeticion.xml: esos cuatro casos detectaron privilegios locales pendientes en el trigger de caché.
- g165_pg_final.xml: repetición final de esos cuatro casos, todos aprobados.
- g165_flujo_combinado.xml: 5 aprobadas; las otras 9 pruebas del archivo temporal fueron deseleccionadas, no omitidas.
- g165_resultados_consolidados.json: 664 IDs distintos, tomando el último resultado de cada uno.
- g165_preflight_local.log y g165_preflight_oficial.log: metadatos y límites de la inspección.

La preparación local incorporó los privilegios SQL mínimos de infraestructura requeridos por los triggers reales, sin modificar políticas, restricciones ni permisos RBAC. El fixture acotado registra los modelos que main.py carga mediante sus routers. Ninguno de esos ajustes requirió modificar producción.

Una corrida unitaria sin acceso al entorno local quedó detenida en un contrato HTTP del broker; se detuvieron únicamente sus dos procesos identificados y se repitió con diagnóstico. No se contabiliza como aprobada. El shim fcntl de Windows se limita al lanzador de pruebas.

## Archivos y límites de entrega

Dos archivos de producción:

- src/telemetry/application/use_cases/calidad/evaluar_calidad_telemetria_use_case.py.
- src/telemetry/application/use_cases/calidad/generar_alerta_calidad_use_case.py.

Cuatro archivos de pruebas: dos nuevos para INC-M03-104-G165 y dos actualizados de DEV-43 para el comportamiento de alerta pendiente. Más este informe: siete archivos en total.

No se ejecutó la colección original de 56 assertions de QA ni se certificó su despliegue. Los adjuntos registran 36 aprobadas y 20 fallidas, pero no incluyen todo su código de preparación para atribuir cada diferencia al despliegue concreto.

Siguen pendientes de Análisis la severidad aprobada para notificar drift significativo y el proveedor de límites físicos históricos versionados. No se certifica el versionado integral de RNF-07 ni se inventan valores para version_evaluacion, que es nullable en el esquema actual. Estas limitaciones no impiden guardar los resultados y la evidencia definidos en el alcance confirmado.

Se preservan AGENTS.md, pendientes_integracion_aiot_por_tarea_y_pr.md y pendientes_por_area/ como archivos locales ajenos. El usuario autorizó el commit y el push de estos siete archivos en la rama de #632, sin crear PR.
