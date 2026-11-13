# TC-M06-G113 — APROBADO

**Caso:** TC-M06-G113  
**Subcaso:** TC-M06-42 — APROBADO  
**RF:** RF-90  
**Ambiente:** TEST (`https://api.inmero.co/api-sgpmp-test`)  
**Ejecución:** COMPLETADA  
**Resultado:** SATISFACTORIO  

## Alcance

Validación de la distribución proporcional de costos compartidos y conservación de la integridad de los importes.

## Resultado de TC-M06-42

- HTTP 201 en `POST /finanzas/costos`.
- Monto: 900000.00 — método `POR_BIOMASA`.
- Grupo: `97e56560-f488-41e9-a5eb-b9a93455f275`.
- Distribución: 1569 → 150000 (4453 / línea 5799); 1570 → 300000 (4454 / 5800); 1571 → 450000 (4455 / 5801).
- Suma distribuida = 900000.00.
- Período 220 permaneció ABIERTO.
- Costo histórico 4448 de G110 intacto y fuera del grupo.

## Conclusión

G113 queda **APROBADO**. Su único subcaso TC-M06-42 se ejecutó satisfactoriamente en TEST.
