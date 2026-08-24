# CLAUDE.md — SGPMP Backend

---

## Qué cubre este documento

- Arquitectura y responsabilidad de cada capa
- Flujo de trabajo para implementar un caso de uso (incluyendo Paso 0 de gaps de BD y RBAC)
- Reglas de construcción y sus razones
- Patrones adicionales: agregados con hijos, concurrencia optimista, auditoría (`_snapshot`), stubs, enums PG
- Jerarquía de errores y cuándo usar cada uno
- Variables de entorno requeridas
- Notas de infraestructura relevantes

## Qué NO cubre

- Estado de implementación de módulos o casos de uso (ver el código)
- Instrucciones de despliegue o CI/CD
- Configuración de base de datos o migraciones
- Historial de cambios (ver `git log`)

---

## Stack

| Componente   | Tecnología                        |
|--------------|-----------------------------------|
| Framework    | FastAPI 0.136.3                   |
| ORM          | SQLAlchemy 2.0.50                 |
| Validación   | Pydantic 2.13.4                   |
| Base de datos| PostgreSQL (psycopg2-binary)      |
| Auth         | python-jose 3.5.0 (JWT)          |
| Passwords    | bcrypt 5.0.0                      |
| Testing      | pytest 9.0.3 + pytest-cov        |
| Runtime      | Python 3.13 / uvicorn             |

---

## Estructura de carpetas

```
src/
├── shared/                      # Utilidades transversales a todos los módulos
│   ├── base_dto.py              # BaseDTO — base Pydantic para todos los DTOs
│   ├── database.py              # Engine SQLAlchemy + get_db()
│   ├── db_error_translator.py   # Convierte IntegrityError → ConflictError
│   ├── email.py                 # Envío SMTP con reintentos
│   ├── error_handlers.py        # Handlers globales FastAPI
│   ├── errors.py                # Jerarquía de errores de dominio
│   ├── jwt.py                   # create_token / verify_token
│   ├── middlewares.py           # Middlewares globales
│   ├── regex.py                 # Expresiones regulares reutilizables
│   └── schemas.py               # MessageResponse, ErrorResponse (Swagger)
└── {modulo}/                    # Un directorio por módulo de negocio
    ├── application/
    │   └── use_cases/           # Casos de uso agrupados por dominio
    │       └── {dominio}/       # ej: registro/, sesiones/
    ├── domain/
    │   ├── entities/            # Entidades de dominio puras y read-models (sin ORM)
    │   ├── repositories/        # Puertos (ABC) de repositorios, en términos de dominio
    │   └── value_objects/       # Value objects (Email, Contrasena, Token...)
    └── infrastructure/
        ├── dto/                 # Input DTOs (entrada del endpoint)
        ├── email_templates.py   # Templates HTML de correos del módulo
        ├── models/              # Modelos ORM (mapean tablas de DB)
        ├── repositories/        # Implementaciones SQLAlchemy de los puertos
        ├── routers/             # Endpoints FastAPI
        └── schema/              # Response schemas (salida del endpoint)
```

---

## Arquitectura por capas

El proyecto sigue **arquitectura hexagonal / DDD**. El flujo es siempre:

```
Router → UseCase → Port (ABC, domain/repositories) ← Repository (SQLAlchemy)
```

El puerto vive en `domain/`, no en `application/`: el dominio declara lo que
necesita y la infraestructura lo implementa, de modo que las flechas siempre
apuntan hacia adentro (infraestructura → aplicación → dominio). Los repositorios
reciben y devuelven **entidades de dominio** (o read-models), nunca modelos ORM.

### Router (`infrastructure/routers/`)
Recibe la petición HTTP, instancia dependencias, ejecuta el use case, retorna el schema de respuesta.
No contiene lógica de negocio. No hace queries directas a DB salvo lecturas simples.

### Use Case (`application/use_cases/{dominio}/`)
Orquesta el flujo completo de una acción de negocio. Es la única capa que:
- Valida reglas de negocio
- Genera tokens o valores derivados (`secrets.token_urlsafe`)
- Llama uno o más ports
- Emite el `commit()` y el `rollback()`
- Envía emails u otras notificaciones externas

Un archivo por acción: `crear_usuario_use_case.py`, `activar_cuenta_use_case.py`, etc.

### Port (`domain/repositories/`)
Interfaz ABC que define qué operaciones de persistencia necesita el use case,
expresada **en términos del dominio**: recibe y devuelve entidades o value
objects, nunca modelos ORM ni `infrastructure`. Un puerto por agregado
(`UsuarioRepository`, `CuentaRepository`, `SesionRepository`...).
La aplicación solo conoce el puerto, nunca el repository concreto.

### Repository (`infrastructure/repositories/`)
Implementación SQLAlchemy del puerto. Es el único punto que cruza la frontera
ORM ↔ dominio: mapea fila ORM → entidad al leer y entidad → fila ORM al escribir.
Usa `flush()`, nunca `commit()`. Captura errores de DB y los traduce con `raise_from_db_error()`.

### DTO (`infrastructure/dto/`)
Input del endpoint. Pydantic con validaciones de formato (regex, EmailStr, etc.).
Hereda de `BaseDTO`. No contiene lógica de negocio.

### Schema (`infrastructure/schema/`)
Response model Pydantic. Lo que el endpoint devuelve al cliente.
Distinto del DTO (entrada) y del modelo ORM.

### Modelo ORM (`infrastructure/models/`)
Mapea la tabla de base de datos. Hereda de `Base` en `base_model.py`.
Solo define columnas y relaciones. Sin lógica.

### Convención de nombres (DDD)

Nombres en **singular** por agregado (`usuario`, `cuenta`, `sesion`, `rol`...):

| Capa | Archivo | Clase |
|------|---------|-------|
| Puerto (dominio) | `domain/repositories/<agregado>_repository.py` | `<Agregado>Repository` |
| Implementación | `infrastructure/repositories/<agregado>_repository.py` | `SqlAlchemy<Agregado>Repository` |
| Entidad | `domain/entities/<agregado>.py` | `<Agregado>` |

El puerto y su implementación comparten nombre de archivo; la carpeta los
desambigua. Las operaciones de escritura siguen el patrón
`entidad = repo.obtener_*(...)` → método de conducta en la entidad →
`repo.guardar(entidad)`; el `commit()` queda en el use case.

---

## Flujo para implementar un caso de uso

### Paso 0 — Análisis de gaps de BD y RBAC (antes de escribir código)

Antes de tocar código, comparar el RF contra el esquema real de la tabla vía MCP postgres:

```sql
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'modulo9' AND table_name = 'mi_tabla';
```

Documentar cada gap encontrado en `anotaciones/cu{nn}_gaps_bd_rf{nn}.md` con la decisión tomada y el SQL aplicado. Categorías habituales de gaps:

- Columnas faltantes (ej. `fecha_actualizacion TIMESTAMPTZ`)
- Restricciones incorrectas (nullable / NOT NULL, constraints de unicidad)
- Tablas de auditoría no creadas
- Recurso y permisos RBAC no insertados

También verificar en DB que `modulo1.recursos` tiene el `id_recurso` para este módulo y que `modulo1.permisos` tiene filas para cada combinación (rol, recurso, acción) que el RF especifica. Sin esto, todos los endpoints devuelven `403` de forma silenciosa.

Aplicar todos los DDL y DML antes de escribir código. Luego continuar con los pasos de abajo.

---

Seguir este orden sin saltarse capas:

1. **Modelo ORM** — mapea la tabla si no existe
2. **Entidad / value objects** — modela el agregado y su conducta en `domain/`
3. **DTO** — define el input del endpoint
4. **Port** — declara las operaciones necesarias (ABC) en `domain/repositories/`, en términos de dominio
5. **Repository** — implementa el puerto con SQLAlchemy (`flush()`, sin `commit()`), mapeando ORM ↔ entidad
6. **Use Case** — orquesta: valida, llama puertos, `commit()`, notificaciones
7. **Schema** — define el response del endpoint
8. **Router** — conecta todo, sin lógica
9. **CURLs** — documentar todos los endpoints en `anotaciones/curls_m09_cu{nn}_{nombre}.md`, siguiendo el formato de los archivos existentes: un bloque por flujo/endpoint, respuesta esperada, errores posibles con su código HTTP y referencia al FA correspondiente

---

## Reglas no negociables

| Regla | Por qué |
|-------|---------|
| `commit()` solo en el use case | Un único punto de control transaccional por operación |
| `rollback()` solo en el use case | El repository no sabe si hay otras operaciones pendientes |
| Tokens y valores generados en el use case, no en el repository | El repository es solo persistencia |
| Emails y notificaciones enviados **después del** `commit()` | Si la notificación falla, los datos deben quedar guardados |
| Errores de DB traducidos antes de salir del repository | La capa de aplicación no conoce `IntegrityError` de SQLAlchemy |
| El dominio y la aplicación no importan nada de `infrastructure` | Inversión de dependencias — facilita pruebas y cambios de adaptador |
| **Autorización por RBAC en el router, nunca con `id_rol` quemado en el use case** | Ver sección RBAC más abajo |

---

## Control de acceso (RBAC)

La autorización se gestiona a través de `src/shared/rbac.py` mediante la dependencia
`require_permission(id_recurso, id_accion)`, que consulta la tabla `modulo1.permisos`
en cada request. Los permisos son dinámicos: cambiar una fila en DB cambia el
comportamiento sin tocar código.

### Cómo aplicarlo en un router

```python
from src.shared.rbac import require_permission

@router.post("", dependencies=[Depends(require_permission(id_recurso, id_accion))])
def mi_endpoint(db, usuario_actual): ...
```

Si el rol del usuario no tiene el permiso activo, `require_permission` lanza
`AuthorizationError 403` antes de que el endpoint se ejecute.

### Tabla de acciones estándar (`modulo1.acciones`)

| id_accion | codigo | descripcion |
|-----------|--------|-------------|
| 1 | C | Crear |
| 2 | R | Leer |
| 3 | U | Actualizar |
| 4 | D | Eliminar / Desactivar |
| 5 | E | Ejecutar |

### Reglas de uso

- **El use case NO verifica roles.** Solo usa `usuario_actual.id_usuario` para auditoría.
- **No hardcodear** `ROL_ADMINISTRADOR = 1` ni similares en use cases para decidir acceso.
- Si el documento RF dice que una operación es exclusiva de un rol, ese rol debe tener
  el permiso correspondiente en `modulo1.permisos` — no expresarlo en código.
- Antes de implementar un router, verificar que `modulo1.permisos` tenga los registros
  necesarios para el recurso. Si faltan, insertarlos y documentarlos en `anotaciones/`
  (para asignar/retirar permisos de un rol ya existente también se puede usar la API
  de `identity_access` — `POST/DELETE /roles/{id_rol}/permisos` — en vez de SQL manual).
- Los recursos están en `modulo1.recursos`. Cada módulo de negocio registra ahí sus
  recursos con un `id_recurso` propio.

### Convención de nombres para permisos

El campo `nombre` en `modulo1.permisos` sigue el patrón `{rol}_{accion}_{recurso_singular}`:

```
admin_crear_especie
vet_leer_umbral_ambiental
prod_actualizar_ciclo_biologico
```

Roles estándar (seed inicial) en `modulo1.roles`:

| id_rol | prefijo | nombre |
|--------|---------|--------|
| 1 | admin | Administrador |
| 2 | prod | Productor |
| 3 | vet | Veterinario |
| 4 | ing | Ingeniero |
| 5 | cont | Contador |

**Los roles no son un catálogo fijo.** `src/identity_access` expone un CRUD completo de roles y permisos
(`infrastructure/routers/roles_routers.py`: crear/editar/eliminar/listar rol, asignar/retirar permiso),
con triggers de BD que protegen el rol Administrador y bloquean dejar un rol sin permisos. La tabla de
arriba es solo el seed inicial — en dev ya existen roles creados después de ese seed (`id_rol` > 5). No
asumas que `id_rol` está limitado a 1-5 en ningún módulo nuevo; consulta `modulo1.roles` en vivo.

Acciones para el nombre: `crear` (C=1), `leer` (R=2), `actualizar` (U=3), `desactivar` (D=4), `ejecutar` (E=5).

### Patrón completo de un endpoint con RBAC

```python
# 1. require_permission verifica el permiso y lanza 403 si no lo tiene
# 2. get_current_user provee usuario_actual (FastAPI lo cachea; no se llama dos veces)
@router.post(
    "",
    dependencies=[Depends(require_permission(8, 1))],  # C sobre recurso 8
)
def registrar(
    dto: MiDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),  # solo para auditoría
) -> MiResponse:
    use_case = MiUseCase(db=db, repo=SqlAlchemyMiRepo(db), ...)
    resultado = use_case.execute(dto, usuario_actual)
    return MiResponse.model_validate(resultado)
```

Patrón de transacción estándar en un use case:

```python
try:
    self.port_a.operacion(...)
    self.port_b.operacion(...)
    self.db.commit()
except Exception:
    self.db.rollback()
    raise

# Notificaciones fuera del bloque DB
send_email(...)
```

---

## Patrones adicionales

### Agregado con colección de hijos

Cuando un agregado posee una lista de entidades hijas (ej. `UmbralAmbiental` → `niveles`):

**ORM** — declarar la relación con cascade y carga eager:

```python
niveles = relationship(
    "NivelAlertaAmbientalModel",
    back_populates="umbral",
    cascade="all, delete-orphan",
    lazy="selectin",
)
```

**Repository `guardar`** — insertar padre primero, luego hijos:

```python
orm = UmbralAmbientalModel(...)
self.db.add(orm)
self.db.flush()  # genera el PK del padre
for nivel in entidad.niveles:
    self.db.add(NivelAlertaAmbientalModel(id_umbral_ambiental=orm.id, ...))
self.db.flush()
self.db.refresh(orm)
return self._a_entidad(orm)
```

**Repository `actualizar`** — delete-then-insert; nunca actualizar hijos en el lugar:

```python
orm.campo = entidad.campo  # actualizar campos del padre
for hijo in list(orm.niveles):
    self.db.delete(hijo)
self.db.flush()
for nivel in entidad.niveles:
    self.db.add(NivelAlertaAmbientalModel(id_umbral_ambiental=orm.id, ...))
self.db.flush()
self.db.refresh(orm)
return self._a_entidad(orm)
```

La razón para delete-then-insert: el nivel (`normal`/`precaucion`/`critico`) es parte de la identidad de cada hijo; no hay forma segura de hacer update in-place cuando el conjunto puede cambiar completamente.

---

### Concurrencia optimista (412)

Para entidades editables con campo `fecha_actualizacion TIMESTAMPTZ`, el use case de edición verifica que el cliente envíe el timestamp exacto que tiene la DB:

```python
from datetime import timezone
from src.shared.errors import PreconditionFailedError

ts_actual = entidad.fecha_actualizacion   # viene de la DB
ts_dto    = dto.fecha_actualizacion       # viene del cliente

if ts_actual is not None and ts_dto is not None:
    if ts_actual.astimezone(timezone.utc) != ts_dto.astimezone(timezone.utc):
        raise PreconditionFailedError(
            code="CONFLICTO_CONCURRENCIA",
            message="El registro fue modificado por otro usuario. Recarga y reintenta.",
        )
elif ts_actual != ts_dto:
    raise PreconditionFailedError(
        code="CONFLICTO_CONCURRENCIA",
        message="El registro fue modificado por otro usuario. Recarga y reintenta.",
    )
```

La doble rama existe porque `None != None` es `False` en Python pero `datetime(tz) != None` es `True`, así que la comparación directa daría falso positivo cuando ambos son `None` (entidad nunca editada).

---

### `_snapshot()` en entidades con auditoría

Toda entidad que registra auditoría implementa `_snapshot() → dict` con el estado actual en formato JSON-serializable. Se llama **antes** de la mutación para capturar `valores_anteriores`:

```python
def _snapshot(self) -> dict:
    return {
        "valor_min": str(self.valor_min),
        "valor_max": str(self.valor_max),
        "niveles": [
            {"nivel": n.nivel.value, "limite_inferior": str(n.limite_inferior)}
            for n in self.niveles
        ],
    }
```

Flujo en el use case de edición:

```python
snapshot_anterior = entidad._snapshot()
entidad.actualizar(...)           # muta la entidad
repo.actualizar(entidad)
auditoria_repo.registrar(
    tipo_op="UPDATE",
    valores_nuevos=entidad._snapshot(),
    valores_anteriores=snapshot_anterior,
)
self.db.commit()
```

---

### Adaptador stub para dependencias cruzadas

Cuando un use case necesita consultar un módulo aún no implementado (ej. verificar si una especie tiene ciclos activos), crear un stub en `infrastructure/adapters/`:

```python
# infrastructure/adapters/ciclo_stub_adapter.py
from src.configuration.domain.repositories.ciclo_dependency_port import CicloDependencyPort

class CicloStubAdapter(CicloDependencyPort):
    def tiene_ciclos_activos(self, id_especie: int) -> bool:
        return False  # valor seguro por defecto hasta implementar el módulo real
```

El router inyecta el stub igual que cualquier repositorio. Cuando el módulo real se implemente, se reemplaza el stub por la implementación concreta sin tocar el use case.

---

### Columnas enum de PostgreSQL en modelos ORM

Usar `String` en lugar de `Enum` de SQLAlchemy cuando la columna mapea a un tipo enum que ya existe en PostgreSQL:

```python
# Correcto — evita conflicto con el tipo enum existente en la DB
nivel = Column(String(20), nullable=False)

# Incorrecto — SQLAlchemy intenta crear el tipo en el ALTER TABLE y falla
nivel = Column(Enum("normal", "precaucion", "critico", name="enum_nivel_alerta"), ...)
```

---

### `raise_from_db_error` en repositories

Todo método de escritura en un repository debe capturar errores de DB y traducirlos antes de que salgan de la capa de infraestructura:

```python
from src.shared.db_error_translator import raise_from_db_error

def guardar(self, entidad: MiEntidad) -> MiEntidad:
    try:
        orm = MiModel(...)
        self.db.add(orm)
        self.db.flush()
        self.db.refresh(orm)
        return self._a_entidad(orm)
    except Exception as exc:
        raise_from_db_error(exc)
```

Esto convierte `IntegrityError` de SQLAlchemy en `ConflictError` (409) con el campo correspondiente. La capa de aplicación no debe conocer `IntegrityError`.

---

## Jerarquía de errores (`src/shared/errors.py`)

Todos heredan de `AppError`. El handler global los convierte a la respuesta HTTP correspondiente.

| Clase | HTTP | Cuándo usarla |
|-------|------|---------------|
| `ValidationError` | 400 | Dato inválido a nivel de regla de dominio |
| `AuthenticationError` | 401 | Credenciales inválidas, JWT inválido o ausente |
| `AuthorizationError` | 403 | Autenticado pero sin permiso para la operación |
| `NotFoundError` | 404 | Recurso no existe |
| `ConflictError` | 409 | Recurso duplicado (correo, identificación) |
| `PreconditionFailedError` | 412 | Edición rechazada por conflicto de concurrencia optimista |
| `BusinessRuleError` | 422 | Violación de regla de negocio |
| `FlowError` | 422 | Fallo a mitad de flujo (token ya usado, transición inválida) |
| `GoneError` | 410 | Recurso que existió pero ya no aplica (token expirado) |
| `TooManyRequestsError` | 429 | Límite de concurrencia u operaciones simultáneas excedido |
| `InfrastructureError` | 500 | Fallo interno de adaptador externo |
| `ServiceUnavailableError` | 503 | Servicio externo no disponible temporalmente (SMTP, terceros) |

Formato de respuesta de error (siempre el mismo):

```json
{
  "code": "CODIGO_NEGOCIO",
  "message": "Mensaje legible para el usuario",
  "field": "nombre_campo_si_aplica"
}
```

---

## Variables de entorno requeridas

Ver `.env.example`. Las obligatorias para levantar el sistema:

```env
DATABASE_URL=postgresql://usuario:clave@host:5432/dbname

# JWT — el código lee SECRET_KEY (no JWT_SECRET). Algoritmo fijo HS256, no configurable.
SECRET_KEY=clave_secreta_larga
JWT_EXPIRE_HOURS=8

# SMTP
SMTP_HOST=smtp.ejemplo.com
SMTP_PORT=587
SMTP_USER=correo@ejemplo.com
SMTP_PASSWORD=clave

# Frontend (usado en links dentro de emails)
FRONTEND_URL=http://localhost:3000
```

---

## Notas de infraestructura

**`root_path="/api"` en `main.py`**
El prefijo `/api` lo agrega el proxy inverso en producción. Localmente los endpoints se acceden sin ese prefijo: `http://localhost:8000/usuarios/`.

**Autenticación frontend → backend**
El backend usa dos tokens con transporte distinto (diseño completo en
`anotaciones/modulo_1/gaps_bd_refresh_tokens.md` y `plan_access_refresh_tokens.md`):
- **Access token** (JWT, `JWT_EXPIRE_HOURS` — 8h por RF-02): viaja en el body
  JSON de `POST /sesiones/`, `POST /sesiones/sso` y `POST /sesiones/refresh`;
  el frontend lo envía en `Authorization: Bearer <token>`. Dónde lo guarda en
  memoria (nunca `localStorage`/`IndexedDB`) es decisión del equipo de frontend.
- **Refresh token** (opaco, no JWT, `REFRESH_TOKEN_EXPIRE_DAYS` — 7 días):
  gestionado exclusivamente por el backend vía cookie `HttpOnly; path=/`,
  invisible para JS. En producción front y backend viven en dominios
  distintos, así que la cookie usa `SameSite=None; Secure` (requiere que el
  frontend llame con `credentials: 'include'`); fuera de producción se usa
  `SameSite=Strict` sin `Secure` (front y backend comparten site en local).
  Rota en cada uso; reusar uno ya rotado revoca la sesión completa (detección
  de robo). El frontend nunca la lee ni la transporta manualmente — esta
  parte del mecanismo sí es contrato de backend, no decisión de frontend.

Ante un `401 TOKEN_EXPIRADO`, el frontend debe llamar `POST /sesiones/refresh`
(sin body, la cookie viaja sola) para obtener un access token nuevo antes de
reintentar la request original.

**Links en emails**
Los templates de correo generan links hacia el frontend (`FRONTEND_URL`), no hacia el backend. El frontend extrae el token del query param y llama el endpoint de activación en el backend. Para pruebas sin frontend, usar Swagger o curl directamente.

**`audit_sdk`**
Disponible como `.whl` local en `vendor/` (`AuditClient`, `AuditContextMiddleware`). **El middleware se
importa en `main.py` pero nunca se registra con `app.add_middleware(...)` — es código muerto, no está
activo.** Los eventos de auditoría reales de módulo 1 usan un mecanismo propio: tabla `modulo1.eventos`
con hash SHA-256 de integridad calculado en el repository (`src/identity_access/infrastructure/repositories/evento_repository.py`),
e inmutabilidad forzada por triggers de BD (bloquean `UPDATE`/`DELETE` incluso para el rol `postgres`).
Si un módulo nuevo necesita auditoría, sigue este patrón — no asumas que `audit_sdk` está inicializado.

**Campo `direccion` en edición de perfil (RF-05)**
El RF-05 no lista `direccion` como campo editable, pero el diagrama del paso 03 sí lo incluye. El campo está implementado como editable en el use case. Pendiente confirmación del grupo de análisis para definir si debe excluirse o mantenerse.

**Esquemas de DB**
Los modelos ORM pueden declarar `schema="nombre_schema"` en el `__table_args__`. Verificar en `base_model.py` o en el modelo específico del módulo.
