# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-79: M06 provisional (recepción)        |
"""M06 — Valoración financiera NIC 41 (provisional).

Por ahora solo recibe la provisión de costos que entrega M05 (RF-79) en
``modulo6.recepciones_provisiones_m05``, con ACK de recepción e idempotencia por
``id_evento_provision``. Cuando M06 tenga su backend completo, consume desde esa
bandeja hacia ``modulo6.registros_costos``.
"""
