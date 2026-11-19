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
