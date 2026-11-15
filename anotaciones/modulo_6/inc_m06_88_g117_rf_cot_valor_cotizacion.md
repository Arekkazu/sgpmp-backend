# INC-M06-88-G117 · RF-COT — Validación del valor propuesto al registrar una cotización

TC-M06-48a y TC-M06-48b reportaron HTTP 400 `VAL_ENTRADA` para cero y −1. En la hoja «Modulo 6» de la especificación, B307 exige un valor positivo antes de persistir y B308 asigna HTTP 422 `VALOR_COTIZACION_INVALIDO` a FA-6. Se reprodujo el HTTP 400 del DTO en `dev` antes del cambio.

El DTO de registro conserva el tipo decimal y los límites de 18 dígitos y cuatro decimales. El caso de uso existente aplica FA-6 y devuelve el error de negocio antes de consultar los activos, resolver el período o escribir. El cambio se limita al alta de cotizaciones. El flujo de modificación conserva su contrato. La corrección no requiere migración.

## Validación

- `tests/financial_valuation` registró 198 pruebas aprobadas, sin fallidas ni omitidas.
- Ocho pruebas distintas de integración aprobaron en PostgreSQL 18 local migrado hasta `0884ba08a944`. La prueba específica se repitió con los permisos del rol de aplicación completados en la base local y RLS activa.
- El flujo HTTP autenticado verificó cero, −1 y −0,0001 con 422, datos ausentes o mal formados y exceso de precisión con 400, y vencimiento anterior a la emisión con 422 `FECHA_VENCIMIENTO_INVALIDA`. Se comprobó que esos rechazos conservan la cotización anterior, los conteos de cotizaciones y auditorías y el período abierto.
- Con un activo reconocido y un valor razonable vigente, el monto de 0,0001 respondió HTTP 201, quedó persistido con cuatro decimales y generó un evento `COTIZACION_REGISTRADA`.

Queda pendiente repetir TC-M06-48a y TC-M06-48b en TEST después del despliegue. La preparación local del rol no acredita las ACL desplegadas.

Referencia [issue #1101](https://github.com/Arekkazu/sgpmp-backend/issues/1101).
