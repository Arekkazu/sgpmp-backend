# INC-M07-377-G025 · RF-97 · `SourceSystem.Environment` reporta "DEV" en TEST

> Numeración **provisional** (377, continúa la serie 373-376): confirmar el consecutivo con la
> líder de pruebas / Taiga antes de publicar.

## Título (GitHub y Taiga)

`[INC-M07-377-G025][RF-97] El envelope AAEF reporta SourceSystem.Environment="DEV" aunque se consulta en TEST`

## Cuerpo del issue (pegar igual en GitHub y en Taiga)

[TC-M07-G025][RF-97] El envelope AAEF reporta SourceSystem.Environment="DEV" aunque se consulta en TEST

Incidencia: INC-M07-377-G025
Módulo: M07
RF: RF-97 (CA-4, 5.4 — sección `metadata`)
Caso: TC-M07-G025
Ambiente: TEST
Equipo responsable: Infraestructura / DevOps (configuración de despliegue)
Repositorio: Infraestructura de despliegue TEST
Categoría: CONFIG_DESPLIEGUE
Severidad: Baja
Prioridad: Normal
Evaluador: Julian Badillo

### Problema

Toda respuesta de `GET /integracion/aaef/vista-previa/productores/{nit}` (y, por el mismo caso de
uso, del endpoint real de AgroFusión) en el entorno TEST trae
`metadata.SourceSystem.Environment = "DEV"` en lugar de `"TEST"`.

### Caso reproducido

```
GET {{base_url}}/integracion/aaef/vista-previa/productores/901444215?desde=2026-10-01&hasta=2026-10-31
Authorization: Bearer <token del Contador>
```

Respuesta real (recortada):

```json
{
  "metadata": {
    "SourceSystem": {"SystemId": "SGPMP", "SystemName": "SIGAB", "SystemNIT": "901444215", "Environment": "DEV"}
  }
}
```

Confirmado de forma estable en tres corridas independientes: 2026-11-17/18, 2026-11-21 (release
v3.0 del contrato) y 2026-11-20 (reprueba de esta sesión, filtrando solo esta carpeta con Newman).

### Resultado esperado

`SourceSystem.Environment` debe reflejar el entorno real que atiende la solicitud (`"TEST"` en
TEST, el valor correspondiente en cada entorno).

### Resultado obtenido

Siempre `"DEV"`, sin importar el entorno real consultado.

### Impacto

Severidad: Baja.

- No afecta ninguna validación de negocio ni el contenido financiero del envelope (CA-1/CA-8/CA-9
  siguen correctos; confirmado por separado en TC-M07-G024/G026).
- Si AgroFusión o SIGCON usan este campo para decidir el flujo de conciliación por entorno
  (sandbox vs. producción), un `"DEV"` persistente en TEST podría enmascarar a qué entorno
  realmente corresponde el dato, y no se ha verificado qué pasaría si el mismo valor aparece en
  producción.

### Causa probable

No confirmada a nivel de código (no hay acceso a la configuración del contenedor desde este
hilo). Es consistente con una variable de entorno del despliegue (`SGPMP_ENTORNO` o equivalente)
fijada en `"DEV"` para el contenedor de TEST, en lugar de reflejar el entorno real.

### Acción requerida

1. Infraestructura/DevOps: revisar la variable de entorno que alimenta `SourceSystem.Environment`
   en el despliegue de TEST y corregirla a `"TEST"`.
2. Confirmar que producción no tiene el mismo problema (debe reportar el valor correcto para su
   propio entorno).
3. Reevaluar TC-M07-G025 tras el ajuste.

### Criterios de aceptación

- `GET /integracion/aaef/vista-previa/productores/{nit}` en TEST devuelve
  `SourceSystem.Environment = "TEST"`.
- El mismo campo en producción devuelve el valor correcto de su propio entorno.
- TC-M07-G025 aprueba sin esta observación.

### Evidencias

- `tests/Test_Testing/Test_Modulo7/RF-97/TC-M07-G025/resultados/resultado_TC-M07-G025.html`/`.json`
  (re-ejecución 2026-11-20, aserción explícita del hallazgo).
- `tests/Test_Testing/Test_Modulo7/RF-97-Verificacion-Live/ficha.md` (confirmado 2026-11-17/18 y
  2026-11-21).

### Estado

INC-M07-377-G025 queda abierta y debe ser derivada a Infraestructura/DevOps. No es un defecto de
código de RF-97.

## Atributos personalizados de Taiga

| Atributo | Valor |
|---|---|
| Modulo | M07 |
| RF | RF-97 (CA-4, 5.4) |
| Codigo de error | CONFIG_DESPLIEGUE |
| Equipo responsable | Infraestructura / DevOps |
| Severidad | Baja |
| Tiempo maximo de solucion | Hasta el martes 24 de noviembre de 2026 (3 días desde el reporte) |
| Fecha de deteccion | 2026-11-17 (re-confirmado 2026-11-20/21) |
| Fecha limite | 2026-11-24 |
| Evaluador | Julian Badillo |

## Adjuntos (ambas plataformas)

`resultado_TC-M07-G025.html`/`.json` (carpeta `RF-97/TC-M07-G025/resultados/`) y
`RF-97-Verificacion-Live/ficha.md`.
