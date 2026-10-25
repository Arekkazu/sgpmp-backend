# Seguimiento del Entorno TEST - Backend SGPMP

## 1. Objetivo

Preparar, validar y dejar técnicamente listo para entrega a Despliegue un entorno TEST independiente para el Backend del proyecto SGPMP, tomando como referencia la configuración vigente de Desarrollo y sin modificar el funcionamiento de la rama `dev`.

El trabajo contempla:

- configuración Docker específica para TEST;
- aislamiento de PostgreSQL TEST respecto a otros ambientes;
- restauración controlada de la base de datos;
- aplicación y validación de migraciones Alembic;
- aplicación del principio de mínima exposición de puertos;
- validación de persistencia;
- validación de comunicación Backend - PostgreSQL;
- validación de `health`, rutas y CORS;
- sincronización final con la rama `dev`;
- documentación de comandos, resultados, hallazgos, evidencias y pendientes.

## 2. Alcance

El alcance actual del grupo de Implementación comprende:

- entorno TEST del Backend;
- PostgreSQL TEST asociado al Backend;
- seguridad y exposición de puertos;
- validación técnica local;
- documentación para entrega a Despliegue.

Quedan fuera del alcance actual:

- PROD;
- configuración final de Dokploy;
- dominios y certificados HTTPS;
- instalación o mantenimiento de herramientas propias del equipo de Pruebas;
- implementación del entorno AIoT;
- modificación funcional del código de Desarrollo para corregir hallazgos que no sean responsabilidad de Implementación.

La rama `dev` se utiliza como referencia vigente de Desarrollo y no se modifica desde la rama de trabajo de Implementación.

---

## 3. Repositorio y ramas

Repositorio:

    Arekkazu/sgpmp-backend

### Base histórica inicial

La rama de trabajo TEST se creó originalmente desde:

    origin/integration-v2

Commit base histórico:

    39b817c453719110cd7af4eb2616fc0d41f7cebe

Mensaje:

    Remove the Oracle-specific direct-port override

Rama de trabajo:

    feat/ambiente-test

### Sincronización final con DEV

Posteriormente se determinó que el ambiente TEST debía quedar alineado con la rama de Desarrollo vigente.

Se actualizó:

    origin/dev

Commit DEV incorporado:

    a61e458

Antes de sincronizar se creó un respaldo local de la rama TEST:

    backup/ambiente-test-pre-dev-sync

apuntando al estado:

    6611fb4

La incorporación de DEV se realizó desde:

    feat/ambiente-test

mediante un merge de:

    origin/dev -> feat/ambiente-test

Commit de merge:

    6866c1d merge: incorpora cambios de dev en ambiente test

El único conflicto ocurrió en:

    docker-compose.yml

Como dicho archivo corresponde a la configuración DEV, se conservó exactamente la versión de `origin/dev`.

Se comprobó posteriormente:

    git diff origin/dev -- docker-compose.yml

Resultado:

    sin diferencias

Después de adaptar TEST al contrato actual de DEV se creó:

    d710681 feat(test): sincroniza configuración backend con dev

Validación final:

    origin/dev...HEAD = 0 10

Interpretación:

- `0`: la rama TEST no tiene commits pendientes por incorporar desde `dev`;
- `10`: la rama TEST contiene sus commits propios adicionales.

La rama de trabajo fue publicada y se confirmó:

    local = d710681
    origin/feat/ambiente-test = d710681
    local vs remoto = 0 0

No se realizó merge ni push hacia `dev`, `main` o `integration-v2`.

---

## 4. Estado inicial y evolución del trabajo

Antes de realizar modificaciones se verificó:

- repositorio correcto;
- remoto `origin` correcto;
- árbol de trabajo limpio;
- referencias remotas actualizadas;
- creación controlada de `feat/ambiente-test`;
- protección de archivos `.env` reales.

Durante una primera etapa TEST se tomó `integration-v2` como referencia.

Posteriormente Desarrollo avanzó y la referencia vigente pasó a ser `dev`.

Por esta razón, varias decisiones históricas fueron reevaluadas.

### Decisiones históricas posteriormente reemplazadas

En fases anteriores se llegó a:

- proponer una red externa `sgpmp-test-internal`;
- modificar temporalmente la configuración DEV para pruebas relacionadas con `pg_cron` y SMTP;
- considerar `ENV=test` como valor definitivo del entorno desplegado;
- utilizar `db` como hostname fijo de PostgreSQL;
- realizar restauraciones iniciales con estrategias específicas para excluir `pg_cron`.

Estas decisiones no representan el estado final.

Después de sincronizar con `dev` se definió como estado vigente:

- sin red externa obligatoria;
- `docker-compose.yml` DEV idéntico a `origin/dev`;
- TEST aislado mediante su propia red automática de Docker Compose;
- PostgreSQL TEST con nombre único basado en `POSTGRES_DB`;
- soporte de `pg_cron` mantenido únicamente donde TEST lo necesita para compatibilidad con el backup;
- `ENV=production` para TEST desplegado por HTTPS debido al comportamiento actual de la cookie refresh;
- `ENV=test` permitido para validaciones locales HTTP.

---

## 5. Arquitectura DEV vigente de referencia

El archivo vigente de Desarrollo es:

    docker-compose.yml

La versión final de este archivo en `feat/ambiente-test` coincide exactamente con:

    origin/dev

### PostgreSQL DEV

La configuración actual de DEV utiliza:

- `postgres:18`;
- `POSTGRES_USER`;
- `POSTGRES_PASSWORD`;
- `POSTGRES_DB`;
- publicación `${DB_PORT:-5447}:5432`;
- volumen persistente;
- healthcheck con `pg_isready`;
- nombre de contenedor basado en la base:

    ${POSTGRES_DB}-db

Este cambio de nomenclatura evita colisiones de DNS cuando existen varios stacks en infraestructura compartida.

### Backend DEV

El Backend:

- se construye desde `Dockerfile`;
- usa Uvicorn en `8000`;
- utiliza `expose: 8000`;
- depende de PostgreSQL saludable;
- construye `DATABASE_URL` usando como hostname:

    ${POSTGRES_DB}-db

DEV también entrega al contenedor variables de runtime como:

- `ENV`;
- `SECRET_KEY`;
- `FRONTEND_URL`;
- `ALLOWED_ORIGINS`;
- `ROOT_PATH`;
- variables SMTP.

---

## 6. Arquitectura TEST final implementada

El archivo específico de TEST es:

    docker-compose.test.yml

Proyecto Compose:

    sgpmp-backend-test

Servicios:

- `db`;
- `backend`.

### 6.1 PostgreSQL TEST

PostgreSQL TEST utiliza una imagen construida mediante:

    Dockerfile.postgres

Base:

    postgres:18

El Dockerfile instala:

    postgresql-18-cron

Esto permite restaurar y mantener la extensión `pg_cron` incluida en la base TEST.

El servicio utiliza:

- `POSTGRES_USER`;
- `POSTGRES_PASSWORD`;
- `POSTGRES_DB`;
- volumen exclusivo:

    sgpmp_pgdata_test

- healthcheck mediante `pg_isready`;
- `expose: 5432`;
- ninguna publicación mediante `ports`.

Nombre final del contenedor:

    ${POSTGRES_DB}-db

Con el valor local utilizado:

    sgpmp_test-db

### 6.2 Backend TEST

El servicio `backend`:

- se construye con `Dockerfile`;
- ejecuta Uvicorn en `8000`;
- utiliza `expose: 8000`;
- no publica `8000` al host en el Compose entregable;
- espera a que PostgreSQL esté `healthy`;
- se conecta mediante:

    ${POSTGRES_DB}-db:5432

La forma general de la conexión es:

    postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_DB}-db:5432/${POSTGRES_DB}

### 6.3 Red Docker final

No existe una dependencia de una red Docker externa.

El stack utiliza la red automática creada por Docker Compose:

    sgpmp-backend-test_default

Esta decisión reemplaza la propuesta histórica:

    sgpmp-test-internal

La red externa fue descartada porque AIoT no forma parte del alcance actual y Backend TEST no requiere dicha dependencia para funcionar.

### 6.4 Volumen persistente

El volumen físico validado es:

    sgpmp-backend-test_sgpmp_pgdata_test

Montado en:

    /var/lib/postgresql

No se comparte con DEV ni con recursos legado.

---

## 7. Archivos del ambiente TEST

### Archivos creados durante el trabajo

    docs/SEGUIMIENTO-ENTORNO-TEST.md
    docker-compose.test.yml
    .env.test.example
    Dockerfile.postgres

### Archivos locales no versionables

    .env.test
    docker-compose.local.yml

`.env.test` está protegido por `.gitignore`.

`docker-compose.local.yml` se mantuvo excluido localmente mediante:

    .git/info/exclude

El override local se utilizó exclusivamente para publicar temporalmente:

    127.0.0.1:8000 -> 8000

durante pruebas locales.

No forma parte del Compose entregable a Despliegue.

### Integridad de DEV

El estado final de:

    docker-compose.yml

es idéntico a `origin/dev`.

Los experimentos o modificaciones históricas realizadas sobre DEV durante etapas anteriores quedaron reemplazados por la sincronización final con `dev`.

---

## 8. Variables y contrato TEST vigente

El contrato final de TEST se revisó nuevamente después de incorporar `dev`.

### PostgreSQL

- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_DB`

`DB_PORT` no es necesario para el Compose TEST porque PostgreSQL no se publica hacia el host.

`DATABASE_URL` no se almacena en `.env.test`; Docker Compose la construye internamente.

### Backend principal

- `SECRET_KEY`
- `JWT_EXPIRE_HOURS`
- `REFRESH_TOKEN_EXPIRE_DAYS`
- `FRONTEND_URL`
- `ENV`
- `ALLOWED_ORIGINS`
- `ROOT_PATH`

### SMTP

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASSWORD`

### Firebase

El código consume:

    FIREBASE_CREDENTIALS_PATH

La inicialización es diferida y no bloquea el arranque básico si la variable no está configurada.

### Modelos

- `MODELOS_STORAGE_PATH`

Si no se define, el código puede utilizar:

    /tmp/sgpmp_modelos

La persistencia funcional de artefactos deberá definirse con Desarrollo/Despliegue si dicha funcionalidad forma parte de las pruebas.

### AgroFusion

- `AGROFUSION_SSO_PUBLIC_KEY_PATH`
- `AGROFUSION_PROJECT_CODE`
- `AGROFUSION_ISSUER`
- `AGROFUSION_HUB_CLIENT_ID`
- `AGROFUSION_HUB_CLIENT_SECRET`

No son necesarias para el arranque básico si las integraciones correspondientes no se validan.

### RF-71

- `RF71_INTERNAL_KEY`

Es utilizada por el flujo interno de registro de versiones de modelo y debe tratarse como secreto.

### MQTT

Después de sincronizar con `dev` se identificó soporte para:

- `MQTT_BROKER_URL`
- `MQTT_BROKER_TOKEN`

Sin embargo, AIoT no forma parte del alcance actual.

El adaptador actual degrada de forma controlada cuando estas variables no se proporcionan, por lo que no fueron incorporadas forzosamente al entorno TEST en esta fase.

---

## 9. `ENV`, CORS, cookies y `ROOT_PATH`

Esta parte cambió respecto de la auditoría inicial y debe utilizarse el comportamiento vigente.

### 9.1 CORS actual

`main.py` utiliza:

    ALLOWED_ORIGINS

como lista explícita de orígenes permitidos.

También mantiene soporte local para:

    localhost
    127.0.0.1

La validación local comprobó que:

    Origin: http://127.0.0.1:8080

es aceptado y recibe:

    Access-Control-Allow-Origin: http://127.0.0.1:8080
    Access-Control-Allow-Credentials: true

Un origen HTTPS ficticio no incluido en `ALLOWED_ORIGINS` no recibió `Access-Control-Allow-Origin`.

Esto confirma que el control de origen funciona.

### 9.2 Cookie refresh

El código actual determina el comportamiento de la cookie refresh mediante:

    ENV == "production"

Cuando es `production` utiliza:

    Secure=true
    SameSite=None

Para una integración Frontend TEST / Backend TEST desplegada mediante dominios HTTPS separados, esta configuración es necesaria para el flujo actual de autenticación.

Por esta razón `.env.test.example` documenta:

    ENV=production

para TEST desplegado por HTTPS.

Para validaciones locales HTTP puede utilizarse:

    ENV=test

### 9.3 `ALLOWED_ORIGINS`

Despliegue deberá definir:

    ALLOWED_ORIGINS=https://<frontend-test-real>

sin inventar el dominio antes de que exista.

### 9.4 `ROOT_PATH`

Se utiliza:

    ROOT_PATH=/api

Se validó que funcionan:

    GET /health
    GET /api/health

ambos con HTTP 200 en el entorno local validado.

---

## 10. Seguridad de puertos

**Actualizado — decisión final revisada.** Esta sección describía
originalmente `expose`-only para PostgreSQL (sin publicar al host). Esa
decisión quedó reemplazada por el commit "Configuración final del Compose
de TEST": `docker-compose.test.yml` **sí publica** PostgreSQL al host
(`${DB_PORT:-5448}:5432`), el mismo patrón que ya usa `dev` (`5447`). El
texto de abajo quedaba desactualizado respecto al compose real; se corrige
aquí en vez de mantener una descripción que ya no coincide con lo que se
despliega.

### PostgreSQL TEST

Puerto interno:

    5432

Compose TEST:

    ports:
      - "${DB_PORT:-5448}:5432"

**Por qué se publica, y no `expose`-only:** el equipo de Pruebas/DBA
necesita poder conectarse directo con `psql`/DBeaver/pgAdmin durante el
ciclo de pruebas para verificar datos — sin eso, cada verificación
manual requeriría pasar por el backend o pedirle a alguien con acceso al
servidor que la haga por ellos. Es el mismo patrón ya validado y usado
activamente en `dev` (puerto `5447`).

**El control de seguridad real no es el compose, es el firewall del
servidor.** Publicar el puerto en Docker solo lo hace alcanzable *dentro*
de la red del servidor; que sea alcanzable desde *internet* depende de si
alguien abre ese puerto en `ufw`/el firewall del proveedor. La
recomendación de seguridad real es:

- Pedir que `DB_PORT` (`5448`) se habilite en el firewall **solo para IPs
  conocidas** (IP de oficina/VPN del equipo), no abierto a `0.0.0.0/0` —
  mismo criterio que ya se usa para el puerto de PostgreSQL de `dev`.
- Postgres sigue exigiendo usuario/contraseña — publicar el puerto no
  expone los datos sin autenticación, solo la superficie de conexión.
- Usar una contraseña de `POSTGRES_PASSWORD` distinta y fuerte para TEST,
  no reutilizar la de `dev`.

### Backend TEST

Puerto interno:

    8000

Compose TEST:

    expose:
      - "8000"

No existe publicación directa mediante:

    ports:
      - "8000:8000"

### Acceso local controlado

Para las pruebas locales se utilizó un override no versionado con:

    127.0.0.1:8000:8000

No se utilizó:

    0.0.0.0:8000:8000

### Exposición esperada en Despliegue

Arquitectura:

    Internet
        |
      HTTPS 443              Puerto DB_PORT (5448)
        |                     restringido a IPs conocidas
        v                              |
    Traefik / Dokploy                  v
        |                    PostgreSQL TEST :5432
        v                    (acceso directo, autenticado,
    Backend TEST :8000         solo para Pruebas/DBA)

PostgreSQL se publica al host (ver sección "PostgreSQL TEST" arriba),
restringido a nivel de firewall a IPs conocidas — no queda abierto a
cualquier IP de internet, ni depende únicamente de la autenticación de
Postgres como única barrera.

TLS/HTTPS debe terminar en Traefik/Dokploy para el Backend; Uvicorn
permanece en el puerto interno `8000` sin publicar al host, enrutado por
dominio.

Resultado: **Seguridad de puertos validada** — con la corrección de esta
revisión: PostgreSQL publicado con acceso restringido por firewall, no
`expose`-only.

---

## 11. Base de datos TEST, backup y migraciones

### 11.1 Backup original

Se trabajó inicialmente con el backup entregado por Desarrollo:

    backup_sgpmp.dump

Características históricas verificadas:

- formato PostgreSQL CUSTOM;
- tamaño aproximado 6,5 MB;
- origen funcional de la base entregada;
- restauración realizada con herramientas PostgreSQL disponibles en el contenedor.

SHA-256 registrado:

    9a1da173b1076dcc5f5e2f955353ca1c762981b1cec6b850e0a4a840f4a9a6b3

### 11.2 Estado posterior a la sincronización con DEV

Después de incorporar `dev`, el repositorio contiene migraciones Alembic:

    f7fe43537842  baseline
    7e2d5f3bf17a  RF-23
    aa24fc52896e  RF-14

Head actual:

    aa24fc52896e

La base TEST se encontró inicialmente en:

    7e2d5f3bf17a

La migración RF-14 fue aplicada mediante:

    alembic upgrade head

Resultado:

    aa24fc52896e (head)

También se comprobó la creación del índice:

    modulo1.ix_notificaciones_bandeja_usuario

### 11.3 Backup pre-RF14 utilizado para reproducibilidad

Antes de aplicar RF-14 se generó un nuevo backup de seguridad:

    sgpmp_test_pre_rf14_20260823_200815.dump

Tamaño:

    6,708,764 bytes

SHA-256:

    716a855169afe7c8cec64b4c864d71327127251714566bd8f747359d01608c8b

La lista del dump fue validada correctamente con `pg_restore -l`.

El backup representa una base con:

    208 tablas de usuario
    Alembic = 7e2d5f3bf17a
    pg_cron = 1.6

y sin el índice RF-14 todavía aplicado.

### 11.4 Estrategia final de creación de una BD TEST nueva

El repositorio no contiene un mecanismo automático de restauración del backup.

Además, el baseline Alembic es intencionalmente un no-op, por lo que una base completamente vacía no puede construirse únicamente mediante:

    alembic upgrade head

El procedimiento validado es:

    1. levantar PostgreSQL TEST vacío
    2. restaurar el backup base una sola vez
    3. ejecutar alembic upgrade head
    4. levantar/usar Backend TEST
    5. conservar el volumen persistente

La restauración no debe ejecutarse automáticamente en cada:

    docker compose up

### 11.5 Opciones de restauración validadas

En la prueba final se utilizó el `pg_restore` disponible dentro del contenedor PostgreSQL:

    --no-owner
    --no-privileges
    --exit-on-error

No fue necesario exponer PostgreSQL al host.

El host local no disponía de `pg_restore`, por lo que se utilizaron las herramientas del contenedor.

---

## 12. Prueba de reproducibilidad `fresh-check`

Para demostrar que TEST puede levantarse desde cero sin tocar la instancia TEST real, se creó un proyecto Compose completamente aislado:

    sgpmp-backend-test-freshcheck

Base de datos:

    sgpmp_test_freshcheck

Contenedor:

    sgpmp_test_freshcheck-db

Volumen:

    sgpmp-backend-test-freshcheck_sgpmp_pgdata_test

Red:

    sgpmp-backend-test-freshcheck_default

### 12.1 Estado vacío inicial

Antes de restaurar:

    tablas de usuario = 0

El TEST real permaneció:

    healthy

### 12.2 Restauración

Se restauró el backup pre-RF14.

Resultado:

    restore-exit=0

Después de la restauración:

    tablas de usuario = 208
    Alembic = 7e2d5f3bf17a
    pg_cron = 1.6
    índice RF-14 = ausente

Este era exactamente el estado esperado del backup.

### 12.3 Migración

Desde el mismo Compose TEST se ejecutó:

    alembic current

Resultado:

    7e2d5f3bf17a

Posteriormente:

    alembic upgrade head

Resultado:

    fresh-migration-exit=0

Estado final:

    Alembic = aa24fc52896e
    índice RF-14 = modulo1|ix_notificaciones_bandeja_usuario
    tablas de usuario = 208

### 12.4 Levantamiento de Backend sobre fresh-check

Se levantó el Backend utilizando la misma configuración TEST.

Resultado:

    backend = Up
    db = healthy

Health:

    status=200
    {"status":"ok","message":"API funcionando correctamente"}

Conexión SQL desde Backend:

    database=sgpmp_test_freshcheck
    alembic=aa24fc52896e
    sql=OK

Los logs mostraron arranque normal de Uvicorn y `GET /health` con `200 OK`.

### 12.5 Aislamiento respecto al TEST real

Durante toda la prueba:

    sgpmp_test-db = healthy
    TEST real /health = 200
    TEST real Alembic = aa24fc52896e

Por tanto, `fresh-check` no modificó la instancia real.

### 12.6 Limpieza

Después de completar la validación se eliminó únicamente:

    sgpmp-backend-test-freshcheck

incluyendo su volumen descartable mediante:

    docker compose -p sgpmp-backend-test-freshcheck ... down -v

Se comprobó posteriormente:

- sin contenedores fresh-check;
- sin volumen fresh-check;
- TEST real operativo;
- TEST real PostgreSQL `healthy`;
- TEST real `/health = 200`;
- TEST real Alembic `aa24fc52896e`.

Resultado general: **Reproducibilidad desde cero validada**.

---

## 13. Pruebas y validaciones finales del Backend TEST

### 13.1 Compose

Se validó:

    docker compose --env-file .env.test -f docker-compose.test.yml config --quiet

Resultado:

    exit=0

También se ejecutó:

    git diff --check

Resultado:

    exit=0

### 13.2 Persistencia

El volumen utilizado por TEST es:

    sgpmp-backend-test_sgpmp_pgdata_test

Después de recrear servicios, los datos permanecieron disponibles.

Estado final observado:

    tablas de usuario = 208
    Alembic = aa24fc52896e
    pg_cron = 1.6
    índice RF-14 presente

### 13.3 DNS interno

Desde Backend se comprobó resolución del hostname:

    sgpmp_test-db

y conectividad TCP a:

    5432

Resultado: **Correcto**.

### 13.4 Backend -> PostgreSQL

Usando el `DATABASE_URL` real del contenedor, sin imprimir secretos:

    database=sgpmp_test
    sql=OK
    alembic=aa24fc52896e

Resultado: **Correcto**.

### 13.5 Health

    GET http://127.0.0.1:8000/health

Resultado:

    HTTP 200
    {"status":"ok","message":"API funcionando correctamente"}

También se comprobó:

    GET /api/health -> HTTP 200

### 13.6 Logs

Los logs mostraron:

    Started server process
    Waiting for application startup
    Application startup complete
    Uvicorn running on http://0.0.0.0:8000
    GET /health -> 200 OK

No se observaron errores críticos de inicialización en la validación final.

### 13.7 CORS local

Origen probado:

    http://127.0.0.1:8080

Preflight:

    HTTP 200
    Access-Control-Allow-Origin: http://127.0.0.1:8080
    Access-Control-Allow-Credentials: true
    Access-Control-Allow-Headers: authorization,content-type

Se validó tanto sobre rutas directas como con prefijo `/api`.

### 13.8 CORS externo no autorizado

Con un origen HTTPS ficticio no configurado se comprobó que no se entrega `Access-Control-Allow-Origin`.

Resultado: **Correcto**.

### 13.9 Integración local con Frontend

Frontend TEST fue construido temporalmente con:

    VITE_API_BASE_URL=http://127.0.0.1:8000/api

Se comprobó que:

    /api/health -> 200

y que el Backend permite el origen local del Frontend con credenciales.

Las pruebas anteriores de autenticación ya habían demostrado el recorrido técnico:

    Frontend TEST
        ->
    Backend TEST
        ->
    SQLAlchemy
        ->
    PostgreSQL TEST

Resultado: **Integración local técnica correcta**.

---

## 14. `pg_cron`

### Estado histórico

En una fase inicial, debido a que la imagen estándar `postgres:18` no incluía `pg_cron`, se evaluó filtrar las entradas relacionadas con la extensión durante la restauración.

Posteriormente se incorporó:

    Dockerfile.postgres

con:

    postgresql-18-cron

Por tanto, la estrategia de excluir `pg_cron` del backup quedó reemplazada.

### Estado final TEST

TEST mantiene soporte para:

    pg_cron 1.6

porque:

- el backup restaurado contiene la extensión;
- una restauración nueva debe disponer del paquete;
- el uso de la imagen personalizada evita incompatibilidades al reproducir la base.

Se comprobó después de la sincronización con DEV:

    pg_cron = 1.6

y el backup pre-RF14 pudo restaurarse correctamente sobre una instancia nueva.

### DEV

La configuración final de:

    docker-compose.yml

se conserva exactamente como `origin/dev`.

No se fuerza `pg_cron` sobre DEV desde la rama TEST.

---

## 15. Errores y hallazgos

### 15.1 Primer intento histórico de `pg_restore`

Un primer intento de restauración falló al no especificar el usuario PostgreSQL:

    FATAL: role "root" does not exist

La base permaneció sin restauración parcial.

Se corrigió usando el usuario PostgreSQL explícito.

Estado: **Resuelto**.

### 15.2 Red externa TEST

La propuesta inicial:

    sgpmp-test-internal

fue reevaluada y eliminada de la configuración final.

Motivo:

- Backend y PostgreSQL funcionan correctamente con la red propia de Compose;
- AIoT se encuentra fuera del alcance actual;
- no existe justificación para obligar a Despliegue a crear una red externa adicional.

Estado: **Resuelto / decisión reemplazada**.

### 15.3 CORS

La auditoría histórica de CORS quedó desactualizada después de incorporar `dev`.

El comportamiento actual utiliza:

    ALLOWED_ORIGINS

más soporte local para localhost/127.0.0.1.

La integración desplegada debe definir el origen HTTPS real del Frontend TEST.

### 15.4 Cookies refresh y `ENV`

TEST desplegado requiere:

    ENV=production

bajo el código actual para obtener:

    Secure=true
    SameSite=None

No significa que TEST se convierta en PROD; corresponde al comportamiento técnico actual de la cookie.

Este punto debe quedar comunicado a Despliegue.

### 15.5 Alembic no crea una base completamente vacía

El baseline actual no reconstruye el esquema histórico.

Por tanto:

    PostgreSQL vacío + alembic upgrade head

no es suficiente.

Se requiere restaurar primero el backup base.

Estado: **Limitación conocida y procedimiento validado**.

### 15.6 `.env.example` y variables reales consumidas

Se identificaron diferencias entre algunas variables documentadas y las realmente consumidas por el código, incluyendo históricamente:

- `RF71_INTERNAL_KEY`;
- `FIREBASE_CREDENTIALS_PATH`;
- variables MQTT.

No se modificó automáticamente `.env.example` de DEV para corregir estos puntos.

### 15.7 AIoT / MQTT

`dev` contiene soporte MQTT, pero la integración AIoT no forma parte de esta etapa.

No se agregaron valores ficticios ni recursos de AIoT al entorno TEST.

---

## 16. Alcance respecto a herramientas de Pruebas

Implementación no debe instalar, configurar ni mantener herramientas como:

- Cypress;
- Playwright;
- cypress-axe;
- k6;
- OWASP ZAP;
- otras herramientas de E2E, carga o seguridad propias del equipo de Pruebas.

El criterio utilizado es:

    Implementación monta y orquesta el ambiente TEST.
    Pruebas lo opera.

Los experimentos anteriores relacionados con tooling de QA fueron limpiados y no forman parte del estado final del repositorio.

No se eliminaron las herramientas o pruebas que ya pertenecieran originalmente a Desarrollo.

---

## 17. Entrega a Despliegue

### 17.1 Estado técnico disponible

La rama técnica validada y publicada es:

    origin/feat/ambiente-test

Estado técnico publicado antes de esta actualización documental:

    d710681

La rama contiene todos los commits vigentes de `dev`.

### 17.2 Recursos que recibe Despliegue

- `docker-compose.test.yml`;
- `.env.test.example`;
- `Dockerfile.postgres`;
- código Backend sincronizado con `dev`;
- migraciones Alembic vigentes;
- documentación de seguimiento.

### 17.3 Variables reales

Despliegue debe configurar valores reales y secretos fuera de Git.

Especialmente:

    POSTGRES_USER
    POSTGRES_PASSWORD
    POSTGRES_DB
    SECRET_KEY
    FRONTEND_URL
    ENV=production
    ALLOWED_ORIGINS=https://<frontend-test-real>
    ROOT_PATH=/api

y las variables de funcionalidades externas que correspondan al alcance funcional del ambiente.

### 17.4 Procedimiento validado para una instalación nueva

Orden recomendado:

    1. configurar variables TEST reales
    2. levantar PostgreSQL TEST
    3. restaurar el backup base una sola vez
    4. ejecutar alembic upgrade head
    5. levantar Backend TEST
    6. configurar dominio y HTTPS en Dokploy/Traefik
    7. validar /health
    8. validar conexión Backend - PostgreSQL
    9. revisar logs
    10. validar CORS con el dominio real del Frontend TEST

### 17.5 Puertos

Despliegue debe conservar:

    PostgreSQL 5432 -> interno únicamente
    Backend 8000 -> interno únicamente

La exposición pública esperada debe realizarse por HTTPS:

    443 -> Traefik/Dokploy -> backend:8000

PostgreSQL no debe publicarse directamente.

---

## 18. Pendientes posteriores

Continúan pendientes acciones que requieren infraestructura o definiciones externas:

- configurar la URL pública HTTPS definitiva del Backend TEST;
- configurar la URL pública HTTPS definitiva del Frontend TEST;
- establecer `ALLOWED_ORIGINS` con el origen real;
- validar CORS sobre los dominios públicos reales;
- validar el comportamiento de la cookie refresh sobre HTTPS real;
- confirmar variables Firebase requeridas para pruebas funcionales;
- confirmar variables AgroFusion si esas integraciones entran en el ciclo TEST;
- confirmar `RF71_INTERNAL_KEY` para la funcionalidad correspondiente;
- coordinar con Pruebas datos/credenciales de prueba;
- evaluar posteriormente un mecanismo explícito y controlado de reset de BD si QA lo requiere;
- integrar AIoT únicamente cuando exista autorización y alcance formal;
- revisar secretos, `git status`, `git diff` y archivos ignorados antes de cada entrega.

No debe agregarse un reset automático de la base a cada `docker compose up`.

---

## 19. Evidencias finales

Evidencias técnicas obtenidas durante la preparación:

    Rama de trabajo                               feat/ambiente-test
    DEV incorporado                              a61e458
    Merge DEV -> TEST                            6866c1d
    Commit técnico final                         d710681
    origin/dev...HEAD                            0 10
    local/remoto técnico                         d710681 / d710681

    Compose TEST                                 VALIDADO
    PostgreSQL TEST                              HEALTHY
    Backend TEST                                 UP
    PostgreSQL puerto 5432 público               NO
    Backend puerto 8000 público                  NO
    Override local Backend                       127.0.0.1:8000

    Tablas de usuario                            208
    pg_cron                                      1.6
    Alembic head                                 aa24fc52896e
    Índice RF-14                                 PRESENTE

    GET /health                                  200
    GET /api/health                              200
    Backend -> PostgreSQL                        SQL OK
    CORS localhost                               VALIDADO
    credentials CORS                             true

    Fresh-check DB vacía                         0 tablas
    Restore fresh-check                          EXIT 0
    Fresh-check post-restore                     208 tablas
    Fresh-check Alembic inicial                  7e2d5f3bf17a
    Fresh-check alembic upgrade head             EXIT 0
    Fresh-check Alembic final                    aa24fc52896e
    Fresh-check Backend /health                  200
    Fresh-check Backend -> PostgreSQL             SQL OK
    Fresh-check eliminado                        SÍ
    TEST real después de fresh-check              HEALTHY

    .env.test                                    IGNORADO
    docker-compose.local.yml                     IGNORADO LOCALMENTE
    git diff --check                             0

---

## 20. Estado final

**Configuración técnica del Backend TEST completada y lista para entrega a Despliegue.**

El Backend TEST:

- está sincronizado con la rama `dev` vigente;
- no modifica `dev`;
- utiliza una configuración TEST separada;
- mantiene PostgreSQL aislado y persistente;
- no expone PostgreSQL al host;
- no expone directamente Backend al host en el Compose entregable;
- soporta el backup actual con `pg_cron`;
- tiene migraciones Alembic actualizadas hasta `aa24fc52896e`;
- fue validado mediante restauración real;
- fue validado mediante una instalación aislada desde cero;
- responde `HTTP 200` en `/health`;
- se conecta correctamente a PostgreSQL;
- tiene CORS local y prefijo `/api` validados;
- tiene la rama técnica publicada en `origin/feat/ambiente-test`.

La siguiente etapa corresponde a Despliegue:

- configurar variables reales;
- restaurar el backup en la infraestructura TEST nueva;
- aplicar Alembic;
- configurar dominio y HTTPS;
- definir `ALLOWED_ORIGINS`;
- validar health, conexión a base, logs y CORS sobre las URLs reales.

Las herramientas de pruebas E2E, carga, accesibilidad y seguridad serán operadas por el equipo de Pruebas contra el ambiente TEST entregado por Implementación.
