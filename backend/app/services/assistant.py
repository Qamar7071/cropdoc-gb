"""AI agriculture assistant: answers farmers' questions in Urdu or English, grounded in CropDoc's knowledge.

Two modes, never a made-up answer:
  * ``ai``: an Anthropic credential is configured (``ANTHROPIC_API_KEY``). Claude answers from the most
    relevant knowledge-base passages (diseases, crops, tips) under strict safety rules: no product or
    active-ingredient names, no doses or spray intervals, honest about what it cannot know.
  * ``knowledge_base``: no credential (fully offline use) or the AI service fails. The best-matching
    verified passages are shown as they are, in the farmer's language.

Retrieval is a small BM25 search (word overlap weighted by rarity) over English, Urdu and common Roman
Urdu words, so it works offline and needs no extra model.
"""

from __future__ import annotations

import logging
import math
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from app.services.crops import CropLibrary
from app.services.diseases import DiseaseLibrary

log = logging.getLogger("cropdoc.assistant")

DEFAULT_MODEL = "claude-opus-5-5"
MAX_HISTORY = 12
MAX_CHARS = 2000

# Roman Urdu → English words used in the knowledge base (farmers often type Urdu in Latin letters)
ROMAN_URDU = {
    "tamatar": "tomato",
    "timatar": "tomato",
    "aloo": "potato",
    "aaloo": "potato",
    "alu": "potato",
    "gandum": "wheat",
    "gehun": "wheat",
    "chawal": "rice",
    "chawel": "rice",
    "dhan": "rice",
    "munji": "rice",
    "kapas": "cotton",
    "kapaas": "cotton",
    "narma": "cotton",
    "ganna": "sugarcane",
    "gana": "sugarcane",
    "makai": "maize",
    "makki": "maize",
    "makkai": "maize",
    "aam": "mango",
    "kinno": "citrus",
    "kino": "citrus",
    "kinnow": "citrus",
    "malta": "citrus",
    "seb": "apple",
    "angoor": "grape",
    "aaru": "peach",
    "aroo": "peach",
    "shimla": "pepper",
    "mirch": "pepper",
    "kaddu": "squash",
    "patta": "leaf",
    "pattay": "leaves",
    "patte": "leaves",
    "pattey": "leaves",
    "peela": "yellow",
    "peelay": "yellow",
    "peele": "yellow",
    "peeli": "yellow",
    "zard": "yellow",
    "dhabba": "spots",
    "dhabbay": "spots",
    "dhabbe": "spots",
    "daag": "spots",
    "keera": "pest",
    "keeray": "pests",
    "keere": "pests",
    "bimari": "disease",
    "beemari": "disease",
    "phaphoond": "fungus",
    "phaphundi": "fungus",
    "makhi": "whitefly",
    "safaid": "white",
    "sufaid": "white",
    "kaali": "black",
    "kala": "black",
    "bhoora": "brown",
    "bhure": "brown",
    "murjhana": "wilting",
    "sookh": "dry",
    "sukh": "dry",
    "khaad": "fertilizer",
    "khad": "fertilizer",
    "paani": "water",
    "pani": "water",
    "fasal": "crop",
    "kangi": "rust",
    "marorr": "curl",
    "maror": "curl",
}
# Common Roman-Urdu function words (Urdu written in Latin letters), used only to pick the answer language.
ROMAN_URDU_WORDS = {
    "ke", "ki", "ka", "ko", "se", "mein", "mai", "hai", "hain", "hy", "kya", "kyun", "kyon", "kiun", "kaise",
    "kaisay", "kese", "kesay", "mera", "meri", "mere", "apni", "apna", "apne", "nahi", "nahin", "raha", "rahi",
    "rahe", "rahay", "ho", "hoti", "hota", "hote", "kar", "karun", "karoon", "karein", "karen", "karna", "bachaon",
    "bachaun", "bachao", "liye", "wala", "wali", "walay", "bhi", "aur", "kab", "konsi", "kaunsi", "kaun",
}  # fmt: skip
STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "of",
    "to",
    "in",
    "on",
    "for",
    "is",
    "are",
    "my",
    "me",
    "i",
    "it",
    "this",
    "that",
    "what",
    "how",
    "why",
    "do",
    "does",
    "can",
    "with",
    "be",
    "should",
    "which",
    "best",
    "way",
    "کی",
    "کے",
    "کا",
    "میں",
    "ہے",
    "ہیں",
    "اور",
    "سے",
    "کو",
    "پر",
    "یہ",
    "وہ",
    "کیا",
    "کیسے",
    "کیوں",
    "میری",
    "میرے",
    "میرا",
    "ہو",
    "رہے",
    "رہی",
    "رہا",
    "بھی",
    "تو",
    "نہیں",
    "ایک",
    "ki",
    "ke",
    "ka",
    "mein",
    "main",
    "hai",
    "hain",
    "aur",
    "se",
    "ko",
    "par",
    "kya",
    "kaise",
    "kyun",
    "kyon",
    "meri",
    "mere",
    "mera",
    "ho",
    "rahe",
    "rahi",
    "raha",
    "bhi",
    "nahi",
}
URDU_SCRIPT = re.compile(r"[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]")
LETTER = re.compile(r"[^\W\d_]", re.UNICODE)

SYSTEM_PROMPT = """You are CropDoc Assistant, a careful agricultural advisor for small farmers in Pakistan, including \
Gilgit-Baltistan. Many users have little formal education and use a phone in the field.

Language: reply in the same language and script as the farmer's latest message (Urdu script, Roman Urdu, or \
English). Use simple, everyday words and short sentences. Explain any technical term in plain words.

Grounding: the user message contains KNOWLEDGE passages from CropDoc's knowledge base, drafted from cited \
agricultural sources and still awaiting expert review. Base your answer on them. You may add widely accepted \
general good practice (field hygiene, crop rotation, healthy seed, soil testing, scouting). Do not state \
specific facts that the passages do not support, such as numbers, dates, variety names or regional statistics. \
If the passages do not cover the question, say so plainly and suggest the local agriculture extension officer.

Safety rules (always):
- Never name a pesticide, fungicide or other product, and never name an active ingredient.
- Never give doses, mixing ratios, spray intervals or application methods. For chemical control, say that the \
local agriculture extension officer can say which product is approved and that the label must be followed.
- For fertilizer questions, recommend a soil test and the local recommendation for that crop; give no rates.
- Encourage protective clothing and safe storage whenever chemicals come up.

Honesty: you cannot see the plant. Describe what the signs could mean (one or two possibilities from the \
knowledge), say how to tell them apart, and suggest the Scan feature for a photo check. If important \
information is missing (crop, which leaves, colour and shape of spots, weather, how fast it spreads), ask one \
short follow-up question.

Scope: farming, crops, plant health, soil and water only. Politely decline anything else.

Format: at most about 150 words. Use short bullet points for steps. Do not write URLs (the app shows the sources)."""


def detect_language(text: str) -> str:
    """'ur' when most letters are Urdu (Arabic) script, else 'en' (Roman Urdu counts as Latin script)."""
    letters = LETTER.findall(text)
    if not letters:
        return "en"
    urdu = sum(1 for ch in letters if URDU_SCRIPT.match(ch))
    return "ur" if urdu / len(letters) >= 0.3 else "en"


def answer_language(text: str) -> str:
    """Language for the reply: Urdu for Urdu script and for Roman Urdu, otherwise English.

    Roman Urdu writers usually read Urdu script better than English, so knowledge-base answers to
    "tamatar ke pattay peelay hain" come in Urdu. (In AI mode Claude mirrors the exact script.)"""
    if detect_language(text) == "ur":
        return "ur"
    words = re.findall(r"[a-z]+", text.lower())
    hits = sum(1 for w in words if w in ROMAN_URDU_WORDS or w in ROMAN_URDU)
    return "ur" if hits >= 2 and hits / max(1, len(words)) >= 0.25 else "en"


def tokenize(text: str) -> list[str]:
    tokens = []
    for raw in re.findall(r"\w+", text.lower(), re.UNICODE):
        if len(raw) < 2 or raw.isdigit() or raw in STOPWORDS:
            continue
        tokens.append(ROMAN_URDU.get(raw, raw))
        if raw.endswith("s") and len(raw) > 3:  # crude English plural folding: leaves → leave, spots → spot
            tokens.append(raw[:-1])
    return tokens


@dataclass
class Doc:
    kind: str  # disease | crop | tip
    id: str
    title: dict[str, str]
    text: dict[str, str]  # passage shown to the model / in offline answers
    sources: list[str]
    tokens: Counter = field(default_factory=Counter)
    short: dict[str, str] = field(default_factory=dict)  # the farmer-facing summary used in offline answers
    names: list[frozenset[str]] = field(default_factory=list)  # name tokens per language (diseases)


def _join(*parts: Any) -> str:
    out = []
    for part in parts:
        if isinstance(part, list | tuple):
            out.extend(str(p) for p in part if p)
        elif part:
            out.append(str(part))
    return " ".join(out)


LABELS = {
    "en": {
        "signs": "Signs",
        "causes": "Causes",
        "risk": "Risk",
        "now": "Do now",
        "prevention": "Prevention",
        "treatment": "Treatment type",
        "expert": "Call an expert when",
        "diseases": "Common diseases",
        "seasonal": "Seasonal care",
        "levels": {"high": "high", "medium": "medium", "low": "low", "none": "none"},
        "sep": "; ",
        "comma": ", ",
    },
    "ur": {
        "signs": "علامات",
        "causes": "وجوہات",
        "risk": "خطرہ",
        "now": "ابھی کریں",
        "prevention": "بچاؤ",
        "treatment": "علاج کی قسم",
        "expert": "ماہر کو کب بلائیں",
        "diseases": "عام بیماریاں",
        "seasonal": "موسمی دیکھ بھال",
        "levels": {"high": "زیادہ", "medium": "درمیانہ", "low": "کم", "none": "کوئی نہیں"},
        "sep": "؛ ",
        "comma": "، ",
    },
}


def _unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(i for i in items if i))


def build_corpus(diseases: DiseaseLibrary, crops: CropLibrary) -> list[Doc]:
    """Passages for retrieval. ``text`` (everything) goes to the AI model; ``short`` is the farmer-facing
    summary shown in knowledge-base mode, short enough to read on a phone. Labels follow the language."""
    docs: list[Doc] = []
    for class_id in diseases.entries:
        r = diseases.report(class_id)
        title = {lang: f"{r['name'][lang]} ({r['crop'][lang]})".strip() for lang in ("en", "ur")}
        text, short = {}, {}
        for lang in ("en", "ur"):
            labels = LABELS[lang]
            sep = labels["sep"]

            def line(label: str, items: list[str], limit: int | None = None) -> str:
                items = items[:limit] if limit else items
                return f"{labels[label]}: " + sep.join(items) if items else ""  # noqa: B023

            symptoms = r["symptoms_early"][lang] + r["symptoms_advanced"][lang]
            level = labels["levels"].get(r["risk_level"], r["risk_level"])
            risk = (
                f"{labels['risk']}: {level} - {r['risk_reason'][lang]}"
                if r["risk_level"] not in ("", "none")
                else ""
            )
            head = f"{title[lang]}: {r['description'][lang]}"
            text[lang] = "\n".join(
                x
                for x in (
                    head,
                    line("signs", symptoms),
                    line("causes", r["causes"][lang]),
                    risk,
                    line("now", r["immediate_actions"][lang]),
                    line("prevention", r["prevention"][lang]),
                    line("treatment", r["treatment_categories"][lang]),
                    line("expert", r["call_expert_when"][lang]),
                )
                if x
            )
            short[lang] = "\n".join(
                x
                for x in (
                    head,
                    line("signs", symptoms, 2),
                    risk,
                    line("now", r["immediate_actions"][lang], 3),
                    line("expert", r["call_expert_when"][lang], 2),
                )
                if x
            )
        names = [frozenset(tokenize(r["name"][lang])) for lang in ("en", "ur")]
        docs.append(
            Doc("disease", class_id, title, text, r["sources"], short=short, names=[n for n in names if n])
        )
    for crop in crops.crops:
        title = crop["name"]
        text, short = {}, {}
        for lang in ("en", "ur"):
            labels = LABELS[lang]
            sep = labels["sep"]
            crop_diseases = crop.get("diseases", [])
            head = f"{crop['name'][lang]} ({crop['season'][lang]}): {crop['summary'][lang]}"
            care = crop["seasonal_care"][lang]
            text[lang] = "\n".join(
                [
                    head,
                    *(
                        f"{d['name'][lang]}: {d['symptoms'][lang]} {labels['prevention']}: "
                        + sep.join(d["prevention"][lang])
                        for d in crop_diseases
                    ),
                    f"{labels['seasonal']}: " + sep.join(care),
                ]
            )
            names = labels["comma"].join(d["name"][lang] for d in crop_diseases)
            key_prevention = _unique(
                [p for d in crop_diseases[:1] for p in d["prevention"][lang][:2]]
                + [p for d in crop_diseases[1:3] for p in d["prevention"][lang][:1]]
            )
            short[lang] = "\n".join(
                x
                for x in (
                    head,
                    f"{labels['diseases']}: {names}" if names else "",
                    f"{labels['prevention']}: " + sep.join(key_prevention) if key_prevention else "",
                    f"{labels['seasonal']}: " + sep.join(care[:2]) if care else "",
                )
                if x
            )
        docs.append(Doc("crop", crop["id"], title, text, crop.get("sources", []), short=short))
    keywords: dict[str, list[str]] = {}
    for tip in crops.tips:
        text = {lang: f"{tip['title'][lang]}: {tip['body'][lang]}" for lang in ("en", "ur")}
        docs.append(Doc("tip", tip["id"], tip["title"], text, crops.tips_meta.get("sources", [])))
        words = tip.get("keywords", {})
        keywords[tip["id"]] = [*words.get("en", []), *words.get("ur", [])]  # search aids, never shown
    for doc in docs:
        doc.tokens = Counter(
            tokenize(
                _join(
                    doc.title["en"],
                    doc.title["ur"],
                    doc.id.replace("_", " "),
                    doc.text["en"],
                    doc.text["ur"],
                    keywords.get(doc.id, []) if doc.kind == "tip" else [],
                )
            )
        )
        if doc.kind == "crop":
            doc.names = [n for n in (frozenset(tokenize(doc.title[lang])) for lang in ("en", "ur")) if n]
    return docs


CROP_WORDS = {
    "tomato",
    "potato",
    "wheat",
    "rice",
    "cotton",
    "sugarcane",
    "maize",
    "corn",
    "mango",
    "citrus",
    "orange",
    "apple",
    "grape",
    "peach",
    "pepper",
    "squash",
    "strawberry",
    "cherry",
    "blueberry",
    "raspberry",
    "soybean",
    "ٹماٹر",
    "آلو",
    "گندم",
    "چاول",
    "کپاس",
    "گنا",
    "گنے",
    "مکئی",
    "آم",
    "کینو",
    "مالٹا",
    "سیب",
    "انگور",
    "آڑو",
    "مرچ",
    "کدو",
}


def mentions_crop(text: str) -> bool:
    return bool(CROP_WORDS & set(tokenize(text)))


# Words that describe what the farmer sees (after Roman-Urdu words are mapped to English).
SYMPTOM_WORDS = {
    "yellow", "spots", "spot", "curl", "curling", "curled", "wilting", "wilt", "wilted", "dry", "drying", "black",
    "brown", "white", "holes", "rot", "rotting", "mold", "mould", "powder", "powdery", "lesions", "streaks",
    "stripes", "rust", "mosaic", "blight", "pustules", "dying", "fungus", "pest", "pests", "insects", "worms",
    "whitefly", "پیلے", "پیلا", "پیلی", "زرد", "دھبے", "دھبہ", "دھبوں", "مرجھا", "مرجھائے", "سوکھ", "سوکھے", "کالے",
    "کالا", "بھورے", "سفید", "سوراخ", "سڑ", "سڑنا", "پھپھوند", "کنگی", "مڑ", "مڑے", "کیڑے", "سنڈی",
}  # fmt: skip


class Retriever:
    """BM25 over the knowledge-base documents."""

    def __init__(self, docs: list[Doc], k1: float = 1.2, b: float = 0.75):
        self.docs, self.k1, self.b = docs, k1, b
        self.avg_len = sum(sum(d.tokens.values()) for d in docs) / max(1, len(docs))
        df = Counter(t for d in docs for t in d.tokens)
        n = len(docs)
        self.idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}

    def search(self, query: str, k: int = 4) -> list[tuple[Doc, float]]:
        """BM25, then three plain rules: a question that names a disease ranks that disease first; a general
        question about a crop ("how do I protect tomatoes?") ranks the crop page first; a general farming
        question with no crop and no signs ("how can I improve my yield?") ranks the farming tips first."""
        terms = set(tokenize(query))
        names_disease = any(d.kind == "disease" and any(n <= terms for n in d.names) for d in self.docs)
        describes_signs = bool(terms & SYMPTOM_WORDS)
        general = not names_disease and not describes_signs
        no_crop = not (terms & CROP_WORDS)
        scored = []
        for doc in self.docs:
            length = sum(doc.tokens.values())
            score = 0.0
            for t in terms:
                tf = doc.tokens.get(t, 0)
                if tf:
                    score += (
                        self.idf[t]
                        * tf
                        * (self.k1 + 1)
                        / (tf + self.k1 * (1 - self.b + self.b * length / self.avg_len))
                    )
            named = any(name <= terms for name in doc.names)
            boosted = (
                (doc.kind == "disease" and named)  # "late blight" → that disease above general pages
                or (doc.kind == "crop" and general and named)
                or (doc.kind == "tip" and general and no_crop)
            )
            if boosted:
                score *= 2.0
            if doc.kind == "disease" and doc.id.endswith("healthy"):
                score *= (
                    0.3  # "healthy" entries list the signs they do NOT have; rank them below real matches
                )
            if score > 0:
                scored.append((doc, score))
        return sorted(scored, key=lambda pair: -pair[1])[:k]


@dataclass
class AssistantConfig:
    model: str = DEFAULT_MODEL
    effort: str = "medium"
    timeout_seconds: float = 30.0

    @property
    def ai_available(self) -> bool:
        return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


class Assistant:
    def __init__(
        self, diseases: DiseaseLibrary, crops: CropLibrary, config: AssistantConfig, client: Any = None
    ):
        self.diseases, self.config = diseases, config
        self.docs = build_corpus(diseases, crops)
        self.retriever = Retriever(self.docs)
        self._client = client  # injected in tests; created lazily otherwise

    # ------------------------------------------------------------------ retrieval
    def retrieve(self, question: str, history_text: str = "", class_id: str | None = None) -> list[Doc]:
        hits = self.retriever.search(f"{question} {question} {history_text}", k=4)
        # keep only real matches: a page scoring under a quarter of the best one is noise ("related: sugarcane")
        found = [doc for doc, score in hits if score >= 0.25 * hits[0][1]] if hits else []
        if class_id:
            pinned = next((d for d in self.docs if d.kind == "disease" and d.id == class_id), None)
            if pinned:
                found = [pinned, *[d for d in found if d is not pinned]][:4]
        return found

    # ------------------------------------------------------------------ answering
    def answer(self, messages: list[dict[str, str]], class_id: str | None = None) -> dict[str, Any]:
        question = messages[-1]["content"]
        language = answer_language(question)
        history_text = " ".join(m["content"] for m in messages[-5:-1] if m["role"] == "user")
        docs = self.retrieve(question, history_text, class_id)
        related = [{"kind": d.kind, "id": d.id, "title": d.title} for d in docs]
        sources = list(dict.fromkeys(s for d in docs for s in d.sources))[:6]
        if self.config.ai_available:
            try:
                reply = self._ask_claude(messages, docs, language)
                return {
                    "reply": reply,
                    "language": language,
                    "mode": "ai",
                    "model": self.config.model,
                    "related": related,
                    "sources": sources,
                }
            except Exception as exc:  # noqa: BLE001 - any AI failure falls back to verified knowledge
                log.warning("assistant AI call failed, using knowledge base: %s", type(exc).__name__)
                notice = "ai_unavailable"
        else:
            notice = "ai_not_configured"
        return {
            "reply": self._knowledge_reply(docs, language, question),
            "language": language,
            "mode": "knowledge_base",
            "notice": notice,
            "related": related,
            "sources": sources,
        }

    def _client_or_create(self):
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic(timeout=self.config.timeout_seconds, max_retries=1)
        return self._client

    def _ask_claude(self, messages: list[dict[str, str]], docs: list[Doc], language: str) -> str:
        knowledge = (
            "\n\n".join(
                f'<passage kind="{d.kind}" id="{d.id}">\n{d.text["en"]}\n{d.text["ur"] if language == "ur" else ""}\n</passage>'
                for d in docs
            )
            or "(no matching passage found)"
        )
        convo = [{"role": m["role"], "content": m["content"]} for m in messages[:-1]]
        convo.append(
            {
                "role": "user",
                "content": f"KNOWLEDGE:\n{knowledge}\n\nFARMER'S MESSAGE:\n{messages[-1]['content']}",
            }
        )
        response = self._client_or_create().beta.messages.create(
            model=self.config.model,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",  # if the model declines for policy reasons, the API retries on its default fallback
            output_config={"effort": self.config.effort},
            system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
            messages=convo,
        )
        if response.stop_reason == "refusal":
            return {
                "ur": "معاف کیجیے، میں اس سوال کا جواب نہیں دے سکتا۔ براہ کرم کھیتی باڑی سے متعلق سوال پوچھیں۔",
                "en": "Sorry, I can't help with that. Please ask a question about your crops.",
            }[language]
        text = "\n".join(
            block.text for block in response.content if getattr(block, "type", "") == "text"
        ).strip()
        if not text:
            raise RuntimeError("empty answer")
        return text

    def _knowledge_reply(self, docs: list[Doc], language: str, question: str = "") -> str:
        if not docs:
            return {
                "ur": "مجھے CropDoc کی معلومات میں اس کا جواب نہیں ملا۔ براہ کرم فصل کا نام اور علامات لکھیں، اسکین استعمال کریں، یا محکمہ زراعت کے زرعی افسر سے رابطہ کریں۔",
                "en": "I could not find this in CropDoc's knowledge base. Please write the crop name and the signs you see, use the Scan feature, or contact your agriculture extension officer.",
            }[language]
        top = docs[0]
        if top.kind == "tip":  # a general farming question: the best few tips, one line each
            lines = [d.text[language] for d in docs if d.kind == "tip"][:3]
            rest = [d for d in docs if d.kind != "tip"]
        else:
            lines = (top.short or top.text)[language].split("\n")
            rest = docs[1:]
        intro = {"ur": "CropDoc کی تصدیق شدہ معلومات سے:", "en": "From CropDoc's knowledge base:"}[language]
        if top.kind == "disease" and question and not mentions_crop(question):
            intro = {
                "ur": "یہ کون سی فصل ہے؟ فصل کا نام اور علامات بتائیں تو جواب زیادہ درست ہوگا۔ ایک ممکنہ مماثلت:",
                "en": "Which crop is it? Tell me the crop and the signs for a more precise answer. One possible match:",
            }[language]
        more = ""
        if rest:
            names = LABELS[language]["comma"].join(d.title[language] for d in rest[:2])
            more = {"ur": f"\n\nمتعلقہ: {names}", "en": f"\n\nRelated: {names}"}[language]
        return f"{intro}\n" + "\n".join(f"• {line}" for line in lines) + more
