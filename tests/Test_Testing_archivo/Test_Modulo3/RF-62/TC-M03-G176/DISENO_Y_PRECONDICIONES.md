# TC-M03-G176: Fuzzing e Inyección (RF-62 / OWASP API8 y API10:2023)

## 1. Alcance y Objetivos
Evaluar la resiliencia, sanitización y robustez del parser de FastAPI/Pydantic en los endpoints de calidad (`/iot/calidad` y `/iot/calidad/reevaluar`) frente a entradas anómalas, inyecciones XSS, desbordamiento de enteros, tipos incompatibles y Content-Types no soportados.

## 2. Herramienta y Enfoque QA
- **Herramienta:** Newman / Postman v2.1.0 con reporte oficial en `resultados/resultado_TC-M03-G176.html` (scanner).
- **CERO DML:** Suite puramente de sondeo y fuzzing por API REST.
- **Aislamiento Sandbox:** Transaccional con headers obligatorios `X-Test-Run-Id`, `X-Sandbox-Secret` y teardown con `DELETE /test-control/runs/{{run_id}}`.

## 3. Batería de Payloads Evaluados (Subcaso TC-M03-335)
1. `GET /iot/calidad?id_sensor=abc` (Cadena en parámetro entero) -> HTTP 422 controlado.
2. `GET /iot/calidad?pagina=-1` (Paginación fuera de rango ge=1) -> HTTP 422 controlado.
3. `GET /iot/calidad?por_pagina=99999` (Página excede le=200) -> HTTP 422 controlado.
4. `GET /iot/calidad?fecha_desde=not-a-date` (Fecha con formato incorrecto) -> HTTP 422 controlado.
5. `GET /iot/calidad?clasificacion=<script>alert(1)</script>` (Inyección XSS) -> Sanitización confirmada: la cadena no se refleja en la respuesta y el backend responde sin error 500.
6. `POST /iot/calidad/reevaluar` con tipos incompatibles (`id_sensor: []`, `fecha_desde: 123`) -> HTTP 422 controlado.
7. `GET /iot/calidad` con Unicode especial, emojis y byte NUL (`%00`) -> Manejo seguro, sin desbordamiento.
8. `GET /iot/calidad?fecha_desde=9999-12-31T23:59:59Z` (Fecha hiper-futura) -> Respuesta segura (200 lista vacía o 422), sin 500.
9. `GET /iot/calidad?pagina=99999999999999999999` (Overflow numérico) -> HTTP 422 controlado.
10. `POST /iot/calidad/reevaluar` con cabecera `Content-Type: text/plain` -> Rechazo controlado (400, 415 o 422), nunca 500.
11. **Comprobación de No-Degradación:** Inmediatamente tras los 10 ataques anómalos, se emite una petición válida `GET /iot/calidad?pagina=1&por_pagina=10` verificando respuesta HTTP 200 exitosa y sin fatiga del servicio.
