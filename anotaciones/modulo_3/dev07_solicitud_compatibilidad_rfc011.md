# DEV-07 — Compatibilidad adicional RF-53/RF-62 / AIOT-SPEC-01

2026-10-19. Documento preparado; no enviado a otros responsables.

## Lo que ya cubre DB-03

`65541db23c71` ya define `observaciones_vision.fecha_inicio_ventana` y
`json_version_cascada`, además de los campos de heartbeat. No se solicita otra
migración para esos campos. El retiro de buffers corresponde a la otra parte
del lote y no bloquea la ingesta D4.

El usuario informa DB-03 aplicada. La conexión remota autorizada consultada a
`sgpmp_dev` por 5447 y la local `.env` a `integrador` por 5432 no mostraron esos
campos en `pg_catalog`. Se necesita confirmar el destino de despliegue para
alinear las verificaciones; no se afirma que falte en todos los entornos.

## Diferencias adicionales comprobadas

Los RF entregados, actualizados 2026-10-16, integran formalmente RFC-011 y
AIOT-SPEC-01. AN-1 no puede seguir describiéndose simplemente como ausencia
de especificación. La discrepancia ahora es de compatibilidad con catálogo,
configuración y transporte existentes.

| Responsabilidad | Diferencia real | Cambio o decisión mínima |
|---|---|---|
| Análisis / AIoT | D4 exige `calidad.n_tracks`; RF-53 agrega `n_individuos_observados`, `tipo_dato`, `origen` | Confirmar el sobre consolidado y procedencia de todos los campos; tracks no equivale a individuos y no se completa por inferencia |
| DBA / M03 | La tabla no tiene columnas para esos campos adicionales | Definir almacenamiento explícito con sus tipos normativos; no mezclar esos datos dentro del vector o versiones |
| DBA / RF-62 | CHECK de estado solo admite `CALIBRADA`, `DEGRADADA`, `SIN_DETECCION` | Habilitar catálogo normativo `CALIBRADO`, `EN_CALIBRACION`, `SIN_LINEA_BASE`, preservando registros históricos y acordando transición; no equiparar estados de significado distinto |
| DBA / RF-62 | CHECK de clase solo admite `APTO`, `APTO_CON_RESERVA`, `NO_APTO` | Acordar persistencia de las clases normativas `OPTIMA`, `DEGRADADA`, `NO_APTA` de visión sin alterar clases escalares |
| M09 / DBA | No hay configuración persistida de calidad de visión | Incorporar fuente M09 para pesos, tolerancia de tracks, modificador y umbrales, con rangos del RF y sin nuevas constantes silenciosas |
| DBA / RF-62 | No hay campos de flags ni parámetros aplicados en esta tabla de visión | Definir persistencia de metadata de evaluación y trazabilidad normativa; reutilizar una estructura aprobada si ya se entrega |
| Análisis | RF-53 menciona origen como parte de deduplicación de cuatro campos, sin adaptación inequívoca a esta tabla | Precisar la regla de visión antes de cambiar su UNIQUE actual cámara/fecha |
| M09 / RF-24 | Estado normativo procede de la línea base por área/especie | Confirmar resolución desde esa fuente; no deducirlo de los estados heredados enviados por el nodo |

Los tipos normativos de los campos adicionales son `n_individuos_observados`
integer ≥0, `tipo_dato=VECTOR_COMPORTAMIENTO` y
`origen=TIEMPO_REAL|BUFFER_LOCAL`. Sus nombres físicos deben seguir las
convenciones DBA. No se propone una tabla de transporte paralela.

Parámetros de RF-62 que requieren fuente M09: `w1/w2/w3` entre 0 y 1 con suma 1;
`tracks_perdidos_tolerables` 1–50; modificador `EN_CALIBRACION`; umbrales de clase
0–100 con óptima > degradada. Los defaults D del RF están sin medir y sujetos
a calibración en sitio; deben persistirse mediante el mecanismo autorizado,
no convertirse en fallbacks dentro del consumidor.

## Criterios de integración

1. Un sobre consolidado conserva todos sus campos sin completar valores ficticios.
2. La tabla acepta los nuevos estados/clases y preserva el historial anterior.
3. La fórmula ponderada utiliza configuración persistida M09 y produce un
   resultado reproducible; `SIN_LINEA_BASE` fuerza no aptitud.
4. Flags y parámetros efectivos quedan trazables.
5. RF-24 consume únicamente aptitud calculada por backend; NIC41 sigue false.
6. Se confirma el destino de DB-03 y se ejecuta el flujo con el broker real BRK-03.

Mientras se coordina esta compatibilidad, DEV-07 implementa el sobre D4 v1 con
el catálogo vigente, conserva el cálculo heredado y rechaza campos no soportados
en vez de ignorarlos. Esa parte no cierra el cumplimiento integral del RF actualizado.
