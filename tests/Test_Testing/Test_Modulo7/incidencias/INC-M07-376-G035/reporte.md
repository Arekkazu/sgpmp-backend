# INC-M07-376-G035 · RF-97 · Techo real de concurrencia entre 13 y 15 solicitudes simultáneas

> Numeración **provisional** (376, continúa la serie 373-375 del 2026-11-18): confirmar el
> consecutivo con la líder de pruebas / Taiga antes de publicar.

## Título (GitHub y Taiga)

`[INC-M07-376-G035][RF-97] A 15+ solicitudes concurrentes a vista-previa AAEF, casi todo expira por timeout`

## Cuerpo del issue (pegar igual en GitHub y en Taiga)

[TC-M07-G035][RF-97] A 15+ solicitudes concurrentes a vista-previa AAEF, casi todo expira por timeout

Incidencia: INC-M07-376-G035
Módulo: M07
RF: RF-97 (RNF-97.7, relacionado con TC-97-077/078)
Caso: TC-M07-G035 (TC-97-077, TC-97-078)
Ambiente: TEST
Equipo responsable: Infraestructura / Desarrollo Backend
Repositorio: Backend / Infraestructura de despliegue TEST
Categoría: PERFORMANCE
Severidad: Alta
Prioridad: Alta
Evaluador: Julian Badillo

### Problema

`GET /integracion/aaef/vista-previa/productores/{nit}` responde con tiempos estables (~300-450ms)
hasta 13 conexiones concurrentes reales, pero colapsa de forma abrupta —no gradual— entre 14 y 15
conexiones concurrentes. TC-97-077 exige que 20 solicitudes concurrentes "respondan en tiempo";
en TEST, a 20 concurrentes el 85% de las solicitudes expira.

### Herramienta y método

k6 v1.6.1 (script `tests/Test_Testing/Test_Modulo7/RF-97/TC-M07-G035/carga_k6_umbral_concurrencia.js`),
un login real compartido (`setup()`), N VUs = N conexiones reales simultáneas (no `http.batch()`
de un solo VU), timeout de cliente de 30s, contra
`GET /integracion/aaef/vista-previa/productores/901444215?desde=2026-10-01&hasta=2026-10-31`.

### Casos reproducidos

| N solicitudes concurrentes | Resultado | `http_req_duration` |
|---|---|---|
| 5 | 100% (5/5) OK | avg 282ms, max 411ms |
| 10 | 100% (10/10) OK | avg 389ms, max 416ms |
| 11 | 100% (11/11) OK | avg 336ms, max 419ms |
| 12 | 100% (12/12) OK | avg 346ms, max 413ms |
| 13 | 100% (13/13) OK | avg 423ms, max 448ms |
| 14 | 100% (14/14) OK, pero en cola | avg 4.25s, med 4.54s (1 rápida ~400ms, 13 esperando) |
| 15 | **0% (0/15)** — timeout | todas ~29.7s (tope del timeout del script) |
| 20 | 15% (3/20) OK, resto timeout | OK: 0.47-0.96s; resto: ~29.7-31.2s |

### Resultado esperado

20 solicitudes concurrentes a `vista-previa` responden en un tiempo razonable (RNF-97.7 implica
que el sistema escala/soporta concurrencia sin degradación abrupta).

### Resultado obtenido

Hasta 13 conexiones concurrentes, tiempos de respuesta estables. En 14 ya hay cola visible
(4-5x más lenta, pero sin fallar). En 15, el 100% expira; en 20, el 85% expira. El patrón
(estable → cola → colapso casi total en un salto de 1-2 unidades) es compatible con un pool de
conexiones o recursos de tamaño ~13-14 agotándose, no con degradación gradual por carga de CPU.

### Impacto

Severidad: Alta.

- No es un bug funcional del caso de uso (`ConsultarAaefUseCase`/`mapear_compras` ya se
  confirmaron sin estado compartido por prueba unitaria, TC-M07-G022): a cualquier concurrencia,
  nunca se mezclaron datos entre titulares, y el hash de contenido fue consistente bajo carga
  concurrente (TC-97-078 pasa).
- Es un límite de capacidad real y bajo: cualquier escenario con ~15+ llamadas simultáneas a
  AgroFusión (o varias sesiones de Contador consultando a la vez) puede colapsar casi por
  completo en lugar de simplemente tardar más.
- No se pudo confirmar si el límite está en la aplicación (pool de conexiones a BD/HTTP del
  backend) o en infraestructura (proxy, balanceador, recursos del contenedor de TEST) desde este
  hilo, por no tener acceso a métricas de infraestructura de TEST.

### Causa probable

No confirmada. Hipótesis principal: un pool de conexiones (a base de datos, o de salida HTTP) o
un límite de workers/threads configurado alrededor de 13-14 en el backend o en el despliegue de
TEST. Debe ser confirmada por Desarrollo/Infraestructura revisando configuración de pool de BD,
configuración del servidor de aplicaciones (workers/threads) y límites del contenedor/proxy de
TEST.

### Acción requerida

1. Infraestructura/Desarrollo: revisar tamaño de pool de conexiones a BD y configuración de
   concurrencia del servidor de aplicaciones en TEST.
2. Confirmar si el mismo límite existe en producción o es específico del dimensionamiento de
   TEST.
3. Si es un límite deliberado de TEST (ambiente más pequeño), documentarlo y decidir si RNF-97.7
   debe revalidarse en un ambiente con el dimensionamiento real de producción.
4. Si no es deliberado, aumentar el pool/los workers y volver a correr este script.
5. Reevaluar TC-97-077/078 (TC-M07-G035) tras el ajuste.

### Criterios de aceptación

- 20 solicitudes concurrentes reales a `vista-previa` responden con éxito (sin expirar) en un
  tiempo razonable, o queda documentado y aceptado que el límite de TEST es menor al de
  producción por dimensionamiento del ambiente.
- Se confirma la causa raíz (pool de BD, workers de aplicación, o límite de infraestructura).
- TC-97-077/078 vuelve a correr y se registra el resultado.

### Evidencias

- `tests/Test_Testing/Test_Modulo7/RF-97/TC-M07-G035/carga_k6_umbral_concurrencia.js` (script
  reproducible, parametrizado por `$env:N_VUS`).
- `tests/Test_Testing/Test_Modulo7/RF-97/TC-M07-G035/carga_k6_concurrencia_y_determinismo.js`
  (aislamiento entre titulares y determinismo del hash bajo concurrencia).
- `tests/Test_Testing/Test_Modulo7/RF-97/TC-M07-G035/NOTA_rendimiento_concurrencia.md` (tabla
  completa y análisis).

### Estado

INC-M07-376-G035 queda abierta y debe ser derivada a Infraestructura/Desarrollo Backend. La
causa raíz permanece como hipótesis hasta su confirmación.

## Atributos personalizados de Taiga

| Atributo | Valor |
|---|---|
| Modulo | M07 |
| RF | RF-97 (RNF-97.7) |
| Codigo de error | PERFORMANCE |
| Equipo responsable | Infraestructura / Desarrollo Backend |
| Severidad | Alta |
| Tiempo maximo de solucion | A definir con la líder de pruebas (hallazgo de infraestructura, no bug funcional puntual) |
| Fecha de deteccion | 2026-11-20 |
| Fecha limite | Pendiente de asignar |
| Evaluador | Julian Badillo |

## Adjuntos (ambas plataformas)

Los tres archivos listados en "Evidencias" arriba (scripts k6 + nota con la tabla completa).
No se generó un .json/.html de salida de k6 para esta corrida (los resultados se capturaron de
la salida estándar de cada ejecución, reproducible en cualquier momento con los scripts).
