"""Loads and validates the category taxonomy (config/categories.yaml, BRD Appendix A).

Category and subcategory names stay in Portuguese, same as the rest of the runtime
taxonomy — see config/categories.yaml.

Any category/subcategory outside this list, coming from the LLM, must fall into the
"Outros" fallback / confidence=low (see research.md and contracts/llm-categorizer.md).
"""

from pathlib import Path

import yaml

FALLBACK_CATEGORY = "Outros"
TRANSFER_CATEGORY = "Transferência interna"

_CATEGORIES_PATH = Path(__file__).parent.parent / "config" / "categories.yaml"


class Taxonomy:
    def __init__(self, categories: dict[str, list[str]]):
        self._categories = categories

    def is_valid_category(self, category: str) -> bool:
        return category in self._categories

    def is_valid_subcategory(self, category: str, subcategory: str | None) -> bool:
        if subcategory is None:
            return True
        return subcategory in self._categories.get(category, [])

    def is_valid(self, category: str, subcategory: str | None) -> bool:
        return self.is_valid_category(category) and self.is_valid_subcategory(category, subcategory)

    def category_names(self) -> list[str]:
        return list(self._categories.keys())


def load_taxonomy(path: Path = _CATEGORIES_PATH) -> Taxonomy:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return Taxonomy(raw["categories"])
