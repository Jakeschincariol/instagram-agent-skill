#!/usr/bin/env python3
"""
The Spanish half of the classifier, tested the same way as the English half.

hooks.json has no Spanish `example` field, so the cases live here: one
Rioplatense hook per formula, written to fall in that formula and not in its
neighbour. They are the Spanish counterpart of the `example` lines that
tests/test_hook_formulas.py checks.

    python3 tests/test_hook_formulas_es.py
    python3 tests/test_hook_formulas_es.py --verbose

Exits non-zero if any case lands on the wrong formula.
"""

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from test_hook_formulas import HOOKS, classify, compile_all, load  # noqa: E402

# (formula id, hook). Formulas 12 and 22 are absent on purpose: the objection
# and the inverted saying both depend on a set phrase the audience already has
# as a reflex, and that phrase is local. Write those cases for your own market
# rather than inheriting a guess.
CASES = [
    (1,  "Me costó 40.000 pesos aprender esto."),
    (2,  "Pará de comprarle el bolsón más barato."),
    (3,  "Nadie te dice que el baño semanal le arruina la piel."),
    (4,  "En vez de pagar peluquería, comprá el cepillo."),
    (5,  "Antes me tardaba dos horas. Ahora tarda veinte minutos."),
    (6,  "Acá están los números de octubre."),
    (7,  "El error más común con el alimento de cachorro."),
    (8,  "Hace 12 años que trabajo con esto."),
    (9,  "Robate la lista de precios que uso en el local."),
    (10, "Si tu perro come rápido, mirá esto."),
    (11, "5 juguetes que sobreviven a un labrador."),
    (13, "Antes tenía el pelo apelmazado, después de un cepillado quedó así."),
    (14, "Atención los que tienen cachorro."),
    (15, "Mis primeros 20 reels no los vio nadie."),
    (16, "¿Cada cuánto hay que bañar al perro?"),
    (17, "Bolsón de 15 kilos versus dos de 7."),
    (18, "Miren esta manta refrigerante."),
    (19, "Antes de que cambie el precio, pasá."),
    (20, "Tu perro no necesita 4 baños por mes."),
    (21, "...y ahí fue cuando entendí el problema."),
    (23, "7 de cada 10 perros comen de más."),
    (24, "Llegaron las camitas nuevas."),
    (25, "Vino una clienta que me dijo algo que no me olvido más."),
    (26, "La forma más rápida de limpiar un comedero."),
]

# Lines that are not hooks at all: a pet name, a greeting, a call to action.
# None of them should pick up a formula. Without this half, widening a pattern
# to pass the cases above can quietly start labelling everything.
NOT_HOOKS = [
    "¡Willy, un bombón que enamora!",
    "Hola cómo están, para los que me preguntaron",
    "Solicitá tu turno de vacunación",
    "¡Que tu mascota pase el calor sin sufrir!",
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--hooks", default=HOOKS)
    args = ap.parse_args()

    _, by_id, order = load(args.hooks)
    formulas = compile_all(by_id, order)

    failures = []
    for want, hook in CASES:
        got_id, got_name = classify(hook, formulas)
        ok = got_id == want
        if not ok:
            failures.append((want, hook, got_name))
        if args.verbose or not ok:
            print("  %s #%-2s -> %-28s %s" % ("ok  " if ok else "FAIL", want, got_name, hook))

    false_hits = []
    for hook in NOT_HOOKS:
        got_id, got_name = classify(hook, formulas)
        if got_id is not None:
            false_hits.append((hook, got_name))
            print("  FALSE POSITIVE  %-28s %s" % (got_name, hook))

    print()
    print("%d of %d Spanish hooks classify as their own formula" % (len(CASES) - len(failures), len(CASES)))
    print("%d of %d non-hooks correctly left unclassified" % (len(NOT_HOOKS) - len(false_hits), len(NOT_HOOKS)))
    return 1 if (failures or false_hits) else 0


if __name__ == "__main__":
    sys.exit(main())
