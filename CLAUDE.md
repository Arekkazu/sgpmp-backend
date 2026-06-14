# CLAUDE.md — SGPMP Backend

---

## Qué cubre este documento

- Arquitectura y responsabilidad de cada capa
- Flujo de trabajo para implementar un caso de uso
- Reglas de construcción y sus razones
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

Seguir este orden sin saltarse capas:

1. **Modelo ORM** — mapea la tabla si no existe
2. **Entidad / value objects** — modela el agregado y su conducta en `domain/`
3. **DTO** — define el input del endpoint
4. **Port** — declara las operaciones necesarias (ABC) en `domain/repositories/`, en términos de dominio
5. **Repository** — implementa el puerto con SQLAlchemy (`flush()`, sin `commit()`), mapeando ORM ↔ entidad
6. **Use Case** — orquesta: valida, llama puertos, `commit()`, notificaciones
7. **Schema** — define el response del endpoint
8. **Router** — conecta todo, sin lógica

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
  necesarios para el recurso. Si faltan, insertarlos y documentarlos en `anotaciones/`.
- Los recursos están en `modulo1.recursos`. Cada módulo de negocio registra ahí sus
  recursos con un `id_recurso` propio.

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

## Jerarquía de errores (`src/shared/errors.py`)

Todos heredan de `AppError`. El handler global los convierte a la respuesta HTTP correspondiente.

| Clase | HTTP | Cuándo usarla |
|-------|------|---------------|
| `ValidationError` | 400 | Dato inválido a nivel de regla de dominio |
| `AuthenticationError` | 401 | Credenciales inválidas, JWT inválido o ausente |
| `AuthorizationError` | 403 | Autenticado pero sin permiso para la operación |
| `NotFoundError` | 404 | Recurso no existe |
| `ConflictError` | 409 | Recurso duplicado (correo, identificación) |
| `BusinessRuleError` | 422 | Violación de regla de negocio |
| `FlowError` | 422 | Fallo a mitad de flujo (token ya usado, transición inválida) |
| `GoneError` | 410 | Recurso que existió pero ya no aplica (token expirado) |
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

# SMTP
SMTP_HOST=smtp.ejemplo.com
SMTP_PORT=587
SMTP_USER=correo@ejemplo.com
SMTP_PASSWORD=clave

# JWT
JWT_SECRET=clave_secreta_larga
JWT_ALGORITHM=HS256
JWT_EXPIRE_HOURS=24

# Frontend (usado en links dentro de emails)
FRONTEND_URL=http://localhost:3000
```

---

## Notas de infraestructura

**`root_path="/api"` en `main.py`**
El prefijo `/api` lo agrega el proxy inverso en producción. Localmente los endpoints se acceden sin ese prefijo: `http://localhost:8000/usuarios/`.

**Autenticación frontend → backend**
El backend expone JWT vía `Authorization: Bearer <token>` en el header HTTP. Dónde y cómo el frontend almacena el token (localStorage, IndexedDB, memoria) y cómo lo inyecta en cada request (manualmente o vía Service Worker) es **decisión exclusiva del equipo de frontend** y no afecta el contrato del backend.

**Links en emails**
Los templates de correo generan links hacia el frontend (`FRONTEND_URL`), no hacia el backend. El frontend extrae el token del query param y llama el endpoint de activación en el backend. Para pruebas sin frontend, usar Swagger o curl directamente.

**`audit_sdk`**
Disponible como `.whl` local en `vendor/`. Se inicializa en `main.py` mediante `AuditContextMiddleware`. Los eventos de auditoría se registran desde los use cases correspondientes.

**Campo `direccion` en edición de perfil (RF-05)**
El RF-05 no lista `direccion` como campo editable, pero el diagrama del paso 03 sí lo incluye. El campo está implementado como editable en el use case. Pendiente confirmación del grupo de análisis para definir si debe excluirse o mantenerse.

**Esquemas de DB**
Los modelos ORM pueden declarar `schema="nombre_schema"` en el `__table_args__`. Verificar en `base_model.py` o en el modelo específico del módulo.
