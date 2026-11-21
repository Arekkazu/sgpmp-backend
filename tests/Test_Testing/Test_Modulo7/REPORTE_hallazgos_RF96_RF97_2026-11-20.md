# Reporte consolidado de hallazgos — Módulo 7, RF-96 y RF-97 (2026-11-20)

Consolida, solo para RF-96 y RF-97, lo que quedó de la reprueba de esta sesión: lo que sigue
abierto, lo que es un hallazgo de configuración "dormido" (código correcto, dato de TEST lo
anula en la práctica), lo nuevo que apareció, y lo que no se pudo ejercitar (bloqueos). No repite
lo que ya quedó cerrado/confirmado-correcto (ver `RF-97-Verificacion-Live/ficha.md` y los
`reporte.md` de cada TC-M07-G0XX para el detalle completo).

## 1. Hallazgos que siguen abiertos

### G025 (RF-97) — `SourceSystem.Environment` dice `"DEV"` en TEST

- **Qué:** toda respuesta de `vista-previa`/AAEF en el entorno TEST trae `metadata.SourceSystem.Environment = "DEV"`.
- **Por qué sigue abierto:** es una variable de entorno del contenedor (`SGPMP_ENTORNO`) mal
  configurada en el despliegue de TEST, no un defecto del código de RF-97. El release de `dev`
  del 2026-11-20 (v8, PR #1185-1194/#1202) no la tocó.
- **Evidencia:** `RF-97-Verificacion-Live/ficha.md` (confirmado 2026-11-17/18 y re-confirmado
  2026-11-21); re-confirmado otra vez 2026-11-20 en `RF-97/TC-M07-G025/resultados/resultado_TC-M07-G025.json`.
- **Responsable sugerido:** Infraestructura/DevOps (config de despliegue de TEST), no Desarrollo.

## 2. Hallazgo de configuración "dormido" (código ya correcto, el dato de TEST lo anula)

### G019 (RF-96) — comodín en la matriz contable hace inalcanzable `LINETYPE_NO_CATALOGADO`

- **Qué:** el fix de G019 (validar `LineType` contra la matriz contable real) está confirmado
  correcto por código/unidad — el release del 2026-11-20 lo trae. Pero en TEST, `GET
  /finanzas/configuracion` muestra que las únicas filas `tipo_hecho=CONSUMO_INSUMO`/`sentido=UNICO`
  tienen `subtipo_costo=null` (comodín): por el propio diseño de `_exigir_catalogo()`
  (`None in catalogados` → pasa), **cualquier** `subtipo_costo` pasa sin excepción. No hay ninguna
  fila específica por subtipo para esa combinación en los datos reales de TEST.
- **Consecuencia práctica:** el bloqueo que el fix de G019 debería producir nunca se dispara en
  TEST mientras la matriz tenga este comodín — no es que el código esté mal, es que el dato de
  configuración de TEST lo vuelve inofensivo en la práctica.
- **Control ya registrado (con autorización explícita, 2026-11-20/21):** costo real
  `id_registro_costo=4589` (titular 901444215, `subtipo_costo=MEDICAMENTO`, período 628 noviembre,
  ABIERTO) se registró sin ningún error — confirma que M06 (RF-90) lo acepta sin objeciones, como
  predice el comodín. **Queda pendiente** cerrar el período 628 y reconsultar `vista-previa` para
  confirmar en la respuesta real que el costo 4589 sale como `02` sin `LINETYPE_NO_CATALOGADO` —
  no se cerró el período porque esa acción mayor no fue autorizada en esta sesión.
- **Evidencia:** `RF-97-Verificacion-Live/ficha.md`, sección "G019 — hallazgo de configuración
  real en TEST".
- **Responsable sugerido:** DBA/Analisis de datos de prueba (decidir si se agrega una fila
  específica no-comodín a la matriz de TEST, o si se acepta que el comodín es el dato real de
  producción también).

## 3. Hallazgos nuevos de esta reprueba

### INC-M07-376-G035 (RF-97, TC-97-077/078) — techo real de concurrencia entre 13 y 15 solicitudes simultáneas

- **Qué:** con carga real (k6), `GET /integracion/aaef/vista-previa/productores/{nit}` responde
  estable (~300-450ms) hasta **13** conexiones concurrentes reales. En **14** ya hay cola (100%
  responde, pero ~4.25s en promedio en vez de ~400ms). En **15**, colapso casi total: **0% de
  éxito**, todo expira (~30s). En 20, solo 15% sobrevive.
- **Por qué es nuevo:** no se buscaba — surgió al usar k6/JMeter (autorizado explícitamente) para
  cubrir TC-M07-G035, que antes solo tenía un chequeo ligero de 8 llamadas sin herramienta de
  carga real.
- **No es:** un problema del caso de uso (`ConsultarAaefUseCase`/`mapear_compras` ya confirmados
  sin estado compartido por unidad, TC-M07-G022) ni del aislamiento/determinismo (ambos pasan
  limpio bajo la misma carga).
- **Severidad:** Alta. Responde directamente TC-97-077 ("20 concurrentes responden en tiempo"):
  no pasa como está.
- **Evidencia:** `RF-97/TC-M07-G035/NOTA_rendimiento_concurrencia.md` (tabla completa),
  `incidencias/INC-M07-376-G035/reporte.md` (formato Taiga/GitHub), scripts
  `carga_k6_concurrencia_y_determinismo.js` y `carga_k6_umbral_concurrencia.js`.
- **Responsable sugerido:** Infraestructura/Desarrollo Backend (revisar pool de conexiones a BD o
  workers del servidor de aplicaciones en TEST).

## 4. Bloqueos (no se pudo ejercitar — limitación de entorno/herramienta, no son bugs)

- **v3.1 real con el Mapper `06` (Comprobante NIC 41) activo** — bloqueado por el límite de 2
  versiones de contrato vigentes del sistema (nota del DBA, 2026-11-17); todas las versiones
  `PENDIENTE` visibles en TEST (3.1, 3.9, 4.0, 5.0, 8.1, 8.2) solo tienen `mapeadores=["COMPRAS"]`.
  Cubierto solo a nivel de unidad en RF-96 (TC-M07-G012).
- **RF-102 caído / Toxiproxy (TC-M07-G031, FA-7/FA-9)** — requiere inyección de fallos de
  infraestructura en TEST, no disponible desde este hilo.
- **Cliente externo real con token de canal (RF-101, consumido por RF-97 en producción real)** —
  no se tienen credenciales de cliente en este hilo; toda la verificación usó `vista-previa`
  (sesión Contador), que ejecuta exactamente el mismo caso de uso (`m07.consultar_aaef().execute(...)`,
  confirmado por lectura de `gateway_aaef.py`).
- **Reproducir en vivo los 4 bugs ya arreglados en `dev` (G016, G028, G031, G032)** — no se
  encontró en TEST ningún dato real que ejercitara esos escenarios de error (comprobante con neto
  negativo, falla real de lectura de M06), ni entre los titulares ya accesibles. Confirmar estos 4
  en vivo requeriría que el DBA cree un registro deliberadamente inválido, o escribir uno
  nosotros mismos (acción de escritura mayor, no solicitada). Quedan confirmados solo contra el
  código real de `dev` por pytest.
- **Interoperabilidad real con AgroFusión (CA-14, RF-97 TC-M07-G035)** — requiere acceso a un
  entorno de AgroFusión de pruebas, no confirmado disponible.
- **RNF-97.1 literal (2.000 facturas, 50 comprobantes, ≤5s) y RNF-97.7 (escalado a 2/4 instancias)**
  — no hay un período con ese volumen real en TEST, y no se controla el despliegue de TEST para
  forzar cuántas instancias atienden la corrida.
