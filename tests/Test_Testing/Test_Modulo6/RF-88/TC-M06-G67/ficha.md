# TC-M06-G67 — RF-88

Caso reconstruido en la rama `laura` a partir del código y del esquema publicados. No sustituye una ejecución contra TEST.

## Qué cubre cada escenario

| Escenario | Intención | Clasificación en esta rama | Motivo |
|---|---|---|---|
| TC-M06-01 | Reconocimiento inicial por el flujo del RF-82 activando COSTO | BLOQUEADO | No hay router, caso de uso ni DTO. `src/financial_valuation` solo recibe la provisión del RF-79. `main.py` no registra reconocimientos. |
| TC-M06-02 | Activar COSTO sin precio de mercado vigente | BLOQUEADO | No hay operación autónoma. `AUTONOMO_CONTADOR` existe en el enum SQL. Ningún caso de uso escribe `ACTIVO_MARCADO_SIN_MERCADO`. |
| TC-M06-03 | Excepción a COSTO con precio vigente, sin justificación | BLOQUEADO | No hay operación ni DTO de esa excepción. No se reutiliza `justificacion` de otro flujo. |
| TC-M06-04 | Excepción a COSTO con precio vigente y justificación | BLOQUEADO | No hay contrato verificado para enviar ni validar esa justificación. |

Aprobación global prevista al ejecutar: `(0 / 4) * 100 = 0`. Un BLOQUEADO no es APROBADO ni RECHAZADO.

## Qué sí existe, y por qué no alcanza

- Esquema `modulo6.reconocimientos_iniciales`, con `indicador_valoracion` `VALOR_RAZONABLE` o `VALORACION_POR_COSTO`, en `alembic/baseline/esquema_baseline.sql`.
- Tabla `modulo6.valoraciones_por_costos`, escenarios `INICIAL_RF82` y `AUTONOMO_CONTADOR`. La columna `justificacion` es nullable; el comentario deja su obligatoriedad a una capa de negocio que no está en `src`.
- Triggers `fn_tgr_m06_12_valor_contable_no_negativo` y `fn_tgr_m06_20_deterioro_positivo`. El segundo exige justificación del deterioro económico, no de la excepción para pasar de valor razonable a COSTO.
- Enum `ACTIVO_MARCADO_SIN_MERCADO` en `enum_auditorias_financieras_tipo_evento_auditoria`. No hay `INSERT` ni caso de uso que lo escriba.
- `POST /suministros/nic41` es el RF-79. La colección lo excluye del inventario y no lo llama.

## Ejecución

Desde `tests/Test_Testing`:

```powershell
.\correr_newman.ps1 -Caso G67 -Modulo 6 -Rf RF-88
```

El runner oficial resuelve `Test_Modulo6/RF-88/TC-M06-G67/tc-m06-g67.json` y escribe `resultados/resultado_TC-M06-G67.html`. No hace falta otro script.

La colección no referencia credenciales ni el secreto de sandbox, así el runner no los pide. La única solicitud es `GET https://api.inmero.co/api-sgpmp-test/openapi.json`. No hay teardown: esta corrida no crea datos y no debe afirmar que algo fue eliminado.

Newman quedará en rojo mientras los cuatro escenarios sigan bloqueados. Ese rojo es la constancia del bloqueo, no un rechazo funcional del backend.
