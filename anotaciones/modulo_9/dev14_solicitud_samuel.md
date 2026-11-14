# DEV-14 / #3591 — Solicitud técnica mínima para M09

Mensaje preparado para revisión y envío por el responsable. **No fue enviado automáticamente.**

Samuel, al implementar #3520 revisé migraciones, modelos y `sgpmp_dev` en solo
lectura. Hay una dependencia real para los parámetros operativos M09, pero no
para la configuración estadística/MLOps.

## Lo comprobado

`modulo9.configuraciones_globales` solo tiene como valores operativos
`frecuencia_muestreo` y `heartbeat`, además de ID, usuario, fecha y estado activo.
No tiene columnas adicionales ni una estructura JSON para los parámetros de
latencia, deduplicación y batería/señal.

`configuraciones_remotas.intervalo_transmision` representa transmisión remota,
no un umbral de latencia ni una cadencia de heartbeat. La ventana de confirmación
de una regla de alerta tampoco es la ventana global de deduplicación. Reutilizar
esos campos cambiaría sus significados y mezclaría unidades/responsabilidades.

`modulo4.parametros_mlops` sí admite parámetros numéricos JSONB por nombre, con
valor actual, valor por defecto, límites, usuario y fecha. Se reutilizó para
RF-62, confianza Edge/IA y RF-72, sin solicitar tablas, columnas ni semillas a DBA.
También confirmé SELECT/INSERT/UPDATE existentes para `sgpmp_app` y `member_dev`
sobre esa tabla; no se necesitan grants nuevos para ese acceso observado.

## Cambio de esquema requerido

Propuesta de ampliación mínima de la tabla global existente; nombres finales
según convención de BD y revisión DBA:

| Tabla | Columna propuesta | Tipo / restricción | Consumidor bloqueado |
|---|---|---|---|
| `modulo9.configuraciones_globales` | `umbral_latencia_alta_ms` | `integer`, valor positivo | RF-53 HTTP: comparación de latencia expresada en ms |
| La misma | `ventana_deduplicacion_alertas_min` | `integer`, valor positivo | RF-57: ventana de búsqueda de alerta activa |
| La misma | `umbral_bateria_baja_pct` | `numeric(5,2)`, entre 0 y 100 | RF-60: batería baja |
| La misma | `umbral_bateria_critica_pct` | `numeric(5,2)`, entre 0 y 100 y no superior al umbral de batería baja | RF-60: batería crítica |
| La misma | `umbral_rssi_dbm` | `numeric(6,2)`; rango operativo final confirmado por Análisis | RF-60: señal degradada |

No se solicita una tabla paralela ni almacenar estos valores operativos de
dispositivos en MLOps. Una alternativa sería un objeto JSONB tipado en esta
misma tabla, pero los cinco escalares anteriores admiten restricciones SQL
directas y contratos de unidades explícitos. No deben aplicarse ambas opciones.

Se requiere una migración versionada y un plan de incorporación de datos para
la configuración activa. Los valores vigentes del código son 30000 ms,
30 minutos, 30 %, 10 % y −100 dBm; **son la referencia de compatibilidad, no
una aprobación normativa nueva**. El backfill/default definitivo debe respetar
los RF y la aprobación correspondiente. Evitar activaciones con configuración
parcial o defaults silenciosos en la aplicación.

Conservar el singleton activo, el usuario/fecha de modificación y la auditoría
existente de `configuraciones_globales`. No modificar los triggers RF-53.

## Temporalidad RF-18 / RF-60: decisión separada de Análisis

RFC-015 C1 ya aclara que `heartbeat` es alias deprecado de `umbral_sin_senal`;
no se solicita renombrar físicamente esa columna ni duplicar el mismo valor.
`intervalo_heartbeat` es otra magnitud.

El RF-60 actualizado exige intervalo por tipo, margen de tolerancia e inactividad
extendida, ausentes en el esquema revisado. Antes de diseñar su almacenamiento
y semillas por tipo/variable, debe aclararse el algoritmo: con "primer PASO que
aplique", PASO 3 absorbe los tiempos de PASO 4 y vuelve inalcanzable INACTIVO;
también falta definir el estado entre el intervalo activo y el umbral sin señal.

Esta aclaración corresponde a Análisis, no a DBA. No se solicita decidirla ni
crear tres columnas con los antiguos 300/1800/86400 segundos como solución.
Una vez confirmada, coordinar almacenamiento por el alcance definido y
validación de la cadena temporal, sin duplicar umbrales derivados.

## Criterios para verificar la entrega

1. La migración expone los parámetros aprobados con tipo, unidad y restricciones.
2. Existe una configuración activa completa y con trazabilidad de responsable.
3. Los consumidores pueden leer valores distintos a los anteriores y observar
   el cambio sin reiniciar el backend.
4. RF-53 compara ms; RF-57 compara minutos; batería conserva `<=` y RSSI `<`.
5. Valores ausentes o inválidos producen un error controlado, sin constantes
   de respaldo que oculten la ausencia de configuración.
6. No cambian la inmutabilidad de RF-53, los contratos de otros campos ni las
   políticas de seguridad existentes.

La implementación independiente de RF-62, confianza RF-57 y ventana RF-72
continúa y tiene pruebas contra PostgreSQL aislado; esta dependencia no bloquea
esas partes.
