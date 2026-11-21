# TC-M03-G126 — RF-59 / CU04 (integridad de solo lectura)

Caso original: **TC-M03-255**. Consultar, filtrar y paginar el historial no crea, modifica ni elimina lecturas históricas. Los dos snapshots de BD deben ser idénticos.

Herramientas: **Newman** para las consultas, más **consultas de BD de solo lectura** (`SELECT` por `/test-control/query`) desde el ejecutor en Node. Sin Cypress ni exportación: la matriz deja la exportación fuera para no depender de M08.

## Conjunto controlado (construido en el sandbox con APIs oficiales)

- **Lecturas:** una unidad QA con **3 sensores** y **6 lecturas válidas por sensor** (18 en total), con timestamps y valores distintos (RF-53).
- **Actor:** Ingeniero de Campo, que tiene lectura del historial.
- **Por qué el conjunto está aislado:** dentro del sandbox ningún proceso externo ve esas filas, así que solo las consultas del RUN pueden alterarlas.
- **Precondiciones `[PRE]`:**
  - el historial del Ingeniero devuelve las 18 lecturas;
  - el snapshot inicial ve las 18 (`modulo3` no tiene RLS: visibilidad completa comprobada, no supuesta);
  - cada consulta responde 200;
  - se recorren al menos dos páginas.

## Snapshots

1. **Contenido:** `row_to_json` de cada fila de:
   - `modulo3.telemetrias` del conjunto. Se seleccionan **por sensor**, así que también se detectan lecturas creadas.
   - Las `vinculaciones_lecturas` y `telemetria_calidad` de esas lecturas, que el historial presenta como contexto (activo y aptitud).
2. **Orden y forma canónica:** las filas se ordenan por clave primaria y se pasan a forma canónica, con las claves ordenadas en todos los niveles. Se calcula un SHA-256 por tabla.
3. **Consultas entre ambos snapshots (6, todas GET al historial):**
   - por unidad, recorriendo páginas de 5;
   - por sensor, página 2;
   - por variable;
   - por estado del dato;
   - por origen, con orden ascendente e incluyendo alertas;
   - por unidad y sensor, con orden descendente.
4. **Comparación por fila y por campo:** lecturas creadas, eliminadas y modificadas, con los campos concretos que cambiaron. No se compara solo el número de filas. El orden de filas o de columnas no produce falsos positivos.

| Aserción | Criterio |
| --- | --- |
| API-255-01 | Las consultas no crean lecturas |
| API-255-02 | Las consultas no eliminan lecturas |
| API-255-03 | Ninguna lectura cambia valores ni atributos (hash idéntico) |
| API-255-04 | Vinculaciones y evaluaciones de calidad de esas lecturas idénticas |

Una consulta de snapshot fallida es **no verificable** (BLOQUEADO), nunca un snapshot vacío.

## Aislamiento, rollback y veredicto

- **Aislamiento:** el testigo es el INSERT del dispositivo en `auditoria.logs_dml`. Se exige 1 dentro del RUN, 0 fuera y 0 tras el rollback.
- **Escrituras:** no hay SQL de escritura.
- **Veredicto:**
  - RECHAZADO: una diferencia entre snapshots con las precondiciones cumplidas.
  - BLOQUEADO: precondiciones, entorno o automatización.

## Dependencias

- **DEV-06:** la credencial del dispositivo está concentrada en `cuerpoLectura`.
- **DEV-02:** si `telemetria_calidad` cambia de esquema, el snapshot lo absorbe (copia cada fila completa).
- **Fecha final:** si el servidor rechaza la fecha de hoy por ser futura (`FECHA_FIN_FUTURA`), se usa la del día anterior y se comprueba que las lecturas sigan visibles.

## Uso

```
node ejecutar_tc_m03_g126.mjs --validar-local
node --test validar_local_g126.mjs
node ejecutar_tc_m03_g126.mjs --ejecutar --ambiente TEST --autorizacion "<referencia>" --tipo evaluacion --aceptar-efectos notificacion-login
```

La ejecución solo procede con autorización de Desarrollo y `QA_AUTORIZADO=SI`. V1 se guarda en `RESULTADOS/<RUN_ID>/` y V2 y siguientes en `EvaluacionVN/RESULTADOS/<RUN_ID>/`.
