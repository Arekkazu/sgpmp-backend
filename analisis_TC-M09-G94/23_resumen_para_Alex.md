# TC-M09-G94 — Resumen para decisión (RF-27 / WCAG 2.1 AA)

**Estado del grupo: RECHAZADO.**  
No se recomienda aprobarlo con la evidencia actual. No se ejecutó Cypress para este resumen.

---

## Qué está confirmado

1. **Contraste del menú lateral (TEST, 179 rev8).** Cuatro textos (nombre de finca, «Módulos», «Mi cuenta», «Productor») tienen ratio **3.64:1** (colores `#7D9A75` sobre `#104325`). Axe aplica **4.5:1** (texto normal, 9–10 px). Eso **no cumple** WCAG 2.1 AA 1.4.3 en esos nodos. No es el mismo cálculo que la marca contra la tarjeta blanca (ahí el ratio local fue 6.54:1).

2. **La API calcula bien la variante y no pisa el color guardado.** Para el verde institucional `#1A6B3C`: en claro cumple AA; en oscuro informa `cumple_aa=false`, ratio **2.69** y `color_ajustado=#249453`. Eso coincide con el código de dominio. El problema de pintado no se explica como un error de esa fórmula.

3. **En TEST, la marca del CSS no usa la variante oscura.** Con productor, `--brand-500` medido fue `#1A6B3C` (el color guardado / la variante clara), no `#249453`. En septiembre (rev4, tema claro y color `#FFFFFF`) el front **sí** aplicó la variante clara `#757575`. El front local del repo **no** es el que está desplegado.

4. **179 nunca cerró en Mocha (rev4–rev9, 0 pases / 1 fallo).** Varias veces el runner se detuvo por el **arnés** (espera de una petición que no tenía por qué repetirse, archivos de evidencia que no se guardaban, restauración con un token ya inválido, y una precondición del spec sobre el GET de identidad del **admin**). Eso no debe reportarse como fallo de contraste.

5. **178 no cubre el grupo.** Solo hay axe 0 en el **dashboard de administrador** (rev2). No cubre productor, modo oscuro ni el sidebar de rev8.

---

## Qué no está cerrado

- Si el HTML debe llevar `data-theme="dark"` cuando el API dice `theme_mode=2`. En rev7 esa espera **pasó**; en rev8 el atributo era `null` al medir (posible carrera). No se inspeccionó el JavaScript desplegado.
- Por qué el GET de identidad del admin pasó de `200` con cuerpo `null` (rev5–rev8) a un **objeto** (rev9). Se registra como diferencia. **No** se pide ampliar RLS ni usar tema global: el acceso restringido del admin se considera decisión de diseño.
- Los nodos exactos de la violación axe de rev4 (el JSON no lista HTML).

---

## Impacto

El flujo RF-27 pide detectar bajo contraste y **aplicar** una variante. El backend detecta e informa. En TEST, el oscuro **no está demostrado** en CSS, y el sidebar **sí muestra** texto bajo 4.5:1. El grupo no puede darse por conforme a WCAG 2.1 AA con esta evidencia.

---

## Decisiones que necesita el equipo

| Quién | Pedido |
|---|---|
| **Frontend (deploy TEST)** | Usar `color_ajustado` del tema **efectivo** (claro/oscuro). Corregir o justificar el contraste de las etiquetas del sidebar. Aclarar cuándo se escribe `data-theme` en `<html>`. |
| **Backend** | No hace falta cambiar el cálculo ni RLS para “hacer pasar” G94. Sí ayuda documentar el GET de identidad del admin (`null` vs objeto). |
| **QA** | No atar 179 al JSON del admin. Medir con productor. Acordar el alcance de 178 (o dejar por escrito que el dashboard admin no cierra el grupo). Una corrida de cierre **después** de cambios de producto, no otra ronda solo de Cypress. |

Informe técnico: `analisis_TC-M09-G94/22_informe_integral_G94.md`.
