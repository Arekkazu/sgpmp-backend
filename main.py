from audit_sdk.context_fastapi import AuditContextMiddleware
from fastapi import FastAPI

from src.identity_access.infrastructure.routers.usuarios_routers import router as usuarios_router

app = FastAPI(
    root_path="/api",
    title="sistema gestion  - Gestión de Usuarios, Roles y Permisos",
    description="Microservicio de gestión de usuarios, roles y permisos dentro del sistema de gestión de maquinaria y nómina.",
    version="1.0.0",
)

app.include_router(usuarios_router)

@app.get("/", tags=["Health"])
async def index():
    return "hello world!"

@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok", "message": "API funcionando correctamente"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
