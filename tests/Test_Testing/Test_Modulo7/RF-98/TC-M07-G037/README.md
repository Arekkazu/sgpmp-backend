# TC-M07-G037 — preparación local RF-98 v1.2

Ejecutor canónico: `g037.mjs`. Colección canónica: `G037.postman_collection.json`. No hay Cypress porque los casos TC-M07-06, 07 y 08 solo exigen API. El RUN oficial V1 fue creado por el lanzador externo; la orden ORD-G037-004 solo enmendó sus archivos locales, sin acceder a TEST.

## Oráculos

- 06: siete valores inválidos (`4`, `4.0.1`, `v4.0`, `4.x`, `4.`, `.4`, cadena vacía): 4xx y ningún contrato; `4.0`: 201 PENDIENTE.
- 07: 29 días: 4xx y sin crear; 30 días: 201 PENDIENTE con 30; omisión: 201 PENDIENTE con 90; M09 debe exponer la gracia.
- 08: 29 días: 4xx y ACTIVO; 30 días: DEPRECADO e inactivación a 30 días exactos.

Fuentes: fila G037 de `Casos_Prueba(Modulo7Agrup).csv` y RF-98 de `Especificacion-Requerimientos-Modulo7.md`. M09 sin gracia en el código local es `DEFECTO_FUNCIONAL_CANDIDATO`, pendiente de evidencia de TEST autorizada.

## Comandos exactos para el responsable QA

Desde esta carpeta, en PowerShell:

```powershell
node pruebas/verificar.mjs
node g037.mjs --capacidades
node g037.mjs --comprobar
node --check g037.mjs
node --check pruebas/verificar.mjs
node pruebas/g037_local.test.mjs
```

`verificar.mjs` crea sus salidas en `%TEMP%`, ejecuta los doce escenarios y los pasos 1 a 10 más RED. Los pasos con `spawn` pueden fallar con `EPERM` dentro de Codex; QA debe ejecutarlos en Windows fuera de ese sandbox. Si falla un paso, el temporal se conserva. El ejemplo conforme queda en `%TEMP%/g037-verificar-ejemplo/`, con `capacidades.json`, para `registro_qa validar`. Los reportes locales son simulaciones, no evidencia de TEST.

El lanzador aprobado debe crear `Resultados/RUN-G037-V1-<timestamp>/contexto_operacion.json` antes de invocar `g037.mjs`; Codex no hace esa invocación a TEST. Login único previo al RUN; DELETE y lectura pública posterior comprueban rollback. Newman hace lecturas siempre que se abra el RUN; si falta permiso M09 R, omite solo el ítem de `/configuracion/parametros` y lo registra en `observaciones`. Cypress se informa NO_APLICA. El informe oficial, `resultado.json` y los reportes Newman reales pertenecen al mismo RUN.

## SHA-256 esperado

SHA-256 esperado de `g037.mjs`: `72bd0cdd6ac6907251c99da8e1c2a4de257f14b82fcc9c5ff9c370a1a6322308`

SHA-256 esperado de `verificar.mjs`: `fc56360f9e6a649005729348dde99081e900c312d9e28603dd92e2a093bc36dd`

SHA-256 de `pruebas/newman_hijo.mjs`: `57896a7b1791c6bc0acb1220c9b6f029eb70a7a315d337abcbf885679d524bba`

SHA-256 de `pruebas/g037_local.test.mjs`: `5bbe446c812cb639717770151e78e1537d0788268d31b4383d6e9843c76801ee`

SHA-256 de `pruebas/simulador_g037.mjs`: `e94365f4267980828dc4d932e7febb3aa22875923d7f9761c82e099c55fba7a9`

SHA-256 de `Resultados/RUN-G037-V1-20261118-071829/resultado.json` antes de la enmienda: `aa6111603b775ab2dedb94b801d0bf2e63e0d321ad0634d54a73151d369c7c05`; después: `597d147e0497a310a67d191b18aa4e459329a280ed431de5b4e25c3b65e28e96`.
