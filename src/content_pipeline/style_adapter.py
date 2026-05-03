"""StyleAdapter — parses generated text to extract style markers and updates ExpertCard.style_profile."""
import json
import logging
import re
from typing import Any

from ..expert_card.card import ExpertCard, StyleProfile

logger = logging.getLogger("content-producer")


class StyleAdapter:
    """Extract style markers from text and update the expert's style profile."""

    def update_profile(self, card: ExpertCard, text: str, scores: dict) -> ExpertCard:
        style = card.style

        # Vocabulary: top repeated meaningful words (>4 chars, excluding common Russian stop words)
        stop_words = {
            "который", "которая", "которые", "чтобы", "также", "своей", "своего", "своим",
            "время", "людей", "может", "нужно", "этого", "этом", "очень", "только", "здесь",
            "такой", "такая", "каждый", "каждая", "другой", "другая", "можно", "будет",
            "будут", "ваш", "ваша", "ваше", "ваши", "мой", "моя", "мое", "мои", "тебе",
            "тебя", "себя", "сейчас", "потом", "когда", "потому", "поэтому", "всегда",
            "никогда", "всего", "всем", "всех", "этот", "эта", "это", "эти", "тот", "та",
            "те", "тому", "тем", "того", "теми", "для", "этим", "нам", "вас", "вам", "них",
            "им", "ему", "нее", "ним", "чем", "чему", "что", "как", "где", "кто", "зачем",
            "почему", "либо", "ибо", "если", "или", "но", "а", "и", "в", "на", "с", "к",
            "о", "у", "по", "за", "до", "из", "от", "об", "при", "про", "через", "без",
            "над", "под", "перед", "между", "около", "вместо", "после", "кроме", "ради",
            "благодаря", "вопреки", "согласно", "насчет", "ввиду", "вследствие",
        }
        words = re.findall(r"[а-яА-Яa-zA-ZёЁ]{5,}", text.lower())
        freq: dict[str, int] = {}
        for w in words:
            if w in stop_words:
                continue
            freq[w] = freq.get(w, 0) + 1
        top = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:10]
        new_vocab = [w for w, _ in top]
        # Merge with existing vocab
        existing = set(style.vocabulary)
        merged = list(existing | set(new_vocab))[:30]
        style.vocabulary = merged

        # Sentence length
        sentences = [s.strip() for s in re.split(r"[.!?\n]", text) if s.strip()]
        avg_len = sum(len(s.split()) for s in sentences) / max(len(sentences), 1)
        if avg_len <= 8:
            style.sentence_length = "short"
        elif avg_len <= 14:
            style.sentence_length = "medium"
        else:
            style.sentence_length = "long"
        if 6 <= avg_len <= 18 and len(sentences) > 1:
            # check variance
            lens = [len(s.split()) for s in sentences]
            var = sum((l - avg_len) ** 2 for l in lens) / max(len(lens), 1)
            if var > 20:
                style.sentence_length = "mixed"

        # Emoji usage
        emojis = re.findall(r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\u2600-\u26FF\u2700-\u27BF]", text)
        emoji_count = len(emojis)
        words_count = len(words)
        if words_count == 0:
            words_count = 1
        ratio = emoji_count / words_count
        if ratio == 0:
            style.emoji_usage = "none"
        elif ratio <= 0.02:
            style.emoji_usage = "minimal"
        elif ratio <= 0.05:
            style.emoji_usage = "moderate"
        else:
            style.emoji_usage = "heavy"

        # Humor level heuristic (sentiment / exclamation / caps / playful punctuation)
        humor_score = 0
        humor_markers = ["😂", "🤣", "😅", "😆", "шутка", "смешно", "юмор", "ирония", "сарказм", "забавно", "прикол"]
        for marker in humor_markers:
            if marker in text.lower():
                humor_score += 1
        humor_score += text.count("!") // 2
        humor_score = min(humor_score, 10)
        # Weight existing humor 70% and new sample 30%
        style.humor_level = int(round(style.humor_level * 0.7 + humor_score * 0.3))
        style.humor_level = max(0, min(10, style.humor_level))

        # Story structure heuristic
        if re.search(r"(?:вопрос|почему|зачем|как думаете|что если|а вы)", text.lower()):
            style.story_structure = "question-answer"
        elif re.search(r"(?:проблема|решение|ошибка|исправить|как это сделать|пошагово|план)", text.lower()):
            style.story_structure = "problem-solution"
        else:
            style.story_structure = "hook-story-lesson"

        # CTA style heuristic
        cta_phrases_direct = [
            "купи", "запишись", "переходи", "закажи", "получи", "подпишись", "жми ссылку",
            "buy now", "click here", "order today", "get it now", "subscribe now",
            "sign up", "join now", "download now", "shop now", "learn more", "get started",
        ]
        cta_phrases_soft = [
            "присоединяйся", "узнай больше", "давайте разберем", "поделись", "напиши мне", "ок",
            "join us", "find out more", "let's explore", "share your thoughts",
            "reach out", "contact me", "get in touch", "let's discuss", "discover more",
        ]
        text_lower = text.lower()
        direct = sum(1 for p in cta_phrases_direct if p in text_lower)
        soft = sum(1 for p in cta_phrases_soft if p in text_lower)
        if direct > soft:
            style.call_to_action_style = "direct"
        elif soft > direct:
            style.call_to_action_style = "soft"
        else:
            style.call_to_action_style = "implied"

        # Update count
        style.update_count += 1

        logger.info("Style profile updated for expert '%s' (update #%s)", card.name, style.update_count)
        return card

    async def write_to_db(self, card: ExpertCard, db_client: Any) -> None:
        """Serialize style profile to DB via db_client."""
        style_data = {
            "style_vocabulary": json.dumps(card.style.vocabulary, ensure_ascii=False),
            "style_sentence_length": card.style.sentence_length,
            "style_humor_level": card.style.humor_level,
            "style_emoji_usage": card.style.emoji_usage,
            "style_story_structure": card.style.story_structure,
            "style_call_to_action_style": card.style.call_to_action_style,
            "style_update_count": card.style.update_count,
        }
        try:
            # NOTE: requires expert_id; caller must pass correct id.
            await db_client.expert_update(getattr(card, "id", card.name), style_data)  # type: ignore[attr-defined]
            logger.info("Style profile written to DB for expert '%s'", card.name)
        except Exception:
            logger.warning("Failed to write style profile to DB for '%s'", card.name, exc_info=True)
