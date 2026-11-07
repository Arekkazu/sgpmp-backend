# Resultado — TC-M02-G43

**RF-40 · Registro exitoso de evento de crecimiento**  
**Veredicto: APROBADO**

Se ejecutaron tres ciclos independientes sobre el ambiente TEST HTTPS, cada uno con la secuencia `ANTES → POST → DESPUÉS`. El SETUP se limitó a consultas `GET` y `SELECT`; no se ejecutaron escrituras SQL ni siembra de datos.

| Actor | Activo individual | Evento oficial | Conteo antes → después | Newman |
|---|---:|---:|---:|---|
| Productor (usuario 35) | 279 | 232 | 2 → 3 | 8 solicitudes, 20 aserciones, 0 fallas |
| Veterinario (usuario 3) | 311 | 229 | 0 → 1 | 8 solicitudes, 20 aserciones, 0 fallas |
| Ingeniero de campo (usuario 4) | 312 | 233 | 2 → 3 | 8 solicitudes, 19 aserciones, 0 fallas |

En los tres POST oficiales se usó `tipo_medicion=PESO`, `valor_medicion=250`, `unidad_medida=kg` y fecha `2026-09-09T23:01:00Z`. Los activos estaban en estado `ACTIVO`, eran de tipo `INDIVIDUAL`, pertenecían al actor correspondiente y tenían una fase productiva activa. Por ser individuales, el cuerpo omitió `tipo_agregacion`.

## Validaciones

| Validación | Productor | Veterinario | Ingeniero de campo | Evidencia |
|---|---|---|---|---|
| V1. El POST crea el evento | OK, HTTP 201 | OK, HTTP 201 | OK, HTTP 201 | Reportes Newman oficiales |
| V2. Persistencia PESO=250 kg | OK | OK | OK | Historial API y SELECT posterior |
| V3. Aparición en historial | OK | OK | OK | `GET /historial` |
| V4. Orden cronológico | OK | OK | OK | Aserciones Newman sobre historial |
| V5. Autor correcto | usuario 35 | usuario 3 | usuario 4 | Respuesta POST y SELECT |
| V6. Auditoría RF40 exitosa | OK | OK | OK | GET de auditoría para Productor/Veterinario; SELECT de bitácora para los tres |
| V7. Incremento de un registro | 2→3 | 0→1 | 2→3 | Historial API y SELECT posterior |

La cuenta del Ingeniero recibe HTTP 403 al consultar `/activos-biologicos/auditoria`: ese endpoint corresponde a RF-52 y exige el permiso independiente del recurso 31. Esto no afecta el registro RF-40 ni su auditoría: la consulta `SELECT` confirma el registro de bitácora exitoso del evento 233, asociado al usuario 4 y al activo 312. El diagnóstico previo con un observador autorizado también confirmó que la bitácora era legible cuando se dispone de ese permiso.

## Evidencia

- [Índice consolidado Newman](reporte_tc_m02_g43.html) y su [JSON](reporte_tc_m02_g43.json).
- Reportes Newman nativos: [Productor](reporte_productor_tc_m02_g43.html), [Veterinario](reporte_veterinario_tc_m02_g43.html) e [Ingeniero](reporte_ingeniero_tc_m02_g43.html).
- [Respuestas HTTP resumidas](respuestas_http.json), [consulta final de los tres eventos oficiales](bd_eventos_oficiales_final.log), [auditoría consultada por SELECT](bd_auditoria_final.log) y [verificación posterior del Ingeniero](bd_ingeniero_final_despues.log).
- [Inventario de escrituras](inventario_escrituras.json): conserva los cuatro intentos metodológicos previos y los excluye del veredicto. Los únicos eventos oficiales son 232, 229 y 233.

## Correcciones de la evidencia

Durante la ejecución se identificaron y corrigieron dos errores de automatización antes de definir el resultado: para activos individuales se verificó el crecimiento con `/historial` en lugar de `/eventos`, que es exclusivo de activos poblacionales; y las repeticiones oficiales del Productor e Ingeniero usaron una fecha posterior a los intentos iniciales. Las ejecuciones oficiales se realizaron de nuevo y son las que respaldan este informe.

No se modificó código fuente, no hubo commit ni push.
