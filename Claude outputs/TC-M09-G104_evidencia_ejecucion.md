# Evidencia de ejecución — TC-M09-G104 (TC-M09-198/199/200)

| Campo | Valor |
|---|---|
| Caso de prueba | TC-M09-G104 (agrupa TC-M09-198, 199 y 200) |
| Descripción | Consulta del listado de plantillas de configuración: con registros, campos visibles por registro, y catálogo vacío |
| Categoría | Funcional / Manejo de errores / Usabilidad |
| RF | RF-30 |
| CU | CU-07 — Gestionar Plantillas de Configuración |
| Tipo | Prueba funcional — Frontend (Cypress) |
| Entorno (frontend) | TEST — `http://sigab-frontendtest-6aqrny-d2b730-158-69-200-27.sslip.io` |
| Backend | TEST — `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test` |
| Cuenta usada | `admin.test@sgpmp.com.co` (Administrador) |
| Fecha de ejecución | 2026-09-05 |
| Ejecutado por | Daniela Castillo |
| Resultado | ✅ **APROBADO — 2/2 pruebas, 7/7 checkpoints correctos** |

## TC-M09-198 — Consultar el listado de plantillas disponibles

Al entrar a Configuración → Plantillas, `GET /configuracion/plantillas` respondió `200 OK` con 76 plantillas (todas las creadas por el equipo hasta la fecha en el entorno de TEST). La interfaz mostró exactamente 76 tarjetas, una por cada plantilla devuelta por la API — sin diferencias entre lo que trae el backend y lo que se pinta en pantalla.

## TC-M09-199 — Verificar que cada plantilla muestre nombre, especie asociada y versión

Se verificaron 3 plantillas de la muestra contra la tarjeta correspondiente en pantalla:

| Plantilla | Especie mostrada | Versión mostrada |
|---|---|---|
| Plantilla estándar camarón | Camarón Blanco | v1 |
| Plantilla estándar tilapia | Tilapia Roja | v1 |
| Plantilla estándar trucha | Trucha Arcoíris | v1 |

En los 3 casos, el nombre de la plantilla, la especie asociada (resuelta correctamente contra el catálogo de especies) y el número de versión aparecen visibles en la tarjeta, cumpliendo el mínimo de información que exige la ficha.

## TC-M09-200 — Consultar listado cuando no existen plantillas registradas

Como el entorno de TEST es compartido y ya tiene plantillas reales (y las plantillas son inmutables por diseño, no se pueden borrar para dejar el catálogo en cero), el escenario de catálogo vacío se forzó interceptando la respuesta de `GET /configuracion/plantillas` para que devolviera `{"total":0,"items":[]}`. Con eso, la interfaz mostró el mensaje "Sin plantillas creadas" junto con el texto de ayuda "Crea la primera plantilla para capturar una configuración base.", y no se presentó ninguna alerta de error técnico en pantalla.

## Impacto

Los tres sub-casos de RF-30 (Flujo A) funcionan correctamente: el listado refleja fielmente los datos del backend, cada tarjeta expone la información mínima requerida (nombre, especie, versión), y el estado sin registros se comunica de forma clara y sin errores técnicos.

## Recomendación

Sin defectos que reportar. Sugerencia menor para el equipo de frontend: agregar atributos `data-testid` a las tarjetas de plantilla (por ejemplo en el contenedor de `PlantillaCard`) facilitaría automatizar pruebas futuras sin depender de selectores basados en estilos inline, que son más frágiles ante cambios visuales.

## Herramienta (Cypress)

```bash
CYPRESS_ADMIN_EMAIL="admin.test@sgpmp.com.co" CYPRESS_ADMIN_PASSWORD="Administrador123#" npx cypress run --browser chrome
```

Evidencia visual generada automáticamente en `RESULTADOS/`: `screenshots/01_listado_con_datos.png`, `screenshots/02_catalogo_vacio.png`, y el video completo de la corrida.
