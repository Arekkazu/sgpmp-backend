# TC-M09-G27 — RBAC en edición de umbrales

Único original: TC-M09-59. Ejecuta exclusivamente `PATCH /configuracion/umbrales/{id}`
con un actor TEST autenticado cuyo rol real y permisos actuales demuestran que no
puede actualizar el recurso 20. No usa Cypress, PostgreSQL, mocks ni actualización
positiva como Administrador.

La evidencia se crea bajo `RESULTADOS/<G27_RUN_ID>/`. Requiere solo variables de
proceso: `TEST_ADMIN_EMAIL`, `TEST_ADMIN_PASSWORD`, `TEST_UNAUTHORIZED_PASSWORD`,
`G27_RUN_ID` y `G27_ATTEMPT`. Las contraseñas y tokens nunca se guardan.

El runner selecciona Productor primero; solo consulta otro candidato si Productor
no puede demostrar ser un actor no autorizado. Descubre un umbral activo real,
construye una modificación válida que cambia efectivamente el estado si fuese
autorizada, valida el `403 ACCESO_DENEGADO` con Newman y compara el GET administrativo
posterior con el snapshot funcional previo.
