from audit_sdk.context_fastapi import AuditContextMiddleware
from fastapi import FastAPI

from src.configuration.infrastructure.routers.ciclo_router import router as ciclo_router
from src.configuration.infrastructure.routers.configuracion_global_router import router as configuracion_global_router
from src.configuration.infrastructure.routers.especie_router import router as especie_router
from src.configuration.infrastructure.routers.finca_router import router as finca_router
from src.configuration.infrastructure.routers.dispositivo_iot_router import router as dispositivo_iot_router
from src.configuration.infrastructure.routers.infraestructura_router import router as infraestructura_router
from src.configuration.infrastructure.routers.sensor_router import router as sensor_router
from src.configuration.infrastructure.routers.contexto_interfaz_router import router as contexto_interfaz_router
from src.configuration.infrastructure.routers.identidad_visual_router import router as identidad_visual_router
from src.configuration.infrastructure.routers.tema_visual_router import router as tema_visual_router
from src.configuration.infrastructure.routers.dashboard_layout_router import router as dashboard_layout_router
from src.configuration.infrastructure.routers.preferencia_idioma_router import router as preferencia_idioma_router
from src.configuration.infrastructure.routers.metrica_router import router as metrica_router
from src.configuration.infrastructure.routers.patologia_router import router as patologia_router
from src.configuration.infrastructure.routers.plantilla_router import router as plantilla_router
from src.configuration.infrastructure.routers.umbral_router import router as umbral_router
from src.identity_access.infrastructure.routers.auditoria_routers import router as auditoria_router
from src.identity_access.infrastructure.routers.contrasena_routers import router as contrasena_router
from src.identity_access.infrastructure.routers.roles_routers import router as roles_router
from src.identity_access.infrastructure.routers.sesiones_routers import router as sesiones_router
from src.identity_access.infrastructure.routers.usuarios_routers import router as usuarios_router
from src.shared.error_handlers import register_error_handlers

app = FastAPI(
    root_path="/api",
    title="sistema gestion  - Gestión de Usuarios, Roles y Permisos",
    description="Microservicio de gestión de usuarios, roles y permisos dentro del sistema de gestión de maquinaria y nómina.",
    version="1.0.0",
)

register_error_handlers(app)

app.include_router(usuarios_router)
app.include_router(sesiones_router)
app.include_router(contrasena_router)
app.include_router(auditoria_router)
app.include_router(roles_router)
app.include_router(especie_router)
app.include_router(ciclo_router)
app.include_router(patologia_router)
app.include_router(metrica_router)
app.include_router(umbral_router)
app.include_router(plantilla_router)
app.include_router(configuracion_global_router)
app.include_router(finca_router)
app.include_router(infraestructura_router)
app.include_router(dispositivo_iot_router)
app.include_router(sensor_router)
app.include_router(contexto_interfaz_router)
app.include_router(identidad_visual_router)
app.include_router(tema_visual_router)
app.include_router(dashboard_layout_router)
app.include_router(preferencia_idioma_router)

@app.get("/", tags=["Health"])
async def index():
    return "hello world!"

@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok", "message": "API funcionando correctamente"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
