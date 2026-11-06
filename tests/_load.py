"""Load a skill script as a module by path. The skills are loose scripts, not
a package, so the tests import them the same way a user runs them."""

import importlib.util
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = os.path.join(ROOT, "skills")


def load(rel, name=None):
    path = os.path.join(SKILLS, rel)
    name = name or os.path.splitext(os.path.basename(rel))[0]
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def lexicon():
    with open(os.path.join(SKILLS, "ig-human", "slop.json"), encoding="utf-8") as fh:
        return json.load(fh)
