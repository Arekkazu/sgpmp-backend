# RF-58 — Conservar la lectura válida y mostrar la condición posterior · #678 / G87

## Desvío identificado

| RF exige | Antes | Ahora |
|---|---|---|
| TC-M03-168: última lectura válida como referencia | Valor, fecha y calidad dependían de la misma fila de caché. | Valor y fecha se obtienen de la última LECTURA_VALIDA de la variable actual. |
| TC-M03-177: 31 FUERA_DE_RANGO no sustituye 25 ni desaparece | La evidencia TEST pierde la anomalía; la consulta del dev actual también puede devolver 31 como valor. | Se conserva 25 y se publica FUERA_DE_RANGO con su indicador independiente. |
| TC-M03-178: condición técnica visible para Ingeniero | La calidad de la caché podía ocultar el error posterior. | ERROR_CALIBRACION y Requiere calibración quedan disponibles con el permiso técnico. |
| TC-M03-178: privacidad del Productor | No existían dos referencias independientes para conservar el valor sin exponer el diagnóstico. | Mantiene la referencia válida y el aviso En revisión técnica; diagnóstico, batería/RSSI/SNR permanecen reservados. |

Referencias: #678, RF-58 R2/E2/CA-8, TC-M03-168/177/178, RUN-G87-V1-20261023-145303. Refs #678: la integración debe coordinar backend y frontend antes de cerrar la incidencia.

## Causa raíz

SqlAlchemyMonitoreoRepository proyectaba valor, timestamp y calidad desde estados_actuales_sensores. La consulta de la lectura más reciente solo aportaba variable y datos técnicos. Una sola referencia no podía representar a la vez la lectura válida anterior y una condición posterior inválida.

La revisión desplegada en TEST no está identificada. En origin/dev, el trigger de caché acepta los tres estados y puede sustituir 25 por 31. Se reprodujo ese resultado con la consulta original, ingesta SQL real y HTTP autenticado en PostgreSQL aislado: las dos variantes de TC-M03-177 fallaron con 31 frente a 25. La consulta corregida supera ambas.

## Cambios implementados

- Proyección independiente de última condición y última lectura válida del mismo sensor y variable; orden por captura e identificador.
- Campos opcionales estado_calidad_valor_operativo y timestamp_estado_actual en dominio/schema.
- Indicador de anomalía compatible con una referencia operativa válida anterior.
- Adaptación por el permiso datos_tecnicos_dashboard existente, sin IDs de rol nuevos ni permisos inventados.
- Conteo de errores del resumen basado en la condición más reciente.
- Frontend complementario: tipos actualizados, indicadores FE-10 reutilizados y leyenda Última lectura válida en tarjeta/detalle, es-CO/en-US.
- Cabeceras de seguimiento y regresiones específicas de G87.

## Migración

No requiere migración ni backfill. Se reutilizan modulo3.telemetrias, estados_actuales_sensores, relaciones M09 e índices existentes. La base aislada se migró desde cero hasta 30168ab97bd4. No se modifica el trigger ni el histórico de telemetría.

## Contrato resultante

ultimo_valor y ultimo_timestamp_captura describen la última LECTURA_VALIDA; estado_calidad y timestamp_estado_actual describen la condición reciente. estado_calidad_valor_operativo identifica la calidad de la referencia mostrada. Sin referencia válida no se inventa un valor.

es_valor_operativo puede ser true junto a indicador_anomalia: el 25 mostrado es válido, aunque el evento posterior sea inválido. La UI distingue las dos referencias. Para Productor, ERROR_CALIBRACION se redacta a estado_calidad nulo y etiqueta genérica; los datos técnicos permanecen nulos. No se genera una alerta operativa por esa condición ni se sustituyen las reglas del semáforo.

## Pruebas realizadas

| Validación | Resultado |
|---|---|
| Telemetría + configuración DEV-14, unitarias/contratos con fakes | 656 aprobadas, 0 fallidas, 0 omitidas |
| PostgreSQL 18 real + GET con JWT y sgpmp_app | 8 aprobadas, 0 fallidas, 0 omitidas |
| Total backend distinto | 664 aprobadas |
| Componentes UI, corrida individual final | 15 aprobadas, 0 fallidas, 0 omitidas |
| Paridad telemetry es-CO/en-US | 781 claves por catálogo, sin diferencias |
| Edge headless: 390/1280 px × claro/oscuro | 4 combinaciones aprobadas; teclado, detalle y privacidad |
| TypeScript de producción del alcance | Exit 0 |

Los casos reales cubren las dos anomalías, ausencia de referencia, recuperación, evento tardío, caché anterior, finca ajena, JWT y RBAC. El rol HTTP no es superusuario ni BYPASSRLS. Los datos técnicos se verifican con permisos persistidos. La reproducción visual utiliza respuestas de esos GET en componentes reales; no acredita un despliegue E2E ni MQTT externo.

Limitaciones verificadas del frontend: el TypeScript global tiene errores en App.tsx y LineChartTelemetria.tsx sin cambios frente a origin/dev; ESLint carece de configuración compatible; Vitest conjunto con i18n tuvo errores de arranque de workers y no se cuenta como aprobado. Se completó la corrida individual de componentes y la paridad del catálogo afectado. Auditoría strict: 135 hallazgos fuera de los archivos de UI de la corrección. El linter documental designmd no estaba disponible en caché offline.

## Integración con sgpmp_dev

Base oficial inspeccionada solo en lectura. Sin DDL/DML, despliegue ni ejecución de QA contra datos compartidos. No se afirma que una migración esté desplegada por existir en Git. La validación se hizo en sgpmp_g87_test local, eliminada al terminar; clúster y Vite detenidos, evidencias conservadas.

## Dependencias y pendientes

Integrar coordinadamente backend y frontend, conservando FE-10 y el permiso técnico DB-08 existentes. Reejecutar G87 en TEST para obtener aprobación oficial. La caché offline Dexie no se modifica ni está cubierta por esta reproducción visual. No se incorporan cambios de firmware, alertas, RF-62 o nuevas políticas.

## Alcance del commit

Entrega de #678 autorizada para un commit y push por repositorio, sin crear PR: backend con 4 archivos de producción, 2 de pruebas y 2 informes; frontend en worktree con tipos, tarjeta/detalle, CSS de la leyenda, 2 catálogos, pruebas y documentación. Excluir caches, scripts temporales, capturas, AGENTS.md y anotaciones ajenas. El contexto DESIGN.md del frontend acompaña su documentación.

## Revisión contra dev

Backend parte de origin/dev 18b4ce67e8d23ed57fdfd108d44e0c2601e66604; frontend parte de origin/dev 28c2171. Ambas ramas locales se denominan fix/issue-678-g87-dashboard-condiciones-rf58. El checkout original FE-12 y su UX-CONTRACT.md modificado permanecen preservados; la UI se trabaja en .worktrees/g87-rf58.

Informe detallado: anotaciones/modulo_3/issue_678_g87_rf58_dashboard_condiciones.md.
