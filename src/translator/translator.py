"""多语言翻译器"""

import os
from typing import List, Dict, Optional
from enum import Enum

from src.models import LanguageCode, ProductData, TranslatedContent


# 家具行业术语表
FURNITURE_GLOSSARY: Dict[str, Dict[str, str]] = {
    "solid wood": {
        LanguageCode.DE: "Massivholz",
        LanguageCode.IT: "legno massello",
        LanguageCode.FR: "bois massif",
        LanguageCode.ES: "macerina sólida",
        LanguageCode.JP: "無垢材",
    },
    "oak": {
        LanguageCode.DE: "Eiche",
        LanguageCode.IT: "quercia",
        LanguageCode.FR: "chêne",
        LanguageCode.ES: "roble",
        LanguageCode.JP: "オーク",
    },
    "assembly": {
        LanguageCode.DE: "Montage",
        LanguageCode.IT: "assemblaggio",
        LanguageCode.FR: "assemblage",
        LanguageCode.ES: "ensamblaje",
        LanguageCode.JP: "組立",
    },
    "dining table": {
        LanguageCode.DE: "Esstisch",
        LanguageCode.IT: "tavolo da pranzo",
        LanguageCode.FR: "table à manger",
        LanguageCode.ES: "mesa de comedor",
        LanguageCode.JP: "ダイニングテーブル",
    },
    "sofa": {
        LanguageCode.DE: "Sofa",
        LanguageCode.IT: "divano",
        LanguageCode.FR: "canapé",
        LanguageCode.ES: "sofá",
        LanguageCode.JP: "ソファ",
    },
    "bookshelf": {
        LanguageCode.DE: "Bücherregal",
        LanguageCode.IT: "scaffale",
        LanguageCode.FR: "étagère",
        LanguageCode.ES: "estantería",
        LanguageCode.JP: "本棚",
    },
}

# 日语敬语后缀
JP_POLITE_SUFFIX = "です"
JP_POLITE_VERB_SUFFIX = "ます"


class TranslationProvider(str, Enum):
    DEEPL = "deepl"
    OPENAI = "openai"
    MOCK = "mock"


class Translator:
    """多语言翻译器"""

    def __init__(self, provider: TranslationProvider = TranslationProvider.MOCK):
        self.provider = provider
        self._init_providers()

    def _init_providers(self):
        """初始化翻译提供者"""
        if self.provider == TranslationProvider.DEEPL:
            api_key = os.environ.get("DEEPL_API_KEY")
            if api_key:
                import deepl
                self.translator = deepl.Translator(api_key)
            else:
                print("警告: 未设置 DEEPL_API_KEY，使用 Mock 翻译")
                self.provider = TranslationProvider.MOCK

        elif self.provider == TranslationProvider.OPENAI:
            api_key = os.environ.get("OPENAI_API_KEY")
            if api_key:
                from openai import OpenAI
                self.client = OpenAI(api_key=api_key)
            else:
                print("警告: 未设置 OPENAI_API_KEY，使用 Mock 翻译")
                self.provider = TranslationProvider.MOCK

    async def translate_product(
        self, product: ProductData, target_languages: List[LanguageCode]
    ) -> Dict[LanguageCode, TranslatedContent]:
        """翻译产品数据到多种语言"""
        results = {}

        for lang in target_languages:
            if lang == LanguageCode.EN:
                # 英语作为源语言，直接使用原文
                results[lang] = TranslatedContent(
                    language=lang,
                    title=product.title,
                    bullet_points=product.bullet_points,
                )
            else:
                translated = await self._translate_content(product, lang)
                results[lang] = translated

        return results

    async def _translate_content(
        self, product: ProductData, target_lang: LanguageCode
    ) -> TranslatedContent:
        """翻译单个语言的内容"""
        title = await self._translate_text(product.title, target_lang)
        bullet_points = []

        for bp in product.bullet_points:
            translated_bp = await self._translate_text(bp, target_lang)
            bullet_points.append(translated_bp)

        # 日语特殊处理
        if target_lang == LanguageCode.JP:
            title = self._apply_jp_politeness(title)
            bullet_points = [self._apply_jp_politeness(bp) for bp in bullet_points]

        return TranslatedContent(
            language=target_lang,
            title=title,
            bullet_points=bullet_points,
        )

    async def _translate_text(self, text: str, target_lang: LanguageCode) -> str:
        """翻译单条文本"""
        # Mock 模式下，日语不使用术语表（避免字体问题）
        if self.provider == TranslationProvider.MOCK and target_lang == LanguageCode.JP:
            return self._translate_mock(text, target_lang)

        # 先检查术语表
        text_lower = text.lower()
        for term, translations in FURNITURE_GLOSSARY.items():
            if term in text_lower:
                if target_lang in translations:
                    # 替换术语
                    text = text.replace(term, translations[target_lang])
                    text = text.replace(term.title(), translations[target_lang])

        # 使用翻译 API
        if self.provider == TranslationProvider.DEEPL:
            return await self._translate_deepl(text, target_lang)
        elif self.provider == TranslationProvider.OPENAI:
            return await self._translate_openai(text, target_lang)
        else:
            return self._translate_mock(text, target_lang)

    async def _translate_deepl(self, text: str, target_lang: LanguageCode) -> str:
        """使用 DeepL 翻译"""
        lang_map = {
            LanguageCode.DE: "DE",
            LanguageCode.IT: "IT",
            LanguageCode.FR: "FR",
            LanguageCode.ES: "ES",
            LanguageCode.JP: "JA",
        }
        try:
            result = self.translator.translate_text(
                text, target_lang=lang_map[target_lang]
            )
            return result.text
        except Exception as e:
            print(f"DeepL 翻译失败: {e}")
            return self._translate_mock(text, target_lang)

    async def _translate_openai(self, text: str, target_lang: LanguageCode) -> str:
        """使用 OpenAI 翻译"""
        lang_names = {
            LanguageCode.DE: "German",
            LanguageCode.IT: "Italian",
            LanguageCode.FR: "French",
            LanguageCode.ES: "Spanish",
            LanguageCode.JP: "Japanese",
        }

        prompt = f"""Translate the following product description to {lang_names[target_lang]}.
Keep the tone professional and suitable for a product manual.
Only return the translation, no explanations.

Text to translate:
{text}"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a professional translator specializing in furniture product manuals."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"OpenAI 翻译失败: {e}")
            return self._translate_mock(text, target_lang)

    def _translate_mock(self, text: str, target_lang: LanguageCode) -> str:
        """Mock 翻译（用于 Demo）"""
        # 日语使用罗马字标注，避免字体问题
        jp_prefixes = {
            "Solid Wood": "Mokkuzai (Solid Wood)",
            "Dining Table": "Dainingu Teeburu (Dining Table)",
            "Oak": "Ooku (Oak)",
            "Assembly": "Kumitate (Assembly)",
        }

        if target_lang == LanguageCode.JP:
            # 检查是否有预定义的罗马字翻译
            for en_term, jp_roman in jp_prefixes.items():
                if en_term.lower() in text.lower():
                    return f"[JP] {jp_roman}"
            return f"[JP] {text} (Japanese)"

        prefixes = {
            LanguageCode.DE: "[DE] ",
            LanguageCode.IT: "[IT] ",
            LanguageCode.FR: "[FR] ",
            LanguageCode.ES: "[ES] ",
        }
        return f"{prefixes.get(target_lang, '')}{text}"

    def _apply_jp_politeness(self, text: str) -> str:
        """日语敬语处理（です/ます体）"""
        # Mock 模式下不添加敬语（避免字体问题）
        if self.provider == TranslationProvider.MOCK:
            return text

        # 简单的敬语处理 - 在句尾添加敬语
        if not text.endswith(("。", "！", "？", ".", "!", "?")):
            # 添加敬语后缀
            if any(verb in text for verb in ["する", "できる", "なる"]):
                text = text + JP_POLITE_VERB_SUFFIX
            else:
                text = text + JP_POLITE_SUFFIX

        return text
