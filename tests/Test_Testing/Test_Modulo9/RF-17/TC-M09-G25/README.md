# TC-M09-G25 — RF17, límites físicos de la variable ambiental

Responsable Juan Esteban. Solo TEST real. No ejecutar G22, G23 ni G24 desde aquí.
No iniciar G26. Grupo de API: **sin Cypress**.

Ejecución `run-20260905` concluida. Resultado del grupo: **APROBADO**.
TC-M09-55 APROBADO · TC-M09-56 APROBADO. Sin defectos que reportar.
Consultar `RESULTADOS/run-20260905/TC-M09-G25_resultado.md`.

| Caso | GIVEN | WHEN | THEN |
|---|---|---|---|
| TC-M09-55 | Admin autorizado, especie activa, variable Humedad activa, combinación libre, rango y niveles estructuralmente correctos | POST con `valor_max = 120 %` sobre un máximo físico de 100 | 400 `RANGO_FISICO_INVALIDO` citando la variable y sus límites, sin ID y GET posterior sin registro |
| TC-M09-56 | Mismas precondiciones con la variable pH | POST con `valor_max = 18` sobre la escala 0–14 | Mismo rechazo controlado y ausencia de persistencia |

## Contrato real revisado una sola vez (solo lectura)

- `registrar_umbral_use_case.py::_validar_rangos` evalúa **FA-04 como primera
  regla**: si `valor_min < valor_fisico_min` o `valor_max > valor_fisico_max`
  lanza `ValidationError(code='RANGO_FISICO_INVALIDO')`.
- `src/shared/errors.py` mapea `ValidationError` a **HTTP 400**, que es lo que
  exige RF-17 para valores fuera de límites físicos. No hay
  `CONTRACT_REQUIREMENT_MISMATCH`.
- `_validar_rangos` corre **antes** de la comprobación de unicidad (409) y, dentro
  de sí, antes de `NIVEL_FUERA_DE_RANGO` y `SOLAPAMIENTO_NIVELES`.
- `registrar_umbral_dto.py` exige exactamente tres niveles (normal, precaucion,
  critico) y `nivel_dto.py` exige `limite_inferior < limite_superior` en cada uno:
  los niveles **son obligatorios** y se construyen contiguos y sin solapamiento
  para que la única invalidez sea la física.
- Catálogo real conforme a RF-17: Humedad Relativa `[0, 100] %` y pH del agua
  `[0, 14] pH`. Sin `CATALOG_REQUIREMENT_MISMATCH`.
- Observación documental: el `openapi.json` desplegado declara para este POST
  `201, 401, 403, 404, 409, 422` y no enumera el 400 que el manejador global sí
  devuelve. No es contradicción de la regla; queda anotada en el informe.

## Datos

Descubiertos dinámicamente antes de cada original: permisos, especies activas,
variables activas, variable que corresponde semánticamente a Humedad y a pH (por
nombre, con coincidencia única, nunca por ID supuesto), límites físicos, umbrales
existentes y combinación libre. Una combinación se considera ocupada aunque el
umbral esté inactivo, para que el 409 de duplicado no enmascare la regla probada.

## Requisitos y ejecución

Ya instalados, no se instala nada: Newman 6.2.2 y `newman-reporter-htmlextra`
1.23.1. G25 no usa Cypress.

Variables de proceso: `TEST_ADMIN_EMAIL`, `TEST_ADMIN_PASSWORD`, `G25_CASE`
(`TC-M09-55` | `TC-M09-56`), `G25_RUN_ID` y `G25_INTENTO` (1 o 2). La contraseña
nunca se escribe en un archivo.

```
NODE_PATH=<npm root -g>  node run-newman.cjs      # una invocación = un original
NODE_PATH=<npm root -g>  node verificar-cierre.cjs # GET final + escaneo de secretos
```

Máximo **2 POST por original**; el runner rechaza por diseño un tercer intento y
también sobrescribir la evidencia de un intento ya registrado. No se reintenta un
PASS. Si un payload inválido llegara a persistir: detener sin limpiar.

## Evidencia

`RESULTADOS/<G25_RUN_ID>/` con el JSON sanitizado por ejecución, los datos y
preflight, la verificación final de solo lectura, el escaneo de secretos, el
estado de Git y el informe; los HTML reales de htmlextra en
`RESULTADOS/<G25_RUN_ID>/newman/`. HTML y JSON se sanitizan tras generarse; el
reporter omite headers y datos de entorno.

Estado inicial: ambas ramas en `qa/juan-esteban-m09`. SHAs locales: backend
`adc3932b9f0293a76ebec7e89ed877274791b6a1`, frontend
`966621df4e2c6a1f2c9233ea5ebefbb9e3bc2f56`. SHA desplegado no confirmado.
