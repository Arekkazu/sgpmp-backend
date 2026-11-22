# #678 · G87 · RF-58 — Referencia válida y condición posterior del sensor

Fecha: 2026-10-26 · Responsable Git verificado: Leandro.

## Alcance y referencias

Issue #678, TC-M03-168 / TC-M03-177 / TC-M03-178. RF-58 R2, E2 y CA-8. Evidencia de QA: RUN-G87-V1-20261023-145303, TEST. Se revisaron el informe tc-m03-g87_resultado.md y las dos aserciones rechazadas del HTML Newman. El archivo resultado_TC-M03-G167.md contiene la descripción de otra entrega (#646), por lo que no se usa como evidencia de G87.

Se parte de origin/dev actualizado: backend 18b4ce67e8d23ed57fdfd108d44e0c2601e66604; frontend 28c2171. Rama de ambos repositorios: fix/issue-678-g87-dashboard-condiciones-rf58. El frontend se trabaja en .worktrees/g87-rf58 para preservar el checkout FE-12 y su UX-CONTRACT.md modificado. El usuario autorizó consolidar y publicar un commit por repositorio en estas ramas. La autorización no incluye crear un PR ni integrar o desplegar los cambios.

## Causa raíz comprobada

El repositorio de monitoreo obtenía valor, fecha y calidad de una sola fila de modulo3.estados_actuales_sensores. La consulta lateral de telemetría reciente solo aportaba variable y datos técnicos. Por ello el caso de uso no disponía de dos referencias independientes.

El reporte TEST muestra una caché con 25 °C y calidad LECTURA_VALIDA después del evento inválido, por lo que la anomalía desaparece. Su revisión desplegada no está identificada. En el dev revisado, el trigger de la migración 60bf7fe3d775 acepta LECTURA_VALIDA, FUERA_DE_RANGO y ERROR_CALIBRACION y reemplaza conjuntamente valor, fecha y calidad. Esto también rompe la referencia válida: una secuencia 23, 24, 25, 31 termina ofreciendo 31 como valor del dashboard.

Se reprodujo este segundo comportamiento con la consulta original de origin/dev, ingesta SQL real y GET autenticado en PostgreSQL 18 aislado: las dos variantes de TC-M03-177 (Productor e Ingeniero) rechazaron 31 frente al esperado 25. La reproducción usa solo la consulta original en el lanzador de pruebas; no modifica archivos de producción.

## Flujo corregido

1. La ingesta conserva su función SQL, clasificación y telemetría original.
2. El repositorio obtiene la última condición por timestamp_captura e id_telemetria y, separadamente, la última LECTURA_VALIDA del mismo sensor y variable.
3. El dominio transporta ambas referencias sin depender del ORM. La compatibilidad con caché sin historial solo aplica cuando no existe telemetría que identifique la variable actual.
4. El caso de uso conserva el indicador de anomalía junto a la referencia válida y adapta el diagnóstico usando el permiso existente datos_tecnicos_dashboard.
5. El schema publica ambas fechas y la calidad de la referencia operativa. El router conserva JWT, RBAC, alcance por finca y serialización existente.
6. El frontend reutiliza EstadoSensorPills: FUERA_DE_RANGO tiene icono rojo; ERROR_CALIBRACION muestra Requiere calibración al permiso técnico; el Productor recibe En revisión técnica. Tarjeta y detalle identifican la referencia mediante Última lectura válida, con traducción en ambos idiomas.

El resumen de unidades obtiene sensores_con_error de la última condición, evitando depender de una calidad de caché anterior. No se crea una alerta operativa por el error de calibración ni se fuerza un semáforo distinto de las reglas RF-17/RF-58 existentes.

## Contrato resultante

| Campo | Semántica |
|---|---|
| ultimo_valor / ultima_unidad / ultimo_timestamp_captura | Última LECTURA_VALIDA de la variable actual; sin referencia válida, valor y fecha nulos. |
| estado_calidad | Condición de la lectura más reciente; ERROR_CALIBRACION se devuelve nulo sin permiso técnico. |
| estado_calidad_valor_operativo | Nuevo campo opcional: LECTURA_VALIDA cuando existe una referencia válida. |
| timestamp_estado_actual | Nuevo campo opcional: momento de captura de la condición actual, independiente de la fecha del valor operativo. |
| indicador_anomalia / etiqueta_estado | Señalan la condición posterior sin sustituir el valor válido. |
| es_valor_operativo | Describe el valor mostrado: puede ser true con indicador de anomalía si ese valor es una referencia válida anterior. |
| batería / RSSI / SNR | Se conservan para el permiso técnico y se devuelven nulos al resto. |

Ejemplo: 25 LECTURA_VALIDA seguido de 31 FUERA_DE_RANGO devuelve valor 25, calidad actual FUERA_DE_RANGO, calidad del valor LECTURA_VALIDA, indicador true y fechas diferentes. Si posteriormente llega ERROR_CALIBRACION, el Ingeniero identifica el diagnóstico y el Productor conserva solo la indicación genérica, sin datos técnicos. Una nueva lectura válida actualiza el valor y retira la anomalía de la vista actual; el histórico sigue en telemetrias.

## Base de datos y seguridad

Se inspeccionó la base oficial solo en lectura: columnas, función de caché, índices, triggers y RLS. No se ejecutó DDL/DML allí. Las tablas modulo3.telemetrias y estados_actuales_sensores inspeccionadas no tienen RLS/FORCE habilitado; no se atribuye a ellas una protección inexistente. Se preservan las políticas de M09 y el alcance de aplicación por finca.

No hay migración nueva: se reutilizan tablas, columnas e índice idx_telemetria_sensor_captura existentes. El cambio es una proyección de lectura y no corrige ni reescribe el histórico de telemetría. No modifica el trigger de caché ni reemplaza su comportamiento para otros consumidores. La comprobación local de tiempos no acredita capacidad de producción con volúmenes reales.

La base sgpmp_g87_test se migró desde cero hasta 30168ab97bd4. La siembra se realiza con el usuario de pruebas y los GET bajo sgpmp_app, sin superusuario ni BYPASSRLS, con JWT y permisos persistidos. Los privilegios SQL necesarios se aprovisionan únicamente en ese entorno local; no se inventan permisos RBAC ni se deshabilitan triggers o restricciones. Los fixtures conservan transacción exterior y rollback.

## Pruebas

| Grupo final | Aprobadas | Fallidas | Omitidas |
|---|---:|---:|---:|
| tests/telemetry + tests/configuration/test_dev14_parametros_dinamicos.py, fakes y contratos | 656 | 0 | 0 |
| tests/integration/test_issue_678_g87_dashboard_condiciones.py, PostgreSQL 18 + HTTP | 8 | 0 | 0 |
| Total backend distinto | 664 | 0 | 0 |

Los 8 casos reales verifican secuencia 23/24/25/31 bajo ambos permisos; ausencia posterior de calibración (21.7 y 22.3); privacidad; recuperación con 26; llegada tardía; ausencia de referencia válida; caché anterior; aislamiento frente a otra finca real; JWT, RBAC y rol PostgreSQL. Para provocar ausencia de calibración se retira exclusivamente la calibración sembrada en la transacción local de la prueba. No se simula ese fallo alterando una función de producción.

El shim fcntl existe solo en el lanzador temporal de Windows. Las primeras corridas parciales no se suman nuevamente. La corrida original de reproducción tuvo 2 fallos esperados y 6 casos deseleccionados; no se confunde con las corridas finales corregidas.

Evidencias temporales: .pytest_cache/g87_unit_total.xml, g87_pg.xml, g87_pg_antes.log, g87_respuestas_dashboard.json y scripts g87_*. El archivo de respuestas no contiene JWT ni credenciales.

### Frontend y límites

- Componentes reales (EstadoLecturaPill.test.tsx): 15 aprobadas, 0 fallidas, 0 omitidas en la corrida individual final; incluye los 5 escenarios nuevos de G87. Se utiliza el paquete Vitest instalado, un lanzador mínimo temporal con jsdom/setupTests y pool forks. No se modifica la configuración de producción ni se desactivan aserciones.
- Catálogos telemetry: paridad de 781 claves en es-CO y en-US, incluida Última lectura válida / Last valid reading. La corrida conjunta del archivo global i18n no terminó por timeout de arranque del worker de Windows; no se cuenta como aprobada. La paridad del catálogo afectado se verificó por comparación independiente de las claves JSON.
- Presentación en Edge headless: 4 combinaciones aprobadas (390/1280 px × claro/oscuro), con las respuestas HTTP reales capturadas del entorno PostgreSQL aislado. Verifica 25 más anomalía roja, diagnóstico del Ingeniero, privacidad del Productor, recuperación con 26, detalle, teclado/Escape y ausencia de desbordamiento horizontal. Sin errores JavaScript. Se inspeccionaron visualmente las capturas. Es una reproducción de respuestas en componentes reales, no un E2E desplegado ni una conexión continua navegador→API.
- TypeScript de los tipos y componentes de producción modificados: aprobado (exit 0) con tsconfig temporal que conserva las opciones del proyecto. El TypeScript global no pasa por errores en App.tsx (IonApp/IonReactRouter) y LineChartTelemetria.tsx (ReferenceArea/fill), archivos sin cambios frente a origin/dev. No se declara el build global aprobado.
- El script lint del repositorio usa ESLint 9 y no dispone de eslint.config.*; no se declara lint global aprobado. La auditoría premium strict detectó 135 hallazgos en otros archivos, ninguno en los componentes, tipos o CSS del alcance. No se amplía #678 para corregirlos.
- Se agregó DESIGN.md al worktree tomando el contexto y tokens existentes. El linter externo designmd no estaba en la caché npm offline; esa comprobación documental queda pendiente.

Evidencias: backend .pytest_cache/g87_ui_resultado.json, g87-ui-*.png, g87_i18n_paridad.json; frontend do-it/g87/vitest-componentes.log y tsconfig temporal. Las pruebas iniciales con lanzadores bloqueados no se suman a las aprobadas finales. Los artefactos do-it/g87 son temporales e ignorados por Git; no forman parte de la entrega.

La API online y el hook useMonitoreo mantienen todos los campos de la respuesta antes de renderizar. No se cambia la caché offline Dexie; la reproducción visual no valida su fallback. Tampoco se prueban cambios de rol sin reconectar. Estas comprobaciones no se sustituyen por las pruebas de componentes.


## Integración y pendientes

Se deben integrar las ramas de backend y frontend antes de repetir G87 en TEST. Backend entrega el estado posterior; frontend debe incluir FE-10 ya presente en origin/dev y la leyenda de referencia válida de esta entrega. No se ha desplegado en sgpmp_dev/TEST ni se han declarado aprobados oficialmente los TC de QA. No se ha probado firmware ni transporte MQTT externo: se usa la frontera SQL de ingesta común con el backend.

Preservados los archivos ajenos del backend y el UX-CONTRACT.md del checkout original del frontend. No se añaden credenciales, cachés ni evidencias temporales al alcance de entrega.

## Cierre del entorno local

La base exclusiva sgpmp_g87_test fue eliminada y el clúster local quedó detenido. El servidor Vite local se detuvo tras la validación visual. Se conservan evidencias y scripts temporales. No se borraron otras bases ni los archivos ajenos del repositorio.
