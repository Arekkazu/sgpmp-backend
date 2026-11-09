# TC-M06-G85

No se usó SQL local. El reparto de 900.000 no se ejecutó en TEST.

La regla del código trunca a 2 decimales y asigna el residuo al de mayor participación, con empate por el menor id.
Aplicada a 100, 200 y 300 sobre 900.000 da 150.000, 300.000 y 450.000, y la suma cuadra.
Aplicada a 100 entre tres partes iguales da 33.34 al id menor y 33.33 a los otros.
Persistencia intacta tras los rechazos: True.
