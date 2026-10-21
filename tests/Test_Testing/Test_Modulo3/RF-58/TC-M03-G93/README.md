# TC-M03-G93 — TC-M03-184 (RF-58 / CU04)

Matriz: `Casos_Prueba(Modulo3 Agrupado).csv`, fila G93 (flujo alterno E1).

## Variantes del caso

| Variante | Origen de los datos | Estado |
| --- | --- | --- |
| Unidad QA nueva sin lecturas | Se crea en el sandbox: finca compartida o creada con acceso del Productor, y área QA | Construida |
| Unidad con todos los sensores `SIN_SEÑAL` | Se descubre entre las unidades del Productor | Dependencia de RF-60 |

La variante `SIN_SEÑAL` depende de RF-60. La transición la produce la tarea periódica global, que no ve el sandbox, y no existe un disparador aislado. No se fuerza por SQL ni se simula. Si no se descubre, esa variante queda bloqueada y el caso no se aprueba.

## Aserciones

Son aserciones, no condiciones previas:

- La unidad nueva aparece en el dashboard.
- Su estado es GRIS.
- Se muestra el mensaje «Sin datos disponibles».
- Se muestra la fecha histórica, si existe.
- No hay valores fabricados.
- No hay errores 5xx.

## Aislamiento y rollback

- **Testigo:** el INSERT del área en `auditoria.logs_dml`, identificado por `id_infraestructura` y por el nombre del RUN.
- **Por qué ese testigo:** el trigger `fn_auditoria_dml` es `SECURITY DEFINER` y no tiene condiciones, y el esquema `auditoria` no tiene RLS. En cambio, `modulo9.infraestructuras` tiene RLS: desde una transacción sin identidad devolvería 0 siempre y no probaría nada.
- **Qué se exige:**
  - dentro del RUN, 1;
  - desde otra transacción, 0;
  - después del rollback, 0.
- **Consulta fallida:** si la consulta falla (por ejemplo, porque el rol no tiene SELECT), el resultado es «no verificable», nunca 0. En ese caso el aislamiento no se declara demostrado y el RUN se detiene antes de los escenarios.

## Veredicto propuesto

- **BLOQUEADO:** fallos de entorno, de rollback, de precondición `[PRE]` o del hook de Cypress (login).
- **RECHAZADO:** solo un criterio `[ASSERT]` incumplido con respuesta real.

## Uso

Validación local, sin conexiones a TEST ni DEV:

```
node ejecutar_tc_m03_g93.mjs --validar-local
node --test validar_local_g93.mjs
```

Ejecución futura, solo con autorización de Desarrollo y `QA_AUTORIZADO=SI`:

```
node ejecutar_tc_m03_g93.mjs --ejecutar --ambiente TEST --autorizacion "<referencia>" --tipo evaluacion --aceptar-efectos notificacion-login
```

- `--tipo reintento` conserva la versión.
- V1 se guarda en `RESULTADOS/<RUN_ID>/`; V2 y siguientes, en `EvaluacionVN/RESULTADOS/<RUN_ID>/`.
- Cada RUN produce un informe Markdown y `evidencia.json`, más una captura de la unidad si aplica.
