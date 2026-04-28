from pathlib import Path
from .card import ExpertCard

def load_card(path: str | Path) -> ExpertCard:
    md = Path(path).read_text()
    return ExpertCard.from_markdown(md)

def save_card(card: ExpertCard, path: str | Path) -> None:
    Path(path).write_text(card.to_markdown())
