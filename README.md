# SGPMP Backend

Sistema de Gestión y Planificación para el Mercado Pecuario.

## Stack

| Componente | Tecnología |
|---|---|
| Runtime | Python 3.13 |
| Framework | FastAPI |
| ORM | SQLAlchemy 2.0 |
| Base de datos | PostgreSQL |
| Validación | Pydantic v2 |
| Autenticación | JWT (python-jose + bcrypt + passlib) |
| Background | Firebase Admin SDK |
| Auditoría | audit-sdk (interno, vendoreado) |
| Testing | pytest + pytest-cov |
| Documentación | OpenAPI (Swagger en /docs) |

## Arquitectura: Monolito Modular + Hexagonal + DDD

Se combinaron tres patrones:

- **Monolito modular** — un solo deploy, pero organizado en módulos independientes por dominio funcional. Permite extracción progresiva a microservicios sin rediseño.
- **Arquitectura Hexagonal (Puertos y Adaptadores)** — el núcleo de dominio define interfaces; la infraestructura las implementa. El dominio no depende de frameworks ni de la base de datos.
- **Domain-Driven Design** — el código se organiza en torno al lenguaje y las reglas del negocio pecuario, no en capas técnicas.

### Regla de dependencia

```
Infrastructure → Application → Domain
```

_Domain_ no depende de nada externo.

## Módulos del sistema

Cada módulo es un Bounded Context independiente. Las carpetas están en inglés y reflejan el nombre del contexto.

| Módulo | Carpeta | Responsabilidad | Depende de | Criticidad |
|---|---|---|---|---|
| Identity & Access | `identity_access` | Autenticación JWT, roles RBAC, auditoría inmutable con SHA-256 | — | Alta |
| Biological Assets | `biological_assets` | Ciclo de vida del activo: crecimiento, reproducción, producción, baja | `identity_access`, `configuration` | Alta |
| IoT Telemetry | `telemetry` | Captura DHT22/pH, edge computing, LoRaWAN, sincronización diferida 72h | `identity_access`, `biological_assets`, `configuration` | Alta |
| Prediction | `prediction` | Modelos ML por escala de especie, inferencia edge/server/híbrido, riesgo de contagio | `identity_access`, `biological_assets`, `telemetry`, `configuration` | Alta |
| Supplies | `supplies` | Costos de alimento/medicamentos, ICA, distinción MANTENIMIENTO/INVERSIÓN/VENTA | `identity_access`, `biological_assets` | Media |
| NIC 41 Valuation | `nic41_valuation` | Valor razonable NIC 41, cierre contable 9 pasos, trazabilidad 4 niveles | `identity_access`, `biological_assets`, `prediction`, `supplies` | Alta |
| External Integration | `integration` | Gateway REST, orquestador AAEF, 6 mappers, hash SHA-256, webhook | `identity_access`, `nic41_valuation` | Alta |
| Business Intelligence | `business_intelligence` | Dashboards con semáforo, reportes NIIF, historial clínico predictivo | `identity_access`, `biological_assets`, `telemetry`, `prediction`, `nic41_valuation`, `configuration` | Media |
| Configuration | `configuration` | Catálogo de especies, fincas, dispositivos IoT, umbrales, catálogos AAEF | `identity_access` | Alta |

### Estructura del proyecto

```
sgpmp-backend/
├── main.py                              ← Punto de entrada FastAPI
├── requirements.txt                     ← Dependencias
├── vendor/                              ← Wheels internos (audit-sdk)
├── .python-version                      ← Python 3.13.13
│
└── src/
    ├── identity_access/                 ← Módulo: Identity & Access
    │   ├── domain/                      ← Entidades, Value Objects, interfaces
    │   ├── application/                 ← Casos de uso
    │   └── infrastructure/              ← Routers FastAPI, repositorios SQLAlchemy
    │
    ├── biological_assets/               ← Módulo: Biological Assets
    │   ├── domain/
    │   ├── application/
    │   └── infrastructure/
    │
    ├── telemetry/                       ← Módulo: IoT Telemetry
    │   ├── domain/
    │   ├── application/
    │   └── infrastructure/
    │
    ├── prediction/                      ← Módulo: Prediction
    │   ├── domain/
    │   ├── application/
    │   └── infrastructure/
    │
    ├── supplies/                        ← Módulo: Supplies
    │   ├── domain/
    │   ├── application/
    │   └── infrastructure/
    │
    ├── nic41_valuation/                 ← Módulo: NIC 41 Valuation
    │   ├── domain/
    │   ├── application/
    │   └── infrastructure/
    │
    ├── integration/                     ← Módulo: External Integration
    │   ├── domain/
    │   ├── application/
    │   └── infrastructure/
    │
    ├── business_intelligence/           ← Módulo: Business Intelligence
    │   ├── domain/
    │   ├── application/
    │   └── infrastructure/
    │
    ├── configuration/                   ← Módulo: Configuration
    │   ├── domain/
    │   ├── application/
    │   └── infrastructure/
    │
    └── shared/                          ← Errores base, DTOs, utilidades
```

La comunicación entre contextos se realiza exclusivamente vía interfaces de aplicación — ningún módulo accede directamente a los repositorios de otro.

## Manejo de errores

Jerarquía propia de excepciones con `AppError` como base:

| Excepción | HTTP | Semántica |
|---|---|---|
| `RequestValidationError` (Pydantic) | 400 | Datos de entrada inválidos |
| `AuthorizationError` | 403 | Sin permisos |
| `NotFoundError` | 404 | Entidad no existe |
| `ConflictError` | 409 | Violación de unicidad |
| `BusinessRuleError` | 422 | Regla de negocio impide continuar |
| `InfrastructureError` | 503 | Componente externo falló |
| `AppError` (base) | 500 | Error no clasificado |

- **Validación de entrada**: Pydantic v2 como primer filtro en infraestructura; el dominio nunca ve datos inválidos.
- **Handler global**: un `add_exception_handler` centraliza la conversión de excepciones → JSON (`error_code`, `message`, `field` opcional, `timestamp`).
- **Base de datos**: cada repositorio SQLAlchemy captura excepciones técnicas y las clasifica (`IntegrityError` → `ConflictError`, `OperationalError` → `InfrastructureError`, etc.).
- **Canales externos** (SMTP, MQTT, HTTP): el adaptador captura la excepción de librería y la envuelve en `InfrastructureError`.

## Desarrollo

### Requisitos

- Python 3.13+
- PostgreSQL

### Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Ejecutar

```bash
uvicorn main:app --reload
```

### Tests

```bash
pytest --cov=src --html=report.html
```

## Convenciones

- **Carpetas**: `snake_case` en inglés, nombre del Bounded Context
- **Clases**: `PascalCase`
- **Funciones/variables**: `snake_case`
- **Constantes**: `UPPER_SNAKE_CASE`
- **Commits**: convencional (`feat:`, `fix:`, `refactor:`)
