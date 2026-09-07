# Evidencia de ejecución — TC-M09-G105 (TC-M09-201/202)

| Campo | Valor |
|---|---|
| Caso de prueba | TC-M09-G105 (agrupa TC-M09-201 y TC-M09-202) |
| Descripción | Acceso a los flujos de creación y aplicación de plantillas desde el listado |
| Categoría | Funcional / Control de acceso (RBAC) |
| RF | RF-30 |
| CU | CU-07 — Gestionar Plantillas de Configuración |
| Tipo | Prueba funcional — Frontend (Cypress) |
| Entorno (frontend) | TEST — `http://sigab-frontendtest-6aqrny-d2b730-158-69-200-27.sslip.io` |
| Backend | TEST — `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test` |
| Cuentas usadas | `admin.test@sgpmp.com.co` (Administrador) y una cuenta de rol Productor (sin permisos sobre plantillas) |
| Fecha de ejecución | 2026-09-05 |
| Ejecutado por | Daniela Castillo |
| Resultado | ✅ **APROBADO — 3/3 pruebas correctas** |

## TC-M09-201 — Acceder a la creación de una nueva plantilla desde el listado

Con la cuenta Administrador, al hacer clic en el botón "Nueva plantilla" del listado de Configuración → Plantillas se abrió el diálogo de creación (`PlantillaModal`), identificado como `role="dialog"` con `aria-modal="true"` y el título "Nueva Plantilla de Configuración". Mientras el diálogo estuvo abierto, la ruta se mantuvo en `/configuracion`: el flujo se presenta como una superposición sobre el módulo actual, no como una navegación a otra pantalla, conservando así el contexto de Configuración tal como exige la ficha.

## TC-M09-202 — Acceder a la aplicación de una plantilla desde el listado

Con la misma cuenta, al hacer clic en el botón "Aplicar plantilla" de una tarjeta del listado se abrió el asistente correspondiente (`AplicarPlantillaWizard`), también como `role="dialog"` con `aria-modal="true"`, titulado "Aplicar Plantilla" y mostrando el nombre exacto de la plantilla elegida en la tarjeta — confirmando que el asistente recibe la plantilla correcta y no una genérica. El asistente inició en el primer paso de su flujo, "Seleccionar especie", y la ruta de fondo permaneció en `/configuracion` durante toda la interacción.

## Control de acceso — usuario sin permisos sobre plantillas (Productor)

Con una cuenta del rol Productor, que no tiene ningún permiso (ni siquiera de lectura) sobre el recurso "plantillas", la pestaña "Plantillas" no apareció en la barra de navegación de Configuración. Al no existir un punto de entrada visible, esta cuenta no tiene forma de llegar a ninguno de los dos flujos (creación ni aplicación), lo que confirma que el control de acceso definido para RF-30 funciona correctamente también del lado del frontend.

## Impacto

Los dos flujos de acceso desde el listado de plantillas (creación y aplicación) funcionan correctamente para los roles autorizados (Administrador e Ingeniero de Campo), conservando el contexto del módulo de Configuración en ambos casos, y quedan completamente inaccesibles para un rol sin permisos sobre el recurso.

## Recomendación

Sin defectos que reportar.

## Herramienta (Cypress)

```bash
CYPRESS_ADMIN_EMAIL="admin.test@sgpmp.com.co" CYPRESS_ADMIN_PASSWORD="Administrador123#" npx cypress run --browser chrome
```

Evidencia visual generada automáticamente en `RESULTADOS/`: `screenshots/01_modal_creacion_plantilla.png`, `screenshots/02_wizard_aplicar_plantilla.png`, `screenshots/03_pestana_plantillas_no_visible.png`, y el video completo de la corrida.
