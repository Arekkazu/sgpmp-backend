# 🛠️ Plan y Hoja de Ruta de DevOps — SGPMP Backend

Este documento detalla la infraestructura actual y el plan de trabajo de DevOps para facilitar la colaboración, calidad y estabilidad del proyecto **SGPMP**, desarrollado de manera conjunta por los diferentes equipos (Análisis, Diseño, Desarrollo, Pruebas y DevOps).

---

## 📍 Estado Actual de la Infraestructura

Actualmente, la infraestructura del proyecto está configurada y automatizada en la instancia de Oracle Cloud de la siguiente manera:

1.  **Panel de Control (Dokploy):**
    *   Instalado de forma 100% aislada para evitar conflictos con otras aplicaciones del servidor.
    *   **URL del Panel:** `http://149.130.187.72:3070`
2.  **Entorno de Producción (`deploy`):**
    *   **URL de la API:** `http://149.130.187.72:8002/docs` (Documentación Interactiva).
    *   **Rama de Git:** `deploy`
    *   **Despliegue Automático:** Configurado mediante GitHub Webhooks. Cada cambio subido a la rama `deploy` reconstruye e inicia el backend automáticamente utilizando Nixpacks.
3.  **Base de Datos (PostgreSQL):**
    *   Base de datos dedicada en la nube conectada al backend de producción.
    *   **Puerto de conexión externa:** `5434` (abierto en el servidor y listo para conexiones de clientes SQL como DBeaver o pgAdmin).

---

## 📋 Tareas Pendientes e Implementaciones Futuras (Hoja de Ruta)

Para optimizar el flujo de trabajo de los más de 20 estudiantes del proyecto, se proponen las siguientes iniciativas de DevOps:

### 1. Creación del Entorno de QA / Staging (Para el Equipo de Pruebas)
*   **Objetivo:** Permitir al equipo de Pruebas verificar los nuevos cambios sin interferir con la versión estable de producción.
*   **Implementación:**
    *   Crear un nuevo servicio de aplicación en Dokploy llamado `sgpmp-backend-staging` conectado a la rama **`dev`**.
    *   Exponer este entorno en el puerto **`8003`** (ej. `http://149.130.187.72:8003/docs`).
    *   El equipo de Pruebas utilizará este enlace para validar el software antes de que sea promovido a la rama `deploy`.

### 2. Integración Continua (CI) con GitHub Actions
*   **Objetivo:** Garantizar que ningún desarrollador suba código roto o que no cumpla con los estándares de estilo al repositorio común.
*   **Implementación:**
    *   Crear la pipeline `.github/workflows/ci.yml`.
    *   La pipeline se disparará en cada Pull Request (PR) hacia las ramas `dev` y `deploy`.
    *   **Fases de la pipeline:**
        1.  **Linter y Formatter:** Ejecutar `ruff check` y `ruff format` para asegurar un estilo de código homogéneo.
        2.  **Pruebas Unitarias:** Ejecutar la suite de pruebas unitarias con `pytest` y generar reporte de cobertura (`pytest-cov`).
    *   Bloquear el merge de cualquier PR si la pipeline de CI falla.

### 3. Automatización de Migraciones de Base de Datos
*   **Objetivo:** Eliminar la necesidad de ejecutar scripts DDL manualmente en las bases de datos de staging o producción cuando se modifiquen modelos.
*   **Implementación:**
    *   Inicializar **Alembic** en el proyecto (`alembic init`).
    *   Configurar la URL de conexión en `alembic.ini` para que lea de la variable `DATABASE_URL`.
    *   Modificar el comando de arranque del contenedor en producción/staging para que ejecute `alembic upgrade head && uvicorn main:app ...`, asegurando que la base de datos se actualice sola en cada despliegue.

### 4. Respaldos Automatizados de la Base de Datos (Backups)
*   **Objetivo:** Evitar la pérdida de datos de prueba o producción en caso de accidentes o mutaciones corruptas.
*   **Implementación:**
    *   Configurar copias de seguridad automáticas diarias en la sección **Backups** de la base de datos dentro del panel de Dokploy.
    *   Destino: Almacenamiento local en el servidor Oracle o integración con servicios Cloud gratuitos (como Cloudflare R2 o AWS S3 Free Tier).

### 5. Dockerización del Entorno de Desarrollo Local
*   **Objetivo:** Minimizar el tiempo de configuración inicial (*onboarding*) de los desarrolladores nuevos.
*   **Implementación:**
    *   Mantener actualizado el archivo `docker-compose.yml` en la raíz del proyecto.
    *   Documentar el comando `docker compose up --build` para que cualquier estudiante pueda levantar el backend y una base de datos local lista para codificar en 5 minutos sin configurar Python ni PostgreSQL manualmente en su sistema operativo.

### 6. Sistema de Monitoreo y Visibilidad de Logs
*   **Objetivo:** Permitir a los desarrolladores y testers analizar los errores de ejecución en tiempo real sin necesidad de acceder al servidor por SSH.
*   **Implementación:**
    *   Crear usuarios de lectura para los líderes de desarrollo/pruebas dentro del panel de Dokploy para que puedan auditar la pestaña **Logs** directamente.
    *   (Opcional) Configurar notificaciones vía Discord/Slack cuando ocurra un fallo crítico de servidor o despliegue.
