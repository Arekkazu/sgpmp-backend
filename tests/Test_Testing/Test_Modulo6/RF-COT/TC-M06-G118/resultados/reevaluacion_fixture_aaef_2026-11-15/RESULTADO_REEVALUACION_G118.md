# Resultado reevaluación G118 — fixture AAEF 2026-11-15

**Fecha UTC:** 2026-11-15T05:44:44.403004+00:00
**Ambiente:** `https://api.inmero.co/api-sgpmp-test`
**Alcance:** solo lectura. Sin cotización, sin cierre 220, sin secreto WhatsApp.

## 1. Fixture
- Activo 2548 / reconocimiento 1248 / finca 481 / área 1457: ver matriz.
- Costos 4476/4477: ver `estado_fixture_aaef.json`.
- Períodos 622 CERRADO / 623 ABIERTO / 220 ABIERTO: ver `estado_periodos_aaef.json`.

## 2. Vista previa Contador
- Ruta: `/integracion/aaef/vista-previa/productores/901333217?desde=2026-11-01&hasta=2026-11-30`
- HTTP: **200**
- Documentos: 2 · tipos=['02', '02'] · ids=['COS-4476-20261114', 'COS-4477-20261114']
- Totales: bruto=530000.0 neto=530000.0
- Transactions: 0
- Dictamen parcial vista previa: **CUMPLE**

## 3. Auth externa AAEF
- Env seguras: {'QA_AAEF_CLIENT_ID': False, 'QA_AAEF_CLIENT_SECRET': False, 'QA_AAEF_EMAIL': False}
- POST token: **no ejecutado**
- GET externo: **no ejecutado**
- Bloqueo: Variables QA_AAEF_CLIENT_ID / QA_AAEF_CLIENT_SECRET / QA_AAEF_EMAIL no configuradas. No se usó secreto de WhatsApp. No se ejecutó POST /integraciones/agrofusion/token.

## 4. Escenario negativo 220
- HTTP 422 · error_code=PERIODO_NO_CERRADO
- Resultado: **CUMPLE**

## 5. TC-M06-50
- Estado: **PENDIENTE DE AUTORIZACIÓN** (no ejecutado).

## 6. Dictamen G118
- **aprobado: false**
- Motivos: ['Canal externo AAEF sin credenciales seguras en env', 'TC-M06-50 cotización no autorizada / no ejecutada']

Evidencias: `C:/Users/ll529/OneDrive/Documentos/proyecto_integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo6/RF-COT/TC-M06-G118/resultados/reevaluacion_fixture_aaef_2026-11-15`