# Seguimiento del Entorno TEST - Backend SGPMP

## 1. Objetivo

Implementar y validar un entorno TEST independiente para el Backend del proyecto SGPMP, tomando como referencia la configuración DEV existente en la rama `integration-v2`.

El trabajo contempla:

- creación del entorno TEST;
- aislamiento de PostgreSQL TEST respecto a DEV;
- aplicación del principio de mínima exposición de puertos;
- validación de persistencia;
- validación de conectividad Backend - PostgreSQL;
- documentación de decisiones, pruebas, hallazgos y evidencias.

## 2. Alcance

El alcance actual del grupo de Implementación comprende exclusivamente:

- entorno TEST;
- seguridad de puertos;
- documentación.

El entorno PROD queda fuera del alcance actual.

El archivo DEV `docker-compose.yml` no debe modificarse innecesariamente.

## 3. Repositorio y ramas

- Repositorio: `Arekkazu/sgpmp-backend`
- Rama DEV de referencia: `integration-v2`
- Rama de trabajo: `feat/ambiente-test`
- Commit base de `integration-v2`: `39b817c453719110cd7af4eb2616fc0d41f7cebe`
- Mensaje del commit base: `Remove the Oracle-specific direct-port override`

La rama `feat/ambiente-test` fue creada directamente desde `origin/integration-v2`.

## 4. Estado inicial

Antes de realizar modificaciones se verificó:

- el clon local corresponde a `sgpmp-backend`;
- el remoto `origin` corresponde a `https://github.com/Arekkazu/sgpmp-backend.git`;
- el árbol de trabajo estaba limpio;
- `origin/integration-v2` existe;
- se actualizaron las referencias mediante `git fetch origin --prune`;
- la rama de trabajo fue creada desde el mismo SHA que `origin/integration-v2`.

## 5. Arquitectura DEV de referencia

Se auditó el archivo `docker-compose.yml` existente en `integration-v2`.

La configuración DEV confirmada contiene dos servicios:

- `db`
- `backend`

### PostgreSQL DEV

El servicio `db` utiliza:

- imagen `postgres:18`;
- variables `POSTGRES_USER`, `POSTGRES_PASSWORD` y `POSTGRES_DB`;
- publicación de puerto `${DB_PORT:-5447}:5432`;
- volumen persistente `sgpmp_pgdata`;
- healthcheck mediante `pg_isready`;
- política de reinicio `unless-stopped`.

El volumen se monta en:

    /var/lib/postgresql

### Backend DEV

El servicio `backend`:

- se construye desde el `Dockerfile` del repositorio;
- recibe explícitamente `DATABASE_URL`, `SECRET_KEY` y `FRONTEND_URL`;
- conecta a PostgreSQL mediante el hostname Docker `db` y el puerto interno `5432`;
- utiliza `expose` para el puerto interno `8000`;
- no publica directamente el puerto `8000` mediante `ports`;
- depende de que `db` alcance el estado `service_healthy`;
- utiliza la política de reinicio `unless-stopped`.

La conexión configurada tiene la forma:

    postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}

### Red DEV

El Compose auditado no declara una sección `networks` explícita.

Por lo tanto, los servicios `db` y `backend` utilizan la red predeterminada creada por Docker Compose para este proyecto.

### Validación de integridad de DEV

Se ejecutó:

    git diff origin/integration-v2 -- docker-compose.yml

El comando no produjo diferencias.

Resultado en ese punto del proceso: el archivo `docker-compose.yml` utilizado como referencia permanecía idéntico al existente en `origin/integration-v2`.

## 6. Arquitectura TEST

El entorno TEST se diseñó inicialmente como un stack independiente dentro del repositorio Backend, sin modificar el `docker-compose.yml` utilizado como referencia DEV.

Esta condición se mantuvo durante la construcción y validación inicial de TEST. Posteriormente, por solicitud explícita del líder de Desarrollo, se autorizó modificar `docker-compose.yml` para incorporar `pg_cron` al PostgreSQL DEV y pasar las variables SMTP al contenedor Backend DEV.

El archivo previsto para este ambiente será:

    docker-compose.test.yml

La arquitectura propuesta contiene dos servicios:

- `db`
- `backend`

### PostgreSQL TEST

El servicio `db` utilizará:

- la misma versión de PostgreSQL que DEV: `postgres:18`;
- credenciales específicas de TEST;
- una base de datos específica de TEST;
- un volumen persistente exclusivo de TEST;
- healthcheck mediante `pg_isready`;
- puerto interno `5432`;
- ninguna publicación directa de `5432` hacia el host.

El volumen TEST deberá ser diferente de `sgpmp_pgdata`, utilizado actualmente por DEV.

Nombre propuesto:

    sgpmp_pgdata_test

El backup de la base de datos deberá restaurarse sobre este PostgreSQL TEST una vez inicializado.

El backup no se restaurará automáticamente en cada `docker compose up`.

### Backend TEST

El servicio `backend` continuará:

- construyéndose desde el `Dockerfile` actual;
- ejecutándose mediante Uvicorn en el puerto interno `8000`;
- esperando a que PostgreSQL alcance el estado saludable;
- conectándose a PostgreSQL mediante DNS interno de Docker.

La conexión mantendrá el patrón:

    postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}

El Backend TEST no publicará directamente:

    8000:8000

Se conservará el uso del puerto interno `8000` para permitir posteriormente el enrutamiento mediante Dokploy/Traefik cuando corresponda.

### Red compartida TEST

Se propone utilizar una red Docker externa específica del ambiente:

    sgpmp-test-internal

Tanto `db` como `backend` se conectarán a esta red.

Esta red permitirá posteriormente conectar el Gateway TEST del repositorio AIoT al mismo PostgreSQL TEST sin crear una segunda base de datos y sin publicar PostgreSQL hacia Internet.

Arquitectura conceptual:

    Backend TEST
    ┌──────────────────────────────┐
    │                              │
    │ backend                      │
    │   puerto interno 8000        │
    │        │                     │
    │        ▼                     │
    │ db                           │
    │   PostgreSQL 18              │
    │   puerto interno 5432        │
    │   volumen TEST independiente │
    │                              │
    └────────────┬─────────────────┘
                 │
                 │ sgpmp-test-internal
                 │
                 ▼
           Gateway TEST
           (fase AIoT posterior)

### Aislamiento respecto a DEV

TEST no deberá compartir con DEV:

- volumen PostgreSQL;
- base de datos;
- credenciales;
- datos persistentes.

Durante la construcción y validación inicial del ambiente TEST, el archivo `docker-compose.yml` de DEV se mantuvo sin modificaciones. Esta condición cambió posteriormente por solicitud explícita de Desarrollo, como se documenta en la sección de actualización posterior de DEV.

### Aislamiento del proyecto Docker Compose

Se inspeccionó el estado local de Docker antes de implementar TEST.

La versión disponible es:

- Docker `29.6.2`;
- Docker Compose `v5.3.1`.

El nuevo stack Backend TEST utilizará un nombre de proyecto Compose independiente:

    sgpmp-backend-test

Esto permitirá diferenciar los recursos TEST de otros stacks ejecutados desde el mismo equipo o repositorio.

No se utilizará `container_name` por defecto. Se permitirá que Docker Compose administre los nombres de los contenedores dentro del proyecto `sgpmp-backend-test`.

### Nomenclatura del nuevo ambiente

Se utilizarán como referencia los siguientes nombres:

- proyecto Compose: `sgpmp-backend-test`;
- red externa compartida: `sgpmp-test-internal`;
- volumen lógico de PostgreSQL TEST: `sgpmp_pgdata_test`;
- imagen base PostgreSQL: `postgres:18`;
- imagen PostgreSQL TEST: construida localmente mediante `Dockerfile.postgres` a partir de `postgres:18`, incorporando `pg_cron`.

El nombre físico final del volumen podrá ser administrado por Docker Compose a partir del nombre del proyecto y del volumen lógico.

### Recursos TEST legado encontrados

Durante la inspección local se encontraron recursos pertenecientes a una implementación TEST anterior:

- contenedor `sgpmp-postgres-test`;
- volumen `sgpmp-postgres-test-data`;
- red `sgpmp-test-network`.

Se comprobó que:

- `sgpmp-postgres-test` utiliza `postgres:16`;
- pertenece al proyecto Compose `implementacion`;
- utiliza el volumen `sgpmp-postgres-test-data`;
- dicho volumen también está etiquetado como perteneciente al proyecto `implementacion`;
- la red `sgpmp-test-network` actualmente no tiene contenedores conectados.

Estos recursos se consideran legado respecto al nuevo trabajo.

No serán:

- reutilizados;
- modificados;
- eliminados;

como parte de la creación inicial del nuevo Backend TEST.

La nueva red `sgpmp-test-internal` no existía al momento de la inspección y queda reservada conceptualmente para la arquitectura TEST actual.

### Estado del diseño

Esta arquitectura quedó definida para la implementación del ambiente TEST.

Se creó `docker-compose.test.yml` para el ambiente TEST. PostgreSQL TEST y Backend TEST fueron posteriormente levantados y validados de forma independiente.

Las validaciones realizadas y sus resultados se documentan en las secciones posteriores.

## 7. Archivos creados

- `docs/SEGUIMIENTO-ENTORNO-TEST.md`
- `docker-compose.test.yml`
- `.env.test.example`
- `.env.test` (archivo local de configuración, ignorado por Git y no versionable)
- `Dockerfile.postgres`: imagen PostgreSQL común para DEV y TEST con soporte de `pg_cron`.

## 8. Archivos modificados

- `.gitignore`: se agregó la excepción `!.env.test.example` para permitir versionar únicamente la plantilla de variables TEST, manteniendo `.env.test` ignorado.
- `docker-compose.yml`: inicialmente permaneció intacto durante la construcción de TEST. Posteriormente fue modificado por solicitud de Desarrollo para utilizar `Dockerfile.postgres`, habilitar `pg_cron` y pasar las variables SMTP al Backend DEV.

## 9. Variables y configuración

Se auditó el archivo `.env.example` de `integration-v2`.

### Variables declaradas

#### PostgreSQL

- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_DB`
- `DB_PORT`

El Compose DEV construye `DATABASE_URL` a partir de las variables de PostgreSQL.

#### Autenticación

- `SECRET_KEY`
- `JWT_EXPIRE_HOURS`

#### Frontend y CORS

- `FRONTEND_URL`

#### Ambiente de ejecución

- `ENV`

La documentación existente indica que `production` habilita comportamiento específico de producción y que DEV/TEST deben utilizar otro valor o dejarlo vacío.

#### SMTP

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASSWORD`

#### Firebase

- `FIREBASE_CREDENTIALS_PATH`

#### Almacenamiento de modelos

- `MODELOS_STORAGE_PATH`

#### AgroFusion

- `AGROFUSION_SSO_PUBLIC_KEY_PATH`
- `AGROFUSION_PROJECT_CODE`
- `AGROFUSION_ISSUER`
- `AGROFUSION_HUB_CLIENT_ID`
- `AGROFUSION_HUB_CLIENT_SECRET`

### Clasificación parcial confirmada

La revisión del código permitió confirmar el comportamiento de las variables principales.

#### `DATABASE_URL`

`src/shared/database.py` obtiene `DATABASE_URL` mediante `os.getenv` y la utiliza inmediatamente para crear el engine de SQLAlchemy.

Además, múltiples routers importados durante el arranque de `main.py` importan a su vez `src.shared.database`.

Por lo tanto:

- `DATABASE_URL` debe estar disponible cuando arranca el Backend;
- no tiene un valor por defecto en el código;
- en Docker Compose DEV se construye a partir de `POSTGRES_USER`, `POSTGRES_PASSWORD` y `POSTGRES_DB`.

#### `POSTGRES_*`

Las variables:

- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_DB`

no son consumidas directamente por el código Python encontrado.

Son utilizadas por Docker Compose para:

- configurar PostgreSQL;
- construir `DATABASE_URL` para el Backend.

#### `SECRET_KEY`

`src/shared/jwt.py` obtiene `SECRET_KEY` sin valor por defecto.

La variable se utiliza para firmar y verificar tokens JWT.

No se observó una validación explícita durante la importación del módulo, pero la funcionalidad de autenticación requiere que TEST proporcione una clave válida.

No se debe versionar su valor real.

#### `JWT_EXPIRE_HOURS`

`JWT_EXPIRE_HOURS` es configurable y tiene un valor por defecto de `8` horas definido en el código.

Por lo tanto, no es estrictamente necesaria para inicializar la aplicación, aunque se mantendrá explícita en la configuración TEST para que el comportamiento del ambiente quede documentado.

### Carga de variables dentro del contenedor

El código utiliza `load_dotenv()`, pero el `Dockerfile` no define variables mediante `ENV` o `ARG`.

Además, `.dockerignore` excluye:

    .env
    .env.*

Por lo tanto, el diseño TEST no debe depender de que un archivo `.env.test` sea copiado dentro de la imagen.

Las variables requeridas por la aplicación deberán ser inyectadas al contenedor mediante la configuración del entorno de ejecución, por ejemplo Docker Compose o posteriormente Dokploy.

### Hallazgo adicional: `RF71_INTERNAL_KEY`

Durante la búsqueda del consumo de variables se encontró:

    RF71_INTERNAL_KEY

en el código del módulo de predicción.

Esta variable no aparece actualmente en `.env.example`.

El hallazgo queda pendiente de revisión antes de definir el contrato definitivo de variables TEST. No se considera todavía un error ni se agregará automáticamente sin analizar su función y necesidad.

### Diferencia entre DEV y variables declaradas

El `docker-compose.yml` DEV auditado entrega explícitamente al contenedor `backend` únicamente:

- `DATABASE_URL`
- `SECRET_KEY`
- `FRONTEND_URL`

Existen otras variables declaradas en `.env.example` que son consumidas por el código.

Su obligatoriedad y comportamiento se continuará auditando antes de crear `.env.test.example`.

### Clasificación de variables SMTP

Se auditó `src/shared/email.py` y la cadena de imports utilizada durante el arranque del Backend.

Se confirmó que `src.shared.email` es cargado durante la inicialización de la aplicación a través de módulos importados por los routers de identidad y acceso.

El módulo obtiene:

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASSWORD`

#### `SMTP_HOST`

Tiene como valor por defecto:

    smtp.gmail.com

Si la variable no está definida, no impide por sí sola el arranque del Backend.

#### `SMTP_PORT`

Tiene como valor por defecto:

    587

El código realiza:

    int(os.getenv("SMTP_PORT", "587"))

Por lo tanto:

- si `SMTP_PORT` no existe, se utiliza `587`;
- si `SMTP_PORT` existe pero contiene una cadena vacía, el código intentaría convertir `""` a entero y podría producir un `ValueError` durante la carga del módulo.

Por esta razón, TEST no debe configurar `SMTP_PORT` como valor vacío.

#### `SMTP_USER` y `SMTP_PASSWORD`

No tienen valor por defecto.

Su ausencia no provoca una validación explícita durante la importación del módulo, pero son necesarias para autenticar y enviar correos mediante SMTP.

Las funcionalidades que utilizan correo incluyen, entre otras:

- creación y activación de cuentas;
- recuperación de contraseña;
- reenvío de tokens;
- algunas notificaciones de la aplicación.

Si el envío SMTP falla durante una operación, el código realiza hasta tres intentos y posteriormente genera un error controlado `EMAIL_NO_DISPONIBLE`.

Para TEST, las credenciales SMTP reales no deberán versionarse en Git.


### Clasificación de Firebase

Se auditó `src/shared/firebase.py` y su uso desde `src/shared/notificacion_service.py`.

La variable involucrada es:

- `FIREBASE_CREDENTIALS_PATH`

La inicialización de Firebase es lazy: el SDK no se inicializa durante la importación del módulo, sino cuando se intenta enviar una notificación push.

#### `FIREBASE_CREDENTIALS_PATH`

No es obligatoria para que el Backend arranque.

Si la variable no está definida:

- Firebase no se inicializa;
- `_get_app()` retorna `None`;
- las notificaciones push se omiten;
- el resto del Backend puede continuar funcionando.

Si la ruta está definida pero las credenciales son inválidas o no pueden cargarse, la excepción es capturada y se registra una advertencia.

La función de envío push retorna `False` en caso de fallo y no propaga la excepción al resto de la aplicación.

Por lo tanto, `FIREBASE_CREDENTIALS_PATH` se clasifica como una variable opcional para el arranque del entorno TEST, aunque será necesaria si se desea validar funcionalmente las notificaciones push.

Las credenciales reales de Firebase no deberán almacenarse en Git.

### Clasificación de `MODELOS_STORAGE_PATH`

Se auditó el uso de `MODELOS_STORAGE_PATH` en el módulo de predicción.

La variable solamente se consulta dentro del método encargado de guardar artefactos de modelos y no durante el arranque general del Backend.

Si `MODELOS_STORAGE_PATH` no está definida, el código utiliza como valor por defecto:

    /tmp/sgpmp_modelos

El directorio se crea automáticamente mediante `os.makedirs` cuando se necesita almacenar un artefacto.

Por lo tanto:

- `MODELOS_STORAGE_PATH` no es obligatoria para arrancar Backend TEST;
- la variable se evalúa únicamente cuando se ejecuta la funcionalidad de almacenamiento de modelos;
- si no se configura, los artefactos se almacenan dentro de `/tmp/sgpmp_modelos` en el filesystem del contenedor.

### Hallazgo de persistencia de artefactos

El `docker-compose.yml` DEV auditado no define actualmente un volumen para el servicio `backend`.

Por ello, si se utiliza la ruta por defecto `/tmp/sgpmp_modelos`, los artefactos almacenados dependen del filesystem del contenedor.

Este hallazgo queda pendiente de análisis.

No se añadirá todavía un volumen TEST ni se modificará la estrategia de almacenamiento hasta determinar si la persistencia de estos artefactos forma parte de las responsabilidades del entorno de Implementación o requiere una definición de Desarrollo.

### Clasificación de variables AgroFusion

Se auditó la configuración de los dos mecanismos de integración con AgroFusion:

- Mecanismo A: SSO interactivo;
- Mecanismo B: integración server-to-server (M2M).

#### SSO de AgroFusion

Las variables involucradas son:

- `AGROFUSION_SSO_PUBLIC_KEY_PATH`
- `AGROFUSION_PROJECT_CODE`
- `AGROFUSION_ISSUER`

El endpoint SSO comprueba que existan `AGROFUSION_SSO_PUBLIC_KEY_PATH` y `AGROFUSION_PROJECT_CODE` antes de instanciar el adaptador.

Si no están configuradas, responde mediante el error controlado:

    SSO_NO_CONFIGURADO

con estado HTTP 503.

Por tanto:

- `AGROFUSION_SSO_PUBLIC_KEY_PATH` no es obligatoria para arrancar Backend TEST;
- `AGROFUSION_PROJECT_CODE` no es obligatoria para arrancar Backend TEST;
- ambas son necesarias únicamente para habilitar funcionalmente el SSO con AgroFusion.

`AGROFUSION_ISSUER` tiene como valor por defecto:

    agrofusion-auth

#### Integración M2M de AgroFusion

Las variables involucradas son:

- `AGROFUSION_HUB_CLIENT_ID`
- `AGROFUSION_HUB_CLIENT_SECRET`

La integración se considera configurada solamente cuando existen ambas variables.

Los cinco endpoints M2M implementados actualmente ejecutan `verify_agrofusion_client` antes de realizar su operación.

Si las credenciales M2M no están completas, la validación genera el error controlado:

    AGROFUSION_NO_CONFIGURADO

con estado HTTP 503.

Además, `main.py` solo monta el router M2M cuando existe `AGROFUSION_HUB_CLIENT_ID`.

Se identificó que esta condición de montaje revisa solamente el `CLIENT_ID`, mientras la validación funcional exige tanto `CLIENT_ID` como `CLIENT_SECRET`.

Por lo tanto:

- ninguna de las variables AgroFusion es obligatoria para el arranque básico de Backend TEST;
- el Backend puede funcionar en modo standalone sin esta integración;
- si se desea validar SSO o M2M en TEST, se deberán proporcionar las variables correspondientes;
- los secretos reales de AgroFusion no deberán versionarse en Git.

### Clasificación de `RF71_INTERNAL_KEY`

Durante la auditoría del código se identificó una variable adicional que no está declarada actualmente en `.env.example`:

- `RF71_INTERNAL_KEY`

Esta variable protege una operación interna del módulo de predicción.

El endpoint involucrado es:

    POST /prediccion/modelos

Este endpoint no utiliza RBAC convencional. Recibe la clave interna mediante el header:

    X-RF71-Internal-Key

El router declara el header como opcional a nivel de FastAPI y lo entrega al caso de uso `RegistrarVersionModeloUseCase`.

El caso de uso obtiene el valor esperado mediante:

    os.environ.get("RF71_INTERNAL_KEY", "")

y rechaza la operación cuando:

- el header no está presente;
- el header está vacío;
- el valor recibido no coincide con `RF71_INTERNAL_KEY`.

Por lo tanto:

- `RF71_INTERNAL_KEY` no es necesaria para arrancar Backend TEST;
- sí es necesaria para validar funcionalmente el registro interno de nuevas versiones de modelos correspondiente al flujo RF-71;
- si no se configura, dicha operación interna queda bloqueada;
- su valor debe tratarse como secreto y nunca deberá almacenarse en Git.

### Hallazgo: variable ausente de `.env.example`

`RF71_INTERNAL_KEY` es consumida realmente por el código, pero no aparece actualmente documentada en `.env.example`.

No se modificará el `.env.example` de DEV de forma automática.

El hallazgo se conservará para:

- incluir la variable de forma segura en el contrato específico de TEST si corresponde;
- informar a Desarrollo sobre la diferencia entre las variables consumidas por el código y las documentadas actualmente.

### Contrato propuesto de variables para TEST

A partir de la auditoría del código y de la configuración DEV se define el siguiente contrato inicial para el ambiente TEST.

La clasificación distingue entre:

- requerida para inicialización del ambiente;
- requerida para una funcionalidad concreta;
- opcional con valor por defecto o degradación controlada;
- no utilizada por la configuración TEST propuesta.

| Variable | Servicio | Clasificación en TEST | Observación |
| --- | --- | --- | --- |
| `POSTGRES_USER` | `db` / Compose | Requerida para inicialización | Usuario exclusivo de PostgreSQL TEST. |
| `POSTGRES_PASSWORD` | `db` / Compose | Requerida para inicialización | Secreto exclusivo de TEST. No versionar valor real. |
| `POSTGRES_DB` | `db` / Compose | Requerida para inicialización | Base de datos exclusiva de TEST. |
| `DB_PORT` | Compose | No utilizada por TEST | TEST no publicará PostgreSQL hacia el host. |
| `DATABASE_URL` | `backend` | Requerida para inicialización | Compose la construirá usando `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` y `db:5432`. |
| `SECRET_KEY` | `backend` | Requerida para funcionalidad | Necesaria para creación y verificación de JWT. No versionar valor real. |
| `JWT_EXPIRE_HOURS` | `backend` | Opcional con default | El código utiliza `8` si no está definida. Se propone mantener `8` explícitamente en TEST. |
| `FRONTEND_URL` | `backend` | Requerida para funcionamiento correcto de TEST | Necesaria para enlaces de correo y para representar la URL real del Frontend TEST. |
| `ENV` | `backend` | Configuración explícita de ambiente | TEST utilizará semánticamente `test`. La incompatibilidad CORS con dominios HTTPS reales permanece documentada como hallazgo. |
| `SMTP_HOST` | `backend` | Opcional con default | Si no existe, utiliza `smtp.gmail.com`. |
| `SMTP_PORT` | `backend` | Opcional con default | Si no existe, utiliza `587`. Si se define, no debe quedar vacío y debe contener un entero válido. |
| `SMTP_USER` | `backend` | Requerida para funcionalidad de correo | No es necesaria para el arranque, pero sí para autenticación SMTP real. |
| `SMTP_PASSWORD` | `backend` | Requerida para funcionalidad de correo | Secreto. No versionar valor real. |
| `FIREBASE_CREDENTIALS_PATH` | `backend` | Opcional | Sin configuración, las notificaciones push se degradan de forma controlada. |
| `MODELOS_STORAGE_PATH` | `backend` | Opcional con default | Sin configuración utiliza `/tmp/sgpmp_modelos`. La persistencia de artefactos permanece pendiente de definición. |
| `AGROFUSION_SSO_PUBLIC_KEY_PATH` | `backend` | Opcional | Necesaria solamente para habilitar SSO con AgroFusion. |
| `AGROFUSION_PROJECT_CODE` | `backend` | Opcional | Necesaria solamente para habilitar SSO con AgroFusion. |
| `AGROFUSION_ISSUER` | `backend` | Opcional con default | Default `agrofusion-auth`. |
| `AGROFUSION_HUB_CLIENT_ID` | `backend` | Opcional | Necesaria solamente para habilitar integración M2M. |
| `AGROFUSION_HUB_CLIENT_SECRET` | `backend` | Opcional | Secreto necesario solamente para integración M2M. |
| `RF71_INTERNAL_KEY` | `backend` | Requerida para funcionalidad RF-71 | Protege `POST /prediccion/modelos`. Secreto no documentado actualmente en `.env.example`. |

### Decisiones para el futuro Compose TEST

El servicio `db` recibirá directamente:

- `POSTGRES_USER`;
- `POSTGRES_PASSWORD`;
- `POSTGRES_DB`.

No se utilizará `DB_PORT` porque PostgreSQL TEST no tendrá una publicación mediante `ports`.

El servicio `backend` deberá recibir explícitamente las variables de runtime necesarias para evitar depender de archivos `.env` copiados dentro de la imagen.

`DATABASE_URL` se construirá dentro del Compose utilizando el hostname interno:

    db:5432

### Valor de `ENV` en TEST

El valor propuesto es:

    ENV=test

No se utilizará `ENV=production` únicamente para evitar el problema CORS.

La incompatibilidad de la lógica CORS actual con un Frontend TEST desplegado mediante HTTPS deberá comprobarse durante la integración y, si se reproduce, reportarse a Desarrollo.

### Secretos

Los valores reales de las siguientes variables no deberán incluirse en `.env.test.example` ni en Git:

- `POSTGRES_PASSWORD`;
- `SECRET_KEY`;
- `SMTP_PASSWORD`;
- `AGROFUSION_HUB_CLIENT_SECRET`;
- `RF71_INTERNAL_KEY`;
- cualquier credencial privada adicional utilizada por integraciones externas.

El futuro `.env.test.example` utilizará únicamente valores de ejemplo seguros o marcadores explícitos.

### Integridad del archivo DEV

Se ejecutó:

    git diff origin/integration-v2 -- .env.example

El comando no produjo diferencias.

Resultado: `.env.example` permanece idéntico al existente en `origin/integration-v2`.

## 10. Seguridad de puertos

El entorno TEST aplicará el principio de mínima exposición.

La comunicación entre servicios deberá utilizar puertos internos y redes Docker siempre que no exista una necesidad justificada de publicar un puerto hacia el host.

### Backend TEST

El Backend escucha internamente en:

    8000

Se conservará el patrón utilizado por DEV:

    expose:
      - "8000"

No se deberá utilizar por defecto:

    ports:
      - "8000:8000"

El acceso externo al Backend TEST deberá realizarse posteriormente mediante Dokploy/Traefik y HTTPS, direccionando hacia el puerto interno `8000`.

Arquitectura esperada:

    Internet
        |
      HTTPS
       443
        |
        v
    Traefik / Dokploy
        |
        v
    backend:8000

### PostgreSQL TEST

PostgreSQL escucha internamente en:

    5432

TEST no deberá publicar este puerto hacia el host mediante `ports`.

El acceso de Backend TEST se realizará mediante la red Docker:

    backend -> db:5432

Posteriormente, Gateway TEST también deberá acceder a la misma base mediante la red compartida:

    gateway -> db:5432

La arquitectura esperada es:

    Internet
        X
        |
    PostgreSQL:5432

mientras que internamente:

    backend -----> db:5432
    gateway -----> db:5432

No se deberá utilizar por defecto una publicación equivalente a:

    0.0.0.0:<puerto>:5432

### Administración excepcional de PostgreSQL

Si durante una actividad de administración o diagnóstico se requiere acceso a PostgreSQL desde el host, la necesidad deberá evaluarse explícitamente.

Una alternativa más restringida sería vincular temporalmente el puerto únicamente a loopback, por ejemplo:

    127.0.0.1:<puerto>:5432

Esto no formará parte de la configuración TEST por defecto.

### Red Docker compartida

La red externa definida para TEST es:

    sgpmp-test-internal

La red fue creada manualmente como red Docker `bridge` de alcance local para permitir que distintos proyectos Compose del ambiente TEST puedan compartir conectividad interna sin publicar los puertos de PostgreSQL hacia el host.

En la fase Backend se conectarán:

- `db`;
- `backend`.

Posteriormente, cuando se pueda implementar AIoT TEST, se conectará también:

- `gateway`.

La red fue inspeccionada después de su creación y se confirmó:

    Name=sgpmp-test-internal
    Driver=bridge
    Scope=local
    Containers=0

El valor `Containers=0` era el esperado en este punto porque todavía no se había levantado ningún servicio TEST.

### Estado

La política de seguridad de puertos ya fue aplicada a nivel de configuración en `docker-compose.test.yml`:

- PostgreSQL utiliza únicamente el puerto interno `5432`;
- Backend utiliza únicamente el puerto interno `8000`;
- ninguno de los dos servicios contiene una publicación mediante `ports`.

La red externa `sgpmp-test-internal` ya fue creada y validada.

PostgreSQL TEST ya fue validado en ejecución y se confirmó que no publica el puerto `5432` hacia el host.

Todavía falta realizar la misma comprobación sobre Backend TEST cuando sea levantado.
## 11. Comandos ejecutados

Se realizaron comandos de inspección Git para:

- localizar el repositorio;
- verificar el estado del árbol de trabajo;
- verificar remotos;
- consultar ramas locales y remotas;
- actualizar referencias remotas;
- validar el commit base;
- crear la rama `feat/ambiente-test`.

## 12. Pruebas y validaciones

### Validación de rama base

`HEAD` de `feat/ambiente-test` y `origin/integration-v2` apuntaron al mismo commit:

`39b817c453719110cd7af4eb2616fc0d41f7cebe`

Resultado: **Correcto**.

### Validación estructural inicial de `docker-compose.test.yml`

Se creó una primera versión de `docker-compose.test.yml` que contiene únicamente el servicio PostgreSQL TEST.

Para validar la sintaxis y resolución de variables se ejecutó `docker compose config` utilizando valores temporales de ejemplo proporcionados únicamente al comando.

La validación produjo una configuración válida.

Se confirmó que Docker Compose reconoce únicamente el servicio:

    db

También se comprobó que:

- el proyecto se resuelve como `sgpmp-backend-test`;
- la imagen configurada es `postgres:18`;
- PostgreSQL utiliza únicamente `expose: 5432`;
- no existe publicación mediante `ports`;
- la red se referencia como externa con el nombre `sgpmp-test-internal`;
- el volumen lógico es `sgpmp_pgdata_test`;
- Docker Compose resolvería el volumen físico como `sgpmp-backend-test_sgpmp_pgdata_test`.

Los valores utilizados durante esta validación fueron placeholders temporales y no fueron almacenados en archivos.

No se ejecutó `docker compose up`, por lo que hasta este punto:

- no se han creado contenedores TEST;
- no se ha creado el volumen PostgreSQL TEST;
- no se ha creado la red `sgpmp-test-internal`.

Resultado: **Correcto**.

### Validación estructural del Compose TEST completo

Después de agregar el servicio `backend`, se volvió a validar `docker-compose.test.yml` mediante `docker compose config`.

Se utilizaron únicamente valores temporales de ejemplo para las variables requeridas.

Docker Compose reconoció correctamente los servicios:

    db
    backend

Se comprobó que el Backend TEST:

- se construye utilizando el `Dockerfile` actual;
- depende de que `db` alcance estado `healthy`;
- utiliza `db:5432` como dirección interna de PostgreSQL;
- expone internamente el puerto `8000`;
- no publica el puerto `8000` mediante `ports`;
- pertenece a la red externa `sgpmp-test-internal`.

También se confirmó la resolución esperada de variables y valores por defecto:

- `ENV=test`;
- `JWT_EXPIRE_HOURS=8`;
- `SMTP_PORT=587`;
- `MODELOS_STORAGE_PATH=/tmp/sgpmp_modelos`;
- `AGROFUSION_ISSUER=agrofusion-auth`.

Resultado: **Correcto**.

### Validación de variables obligatorias

Se configuraron como obligatorias para la interpolación del Compose TEST:

- `POSTGRES_USER`;
- `POSTGRES_PASSWORD`;
- `POSTGRES_DB`;
- `SECRET_KEY`;
- `FRONTEND_URL`.

Con todas las variables requeridas presentes, el comando:

    docker compose -f docker-compose.test.yml config --services

resolvió correctamente:

    db
    backend

Posteriormente se realizó una prueba negativa controlada omitiendo `SECRET_KEY`.

Docker Compose detuvo la interpretación de la configuración con el mensaje:

    required variable SECRET_KEY is missing a value: SECRET_KEY requerido para TEST

Este comportamiento es el esperado.

La validación demuestra que el stack no puede continuar accidentalmente cuando falta esta variable crítica.

No se creó ningún contenedor, volumen ni red durante estas pruebas.

Resultado: **Correcto**.

### Validación de `.env.test.example`

Se creó `.env.test.example` como plantilla versionable para la configuración del Backend TEST.

La plantilla contiene únicamente valores de ejemplo, valores por defecto y campos vacíos para variables que deben definirse localmente.

No contiene secretos reales.

Se confirmó que `.env.test.example` declara exactamente las mismas variables interpoladas por `docker-compose.test.yml`.

La comparación se realizó extrayendo ambos conjuntos de variables y utilizando:

    comm -3

El comando no produjo salida.

Esto confirma que:

- no existen variables utilizadas por el Compose que falten en `.env.test.example`;
- no existen variables adicionales en `.env.test.example` que no sean utilizadas por el Compose.

Se confirmó además que:

    .env.test.example exit=1

por lo que la plantilla no está ignorada por Git y puede versionarse.

También se confirmó:

    .env.test exit=0

por lo que el archivo real de configuración TEST continúa ignorado.

`DB_PORT` no forma parte de la plantilla TEST porque PostgreSQL no se publica hacia el host.

`DATABASE_URL` tampoco se declara en la plantilla porque `docker-compose.test.yml` la construye internamente utilizando `db:5432`.

Resultado: **Correcto**.

### Validación de `.env.test` local

Se creó `.env.test` como archivo local a partir de `.env.test.example`.

Las variables críticas requeridas para la configuración local fueron completadas sin registrar sus valores en la documentación ni mostrarlos durante la validación.

Se comprobó únicamente su estado:

    POSTGRES_USER=SET
    POSTGRES_PASSWORD=SET
    POSTGRES_DB=SET
    SECRET_KEY=SET
    FRONTEND_URL=SET

También se validó que Git continúa ignorando el archivo:

    .env.test exit=0

Por tanto, `.env.test` no aparece en `git status` y sus valores locales no serán versionados.

Finalmente se ejecutó:

    docker compose --env-file .env.test -f docker-compose.test.yml config --quiet

Resultado:

    Compose TEST: OK

Esto confirma que la configuración local puede resolver correctamente `docker-compose.test.yml`.

No se mostraron ni documentaron secretos reales.

No se ejecutó `docker compose up`, por lo que todavía no se han creado los servicios TEST.

Resultado: **Correcto**.

### Creación y validación de la red TEST

Antes de crear la red se comprobó que `sgpmp-test-internal` no existía.

La comprobación produjo:

    network exists exit=1

Posteriormente se creó mediante:

    docker network create --driver bridge sgpmp-test-internal

Después de la creación se inspeccionó la red.

Resultado:

    Name=sgpmp-test-internal Driver=bridge Scope=local Containers=0

Se confirmó además que no existía todavía ningún contenedor asociado al proyecto Compose:

    sgpmp-backend-test

Por tanto, la creación de la red fue el único cambio realizado en Docker durante este checkpoint.

Resultado: **Correcto**.

### Levantamiento y validación de PostgreSQL TEST

Se levantó únicamente el servicio:

    db

mediante `docker-compose.test.yml` y `.env.test`.

Docker Compose creó:

    sgpmp-backend-test-db-1
    sgpmp-backend-test_sgpmp_pgdata_test

El contenedor utilizó la imagen:

    postgres:18

Después del arranque se comprobó:

    Status=running
    Health=healthy

La versión efectiva del servidor fue:

    PostgreSQL 18.6

### Validación SQL

Se ejecutó dentro del contenedor:

    SELECT 1;

Resultado:

    1

Esto confirma que PostgreSQL TEST acepta conexiones y ejecuta consultas correctamente.

### Validación del volumen

Se comprobó el montaje:

    Source=sgpmp-backend-test_sgpmp_pgdata_test
    Destination=/var/lib/postgresql

El volumen es independiente de los volúmenes DEV y de los recursos TEST legado identificados previamente.

### Validación de red

El contenedor quedó conectado a:

    sgpmp-test-internal

### Validación de seguridad del puerto PostgreSQL

`docker compose ps` muestra:

    5432/tcp

Este valor representa el puerto interno declarado por el contenedor y no una publicación hacia el host.

Para verificarlo se ejecutó:

    docker port <contenedor-db>

El comando no produjo salida.

Por tanto, PostgreSQL TEST no tiene ningún `host:puerto` asociado a su puerto interno `5432`.

Resultado: **Correcto**.

### Revisión de logs de PostgreSQL

Los logs mostraron el ciclo normal de inicialización de la imagen oficial de PostgreSQL y finalizaron con:

    database system is ready to accept connections

Durante la inicialización apareció un apagado temporal del servidor utilizado por el proceso `initdb`. Posteriormente PostgreSQL inició nuevamente y permaneció operativo.

Al finalizar la revisión, el servicio continuaba:

    Up (healthy)

Resultado: **Correcto**.

### Validación de persistencia de PostgreSQL TEST

Después de restaurar el backup se validó que los datos permanecieran almacenados en el volumen persistente aunque el contenedor PostgreSQL fuera eliminado y recreado.

Antes de detener el stack se obtuvo:

    user_tables=206
    usuarios=22
    telemetrias=10
    versiones_modelos=15
    dispositivos_iot=11

Se ejecutó:

    docker compose --env-file .env.test -f docker-compose.test.yml down

No se utilizó la opción `-v`.

Después del `down` se confirmó que el contenedor había sido eliminado, mientras que el volumen continuaba existiendo:

    Name=sgpmp-backend-test_sgpmp_pgdata_test
    Driver=local

Posteriormente se recreó únicamente PostgreSQL TEST mediante:

    docker compose --env-file .env.test -f docker-compose.test.yml up -d db

Una vez iniciado nuevamente, los conteos permanecieron sin cambios:

    user_tables=206
    usuarios=22
    telemetrias=10
    versiones_modelos=15
    dispositivos_iot=11

Finalmente PostgreSQL alcanzó el estado:

    healthy

Esto demuestra que los datos restaurados permanecen en el volumen `sgpmp-backend-test_sgpmp_pgdata_test` y sobreviven a la eliminación y recreación normal del contenedor.

Resultado: **Correcto**.

### Construcción y levantamiento de Backend TEST

Se construyó y levantó por primera vez el servicio `backend` utilizando:

    docker compose --env-file .env.test -f docker-compose.test.yml up -d --build backend

Resultado:

    backend-up exit=0

Docker Compose informó:

    Image sgpmp-backend-test-backend Built
    Container sgpmp-backend-test-db-1 Healthy
    Container sgpmp-backend-test-backend-1 Started

El estado posterior fue:

    backend -> Up
    db -> Up (healthy)

Los logs de arranque del Backend mostraron:

    Started server process [1]
    Waiting for application startup.
    Application startup complete.
    Uvicorn running on http://0.0.0.0:8000

No se observaron excepciones críticas durante el arranque.

Resultado: **Correcto**.

### Validación de seguridad del puerto `8000`

Se comprobó en ejecución que Backend TEST utiliza únicamente el puerto interno `8000/tcp`.

El comando:

    docker port "$BACKEND_CONTAINER"

no produjo salida.

También se inspeccionó directamente la configuración del contenedor:

    PortBindings={}

Por tanto, el puerto `8000` no está publicado hacia el host.

La visualización:

    8000/tcp

en `docker compose ps` corresponde únicamente al puerto interno expuesto por el contenedor.

Resultado: **Correcto**.

### Validación de `GET /health`

La ruta de salud fue consultada desde el propio contenedor Backend:

    GET /health

Resultado:

    status=200
    body={"status":"ok","message":"API funcionando correctamente"}

Los logs registraron:

    "GET /health HTTP/1.1" 200 OK

Resultado: **Correcto**.

### Validación de ruta raíz, documentación y OpenAPI

Se validaron directamente las rutas internas del Backend TEST.

Resultados:

    GET / -> 200
    body="hello world!"

    GET /docs -> 200
    content_type=text/html; charset=utf-8

    GET /openapi.json -> 200
    content_type=application/json
    openapi=3.1.0
    servers=[{'url': '/api'}]

Por tanto, la aplicación expone correctamente su ruta raíz, documentación Swagger y especificación OpenAPI.

Resultado: **Correcto**.

### Validación del prefijo `/api`

Se comprobó el comportamiento real del `root_path="/api"` configurado por la aplicación.

Resultados:

    GET /api -> 307 Temporary Redirect
    GET /api/health -> 200
    GET /api/docs -> 200
    GET /api/openapi.json -> 200

Los logs del Backend confirmaron las cuatro solicitudes.

Además, la especificación OpenAPI declara:

    servers=[{'url': '/api'}]

Por tanto, el Backend acepta las rutas prefijadas con `/api` y anuncia dicho prefijo en OpenAPI.

La configuración definitiva de exposición mediante Traefik/Dokploy deberá respetar este comportamiento y será validada nuevamente cuando exista la URL pública de TEST.

Resultado: **Correcto en ejecución local TEST**.

### Validación de comunicación Backend TEST - PostgreSQL TEST

Se realizó una consulta desde el contenedor Backend utilizando la variable `DATABASE_URL` inyectada por Docker Compose.

No se imprimió el contenido de `DATABASE_URL` ni ninguna credencial.

Resultados:

    db_select_1=1
    db_user_tables=206

Esto demuestra que Backend TEST pudo:

- utilizar su configuración real de conexión;
- resolver el servicio interno `db`;
- autenticarse contra PostgreSQL TEST;
- ejecutar consultas sobre la base restaurada.

Después de la prueba:

    backend -> Up
    db -> Up (healthy)

Resultado: **Correcto**.

### Validación de integridad de `docker-compose.yml` DEV

Después de completar la configuración y las pruebas locales de TEST se comparó el archivo DEV actual contra la rama base:

    git diff --exit-code origin/integration-v2 -- docker-compose.yml

Resultado:

    dev-compose-diff-exit=0

Esto confirma que `docker-compose.yml` no presenta diferencias respecto de `origin/integration-v2`.

Por tanto, la creación y validación inicial del ambiente TEST no modificó la configuración Compose existente de DEV.

Resultado: **Correcto en ese punto del proceso**.

### Actualización posterior del entorno DEV por solicitud de Desarrollo

Después de finalizar la configuración inicial de TEST, el líder de Desarrollo solicitó explícitamente que PostgreSQL también tuviera disponible `pg_cron` en DEV, con el objetivo de evitar errores cuando Desarrollo valide localmente futuras migraciones y trabajos programados.

También solicitó que el Backend DEV recibiera explícitamente las variables:

    SMTP_HOST
    SMTP_PORT
    SMTP_USER
    SMTP_PASSWORD

Por esta razón se autorizó modificar posteriormente `docker-compose.yml` dentro de la misma rama de trabajo.

#### Reutilización de la imagen PostgreSQL

DEV fue actualizado para utilizar el mismo:

    Dockerfile.postgres

que ya había sido validado en TEST.

La imagen parte de:

    postgres:18

e instala:

    postgresql-18-cron

El servicio PostgreSQL DEV arranca con:

    shared_preload_libraries=pg_cron

y:

    cron.database_name=${POSTGRES_DB}

De esta forma DEV y TEST comparten la misma capacidad de PostgreSQL respecto de `pg_cron`.

#### Prueba DEV local aislada

Para no reutilizar recursos históricos del antiguo repositorio central de Implementación se creó un proyecto Compose local independiente:

    sgpmp-backend-dev-local

Se comprobó que los contenedores DEV legado pertenecían al proyecto:

    sgpmp-dev

y tenían como directorio de trabajo:

    implementacion/compose

Por tanto, esos recursos no fueron reutilizados ni modificados.

El nuevo DEV local creó un volumen independiente:

    sgpmp-backend-dev-local_sgpmp_pgdata

La base se publicó localmente mediante el puerto definido por el Compose DEV:

    5447 -> 5432

El puerto `5447` se encontraba libre antes del levantamiento.

#### Validación de `pg_cron` en DEV

PostgreSQL DEV inició correctamente utilizando la imagen construida con `Dockerfile.postgres`.

Se comprobó:

    shared_preload_libraries = pg_cron
    cron.database_name = sgpmp_dev
    pg_cron disponible = 1.6

Posteriormente se ejecutó:

    CREATE EXTENSION IF NOT EXISTS pg_cron;

Resultado:

    dev-create-pgcron-exit=0

La extensión quedó instalada como:

    pg_cron 1.6

Para comprobar la ejecución real se creó temporalmente:

    implementation_pgcron_dev_probe

con el comando:

    SELECT 1;

El trabajo se ejecutó correctamente y `cron.job_run_details` reportó:

    status = succeeded
    return_message = 1 row

Los logs de PostgreSQL confirmaron:

    cron job 1 starting: SELECT 1;
    cron job 1 completed: 1 row

Durante la inicialización inicial de PostgreSQL se registró temporalmente:

    FATAL: database "sgpmp_dev" does not exist

Esto ocurrió mientras el entrypoint todavía estaba creando la base y antes del arranque definitivo del scheduler.

Posteriormente los logs mostraron:

    pg_cron scheduler started

y la ejecución real del job fue exitosa, por lo que el evento inicial no impidió el funcionamiento posterior de `pg_cron`.

Después de la prueba:

- el job técnico fue eliminado mediante `cron.unschedule`;
- `cron.job` volvió a `0` registros;
- se inspeccionaron los dos registros técnicos generados por las ejecuciones;
- se eliminaron exclusivamente dichos registros;
- `cron.job_run_details` volvió a `0` registros.

Estado final:

    pg_cron = 1.6
    shared_preload_libraries = pg_cron
    cron.database_name = sgpmp_dev
    cron.job = 0
    cron.job_run_details = 0

También se reinició únicamente PostgreSQL DEV.

Resultado:

    dev-db-restart-exit=0

El servicio pasó nuevamente a:

    healthy

y `pg_cron` permaneció instalado, precargado y operativo después del reinicio.

#### Validación de variables SMTP en Backend DEV

El `docker-compose.yml` DEV fue actualizado para entregar al contenedor Backend:

    SMTP_HOST
    SMTP_PORT
    SMTP_USER
    SMTP_PASSWORD

Para la prueba se utilizó un `.env.dev` local ignorado por Git. No se utilizaron ni mostraron credenciales SMTP reales.

Dentro del contenedor Backend se comprobó únicamente presencia y estado de las variables.

Resultado:

    SMTP_HOST: PRESENTE / CON_VALOR
    SMTP_PORT: PRESENTE / CON_VALOR
    SMTP_USER: PRESENTE / VACIA
    SMTP_PASSWORD: PRESENTE / VACIA

`SMTP_USER` y `SMTP_PASSWORD` fueron dejadas vacías deliberadamente porque esta prueba solo tenía como objetivo demostrar que Compose pasa correctamente las cuatro variables al contenedor.

Las credenciales reales no deberán versionarse.

#### Hallazgo al iniciar Backend DEV con una base nueva

El Backend DEV logró iniciar y Uvicorn reportó:

    Application startup complete

Sin embargo, durante uno de los procesos periódicos apareció:

    relation "modulo5.configuracion_batch_historial_suministros" does not exist

La base `sgpmp_dev` utilizada para esta prueba fue creada desde un volumen nuevo y no recibió restauración del backup ni inicialización completa del esquema funcional.

Por tanto, este error no se atribuye a `pg_cron` ni a la configuración SMTP.

La evidencia confirma que:

    Backend -> PostgreSQL DEV = conexión alcanzada
    esquema funcional completo DEV = no preparado en esta prueba

No se creó manualmente la tabla faltante ni se alteró el esquema para ocultar este hallazgo.

## 13. Errores encontrados

### Primer intento de restauración del backup

El primer intento de `pg_restore` falló antes de iniciar la restauración porque no se indicó explícitamente el usuario PostgreSQL.

El error recibido fue:

    FATAL: role "root" does not exist

Resultado del comando:

    restore exit=1

Antes de reintentar se comprobó que la base continuaba sin tablas de usuario:

    user_tables=0

y que PostgreSQL permanecía:

    healthy

La causa fue que `pg_restore` intentó utilizar el usuario de sistema `root` dentro del contenedor.

Se corrigió agregando:

    --username="$POSTGRES_USER"

El segundo intento finalizó correctamente:

    restore exit=0

No quedó una restauración parcial del primer intento.

Estado: **Resuelto**.

## 14. Hallazgos

### Excepción de Git para `.env.test.example`

Durante la auditoría inicial se comprobó que la regla:

    .env.*

provocaba que `.env.test.example` fuera ignorado por Git.

Para permitir versionar exclusivamente la plantilla TEST se agregó a `.gitignore`:

    !.env.test.example

La configuración resultante mantiene:

    .env
    .env.*
    !.env.example
    !.env.test.example

Se validó el comportamiento mediante `git check-ignore`.

Resultado para `.env.test.example`:

    exit=1

Esto confirma que `.env.test.example` ya no está ignorado y podrá versionarse.

Resultado para `.env.test`:

    exit=0

Esto confirma que `.env.test` continúa ignorado y protegido frente a inclusión accidental en Git.

Resultado: **Hallazgo resuelto**.

### CORS de TEST con dominio real

Se auditó la configuración de CORS existente en `main.py`.

El comportamiento confirmado es:

- si `ENV` es exactamente `production`, el Backend permite como origen el valor configurado en `FRONTEND_URL`;
- para cualquier otro valor de `ENV`, el Backend no utiliza `FRONTEND_URL` como origen permitido;
- en ambientes distintos de `production` únicamente se permiten orígenes HTTP sobre `localhost` o `127.0.0.1`.

La expresión regular utilizada actualmente para ambientes distintos de producción es:

    http://(localhost|127\.0\.0\.1)(:\d+)?

Por lo tanto, un Frontend TEST desplegado mediante un dominio HTTPS real, por ejemplo:

    https://frontend-test...

no coincidiría con la configuración CORS actual.

Esto representa un posible bloqueo para la integración Frontend TEST -> Backend TEST.

No se modificará automáticamente `main.py` ni se utilizará `ENV=production` como solución para TEST.

El procedimiento acordado es:

- construir el entorno TEST respetando la semántica del ambiente;
- comprobar el comportamiento durante la integración real con Frontend TEST;
- registrar evidencia si CORS bloquea la comunicación;
- reportar a Desarrollo la necesidad de ajustar la lógica de CORS.

### Uso de `FRONTEND_URL`

También se confirmó que `FRONTEND_URL` se utiliza para generar enlaces enviados por correo, incluyendo:

- activación de cuenta;
- recuperación de contraseña.

Si no se proporciona, el código utiliza como fallback:

    http://localhost:3000

Por tanto, `FRONTEND_URL` deberá configurarse explícitamente en TEST con la URL correspondiente al Frontend TEST.

## 15. Dependencias externas

### Backup de PostgreSQL

Se identificó como respaldo entregado por Desarrollo:

    backup_sgpmp.dump

Características verificadas:

- tamaño aproximado: `6,5 MB`;
- formato: PostgreSQL `CUSTOM`;
- versión del formato del dump: `1.16-0`;
- base origen: PostgreSQL `17.10`;
- generado mediante `pg_dump 18.4`;
- restaurado con herramientas PostgreSQL `18.6`.

SHA-256 del archivo utilizado:

    9a1da173b1076dcc5f5e2f955353ca1c762981b1cec6b850e0a4a840f4a9a6b3

El respaldo contiene estructura y datos:

    TABLE=331
    TABLE DATA=208

### Tratamiento de `pg_cron`

El backup contenía la extensión `pg_cron`, pero la imagen `postgres:18` utilizada en TEST no la incluye.

Se comprobó que:

- el código del Backend no contiene referencias a `pg_cron`, `cron.schedule` ni `cron.unschedule`;
- `cron.job` contiene `0` registros;
- `cron.job_run_details` contiene `0` registros;
- el SQL del esquema solo contiene la creación y comentario de la extensión.

Por esta razón se generó una lista de restauración filtrada excluyendo únicamente seis entradas relacionadas con `pg_cron`.

Entradas originales del TOC:

    4170

Entradas filtradas:

    4164

La extensión `pgcrypto` se conservó y fue restaurada correctamente.

#### Incorporación posterior de `pg_cron` por solicitud de Desarrollo

Posteriormente el líder de Desarrollo solicitó que la infraestructura PostgreSQL del Backend incluyera `pg_cron`, debido a que futuras migraciones y trabajos programados dependerán de esta extensión.

Antes de modificar TEST se realizó una prueba aislada sobre la misma imagen base `postgres:18`.

Se comprobó que:

- la imagen utiliza Debian 13 `trixie`;
- el paquete `postgresql-18-cron` está disponible en los repositorios configurados de la imagen;
- se instaló correctamente la versión `1.6.7-3.pgdg13+1`;
- PostgreSQL continuó utilizando la versión `18.6`;
- el archivo `pg_cron.control` quedó disponible para PostgreSQL 18.

Se creó el archivo:

    Dockerfile.postgres

Su objetivo es construir la imagen PostgreSQL utilizada por TEST a partir de `postgres:18` e instalar:

    postgresql-18-cron

El servicio `db` de `docker-compose.test.yml` se modificó para construir esta imagen y arrancar PostgreSQL con:

    shared_preload_libraries=pg_cron

y con:

    cron.database_name=sgpmp_test

Antes de recrear el contenedor PostgreSQL se registró la siguiente línea base:

    user_tables=206
    usuarios=22
    telemetrias=10
    versiones_modelos=15
    dispositivos_iot=11

El contenedor `db` fue recreado sin eliminar el volumen persistente.

El volumen utilizado antes y después del cambio fue:

    sgpmp-backend-test_sgpmp_pgdata_test -> /var/lib/postgresql

Después de la recreación se obtuvieron nuevamente:

    user_tables=206
    usuarios=22
    telemetrias=10
    versiones_modelos=15
    dispositivos_iot=11

Por tanto, la incorporación de la nueva imagen PostgreSQL no produjo pérdida de los datos restaurados.

Se comprobó posteriormente que:

    shared_preload_libraries = pg_cron
    cron.database_name = sgpmp_test
    pg_cron disponible = 1.6
    pgcrypto instalado = 1.4

La extensión se activó en la base TEST mediante:

    CREATE EXTENSION IF NOT EXISTS pg_cron;

Resultado:

    create-pgcron-test-exit=0

Los logs de PostgreSQL confirmaron:

    pg_cron scheduler started

Para validar que la extensión no estuviera únicamente instalada, sino funcional, se creó temporalmente el job técnico:

    implementation_pgcron_probe

con la instrucción:

    SELECT 1;

y programación de una ejecución por minuto.

Se observaron dos ejecuciones reales con estado:

    succeeded

Los logs registraron tanto el inicio como la finalización correcta de ambas ejecuciones.

Después de la validación:

- el job técnico fue eliminado mediante `cron.unschedule`;
- se verificó que `cron.job` volviera a contener `0` registros;
- se inspeccionaron los dos registros de ejecución generados;
- se eliminaron exclusivamente esos dos registros técnicos;
- `cron.job_run_details` volvió a contener `0` registros;
- `pg_cron` permaneció instalado y habilitado.

Estado final:

    cron.job = 0
    cron.job_run_details = 0
    pg_cron = 1.6
    shared_preload_libraries = pg_cron
    cron.database_name = sgpmp_test

El Backend permaneció operativo después de la recreación de PostgreSQL y se verificó nuevamente la comunicación Backend - PostgreSQL mediante:

    SELECT 1

Resultado:

    db_select_1=1

Los recursos Docker creados exclusivamente para la prueba aislada inicial de `pg_cron` fueron eliminados después de completar la validación.

#### Validación después de reiniciar PostgreSQL

Como comprobación final se reinició únicamente el servicio `db`, sin recrear ni eliminar el volumen persistente.

Resultado:

    pgcron-db-restart-exit=0

PostgreSQL pasó de:

    starting

a:

    healthy

Después del reinicio se volvió a verificar:

    pg_cron = 1.6
    pgcrypto = 1.4
    shared_preload_libraries = pg_cron
    cron.database_name = sgpmp_test
    cron.job = 0
    cron.job_run_details = 0
    usuarios = 22

Esto confirma que la configuración de `pg_cron`, la extensión instalada y los datos de TEST permanecen disponibles después de un reinicio normal del servicio PostgreSQL.


No se incorporará ninguna otra extensión adicional hasta que Desarrollo confirme explícitamente su nombre y necesidad técnica.

### Estrategia de restauración

La restauración se ejecutó utilizando:

- `--no-owner`, porque los objetos del origen pertenecían principalmente al rol `postgres` y dicho rol no existe en TEST;
- `--exit-on-error`;
- `--single-transaction`;
- usuario explícito `POSTGRES_USER`;
- lista filtrada sin `pg_cron`.

La restauración final terminó con:

    restore exit=0

La restauración no será automática en cada `docker compose up`.

### Dependencia con AIoT

El repositorio AIoT continúa siendo de solo lectura para el grupo de Implementación.

El equipo de Pruebas indicó que para la validación funcional de los módulos:

- M03 - Telemetría IoT;
- M04 - Predicción;
- M09 - Configuración relacionada con dispositivos IoT;

será necesario disponer también de:

- Gateway AIoT;
- Mosquitto.

Por tanto, el Backend TEST podrá construirse y validarse de forma independiente, pero la validación funcional completa de esos módulos dependerá de la futura disponibilidad del entorno AIoT TEST.

### Requisitos recibidos del equipo de Pruebas

El equipo de Pruebas informó que las herramientas de integración, E2E, carga y seguridad utilizarán las URLs reales expuestas por el ambiente TEST.

Al momento de entregar el ambiente deberán definirse claramente:

- URL del Frontend TEST;
- URL del Backend TEST;
- ruta o prefijo utilizado por el Backend;
- cualquier restricción de red requerida para acceder al ambiente.

También se indicó que deberán estar disponibles para validación:

- `GET /health`;
- `GET /`;
- documentación `/docs`;
- especificación OpenAPI del Backend.

La aplicación real del prefijo `/api` en TEST deberá comprobarse ejecutando el ambiente antes de responder formalmente al equipo de Pruebas.

### Datos y usuarios de prueba

QA requiere datos semilla para ejecutar los ciclos de prueba.

El backup restaurado contiene datos funcionales. Entre las comprobaciones realizadas se obtuvieron:

    modulo1.roles=9
    modulo1.usuarios=22
    modulo1.cuentas_usuarios=21
    modulo3.telemetrias=10
    modulo4.versiones_modelos=15
    modulo9.dispositivos_iot=11
    modulo9.sensores=21

Esto confirma que el respaldo contiene datos además de estructura.

Todavía debe confirmarse con QA o Base de Datos que este conjunto corresponde oficialmente al estado semilla que deberá utilizarse para los ciclos de regresión.

### Roles requeridos por QA

QA solicitó disponer de cuentas para:

- Administrador;
- Productor;
- Veterinario;
- Contador;
- Ingeniero de Campo.

Se comprobó que existe al menos una cuenta por cada rol que cumple simultáneamente:

- estado `Activo`;
- correo verificado;
- contraseña cifrada presente.

Resultado agregado:

    Administrador|login_ready=2
    Contador|login_ready=1
    Ingeniero de Campo|login_ready=2
    Productor|login_ready=1
    Veterinario|login_ready=1

Esto confirma que la base restaurada contiene cuentas potencialmente utilizables para autenticación en los cinco roles.

No se ha comprobado todavía que el equipo de Pruebas conozca las credenciales correspondientes.

### Discrepancia sobre `member_qa`

El equipo de Pruebas informó que el usuario `member_qa` había sido preparado previamente.

En la base TEST restaurada se realizaron búsquedas controladas sin exponer datos personales.

Resultado:

    member_qa en usuarios=false
    member_qa en credenciales_servicio=false
    member_qa en pg_roles=false

Por tanto, `member_qa` no fue localizado en el backup restaurado mediante las estructuras revisadas.

No se creará automáticamente.

La discrepancia deberá confirmarse con QA y/o el equipo responsable de Base de Datos.

### Política de reinicio de datos

QA recomienda restaurar la base a un estado conocido antes de cada ciclo de regresión, pero no antes de cada prueba individual.

Esta necesidad es compatible con el diseño actual de TEST:

- volumen persistente;
- restauración inicial del backup;
- ausencia de reset automático en cada `docker compose up`.

Posteriormente podrá evaluarse un mecanismo explícito de reset controlado.

### Pruebas de carga

QA indicó que las pruebas de carga con k6 deberán ejecutarse sobre una copia de la base de datos que pueda reiniciarse independientemente de los datos utilizados por las demás pruebas.

Este requisito queda pendiente de diseño.

No se creará todavía una segunda base de datos ni otro stack hasta definir con precisión cómo se ejecutarán dichas pruebas.

El listado definitivo de endpoints de carga continúa pendiente por parte del equipo de Pruebas.

## 16. Pendientes

- Confirmar con QA/Base de Datos que los datos restaurados corresponden al estado semilla oficial para regresión.
- Confirmar con QA las credenciales utilizables para las cuentas de los cinco roles.
- Confirmar con QA/Base de Datos la ausencia o ubicación de `member_qa`.
- Validar posteriormente integración Frontend TEST - Backend TEST.
- Registrar evidencia del posible bloqueo CORS si se presenta.
- Diseñar posteriormente el mecanismo explícito de reset de la BD TEST.
- Definir posteriormente la estrategia de BD independiente para pruebas k6.
- Esperar acceso al repositorio AIoT para completar TEST de M03, M04 y M09.
- Revisar archivos, secretos y diferencias antes de cada commit.

## 17. Evidencias

Las evidencias se agregarán progresivamente durante las pruebas del entorno.

## 18. Estado actual

**En progreso.**

PostgreSQL TEST y Backend TEST se encuentran levantados y operativos.

Hasta este punto se completó:

- creación de la red interna TEST;
- creación y validación del volumen PostgreSQL TEST independiente;
- restauración controlada del backup;
- validación de estructura y datos restaurados;
- validación de cuentas correspondientes a los roles requeridos por QA;
- validación de persistencia de PostgreSQL;
- construcción y levantamiento de Backend TEST;
- validación de que PostgreSQL no publica `5432` hacia el host;
- validación de que Backend no publica `8000` hacia el host;
- validación de `GET /health`;
- validación de `GET /`;
- validación de `/docs`;
- validación de `/openapi.json`;
- validación del comportamiento del prefijo `/api`;
- validación de comunicación Backend TEST - PostgreSQL TEST.

PostgreSQL TEST permanece en estado `healthy` y Backend TEST permanece en ejecución.

La creación y validación inicial de TEST se realizó sin modificar `docker-compose.yml` DEV.

Posteriormente, por solicitud explícita del líder de Desarrollo, `docker-compose.yml` DEV fue actualizado para:

- reutilizar `Dockerfile.postgres`;
- instalar y precargar `pg_cron` en PostgreSQL DEV;
- pasar `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER` y `SMTP_PASSWORD` al contenedor Backend.

`pg_cron` fue validado mediante una ejecución real, limpieza del job técnico y reinicio de PostgreSQL.

Las variables SMTP fueron verificadas dentro del contenedor sin exponer valores sensibles.

Continúan pendientes las dependencias externas de QA, la integración Frontend TEST - Backend TEST y AIoT TEST.
