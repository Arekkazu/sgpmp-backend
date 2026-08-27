# RF-01 — Confirmación, identificación numérica y correo asíncrono

## Hallazgos corregidos

- El registro no exigía confirmar la contraseña.
- `numero_identificacion` aceptaba caracteres no numéricos.
- Los tres intentos SMTP y sus pausas de cinco segundos bloqueaban el request.

## Implementación

- `UsuarioCreateDTO` exige `confirmar_contrasena`, valida su coincidencia y
  acepta únicamente dígitos ASCII en `numero_identificacion`.
- La entidad `Usuario` repite la invariante numérica y los DTO de perfil y
  AgroFusion evitan que otros flujos introduzcan valores incompatibles.
- La migración Alembic `e7b31f4a6c20` agrega un trigger para nuevas altas y
  cambios del documento. No modifica las cinco filas históricas incompatibles
  encontradas en DEV ni impide que actualicen otros campos.
- `CorreoActivacionBackgroundAdapter` agenda la notificación centralizada con
  `BackgroundTasks` y abre una sesión independiente. Los tres intentos con
  pausas de cinco segundos se mantienen, pero ya no forman parte del tiempo de
  respuesta del registro.

La tarea en segundo plano vive en el proceso de FastAPI y no constituye una
cola durable. Una cola persistente para sobrevivir reinicios queda como mejora
de infraestructura separada.

## Aplicación de base de datos

```powershell
.\.venv\Scripts\alembic.exe upgrade head
```

La revisión de DEV fue exclusivamente de lectura; no se aplicó la migración.

## Pruebas

- Unitarias: `tests/identity_access/test_rf01_validaciones_registro.py`.
- Integración: `tests/integration/test_rf01_validaciones_registro_integration.py`.
