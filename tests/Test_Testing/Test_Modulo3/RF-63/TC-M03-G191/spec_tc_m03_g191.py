"""Oraculo puro de TC-M03-G191. No toca BD, no importa use cases."""

CASOS = {
    "367a": {
        "descripcion": "Evento SIN tipo_evento se registra con registro_incompleto=true",
        "esperado": {
            "persiste": True,           # CA-13: no debe rechazarse
            "registro_incompleto": True,
            "tipo_evento": None,         # o "DESCONOCIDO" si hay fallback
        },
    },
    "367b": {
        "descripcion": "Evento SIN componente_origen se registra con registro_incompleto=true",
        "esperado": {
            "persiste": True,
            "registro_incompleto": True,
            "componente_origen": None,
        },
    },
    "367c": {
        "descripcion": "Evento SIN timestamp_evento se registra con registro_incompleto=true",
        "esperado": {
            "persiste": True,
            "registro_incompleto": True,
            "nota": "NO verificable si use_case autogenera timestamp. Requiere parametro.",
        },
    },
    "367d": {
        "descripcion": "Evento COMPLETO se registra con registro_incompleto=false",
        "esperado": {
            "persiste": True,
            "registro_incompleto": False,
        },
    },
    "367e": {
        "descripcion": "POST manual por usuario es rechazado (403/405/404)",
        "esperado": {
            "rechazado": True,
            "codigos_aceptables": [403, 405, 404],
        },
    },
}
