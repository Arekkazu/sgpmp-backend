# 🔌 Catálogo de Servicios y Dependencias Externas — SGPMP Backend

Este documento detalla todos los servicios, integraciones de terceros y dependencias de infraestructura requeridos por el backend de **SGPMP** para funcionar en producción.

---

## 🗄️ 1. Servicios de Base de Datos y Persistencia

### PostgreSQL (Base de Datos Relacional)
*   **Rol:** Base de datos principal del sistema. Guarda usuarios, roles, permisos, registros biológicos, telemetría y predicciones.
*   **Dependencia Python:** `psycopg2-binary`, `SQLAlchemy` (ORM).
*   **Configuración (.env):**
    *   `DATABASE_URL`: Cadena de conexión (ej. `postgresql://usuario:clave@host:puerto/bd`).
*   **Estado DevOps:** Desplegada en Dokploy como un servicio independiente en el puerto host `5434`.

---

## ☁️ 2. Integraciones Cloud (Firebase / Google)

### Firebase Storage (Almacenamiento de Archivos)
*   **Rol:** Repositorio en la nube para guardar archivos adjuntos pesados del sistema (fotos de activos biológicos, reportes médicos, imágenes de perfil, etc.).
*   **Dependencia Python:** `firebase-admin` (SDK de Firebase).
*   **Configuración (.env):**
    *   `FIREBASE_STORAGE_BUCKET`: Nombre del bucket de Firebase (ej. `proyecto.appspot.com`).
    *   `FIREBASE_CREDENTIALS_PATH`: Ruta al archivo JSON con la llave privada de la cuenta de servicio de Firebase.

### Firebase Cloud Messaging (FCM - Notificaciones Push)
*   **Rol:** Envío en tiempo real de notificaciones push a dispositivos móviles y aplicaciones web cuando se generan alertas críticas de sensores o diagnósticos.
*   **Dependencia Python:** `firebase-admin` (Modulo `messaging`).
*   **Código de Integración:** [src/shared/firebase.py](file:///home/miguel/Proyectos/sgpmp-backend/src/shared/firebase.py)
*   **Configuración (.env):**
    *   `FIREBASE_CREDENTIALS_PATH`: Comparte el mismo archivo de credenciales que Firebase Storage.

---

## ✉️ 3. Servicios de Comunicación

### Servidor de Correo Transaccional (SMTP)
*   **Rol:** Envío de correos electrónicos transaccionales del sistema (códigos de activación de cuenta, correos de recuperación de contraseña, alertas analíticas).
*   **Dependencia Python:** `smtplib`, `email.mime` (Librerías estándar de Python).
*   **Código de Integración:** [src/shared/email.py](file:///home/miguel/Proyectos/sgpmp-backend/src/shared/email.py) (incluye reintentos automáticos y manejo de fallos).
*   **Configuración (.env):**
    *   `SMTP_HOST`: Dirección del servidor de correo (ej. `smtp.gmail.com`).
    *   `SMTP_PORT`: Puerto de conexión TLS (normalmente `587`).
    *   `SMTP_USER`: Cuenta de correo emisora.
    *   `SMTP_PASSWORD`: Contraseña de aplicación o clave de acceso SMTP.

---

## 🔑 4. Autenticación e Identidad (Planificado / En Progreso)

### OAuth Social Login (Google & Microsoft)
*   **Rol:** Permitir el registro e inicio de sesión de usuarios de forma ágil utilizando cuentas institucionales o personales de Google y Microsoft Azure.
*   **Configuración (.env):**
    *   `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`
    *   `MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET`, `MICROSOFT_REDIRECT_URI`

---

## 🔎 5. Trazabilidad y Auditoría

### Audit Service (`audit-sdk`)
*   **Rol:** Registrar eventos y mutaciones del dominio funcional para mantener una bitácora e historial de auditoría de las acciones de los usuarios (como cambios de umbrales o registros de producción).
*   **Dependencia Python:** `audit-sdk` (instalado localmente desde el empaquetado Wheel en [vendor/](file:///home/miguel/Proyectos/sgpmp-backend/vendor)).
*   **Configuración (.env):**
    *   `AUDIT_SERVICE_URL`: URL del microservicio de auditoría encargado de centralizar y persistir estos eventos (ej. `http://localhost:8002` o la URL del contenedor correspondiente).
