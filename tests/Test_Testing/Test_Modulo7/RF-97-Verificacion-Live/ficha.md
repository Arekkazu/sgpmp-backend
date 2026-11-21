# Verificación en vivo RF-97 (Módulo 7) contra TEST

**Fecha:** 2026-11-17/18
**Herramienta:** Newman/Postman (`tc_m07_rf97_live.postman_collection.json`)
**Entorno:** TEST (`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`)
**Cuenta:** Contador (`contador@pecuaria.co`), vista-previa AAEF (misma generación que usaría AgroFusión, sin necesitar token de canal).
**Resultado:** 35/35 assertions en verde.

## Por qué `vista-previa`, no el endpoint del canal

`GET /integracion/aaef/productores/{nit}` (el que llamaría AgroFusión) exige un token de canal
(cliente externo, RF-101) que no está en este hilo. `GET /integracion/aaef/vista-previa/productores/{nit}`
ejecuta exactamente el mismo caso de uso (`ConsultarAaefUseCase`) con la sesión web del Contador —
confirmado por lectura directa de `gateway_aaef.py`: ambas funciones llaman a `m07.consultar_aaef().execute(...)`.
Es la misma generación real, solo cambia cómo se autentica.

## Hallazgos confirmados en vivo

1. **ExchangeId no sigue el formato de la ficha.** RF-97 5.4/CA-4 esperan
   `SGPMP-{NIT}-{desde}-{hasta}-{nonce de 7 dígitos}`. El real es
   `AF-SIGAB-{AAAA-MM}-{nonce de 7 dígitos}` (confirmado commit `4353483f`, 2026-11-14: el formato
   lo exige SIGCON, no el que describe el RF). Dato real: `AF-SIGAB-2026-10-3972113`.
2. **`SourceSystem.Environment` dice `DEV` en TEST.** Confirmado en todas las respuestas de este
   entorno — es una variable de entorno del contenedor (`SGPMP_ENTORNO`) mal configurada en el
   despliegue de TEST, no un defecto del código de RF-97 en sí.
3. **El acceso de fincas que pidió el equipo ya está activo.** `contador@pecuaria.co` consulta
   901333217 (noviembre, período 622) sin 403 — confirma que la ampliación de alcance que pidió el
   DBA (2026-11-17) ya se aplicó.
4. **CA-13/FA-6 — un NIT inexistente da 404 `TITULAR_NO_ENCONTRADO`, no `CONTRATO_NO_ACTIVO`.**
   El chequeo de existencia del titular corre antes que la resolución del contrato
   (`ConsultarAaefUseCase.execute()`), así que `FA-6` nunca se alcanza por esta vía — es un error
   de secuencia de Fases más preciso que lo que describe la ficha, no un hallazgo nuevo.

## Confirmado correcto (sin hallazgo)

- Las 4 secciones exactas del envelope (`metadata`, `summary`, `invoices`, `transactions`), sin
  claves adicionales, JSON UTF-8 válido con tildes/eñes preservadas (`Activo biológico`, no
  `Activo biolÃ³gico` — esa corrupción solo aparecía en PowerShell/`Invoke-WebRequest`, nunca en
  los bytes reales, confirmado con Python puro).
- `summary` cuadra exactamente con los 3 documentos reales de octubre (NIT 901444215, período
  627): `TotalDocuments=TotalInvoices=3`, `TotalGrossAmount=TotalNet=740000`, `Currency=COP`.
- `RANGO_NO_ALINEADO`, `PERIODO_NO_CERRADO` y `PARAMETROS_INVALIDOS` (rango invertido) — los tres
  con 4xx, nunca 500.
- Con el contrato real activo (v2.1, solo `COMPRAS`, equivalente funcional de v3.0): nunca aparece
  un documento `06`, aunque el período 627 **sí tiene** un comprobante NIC 41 real (confirmado por
  separado vía `GET /finanzas/periodos/627/comprobantes`) — confirma CA-3/CA-5 en código real, no
  solo por unidad (ver TC-M07-G012 de RF-96).
- `invoices` ordenados por `DocumentId` ascendente.
- Un rango cerrado sin datos (NIT 901458732, período 253) da un envelope **válido y vacío**
  (`invoices=[]`, `summary` en cero), no un error — confirma CA-11/FA-8.
- Un NIT con payload de inyección (`' OR '1'='1`) nunca llega a 500 — lo rechaza el propio patrón
  de FastAPI (`Path(pattern=...)`) antes de tocar cualquier lógica de negocio.

## Actualización 2026-11-21 — contrato real ya es v3.0, no v2.1

Reejecución completa (35/35 en verde). Cambios del entorno desde el 2026-11-18:

- **El contrato activo real ahora es literalmente v3.0** (`id_version_contrato_aaef=18`,
  activado 2026-11-18, mapeadores=["COMPRAS"]) — ya no es "v2.1 como equivalente funcional
  de v3.0", es la versión exacta que describe la ficha. v2.1 quedó DEPRECADO el mismo día. Se
  actualizó la colección (`X-Version-Contrato-AAEF` esperado ahora es `3.0`).
- **Sigue sin existir ningún contrato con el Mapper Comprobante NIC41** (todas las versiones
  visibles, incluidas varias `PENDIENTE` de otros QA -- 3.1, 3.9, 4.0, 5.0, 8.1, 8.2 -- solo
  tienen `mapeadores=["COMPRAS"]`). El feature flag `M07_COMPROBANTE_NIC41_HABILITADO` sigue
  aparentemente apagado en TEST.
- **Titular 901458732 (período 253) empezó a dar 403 `ALCANCE_INSUFICIENTE`** donde antes daba
  200 con 0 documentos -- no es un hallazgo nuestro: es deriva del entorno compartido (otro QA
  modificó las fincas de ese titular). Se reemplazó por NIT `900000002` (período 219) para el
  caso de envelope vacío (TC-M07-G033).
- **`SourceSystem.Environment` sigue reportando `"DEV"` en TEST** (Issue 4 de nuestro reporte de
  bugs) -- no se tocó en este release.

### Intento de reproducir en vivo los 5 bugs ya arreglados en `dev` (G016, G019, G028, G031, G032)

Se buscó, sin escribir nada, algún dato real ya existente en TEST que ejercitara alguno de los
escenarios de error (comprobante con neto negativo, costo con `LineType` fuera de catálogo,
una falla real de lectura de M06). No se encontró ninguno entre los titulares accesibles
(incluido el nuevo `901333217` "Agropecuaria Aaef QA S.A.S.", con 2 facturas limpias sin
errores). Confirmar estos 5 arreglos en vivo requeriría: (a) que el DBA cree un registro de
costo o comprobante deliberadamente inválido para este fin, o (b) escribir uno nosotros mismos
(acción de escritura, necesita autorización explícita). Mientras tanto, los 5 quedan
confirmados contra el código real de `dev` por pytest (ver RF-96/TC-M07-G016/G019,
RF-97/TC-M07-G028/G031/G032), que es el mismo código que ya resuelve correctamente las
versiones de contrato en TEST.

## Lo que esta colección NO cubre (requiere otra vía)

- **v3.1 real con el Mapper `06` activo** — sigue bloqueado por el límite de 2 versiones vigentes
  del sistema (ver nota del DBA, 2026-11-17). Cubierto solo a nivel de unidad en RF-96 (TC-M07-G012).
- **Rendimiento/concurrencia (TC-M07-G035)** — requiere k6/JMeter; no se intentó aquí.
- **RF-102 caído / Toxiproxy (TC-M07-G031, FA-7/FA-9)** — requiere inyección de fallos en TEST, no
  disponible desde este hilo.
- **Cliente externo real con token de canal** — no se tienen las credenciales en este hilo; toda
  la verificación de arriba usa `vista-previa` (sesión Contador), que ejecuta el mismo caso de uso.

## Cómo correrlo

```powershell
cd tests/Test_Testing/Test_Modulo7/RF-97-Verificacion-Live
npx newman run tc_m07_rf97_live.postman_collection.json `
  --env-var "contador_pass=<clave real del roster>" `
  -r cli,htmlextra --reporter-htmlextra-export resultados/resultado_live_rf97.html
```

No requiere ninguna acción de escritura: toda la colección es de solo lectura (`vista-previa` no
modifica nada de M06, confirmado en RF-96 TC-M07-G021).
