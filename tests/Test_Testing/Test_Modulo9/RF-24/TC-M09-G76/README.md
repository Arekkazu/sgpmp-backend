# TC-M09-G76 — RF-24, precondiciones de integridad de la calibración

Responsable QA Juan Esteban. Solo TEST real. No ejecutar G74 ni G75 desde aquí. No
avanzar a otro grupo. Grupo de API: **sin Cypress, sin mocks, sin PostgreSQL**.

Ejecución `run-20260906` concluida. Decisión general: **APROBADO**.
TC-M09-146 y TC-M09-147, ambos APROBADOS. Sin defectos que reportar.
Consultar `RESULTADOS/run-20260906/TC-M09-G76_resultado.md`.

| Caso | GIVEN | WHEN | THEN |
|---|---|---|---|
| TC-M09-146 | Dispositivo existente pero `es_activo=false`, con sensor propio, área correcta y valor interior del rango | POST de calibración | **422** `DISPOSITIVO_INACTIVO`, sin calibración creada y sin alterar históricos |
| TC-M09-147 | Dispositivo activo, sensor suyo, área correcta conocida y **otra área real** no asociada al sensor | POST de calibración con esa otra área | **400** `SENSOR_AREA_INVALIDA` por conflicto de ubicación, sin persistencia y con los históricos intactos |

## Contrato revisado una sola vez (solo lectura)

- `POST /configuracion/sensores/{id_sensor}/calibrar`, éxito 201.
- Dispositivo inactivo → `DISPOSITIVO_INACTIVO` (`BusinessRuleError`) → **422**.
- Sensor no asociado al área → `SENSOR_AREA_INVALIDA` (`ValidationError`,
  `field: id_infraestructura`) → **400**.
- Ambos coinciden con RF-24: **sin `CONTRACT_REQUIREMENT_MISMATCH`**, no hubo que
  ajustar ninguna expectativa.
- Orden de validación: dispositivo existe → **activo** → sensor existe → pertenece al
  dispositivo → **asociación de área vigente** → valor decimal → rango técnico. Cada
  payload supera todas las reglas anteriores a la suya, así que el rechazo observado
  solo puede venir de la regla bajo prueba.

## El área alternativa de TC-147 debe existir de verdad

`GET /configuracion/infraestructuras/999` devuelve **404
`INFRAESTRUCTURA_NO_ENCONTRADA`**: usar el 999 del ejemplo de la matriz probaría
«área inexistente», no «asociación incorrecta». La automatización descubre un área
**real**, comprueba su existencia con un GET directo (200), verifica que es distinta
de la correcta y que el historial de asociaciones del sensor no la contiene. Solo
entonces la envía.

## Datos

Descubiertos dinámicamente, sin IDs supuestos: para TC-146 un dispositivo que **ya
estaba inactivo** en TEST —nunca se desactiva ninguno— con sensor propio y asociación
de área vigente; para TC-147 un dispositivo activo con sensor propio, su área vigente
y un área alternativa real. El valor se calcula como punto **interior** del rango
técnico publicado por `GET /configuracion/sensores/rangos-calibracion`, con
aritmética decimal exacta: aquí no se prueban fronteras.

La selección **prefiere sensores con calibraciones previas**, para que la
comprobación de «históricos intactos» tras el rechazo sea significativa y no vacía.

## Requisitos y ejecución

Ya instalados, no se instala nada: Newman 6.2.2 y `newman-reporter-htmlextra` 1.23.1.

Variables de proceso: `QA_EMAIL` y `QA_PASSWORD` (Ingeniero de campo), `G76_RUN_ID`,
`G76_CASE` (`TC-M09-146` | `TC-M09-147`) y `G76_INTENTO` (1 o 2). Las credenciales
nunca se escriben en archivos. El runner aborta si el actor no tiene la acción de
creación sobre el recurso 12, para no confundir un 403 con un fallo de la regla.

```
NODE_PATH=<npm root -g>  node run-newman.cjs      # una invocación = un original
NODE_PATH=<npm root -g>  node verificar-cierre.cjs # GET final + escaneo de secretos
```

Presupuesto por original: **máximo 2 POST**, implementado y no solo documentado; el
runner rechaza un tercero y también sobrescribir la evidencia de un intento ya
registrado. No se reintenta un PASS. Si una calibración inválida llegara a persistir
o un histórico resultara alterado, el runner marca `STOP_ALL`: detener sin limpiar,
sin borrar y sin restaurar.

## Evidencia

`RESULTADOS/<G76_RUN_ID>/` con el JSON sanitizado por original, los datos y
preflight, el plan de descubrimiento, la verificación final de solo lectura, el
escaneo de secretos, el estado de Git y el informe; los HTML reales de htmlextra en
`RESULTADOS/<G76_RUN_ID>/newman/`.

Estado inicial: ambas ramas en `qa/juan-esteban-m09`. SHAs locales: backend
`adc3932b9f0293a76ebec7e89ed877274791b6a1`, frontend
`966621df4e2c6a1f2c9233ea5ebefbb9e3bc2f56`. SHA desplegado no confirmado.
