# RF-02 — Vigencia del JWT de 8 horas

## Requisito

Los tokens JWT de autenticación deben tener una vigencia de 8 horas. La variable
`JWT_EXPIRE_HOURS` debe estar declarada en `.env.example` para que los ambientes
nuevos no dependan de una configuración implícita diferente al requisito.

## Hallazgo corregido

La configuración utilizaba anteriormente una vigencia predeterminada de 24 horas
y `.env.example` no declaraba `JWT_EXPIRE_HOURS`. Esto permitía que un ambiente
nuevo emitiera JWT con una duración distinta a la definida por RF-02.

## Implementación

- `src/shared/jwt.py` define 8 horas como valor predeterminado.
- La vigencia puede configurarse mediante `JWT_EXPIRE_HOURS`.
- `.env.example` declara `JWT_EXPIRE_HOURS=8`.
- La creación del JWT y el cálculo de expiración de la sesión usan la misma
  configuración de horas, manteniendo coherencia entre ambos mecanismos.
- El cambio no requiere una migración de base de datos.

## Verificación

Las pruebas de `tests/shared/test_jwt_config.py` comprueban que:

1. Sin variable de entorno, el valor predeterminado es 8 horas.
2. La variable `JWT_EXPIRE_HOURS` permite configurar otra vigencia explícita.
3. Un JWT nuevo se emite con una expiración aproximada de 8 horas.
4. `.env.example` contiene `JWT_EXPIRE_HOURS=8`.

La prueba dedicada puede ejecutarse con:

```bash
pytest tests/shared/test_jwt_config.py
```

## Consideraciones de despliegue

- Configurar `JWT_EXPIRE_HOURS=8` en cada ambiente.
- Reiniciar la aplicación después de modificar la variable, porque la
  configuración se carga al importar el módulo JWT.
- Los JWT emitidos antes del cambio conservan la expiración incluida en ellos;
  la vigencia de 8 horas aplica a los tokens emitidos posteriormente.