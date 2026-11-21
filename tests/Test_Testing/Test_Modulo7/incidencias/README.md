# Incidencias de M07 · RF-95 y RF-101 (18-nov-2026)

Ambiente: TEST · Evaluador: Julian Badillo · Reportadas el 2026-11-18; tiempo máximo de solución: hasta el sábado 2026-11-21 · Casos: TC-M07-G001 a G006 (RF-95) y G042 a G047 (RF-101).

| Incidencia (provisional) | Caso | RF | Resumen | Severidad | Equipo | Límite |
|---|---|---|---|---|---|---|
| INC-M07-373-G043 | TC-M07-G043 | RF-101 FA-8 | Nombre de cliente duplicado se registra (201, sin 409) | Baja | Desarrollo Backend (+ Análisis) | 2026-11-21 |
| INC-M07-374-G047 | TC-M07-G047 | RF-101 5.1 | Credenciales de clientes 1 y 2 sin bcrypt | Media | DBA / Implementación | 2026-11-21 |
| INC-M07-375-G002 | TC-M07-G002 | RF-95 Salida | Cuerpo de error con `fields[]` en vez de `field` | Baja | Desarrollo Backend | 2026-11-21 |

Cada carpeta trae `reporte.md` (título, cuerpo, atributos de Taiga y lista de adjuntos) y `evidencias/`.
Las observaciones que no son incidencia están en `observaciones_para_analisis_M07.md`.

## Antes de publicar
1. Confirmar el consecutivo `INC-M07-37x` con la líder de pruebas (373 a 375 son provisionales; el último visto es el 372 de RF-98).
2. Publicar el cuerpo de cada `reporte.md` como issue en GitHub y en Taiga, con los atributos personalizados de la tabla y los archivos de `evidencias/` como adjuntos.
3. Las evidencias no contienen secretos, tokens ni hashes completos (verificado con búsqueda de los valores usados).
