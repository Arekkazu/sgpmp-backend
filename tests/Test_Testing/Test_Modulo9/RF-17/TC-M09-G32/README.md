# TC-M09-G32 — RF-17 / TC-M09-69

Este directorio contiene únicamente automatización y evidencia QA del caso de integración entre configuración de umbrales y Monitoreo.

La ejecución no puede enviar una modificación hasta demostrar, mediante API, que Monitoreo utiliza la misma configuración que se pretende editar. `run-newman.cjs` realiza discovery de solo lectura y deja evidencia sanitizada para decidir esa precondición.

Variables de proceso requeridas para ejecutar el discovery:

- `G32_CASE=TC-M09-69`
- `G32_RUN_ID=<identificador de ejecución>`
- `TEST_ADMIN_PASSWORD` únicamente en memoria del proceso

No persistir credenciales ni datos de sesión.
