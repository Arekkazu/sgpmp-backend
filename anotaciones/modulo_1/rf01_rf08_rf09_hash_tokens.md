# RF-01, RF-08 y RF-09 — Hash de tokens de un solo uso

## Gap encontrado

`modulo1.cuentas_usuarios.token_activacion_actual` almacenaba en texto plano
los tokens de activación, reverificación de correo y recuperación de
contraseña. La validación también consultaba la columna usando el valor crudo.

RF-08 y RF-09 exigen almacenamiento mediante hash, integridad y uso único. El
mismo control se aplicó a RF-01 porque comparte la columna y el ciclo de vida.

## Decisión

- Generar el token crudo con `secrets.token_urlsafe(32)` en el caso de uso.
- Calcular SHA-256 y persistir únicamente el hexadecimal de 64 caracteres.
- Enviar el token crudo exclusivamente por correo.
- Hashear el token recibido antes de consultar la cuenta.
- Mantener la columna existente `VARCHAR(255)` para no requerir DDL.
- Rotar el token de activación cuando una recuperación se solicita para una
  cuenta pendiente; el hash almacenado no es reversible ni reenviable.
- Invalidar el hash asignando `NULL` después de activar la cuenta o restablecer
  la contraseña.

## Transición de datos

Antes de desplegar el código, ejecutar
`hash_tokens_rf01_rf08_rf09.sql`. Así los enlaces ya emitidos siguen
siendo válidos: el token crudo del correo producirá el mismo SHA-256 almacenado.
La actualización ignora valores que ya tienen el formato hexadecimal esperado.

El despliegue debe detener temporalmente las instancias anteriores mientras se
aplica la actualización, para evitar que vuelvan a escribir tokens en texto
plano entre la migración y el arranque de la nueva versión.
