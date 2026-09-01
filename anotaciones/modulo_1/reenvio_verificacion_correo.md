# Reenvío de verificación de correo

Feature sin RF asociado. El token de activación expira a las 24 h
(`Cuenta.TOKEN_EXPIRACION_HORAS`); quien no abre el correo a tiempo queda con la
cuenta en PENDIENTE y sin forma cómoda de pedir uno nuevo.

## Qué ya existía

- `POST /usuarios/activar/reenviar` → `ReenviarTokenUseCase`: rota el token de la
  cuenta PENDIENTE y reenvía el correo.
- Login devuelve `403 CUENTA_PENDIENTE` con un mensaje que ya menciona la opción
  de reenviar (`sesiones/sesion_comun.py`).
- Frontend: página `/reenviar-activacion`, enlazada desde registro y activación.

## Qué se cambió aquí

### Backend

`src/identity_access/application/use_cases/registro/reenviar_token_use_case.py`

1. **Rate limiting por IP** — máx. `MAX_REENVIOS_POR_HORA = 3`. Sin esto el
   endpoint es un vector de bombardeo de correo contra cualquier usuario
   pendiente: bastaba conocer su dirección. Excedido → `422
   LIMITE_SOLICITUDES_EXCEDIDO`.

2. **Respuesta uniforme** — antes devolvía `400 CORREO_NO_REGISTRADO` y `422
   CUENTA_YA_ACTIVA`, o sea confirmaba qué correos existen en el sistema y en qué
   estado están. Ahora los tres casos (no existe / no está pendiente / reenvío
   real) responden `200` con el mismo texto genérico. Es lo que el front ya
   mostraba en su pantalla de éxito ("*Si* el correo tiene una cuenta
   pendiente..."), así que el backend dejó de contradecirlo.

Se reutiliza el tipo de evento `7 SOLICITUD_RECUPERACION` con
`detalle.motivo = "reenvio_token_activacion"` en vez de crear uno nuevo:
`solicitar_recuperacion_use_case.py` ya registra ese mismo tipo cuando rota un
token de activación de una cuenta pendiente. Consecuencia buscada: ambos flujos
que envían correo comparten la ventana de 3/hora por IP, que es justo el
presupuesto que se quiere limitar. Sin migración ni cambios en el puerto.

### Frontend

`LoginPage` renderiza un enlace a `/reenviar-activacion` dentro de la alerta
cuando el login falla con `CUENTA_PENDIENTE`, pasando el correo ya tecleado para
prellenar el formulario. Era el hueco real: el usuario leía "utilice la opción
re-enviar" sin tener dónde hacer clic.

## Pruebas

`tests/identity_access/test_reenvio_activacion.py` — reenvío + auditoría, no
enumeración (mismo mensaje y cero efectos para correo inexistente y para cuenta
no pendiente), y rate limit.

## CURLs

```bash
# Reenvío (cuenta pendiente, correo inexistente o cuenta activa: misma respuesta)
curl -X POST http://localhost:8000/usuarios/activar/reenviar \
  -H "Content-Type: application/json" \
  -d '{"correo_electronico": "pendiente@ejemplo.com"}'
# 200 {"message": "Si el correo corresponde a una cuenta pendiente de activación,
#      recibirás un nuevo enlace en unos minutos."}

# Cuarta llamada dentro de la misma hora desde la misma IP
# 422 {"error_code": "LIMITE_SOLICITUDES_EXCEDIDO", "message": "Límite de
#      solicitudes excedido para su conexión. ..."}
```
