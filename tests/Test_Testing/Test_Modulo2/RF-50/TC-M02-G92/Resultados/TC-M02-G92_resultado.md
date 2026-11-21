# RESULTADO — TC-M02-G92

## Resumen ejecutivo

| Dimensión | Resultado |
|---|---|
| VEREDICTO | **BLOQUEADO** |
| Subtipos | CREDENCIAL/SCOPE M04 NO DISPONIBLE; RESTRICCIÓN |
| TC-M02-154 | BLOQUEADO — no ejecutado |
| TC-M02-159 | BLOQUEADO — no ejecutado |
| Tiempo RF50 / GDP API | NO VERIFICADO / NO OBTENIDA |
| GDP esperada BD/QA | 30/31 = 0.9677419354838709677419354839 kg/día |
| Precisión del código local | 0.9677 kg/dia, quantize Decimal(0.0001) |
| Escrituras SQL/API emitidas | 0 |
| Responsables | Desarrollo Backend / Implementación (M04); Responsable QA / Desarrollo Backend (restricción) |

Se comprob? disponibilidad del ambiente y de los datos. No se ejecutaron los dos GET oficiales porque no se dispone de identidad M04 comprobada y el código local evidencia escrituras de acceso/auditoría. No se atribuye un defecto funcional al despliegue sin ejecución. Los reportes Newman corresponden exclusivamente al gate OpenAPI, no a una aprobación de G92.

## Identificación y gate

- Responsable: Juan Esteban. CU12; RF50/RF51; TC-M02-154 y TC-M02-159.
- Fecha/hora inicial: 2026-09-10T15:42:55.015018-05:00.
- Repositorio: https://github.com/Arekkazu/sgpmp-backend.git
- Rama: qa/juan-esteban-m02
- HEAD: 41369ea4ab3948eacb1ab9b2d0549310e285eeae
- Ambiente: https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test
- HTTPS OpenAPI: HTTP 200; ambos contratos encontrados.
- PostgreSQL: SELECT 1 exitoso; current_database=sgpmp_test; transaction_read_only=on.
- Herramientas: SELECT con psycopg2 y Newman.
- Carpeta: RF-50/TC-M02-G92 por solicitud del usuario, prevalece sobre RF-50_RF-51 del documento.

?ltimos commits:
```text
41369ea Agrega variables jwt y cookie a enviroments de back
a729fef Merge branch 'dev' into test
f707e8d chore(release): 1.0.0-rc.35 [skip ci]
f51316f Merge pull request #197 from Arekkazu/feature/rf25-alcance-finca-todos-modulos
d88af48 docs(rf25): documentar alcance por finca y deuda de modelo multi-finca
```
Estado de trabajo capturado; archivos previos ajenos al caso preservados:
```text
?? tests/Test_Testing/Test_Modulo2/RF-40/TC-M02-G43/Resultados/
?? tests/Test_Testing/Test_Modulo2/RF-40/TC-M02-G43/consolidar_evidencias.cjs
?? tests/Test_Testing/Test_Modulo2/RF-40/TC-M02-G43/construir_coleccion.cjs
?? tests/Test_Testing/Test_Modulo2/RF-40/TC-M02-G43/consultas_bd.sql
?? tests/Test_Testing/Test_Modulo2/RF-40/TC-M02-G43/redactar_evidencias.cjs
?? tests/Test_Testing/Test_Modulo2/RF-40/TC-M02-G43/test_tc_m02_g43.json
?? tests/Test_Testing/Test_Modulo2/RF-40/TC-M02-G44/Resultados/
?? tests/Test_Testing/Test_Modulo2/RF-40/TC-M02-G44/construir_coleccion.cjs
?? tests/Test_Testing/Test_Modulo2/RF-40/TC-M02-G44/test_tc_m02_g44.json
?? tests/Test_Testing/Test_Modulo2/RF-40/TC-M02-G45/Resultados/
?? tests/Test_Testing/Test_Modulo2/RF-40/TC-M02-G45/construir_coleccion.cjs
?? tests/Test_Testing/Test_Modulo2/RF-40/TC-M02-G45/test_tc_m02_g45.json
?? tests/Test_Testing/Test_Modulo2/RF-40/TC-M02-G46/Resultados/
?? tests/Test_Testing/Test_Modulo2/RF-40/TC-M02-G46/test_tc_m02_g46.json
?? tests/Test_Testing/Test_Modulo2/RF-40/TC-M02-G47/Resultados/
?? tests/Test_Testing/Test_Modulo2/RF-40/TC-M02-G47/test_tc_m02_g47.py
?? tests/Test_Testing/Test_Modulo2/RF-40/TC-M02-G47/verificar_render_tc_m02_g47.cy.js
?? tests/Test_Testing/Test_Modulo2/RF-40/TC-M02-G48/Resultados/
?? tests/Test_Testing/Test_Modulo2/RF-40/TC-M02-G48/construir_coleccion.cjs
?? tests/Test_Testing/Test_Modulo2/RF-40/TC-M02-G48/test_tc_m02_g48.json
?? tests/Test_Testing/Test_Modulo2/RF-48/TC-M02-G79/Resultados/
?? tests/Test_Testing/Test_Modulo2/RF-48/TC-M02-G79/test_tc_m02_g79.json
?? tests/Test_Testing/Test_Modulo2/RF-48/TC-M02-G80/Resultados/
?? tests/Test_Testing/Test_Modulo2/RF-48/TC-M02-G80/construir_coleccion.cjs
?? tests/Test_Testing/Test_Modulo2/RF-48/TC-M02-G80/test_tc_m02_g80.json
?? tests/Test_Testing/Test_Modulo2/RF-48/TC-M02-G81/Resultados/
?? tests/Test_Testing/Test_Modulo2/RF-48/TC-M02-G81/construir_coleccion.cjs
?? tests/Test_Testing/Test_Modulo2/RF-48/TC-M02-G81/test_tc_m02_g81.json
?? tests/Test_Testing/Test_Modulo2/RF-48/TC-M02-G82/Resultados/
?? tests/Test_Testing/Test_Modulo2/RF-48/TC-M02-G82/test_tc_m02_g82.py
?? tests/Test_Testing/Test_Modulo2/RF-48/TC-M02-G83/Resultados/
?? tests/Test_Testing/Test_Modulo2/RF-48/TC-M02-G83/construir_coleccion.cjs
?? tests/Test_Testing/Test_Modulo2/RF-48/TC-M02-G83/test_tc_m02_g83.json
?? tests/Test_Testing/Test_Modulo2/RF-50/TC-M02-G92/test_tc_m02_g92.json
?? tests/Test_Testing/Test_Modulo2/_datos_prueba/
?? tests/openapi.json
```

## Datos e interpretación independiente

Activo 295, QAJE-DAT-COMPL, INDIVIDUAL, especie 40, estado 1; ciclo desde 2026-06-01. Infraestructura 48, Corral QA JE Origen, activa. Fase 74/ciclo 10 activa. Historial: dos eventos CRECIMIENTO y una FASE_PRODUCTIVA.

| Evento | Fecha UTC | Peso | Unidad |
|---|---|---:|---|
| 224 | 2026-07-15 10:00:00+00:00 | 200.00 | kg |
| 225 | 2026-08-15 10:00:00+00:00 | 230.00 | kg |

Rango previsto: 2026-07-15 a 2026-08-15, inclusivo. Dos pesos en fechas distintas, dentro del ciclo. Cálculo QA con Decimal y diferencia real de fechas:
```text
(230 - 200) / 31 = 0.9677419354838709677419354839 kg/día
```
La implementación local toma primera y última medición por fecha y cuantiza a cuatro decimales. El OpenAPI no documenta esa precisión; no se confirma que el despliegue tenga el mismo HEAD. Esperado de referencia local 0.9677; comparación API, unidad, periodo, variables y fecha de cálculo: NO VERIFICADAS.

## Evidencia SELECT

Conexiones con default_transaction_read_only=on, statement_timeout=15000 y cierre sin commit. No se consultaron valores hash ni secretos de credenciales.

```sql
SELECT table_schema,table_name,column_name,data_type FROM information_schema.columns WHERE (table_schema='modulo1' AND table_name='credenciales_servicio') OR (table_schema='modulo2' AND table_name IN ('eventos_crecimeinto','activos_biologicos')) ORDER BY 1,2,ordinal_position;
```
```json
{
  "columns": [
    "table_schema",
    "table_name",
    "column_name",
    "data_type"
  ],
  "rows": [
    [
      "modulo1",
      "credenciales_servicio",
      "id_credencial_servicio",
      "integer"
    ],
    [
      "modulo1",
      "credenciales_servicio",
      "nombre_servicio",
      "character varying"
    ],
    [
      "modulo1",
      "credenciales_servicio",
      "hash_valor",
      "character varying"
    ],
    [
      "modulo1",
      "credenciales_servicio",
      "es_activo",
      "boolean"
    ],
    [
      "modulo1",
      "credenciales_servicio",
      "fecha_creacion",
      "timestamp with time zone"
    ],
    [
      "modulo1",
      "credenciales_servicio",
      "fecha_revocacion",
      "timestamp with time zone"
    ],
    [
      "modulo2",
      "activos_biologicos",
      "id_activo_biologico",
      "integer"
    ],
    [
      "modulo2",
      "activos_biologicos",
      "id_especie",
      "integer"
    ],
    [
      "modulo2",
      "activos_biologicos",
      "identificador",
      "character varying"
    ],
    [
      "modulo2",
      "activos_biologicos",
      "id_infraestructura",
      "integer"
    ],
    [
      "modulo2",
      "activos_biologicos",
      "tipo",
      "USER-DEFINED"
    ],
    [
      "modulo2",
      "activos_biologicos",
      "fecha_inicio_ciclo",
      "date"
    ],
    [
      "modulo2",
      "activos_biologicos",
      "id_estado",
      "integer"
    ],
    [
      "modulo2",
      "activos_biologicos",
      "descripcion",
      "character varying"
    ],
    [
      "modulo2",
      "activos_biologicos",
      "origen_financiero",
      "USER-DEFINED"
    ],
    [
      "modulo2",
      "activos_biologicos",
      "costo_adquisicion",
      "numeric"
    ],
    [
      "modulo2",
      "activos_biologicos",
      "atributos_dinamicos",
      "jsonb"
    ],
    [
      "modulo2",
      "activos_biologicos",
      "id_usuario",
      "integer"
    ],
    [
      "modulo2",
      "activos_biologicos",
      "fecha_creacion",
      "timestamp with time zone"
    ],
    [
      "modulo2",
      "activos_biologicos",
      "id_dispositivo_iot",
      "integer"
    ],
    [
      "modulo2",
      "activos_biologicos",
      "soporte_documental",
      "character varying"
    ],
    [
      "modulo2",
      "activos_biologicos",
      "detalles_procedencia",
      "character varying"
    ],
    [
      "modulo2",
      "eventos_crecimeinto",
      "id_evento",
      "integer"
    ],
    [
      "modulo2",
      "eventos_crecimeinto",
      "tipo_medicion",
      "character varying"
    ],
    [
      "modulo2",
      "eventos_crecimeinto",
      "valor_medicion",
      "numeric"
    ],
    [
      "modulo2",
      "eventos_crecimeinto",
      "unidad_medida",
      "character varying"
    ],
    [
      "modulo2",
      "eventos_crecimeinto",
      "tipo_agregacion",
      "character varying"
    ],
    [
      "modulo2",
      "eventos_crecimeinto",
      "frecuencia",
      "character varying"
    ],
    [
      "modulo2",
      "eventos_crecimeinto",
      "nuevo_peso_promedio",
      "numeric"
    ],
    [
      "modulo2",
      "eventos_crecimeinto",
      "cantidad_medida",
      "integer"
    ]
  ]
}
```

```sql
SELECT id_activo_biologico,identificador,tipo,id_especie,id_estado,id_infraestructura FROM modulo2.activos_biologicos WHERE identificador='QAJE-DAT-COMPL';
```
```json
{
  "columns": [
    "id_activo_biologico",
    "identificador",
    "tipo",
    "id_especie",
    "id_estado",
    "id_infraestructura"
  ],
  "rows": [
    [
      295,
      "QAJE-DAT-COMPL",
      "INDIVIDUAL",
      40,
      1,
      48
    ]
  ]
}
```

```sql
SELECT id_credencial_servicio,nombre_servicio,es_activo,fecha_revocacion FROM modulo1.credenciales_servicio ORDER BY id_credencial_servicio;
```
```json
{
  "columns": [
    "id_credencial_servicio",
    "nombre_servicio",
    "es_activo",
    "fecha_revocacion"
  ],
  "rows": [
    [
      1,
      "broker_mqtt",
      true,
      null
    ]
  ]
}
```

```sql
SELECT ea.id_eventos,ea.id_activo_biologico,ea.fecha,ec.tipo_medicion,ec.valor_medicion,ec.unidad_medida FROM modulo2.eventos_activos ea JOIN modulo2.eventos_crecimeinto ec ON ec.id_evento=ea.id_eventos WHERE ea.id_activo_biologico=295 AND lower(ec.tipo_medicion)='peso' ORDER BY ea.fecha,ea.id_eventos;
```
```json
{
  "columns": [
    "id_eventos",
    "id_activo_biologico",
    "fecha",
    "tipo_medicion",
    "valor_medicion",
    "unidad_medida"
  ],
  "rows": [
    [
      224,
      295,
      "2026-07-15 10:00:00+00:00",
      "PESO",
      "200.00",
      "kg"
    ],
    [
      225,
      295,
      "2026-08-15 10:00:00+00:00",
      "PESO",
      "230.00",
      "kg"
    ]
  ]
}
```

```sql
SELECT id_activo_biologico,identificador,tipo,fecha_inicio_ciclo,id_estado,id_infraestructura FROM modulo2.activos_biologicos WHERE id_activo_biologico=295;
```
```json
{
  "columns": [
    "id_activo_biologico",
    "identificador",
    "tipo",
    "fecha_inicio_ciclo",
    "id_estado",
    "id_infraestructura"
  ],
  "rows": [
    [
      295,
      "QAJE-DAT-COMPL",
      "INDIVIDUAL",
      "2026-06-01",
      1,
      48
    ]
  ]
}
```

```sql
SELECT * FROM modulo2.gestiones_fases WHERE id_activo_biologico=295;
```
```json
{
  "columns": [
    "id_gestion_fases",
    "id_activo_biologico",
    "id_ciclo_productiva",
    "fecha_inicio",
    "fecha_finalizacion",
    "es_activa",
    "id_usuario",
    "motivo_cambio"
  ],
  "rows": [
    [
      74,
      295,
      10,
      "2026-06-01 08:00:00+00:00",
      null,
      true,
      1,
      "Fase inicial sembrada para pruebas M02 (Juan Esteban)."
    ]
  ]
}
```

```sql
SELECT categoria,count(*) FROM modulo2.vw_rf46_historial_completo_activo WHERE id_activo_biologico=295 GROUP BY categoria;
```
```json
{
  "columns": [
    "categoria",
    "count"
  ],
  "rows": [
    [
      "CRECIMIENTO",
      2
    ],
    [
      "FASE_PRODUCTIVA",
      1
    ]
  ]
}
```

```sql
SELECT id_infraestructura,nombre,es_activo FROM modulo9.infraestructuras WHERE id_infraestructura=48;
```
```json
{
  "columns": [
    "id_infraestructura",
    "nombre",
    "es_activo"
  ],
  "rows": [
    [
      48,
      "Corral QA JE Origen",
      true
    ]
  ]
}
```

## Contrato vivo

Ambos endpoints exponen cabecera authorization y respuestas 200/400/401/403/404/422. El OpenAPI no declara securitySchemes; esto no demuestra acceso público. Código local: Bearer JWT de usuario y permiso de consulta. No se demuestra soporte M04.
```json
{
  "/activos-biologicos/{id_activo}/indicadores": {
    "get": {
      "tags": [
        "Activos Biológicos"
      ],
      "summary": "Consultar indicadores zootécnicos del activo biológico (CU12 - RF-51)",
      "operationId": "consultar_indicadores_activos_biologicos__id_activo__indicadores_get",
      "parameters": [
        {
          "name": "id_activo",
          "in": "path",
          "required": true,
          "schema": {
            "type": "integer",
            "title": "Id Activo"
          }
        },
        {
          "name": "fecha_inicio",
          "in": "query",
          "required": false,
          "schema": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "description": "Filtro fecha inicio (YYYY-MM-DD)",
            "title": "Fecha Inicio"
          },
          "description": "Filtro fecha inicio (YYYY-MM-DD)"
        },
        {
          "name": "fecha_fin",
          "in": "query",
          "required": false,
          "schema": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "description": "Filtro fecha fin (YYYY-MM-DD)",
            "title": "Fecha Fin"
          },
          "description": "Filtro fecha fin (YYYY-MM-DD)"
        },
        {
          "name": "tipo_indicador",
          "in": "query",
          "required": false,
          "schema": {
            "type": "string",
            "description": "Tipo de indicador: CRECIMIENTO | PRODUCCION | SANITARIO | EFICIENCIA | TODOS",
            "default": "TODOS",
            "title": "Tipo Indicador"
          },
          "description": "Tipo de indicador: CRECIMIENTO | PRODUCCION | SANITARIO | EFICIENCIA | TODOS"
        },
        {
          "name": "authorization",
          "in": "header",
          "required": false,
          "schema": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "title": "Authorization"
          }
        }
      ],
      "responses": {
        "200": {
          "description": "Successful Response",
          "content": {
            "application/json": {
              "schema": {
                "$ref": "#/components/schemas/IndicadoresActivoResponse"
              }
            }
          }
        },
        "400": {
          "content": {
            "application/json": {
              "schema": {
                "$ref": "#/components/schemas/ErrorResponse"
              }
            }
          },
          "description": "Bad Request"
        },
        "401": {
          "content": {
            "application/json": {
              "schema": {
                "$ref": "#/components/schemas/ErrorResponse"
              }
            }
          },
          "description": "Unauthorized"
        },
        "403": {
          "content": {
            "application/json": {
              "schema": {
                "$ref": "#/components/schemas/ErrorResponse"
              }
            }
          },
          "description": "Forbidden"
        },
        "404": {
          "content": {
            "application/json": {
              "schema": {
                "$ref": "#/components/schemas/ErrorResponse"
              }
            }
          },
          "description": "Not Found"
        },
        "422": {
          "description": "Validation Error",
          "content": {
            "application/json": {
              "schema": {
                "$ref": "#/components/schemas/HTTPValidationError"
              }
            }
          }
        }
      }
    }
  },
  "/activos-biologicos/{id_activo}/datos-consolidados": {
    "get": {
      "tags": [
        "Activos Biológicos"
      ],
      "summary": "Exponer datos consolidados del activo biológico para módulos analíticos (CU12 - RF-50)",
      "operationId": "consultar_datos_consolidados_activos_biologicos__id_activo__datos_consolidados_get",
      "parameters": [
        {
          "name": "id_activo",
          "in": "path",
          "required": true,
          "schema": {
            "type": "integer",
            "title": "Id Activo"
          }
        },
        {
          "name": "tipo_dato",
          "in": "query",
          "required": false,
          "schema": {
            "type": "string",
            "description": "Sección de datos: eventos | fases | estado | metricas | todos",
            "default": "todos",
            "title": "Tipo Dato"
          },
          "description": "Sección de datos: eventos | fases | estado | metricas | todos"
        },
        {
          "name": "fecha_inicio",
          "in": "query",
          "required": false,
          "schema": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "description": "Filtro fecha inicio (YYYY-MM-DD)",
            "title": "Fecha Inicio"
          },
          "description": "Filtro fecha inicio (YYYY-MM-DD)"
        },
        {
          "name": "fecha_fin",
          "in": "query",
          "required": false,
          "schema": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "description": "Filtro fecha fin (YYYY-MM-DD)",
            "title": "Fecha Fin"
          },
          "description": "Filtro fecha fin (YYYY-MM-DD)"
        },
        {
          "name": "pagina",
          "in": "query",
          "required": false,
          "schema": {
            "type": "integer",
            "minimum": 1,
            "default": 1,
            "title": "Pagina"
          }
        },
        {
          "name": "page_size",
          "in": "query",
          "required": false,
          "schema": {
            "type": "integer",
            "maximum": 100,
            "minimum": 1,
            "default": 20,
            "title": "Page Size"
          }
        },
        {
          "name": "authorization",
          "in": "header",
          "required": false,
          "schema": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "title": "Authorization"
          }
        }
      ],
      "responses": {
        "200": {
          "description": "Successful Response",
          "content": {
            "application/json": {
              "schema": {
                "$ref": "#/components/schemas/DatosConsolidadosResponse"
              }
            }
          }
        },
        "400": {
          "content": {
            "application/json": {
              "schema": {
                "$ref": "#/components/schemas/ErrorResponse"
              }
            }
          },
          "description": "Bad Request"
        },
        "401": {
          "content": {
            "application/json": {
              "schema": {
                "$ref": "#/components/schemas/ErrorResponse"
              }
            }
          },
          "description": "Unauthorized"
        },
        "403": {
          "content": {
            "application/json": {
              "schema": {
                "$ref": "#/components/schemas/ErrorResponse"
              }
            }
          },
          "description": "Forbidden"
        },
        "404": {
          "content": {
            "application/json": {
              "schema": {
                "$ref": "#/components/schemas/ErrorResponse"
              }
            }
          },
          "description": "Not Found"
        },
        "422": {
          "description": "Validation Error",
          "content": {
            "application/json": {
              "schema": {
                "$ref": "#/components/schemas/HTTPValidationError"
              }
            }
          }
        }
      }
    }
  }
}
```

## Diagnóstico y atribución

1. **M04 no disponible en las fuentes revisadas.** SELECT de credenciales_servicio devuelve solo broker_mqtt activo. No hay claves M04/scope/service/module en .env.test o .env.dev ni nombres M04 en el entorno del proceso. No se obtuvo ni cre? token, ni se us? una cuenta humana. No se afirma inexistencia global de M04: falta una credencial/scope utilizable y verificable para QA. Equipo: Desarrollo Backend / Implementación. Acción: entregar configuración M04 existente y demostrar permiso RF50/RF51 en TEST.
2. **Restricción de cero escrituras.** get_current_user actualiza ultimo_acceso y hace commit (dependencies.py:126–127). ConsultarDatosConsolidadosUseCase registra DATOS_ANALITICOS_CONSULTADOS y commit (57–65); ConsultarIndicadoresUseCase registra INDICADOR_CALCULADO y commit (56–64). SqlAlchemyBitacoraAuditoriaRepository.registrar hace add/flush. El router inyecta el repositorio en ambos flujos. Evidencia estática del HEAD local; efectos del despliegue no reproducidos. Equipo: Responsable QA / Desarrollo Backend. Acción: resolver formalmente alcance de la regla cero escrituras y confirmar comportamiento del despliegue antes de ejecutar.

Atribución: NO CONCLUYENTE para producto; bloqueos de configuración y restricción del paquete. Categoría: Configuración/ambiente y RESTRICCIÓN. Severidad QA propuesta: Medio (bloqueo específico del caso, sin pérdida observada). Tiempo máximo: 2 días hábiles; fecha límite de gestión: 2026-09-14 15:43 America/Bogota. No es un SLA acordado ni prueba de defecto en producción. Activo 295, consumidor M04; requests previstos en la colección; obtenido: no ejecutado; evidencia API funcional: no disponible.

## Verificaciones oficiales

| V | Resultado | Evidencia |
|---|---|---|
| V1 | NO VERIFICADO — bloqueado | M04 no disponible en fuentes revisadas |
| V2 | NO VERIFICADO — bloqueado | GET oficial no ejecutado |
| V3 | NO VERIFICADO — bloqueado | GET oficial no ejecutado |
| V4 | NO VERIFICADO — bloqueado | GET oficial no ejecutado |
| V5 | NO VERIFICADO — bloqueado | GET oficial no ejecutado |
| V6 | NO VERIFICADO — bloqueado | GET oficial no ejecutado |
| V7 | NO VERIFICADO — bloqueado | GET oficial no ejecutado |
| V8 | NO VERIFICADO — bloqueado | GET oficial no ejecutado |
| V9 | 0 escrituras emitidas; comportamiento GET NO VERIFICADO | GET oficial omitido por restricción |
| V10 | CUMPLE precondición | SELECT de pesos y fecha inicio ciclo |
| V11 | CUMPLE precondición | SELECT de pesos y fecha inicio ciclo |
| V12 | NO VERIFICADO — bloqueado | GET oficial no ejecutado |
| V13 | NO VERIFICADO — bloqueado | GET oficial no ejecutado |
| V14 | NO VERIFICADO — bloqueado | GET oficial no ejecutado |
| V15 | NO VERIFICADO — bloqueado | GET oficial no ejecutado |
| V16 | NO VERIFICADO — bloqueado | GET oficial no ejecutado |
| V17 | NO VERIFICADO — bloqueado | GET oficial no ejecutado |
| V18 | 0 escrituras emitidas; comportamiento GET NO VERIFICADO | GET oficial omitido por restricción |

## Artefactos y cumplimiento

- test_tc_m02_g92.json: gate ejecutable y dos plantillas oficiales con skipRequest incondicional. RF50 requiere completar comparación exhaustiva de datos/eventos antes de habilitar; el guard evita presentarla como prueba lista/aprobada.
- reporte_tc_m02_g92.html y reporte_tc_m02_g92.json: ejecución real Newman del gate únicamente.
- SETUP SQL/API de escritura: 0. POST/PUT/PATCH/DELETE: 0. GET oficiales: 0 de 2.
- No se modificó código del producto; no hubo commit/push ni creación de datos, tokens o scopes.
- No se ejecutaron escenarios negativos G93–G97.
- Cero cambios funcionales realizados por QA; no se afirma ausencia de cambios concurrentes ajenos.
- Veredicto final: **BLOQUEADO**, nunca APROBADO.

Validación Newman del gate: 1 solicitud GET OpenAPI, HTTP 200, 1086 ms, 3 assertions aprobadas, 0 fallos. Este tiempo no corresponde a RF50. Se verificó que el JSON de ejecución contiene únicamente OpenAPI.
