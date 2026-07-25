import ast
import inspect
import textwrap

from chunking.splitters import ChunkingFactory
from retrieval.strategies import RetrieverFactory


def _extract_strategy_literals(factory: type, method_name: str) -> list[str]:
    method = getattr(factory, method_name)
    source = textwrap.dedent(inspect.getsource(method))
    tree = ast.parse(source)
    strategies: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        if not isinstance(node.left, ast.Name) or node.left.id != "strategy":
            continue
        if len(node.ops) != 1 or not isinstance(node.ops[0], ast.Eq):
            continue
        if len(node.comparators) != 1:
            continue
        comparator = node.comparators[0]
        if isinstance(comparator, ast.Constant) and isinstance(comparator.value, str):
            if comparator.value not in strategies:
                strategies.append(comparator.value)

    return strategies


def get_chunking_strategies() -> list[str]:
    return _extract_strategy_literals(ChunkingFactory, "get_chunks")


def get_retrieval_strategies() -> list[str]:
    return _extract_strategy_literals(RetrieverFactory, "get_retriever")
