# Curls — Módulo Identity & Access

Base URL: `http://localhost:8000`

Para endpoints que requieren autenticación, reemplaza `<TOKEN>` con el JWT obtenido del login.

---

## Sesiones

### Iniciar sesión
```bash
curl -s -X POST http://localhost:8000/sesiones/ \
  -H "Content-Type: application/json" \
  -d '{
    "correo_electronico": "usuario@ejemplo.com",
    "contrasena": "Contrasena1!"
  }' | jq
```

### Cerrar sesión
```bash
curl -s -X DELETE http://localhost:8000/sesiones/ \
  -H "Authorization: Bearer <TOKEN>" | jq
```

---

## Usuarios

### Registrar nuevo usuario
```bash
curl -s -X POST http://localhost:8000/usuarios/ \
  -H "Content-Type: application/json" \
  -d '{
    "correo_electronico": "nuevo@ejemplo.com",
    "telefono": "3001234567",
    "tipo_identificacion": "CC",
    "numero_identificacion": "1234567890",
    "nombre": "Juan",
    "apellidos": "Pérez García",
    "fecha_nacimiento": "1990-05-15",
    "genero": "M",
    "contrasena": "Contrasena1!",
    "direccion": "Calle 123 # 45-67"
  }' | jq
```

### Activar cuenta con token
```bash
curl -s -X GET "http://localhost:8000/usuarios/activar/<TOKEN_ACTIVACION>" | jq
```

### Reenviar correo de activación
```bash
curl -s -X POST http://localhost:8000/usuarios/activar/reenviar \
  -H "Content-Type: application/json" \
  -d '{
    "correo_electronico": "usuario@ejemplo.com"
  }' | jq
```

### Ver perfil propio
```bash
curl -s -X GET http://localhost:8000/usuarios/me \
  -H "Authorization: Bearer <TOKEN>" | jq
```

### Editar perfil propio
```bash
curl -s -X PATCH http://localhost:8000/usuarios/me \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "nombre": "Juan",
    "apellidos": "Pérez García",
    "correo_electronico": "nuevo_correo@ejemplo.com",
    "telefono": "3009876543",
    "direccion": "Carrera 10 # 20-30",
    "version": 1
  }' | jq
```

### Completar perfil tras provisión SSO (cuenta PENDIENTE_DATOS)
```bash
# tipo_identificacion/numero_identificacion/fecha_nacimiento/genero solo se
# aceptan mientras la cuenta está en estado PENDIENTE_DATOS (provista vía SSO
# de AgroFusion sin sincronización previa). Al completar los 6 campos
# requeridos (nombre, apellidos, tipo y número de identificación, fecha de
# nacimiento, género) la cuenta pasa a ACTIVO automáticamente.
curl -s -X PATCH http://localhost:8000/usuarios/me \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "nombre": "Juan",
    "apellidos": "Pérez García",
    "tipo_identificacion": "CC",
    "numero_identificacion": "1234567890",
    "fecha_nacimiento": "1995-05-05",
    "genero": "M",
    "version": 1
  }' | jq
```

### Editar perfil o rol de otro usuario (administrativo)
```bash
# Requiere el permiso Actualizar sobre el recurso Usuarios (1, 3).
# El estado no se acepta aquí: se cambia exclusivamente mediante /gestionar.
curl -s -X PATCH http://localhost:8000/usuarios/<ID_USUARIO> \
  -H "Authorization: Bearer <TOKEN_ADMIN>" \
  -H "Content-Type: application/json" \
  -d '{
    "nombre": "Juan",
    "apellidos": "Pérez García",
    "correo_electronico": "nuevo_correo@ejemplo.com",
    "telefono": "3009876543",
    "direccion": "Carrera 10 # 20-30",
    "version": 1,
    "id_rol": 3
  }' | jq
```

### Registrar token FCM (notificaciones push)
```bash
curl -s -X POST http://localhost:8000/usuarios/me/fcm-token \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "token": "fcm_token_del_dispositivo_aqui"
  }' | jq
```

### Listar usuarios paginado (admin)
```bash
curl -s -X GET "http://localhost:8000/usuarios/admin?pagina=1&tamano=20" \
  -H "Authorization: Bearer <TOKEN>" | jq

# Con filtros opcionales
curl -s -X GET "http://localhost:8000/usuarios/admin?nombre=Juan&id_rol=2&pagina=1&tamano=10" \
  -H "Authorization: Bearer <TOKEN>" | jq

# Filtro por nombre de estado de cuenta (case-insensitive), alternativa a id_estado
curl -s -X GET "http://localhost:8000/usuarios/admin?estado_cuenta=Activo" \
  -H "Authorization: Bearer <TOKEN>" | jq

# Refresco incremental: solo usuarios modificados (datos o estado de cuenta)
# desde el último `ultima_modificacion` visto en una fila del listado previo
curl -s -X GET "http://localhost:8000/usuarios/admin?actualizado_desde=2026-08-17T20:00:00Z" \
  -H "Authorization: Bearer <TOKEN>" | jq
```
> El endpoint legacy `GET /usuarios/` fue retirado por RF-11 porque no tenía
> autenticación, no estaba paginado y exponía datos personales completos.

> El listado ordena por `fecha_registro` descendente y cada item incluye
> `ultima_modificacion` (máximo entre `fecha_actualizacion` del usuario y
> `fecha_cambio_estado` de su cuenta) para que el frontend detecte filas
> desactualizadas sin recargar la página completa (RF-11, mecanismo de
> refresco). Si el resultado queda vacío (por filtros o por
> `actualizado_desde`), la respuesta incluye `mensaje` con un texto
> explicativo en vez de solo `items: []`.

> Solo el rol Administrador tiene el permiso `admin_leer_usuario`
> (`require_permission(1, 2)`). Un token de Veterinario (o cualquier otro rol
> no administrativo) recibe `403 ACCESO_DENEGADO`:
> ```bash
> curl -s -X GET http://localhost:8000/usuarios/admin \
>   -H "Authorization: Bearer <TOKEN_VETERINARIO>" | jq
> # {"error_code":"ACCESO_DENEGADO","message":"Acceso denegado. Su rol no tiene permisos para realizar esta operación."}
> ```

### Ver detalle de un usuario (admin)
```bash
curl -s -X GET http://localhost:8000/usuarios/<ID_USUARIO>/detalle \
  -H "Authorization: Bearer <TOKEN>" | jq
```
> Comparte `require_permission(1, 2)` con el listado — mismo 403 para roles
> no administrativos (ver nota de RF-11 arriba).

### Gestionar cuenta de usuario (admin)
```bash
# Acciones válidas: activar | inactivar | bloquear | eliminar
curl -s -X POST http://localhost:8000/usuarios/<ID_USUARIO>/gestionar \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "accion_cuenta": "inactivar",
    "motivo_accion": "Incumplimiento de términos de uso"
  }' | jq

# Para activar (sin motivo)
curl -s -X POST http://localhost:8000/usuarios/<ID_USUARIO>/gestionar \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "accion_cuenta": "activar"
  }' | jq
```

---

## Contraseña

### Cambiar contraseña (usuario autenticado)
```bash
curl -s -X PUT http://localhost:8000/contrasena/usuarios/<ID_USUARIO> \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "contrasena_actual": "ContrasenaVieja1!",
    "nueva_contrasena": "ContrasenaNueva1!",
    "confirmar_nueva_contrasena": "ContrasenaNueva1!"
  }' | jq
```

### Solicitar recuperación de contraseña
```bash
curl -s -X POST http://localhost:8000/contrasena/recuperar \
  -H "Content-Type: application/json" \
  -d '{
    "correo_electronico": "usuario@ejemplo.com"
  }' | jq
```

### Restablecer contraseña con token
```bash
curl -s -X POST http://localhost:8000/contrasena/restablecer \
  -H "Content-Type: application/json" \
  -d '{
    "token": "<TOKEN_RECUPERACION>",
    "nueva_contrasena": "ContrasenaNueva1!",
    "confirmar_contrasena": "ContrasenaNueva1!"
  }' | jq
```

---

## Roles y Permisos

### Listar roles con sus permisos (admin)
```bash
curl -s -X GET http://localhost:8000/roles/ \
  -H "Authorization: Bearer <TOKEN>" | jq
```

### Crear rol (admin)
```bash
curl -s -X POST http://localhost:8000/roles/ \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "nombre_rol": "Supervisor",
    "descripcion": "Rol con acceso de supervisión",
    "permisos": [
      {"id_recurso": 1, "id_accion": 2}
    ]
  }' | jq
```

### Ver detalle de un rol (admin)
```bash
curl -s -X GET http://localhost:8000/roles/<ID_ROL> \
  -H "Authorization: Bearer <TOKEN>" | jq
```

### Editar rol (admin)
```bash
curl -s -X PUT http://localhost:8000/roles/<ID_ROL> \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "nombre_rol": "Supervisor Senior",
    "descripcion": "Descripción actualizada"
  }' | jq
```

### Eliminar rol (admin)
```bash
curl -s -X DELETE http://localhost:8000/roles/<ID_ROL> \
  -H "Authorization: Bearer <TOKEN>" | jq
```

### Catálogo de recursos
```bash
curl -s -X GET http://localhost:8000/roles/catalogo/recursos \
  -H "Authorization: Bearer <TOKEN>" | jq
```

### Catálogo de acciones
```bash
curl -s -X GET http://localhost:8000/roles/catalogo/acciones \
  -H "Authorization: Bearer <TOKEN>" | jq
```

### Listar permisos de un rol
```bash
curl -s -X GET http://localhost:8000/roles/<ID_ROL>/permisos \
  -H "Authorization: Bearer <TOKEN>" | jq
```

### Asignar permiso a un rol (admin)
```bash
curl -s -X POST http://localhost:8000/roles/<ID_ROL>/permisos \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "id_recurso": 2,
    "id_accion": 1
  }' | jq
```

### Retirar permiso de un rol (admin)
```bash
curl -s -X DELETE http://localhost:8000/roles/<ID_ROL>/permisos/<ID_PERMISO> \
  -H "Authorization: Bearer <TOKEN>" | jq
```

---

## Auditoría

### Consultar log de eventos paginado (admin)
```bash
curl -s -X GET "http://localhost:8000/auditoria/?pagina=1&tamano=20" \
  -H "Authorization: Bearer <TOKEN>" | jq

# Con filtros opcionales
curl -s -X GET "http://localhost:8000/auditoria/?id_usuario=5&tipo_evento=1&pagina=1&tamano=10" \
  -H "Authorization: Bearer <TOKEN>" | jq

# Con rango de fechas (formato ISO 8601)
curl -s -X GET "http://localhost:8000/auditoria/?fecha_desde=2026-01-01T00:00:00&fecha_hasta=2026-06-10T23:59:59&pagina=1&tamano=20" \
  -H "Authorization: Bearer <TOKEN>" | jq
```