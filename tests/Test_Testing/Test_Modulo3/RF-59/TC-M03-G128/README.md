# TC-M03-G128 — RF-59 / CU04 (autenticación, OWASP API2)

Caso original: **TC-M03-257**. El historial y la exportación exigen un token válido. Las seis combinaciones deben responder **HTTP 401** sin devolver lecturas, estadísticas, alertas, metadatos ni archivos.

| Endpoint | Sin token | Token expirado | Firma manipulada |
| --- | --- | --- | --- |
| `GET /iot/monitoreo/historial` | HISTORIAL_SIN_TOKEN | HISTORIAL_EXPIRADO | HISTORIAL_FIRMA |
| `GET /iot/monitoreo/historial/exportar` | EXPORTAR_SIN_TOKEN | EXPORTAR_EXPIRADO | EXPORTAR_FIRMA |

Herramienta: **Newman**, orquestado desde Node. Sin Cypress.

## Aserciones (en cada una de las seis)

- **API-257-01:** HTTP 401.
- **API-257-02:** la respuesta no expone información. Se revisa todo el JSON, a cualquier profundidad, en busca de `items`, `estadisticas`, `total`, `filtros_aplicados`, `rango_real_datos`, `paginas_totales`, `sensores`, `alertas` y `resumen_unidades`. Se comprueba además que no aparezcan los nombres del sensor y la unidad del escenario, y que no haya archivo (`Content-Disposition` de adjunto, o tipo PDF, Excel, CSV u `octet-stream`).
- **INFO:** el `error_code` devuelto (por ejemplo, `TOKEN_REQUERIDO`, `TOKEN_EXPIRADO` o `TOKEN_INVALIDO`).

Las peticiones llevan filtros y parámetros válidos, de modo que la autenticación es el único elemento inválido. Las verificaciones 401 no dependen de M08.

## Precondiciones `[PRE]`

- **Control:** con el token válido, el historial responde 200 con las lecturas del escenario. Así consta que los 401 se deben a la autenticación y que hay datos que podrían exponerse.
- **Escenario:** una unidad QA con un sensor y una lectura, construida en el sandbox con APIs oficiales.

## Tokens

- **Sin token:** la petición no lleva cabecera `Authorization`.
- **Firma manipulada:** se toma un token **válido del propio RUN** (login oficial del Ingeniero) y se invierte un bit del primer byte de la firma. La cabecera y el contenido quedan intactos, así que el token es estructuralmente válido y su firma no corresponde.
- **Expirado:** un JWT **emitido por el sistema**. No se fabrica ni se altera ningún reloj.
  1. `--preparar-token-expirable` (requiere la misma autorización) inicia sesión como Ingeniero por `POST /sesiones/` dentro de un RUN de sandbox. Guarda el token **fuera del repositorio**, en `~/.sigab-qa/TC-M03-G128/token_emitido.json` (permisos 600), con su huella SHA-256, el RUN de emisión y los claims `sub`, `jti`, `iat` y `exp`.
  2. El rollback elimina la sesión, así que el token **nunca es utilizable**. El servidor comprueba la expiración (`TOKEN_EXPIRADO`) antes de consultar la sesión.
  3. `--ejecutar` lo usa solo si se cumplen todas estas condiciones: su `exp`, más la tolerancia `JWT_LEEWAY` (30 s) y un margen de 120 s, ya pasó; la huella coincide; la procedencia es el login oficial; y su `sub` es la cuenta del Ingeniero.
  4. Mientras no expire (`JWT_EXPIRE_HOURS`, 8 h por defecto), las dos variantes con token expirado quedan **BLOQUEADAS**, con la fecha en que estará disponible. Las otras cuatro se evalúan igual.
  5. El mismo token sirve para V2 y siguientes.
- **En la evidencia** no se registran tokens: solo huellas parciales y fechas.

## Veredicto

- RECHAZADO: una combinación responde distinto de 401 o expone información, con el control previo cumplido. Se conserva aunque falte el token expirado.
- BLOQUEADO: falta el token expirado o hay fallos de precondición, entorno o automatización.
- APROBADO: solo con las seis combinaciones verificadas.

## Uso

```
node ejecutar_tc_m03_g128.mjs --validar-local
node --test validar_local_g128.mjs
node ejecutar_tc_m03_g128.mjs --preparar-token-expirable --ambiente TEST --autorizacion "<referencia>" --aceptar-efectos notificacion-login
# al menos 8 h después (o lo que fije JWT_EXPIRE_HOURS en TEST):
node ejecutar_tc_m03_g128.mjs --ejecutar --ambiente TEST --autorizacion "<referencia>" --tipo evaluacion --aceptar-efectos notificacion-login
```

Ambas operaciones requieren autorización de Desarrollo y `QA_AUTORIZADO=SI`. V1 se guarda en `RESULTADOS/<RUN_ID>/` y V2 y siguientes en `EvaluacionVN/RESULTADOS/<RUN_ID>/`.
