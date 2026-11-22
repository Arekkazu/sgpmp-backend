# RF-92 — Métodos y supuestos por activo · #1106

La evidencia Newman de `TC-M06-G61` muestra que el activo 951 estaba en la conciliación y no en métodos y supuestos. La fila del activo 948 carecía de la fuente de precio y la tasa de descuento en el nivel que consume la API. Se reprodujo la causa por inspección de `dev` en `08e65db4`. El repositorio solo seleccionaba cálculos del período y el constructor trataba la ausencia de datos a nivel de la sección completa.

La hoja **Modulo 6** del Excel de requisitos, celdas B352, B355, B369 y B372, establece la cobertura por activo, la tasa de descuento cuando aplique y la advertencia no bloqueante de FA-5 ante supuestos ausentes. El informe conserva los datos recuperados y marca `datos_insuficientes` junto con los campos faltantes por activo.

Para valorar a precio de mercado se usa el último cálculo base válido hasta la fecha de corte y, cuando existe, el detalle de RF-83 vinculado al mismo cálculo. La fuente de precio se toma de la evidencia persistida o del precio RF-89 referenciado. El modelo por costo aparece en la sección sin atribuirle un precio de mercado. Los supuestos biológicos que los RF fuente no hayan persistido quedan como faltantes. La tasa permanece nula si no hay valor informado y se marca como faltante si la fuente indica que aplica.

La generación manual y la del cierre registran el contenido en la versión del informe y envían el aviso de FA-5 después del commit. Se emite un aviso por finca afectada para sus Contadores, con la versión y el detalle de activos faltantes. La API, Excel y PDF usan el mismo contenido persistido. El contenido y hash de versiones históricas permanecen intactos cuando se archivan.

La revisión Alembic `f110692a0001` concede a los roles de aplicación la lectura de las seis columnas de `mediciones_posteriores` que usa RF-92 bajo las políticas RLS vigentes. El descenso conserva las concesiones para evitar revocar privilegios que el ambiente podía tener de antemano. La revisión parte de `0884ba08a944` y es cabeza única sobre esta rama.

## Validación

- Suite de M06 con 198 aprobadas, 0 fallidas y 0 omitidas.
- Integración en PostgreSQL 18 aislado con 12 aprobadas, 0 fallidas y 0 omitidas. Se verificaron generación manual y desde cierre, cobertura de la conciliación, conservación de ceros, avisos en la bandeja del Contador asignado, aprobación, descarga y archivo con hash intacto.
- Los endpoints se probaron con JWT y RBAC. Se verificó aparte la lectura de los supuestos de RF-83 con `sgpmp_app` y RLS forzada. La prueba HTTP completa usa la conexión de integración, pues la línea base local carece de varias concesiones previas del flujo de informes.

Para la re-prueba en TEST se necesita desplegar el backend con la revisión y generar una versión nueva del informe del período. Al aprobarla, la versión aprobada anterior pasa a archivada con su contenido y hash originales.
