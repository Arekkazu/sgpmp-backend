# TC-M07-G035 — Rendimiento, concurrencia e interoperabilidad

Agrupa TC-97-076 a TC-97-081. Herramienta sugerida por la ficha: k6/JMeter + APM —
infraestructura de carga no disponible en este hilo. No se fabrica un resultado de RNF-97.1
(≤5s con 2.000 facturas) ni de RNF-97.7 (escalado) sin esa herramienta.

## Confirmado en vivo, de forma ligera (no es una prueba de carga formal)

2026-11-18, 12 llamadas concurrentes (`ThreadPoolExecutor`, 12 workers) mezclando 3 titulares
distintos contra `GET /integracion/aaef/vista-previa/productores/{nit}` en TEST:

- Duración total: 0.69 s para las 12 llamadas.
- **Ninguna mezcla de datos entre titulares**: cada respuesta devolvió `SourceSystem.SystemNIT`
  exactamente igual al NIT solicitado, confirmando que no hay estado compartido visible entre
  solicitudes concurrentes (consistente con que `ConsultarAaefUseCase`/`mapear_compras` son
  funciones puras sin estado global, ya confirmado por unidad en TC-M07-G022 de RF-96).
- Esto es una señal a favor de CA-7 bajo concurrencia ligera, **no** una confirmación de
  RNF-97.1 (2.000 facturas), RNF-97.7 (escalado con múltiples instancias) ni de los 20
  concurrentes exactos que pide TC-97-077/078.

## Pendiente de herramienta de carga

- Volumen normal (hasta 2.000 facturas y 50 comprobantes) ≤ 5 segundos (RNF-97.1).
- 20 solicitudes concurrentes del mismo rango → mismo hash (TC-97-078).
- Escalado a 2/4 instancias sin estado compartido (RNF-97.7).
- Tiempo máximo configurado excedido → error controlado (RNF-97.8).
- Interoperabilidad real con AgroFusión TEST (CA-14) — requiere acceso a un entorno de
  AgroFusión de pruebas, no confirmado disponible.

Si se prioriza esta cobertura, se necesita: acceso a k6 o JMeter, un dataset sintético de alto
volumen (pedir al DBA, ya marcado como pendiente desde RF-96), y confirmación de si existe un
entorno de AgroFusión en TEST para el caso de interoperabilidad.
