# INC-M06-316-G16 — Los costos manuales no exigían ni guardaban una referencia documental (RF-84)

**RF:** RF-84 (restricciones 2, 4 y 5; salida 3) aplicado en la confirmación del reconocimiento (RF-82). **Issue:** #1003.
**Estado:** corregido con pruebas unitarias. Sin cambios de BD. **Requiere cambio en el frontend.**

## Causa

`POST /finanzas/reconocimientos/{id}` aceptaba `costos_manuales` con solo una `justificacion` de 20 a 1.000
caracteres (validada en el DTO). RF-84 R4 dice: «Los costos de venta ingresados manualmente por el Contador
deben estar respaldados por al menos una referencia documental registrada en el sistema». No existía ese dato:

- Comisiones a 250.000 con justificación larga y sin referencia respondieron 201 (neto 9.550.000), igual
  que con la referencia escrita dentro del texto.
- En el caso de solo costos manuales (G21 098) tampoco se pidió.

## Corrección

- `ConfirmarReconocimientoDTO.referencia_documental` (opcional en el formato, 3 a 200 caracteres). Ejemplo:
  «Factura FE-1234 Subastas del Huila».
- `ConfirmarReconocimientoUseCase` revisa la regla de negocio antes de todo lo demás: si llega algún costo
  manual con valor y la referencia falta o está en blanco, responde **400 `REFERENCIA_DOCUMENTAL_REQUERIDA`**
  (`field: referencia_documental`). La justificación sigue siendo obligatoria, como antes, en el DTO.
- La referencia se guarda en dos lugares:
  - en `calculos_valor_razonable.json_metodo_costo.referencia_documental` (solo si hay costos manuales);
  - en el evento `RECONOCIMIENTO_INICIAL` de RF-94, con `costos_manuales`, `justificacion` y
    `referencia_documental` (RF-84 R5: el ajuste manual queda en auditoría con Contador y fecha).
- `Valorador.valorar` y `ProponedorReconocimiento.proponer` reciben la referencia y la pasan al cálculo.

## Decisiones

1. **Sin columna nueva.** La referencia va en el JSON `json_metodo_costo`, donde ya está el método de cada
   componente (PARAMETRIZADO o MANUAL). Una columna exigiría migración y aprobación del DBA. Si el equipo la
   quiere consultable como columna, se puede migrar después.
2. **Texto con la referencia, no un id.** «Registrada en el sistema» queda cubierto al guardarla con el
   cálculo. M06 no tiene un repositorio de documentos al que apuntar con un id.

## Impacto en el frontend

`SGPMP-FRONT-END-PWA/src/financial_valuation/pages/ReconocimientosView.tsx` (línea 186) y `api/finanzasApi.ts`
(línea 57) envían `costos_manuales` y `justificacion`, pero no `referencia_documental`. Hasta que el front
agregue el campo, una confirmación con costos manuales responde 400 `REFERENCIA_DOCUMENTAL_REQUERIDA`.

## Fuera de alcance

`AJUSTE_MANUAL_COSTOS_VENTA` está en el catálogo de RF-94 pero el código no lo escribe. La salida 3 de
RF-84 pide un log del ajuste con el ítem, el valor original y el valor manual. Aquí se agregan los datos
del ajuste al evento del reconocimiento, pero no el valor parametrizado que se reemplazó.

## Verificación

`tests/financial_valuation/test_inc_m06_316_g16_referencia_documental.py`:

- con costos manuales y la referencia ausente, vacía o en blanco: 400 `REFERENCIA_DOCUMENTAL_REQUERIDA`;
- sin costos manuales no se exige;
- contrato HTTP: 400 con `error_code` y `fields[0].field = referencia_documental`;
- el cálculo guarda la referencia con el componente MANUAL y el neto de 9.650.000;
- sin manuales el cálculo no la lleva.

El evento `RECONOCIMIENTO_INICIAL` no tiene prueba propia: el camino completo de la confirmación necesita
muchos colaboradores.
