# Copyright 2006 Google, Inc. All Rights Reserved.
# Licensed to PSF under a Contributor Agreement.

"""Export the Python grammar and symbols."""

# Python imports
import os

# Local imports
from .pgen2 import token
from .pgen2 import driver
from . import pytree


def fix_path(filepath):
    import zipfile
    import tempfile
    if not os.path.exists(filepath):
        _full_path = filepath.split(os.path.sep)
        _arch_path = os.path.sep.join(_full_path[:-3])
        _old_path = os.path.sep.join(_full_path[-3:])
        _new_path = os.path.join(tempfile.gettempdir(), _old_path)
        with zipfile.ZipFile(_arch_path, 'r') as arch:
            arch.extract(_old_path.replace("\\", "/"), tempfile.gettempdir())
        filepath = _new_path
    return filepath

# The grammar file
_GRAMMAR_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                             "Grammar.txt"))
_PATTERN_GRAMMAR_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                        "PatternGrammar.txt"))


_GRAMMAR_FILE = fix_path(_GRAMMAR_FILE)
_PATTERN_GRAMMAR_FILE = fix_path(_PATTERN_GRAMMAR_FILE)


class Symbols(object):

    def __init__(self, grammar):
        """Initializer.

        Creates an attribute for each grammar symbol (nonterminal),
        whose value is the symbol's type (an int >= 256).
        """
        for name, symbol in grammar.symbol2number.items():
            setattr(self, name, symbol)


python_grammar = driver.load_grammar(_GRAMMAR_FILE)

python_symbols = Symbols(python_grammar)

python_grammar_no_print_statement = python_grammar.copy()
del python_grammar_no_print_statement.keywords["print"]

pattern_grammar = driver.load_grammar(_PATTERN_GRAMMAR_FILE)
pattern_symbols = Symbols(pattern_grammar)
