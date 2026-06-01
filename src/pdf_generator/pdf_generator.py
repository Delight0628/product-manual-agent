"""PDF 说明书生成器"""

import json
import os
from typing import Dict, List, Optional
from pathlib import Path

try:
    from fpdf import FPDF
    FPDF_AVAILABLE = True
except ImportError:
    FPDF_AVAILABLE = False

from src.models import ProductData, TranslatedContent, LanguageCode


class PDFGenerator:
    """PDF 说明书生成器"""

    def __init__(self, output_dir: str = "output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

    def generate_manual(
        self,
        product: ProductData,
        translations: Dict[LanguageCode, TranslatedContent],
        filename: Optional[str] = None,
    ) -> str:
        """生成产品说明书 PDF"""
        if not filename:
            asin = product.asin or "manual"
            filename = f"manual_{asin}.pdf"

        filepath = self.output_dir / filename

        if not FPDF_AVAILABLE:
            return self._generate_text_manual(product, translations, filepath)

        return self._generate_pdf(product, translations, filepath)

    def _generate_pdf(
        self,
        product: ProductData,
        translations: Dict[LanguageCode, TranslatedContent],
        filepath: Path,
    ) -> str:
        """使用 fpdf2 生成 PDF"""
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)

        # 添加 Unicode 字体支持
        font_paths = [
            "C:/Windows/Fonts/msyh.ttc",  # 微软雅黑
            "C:/Windows/Fonts/simsun.ttc",  # 宋体
            "C:/Windows/Fonts/simhei.ttf",  # 黑体
        ]

        font_added = False
        for font_path in font_paths:
            if os.path.exists(font_path):
                try:
                    pdf.add_font("Chinese", "", font_path, uni=True)
                    pdf.add_font("Chinese", "B", font_path, uni=True)
                    font_added = True
                    break
                except:
                    continue

        # 封面页
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 24)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(0, 20, "Product Manual", align="C")
        pdf.ln(10)

        # 产品标题（多语言）
        for lang, content in translations.items():
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(100, 100, 100)
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(0, 8, f"{lang.value}:")

            if font_added and lang in [LanguageCode.JP]:
                pdf.set_font("Chinese", "B", 16)
            else:
                pdf.set_font("Helvetica", "B", 16)
            pdf.set_text_color(0, 0, 0)
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(0, 10, content.title)
            pdf.ln(5)

        # 品牌和价格
        if product.brand or product.price:
            pdf.ln(10)
            pdf.set_font("Helvetica", "", 12)
            if product.brand:
                pdf.set_x(pdf.l_margin)
                pdf.multi_cell(0, 8, f"Brand: {product.brand}")
            if product.price:
                pdf.set_x(pdf.l_margin)
                pdf.multi_cell(0, 8, f"Price: {product.price}")

        # 产品概览页
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 18)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(0, 15, "Product Overview")
        pdf.ln(5)

        # 产品信息
        pdf.set_font("Helvetica", "", 11)
        info_items = [
            ("ASIN", product.asin or "N/A"),
            ("Price", product.price or "N/A"),
            ("Brand", product.brand or "N/A"),
        ]
        for label, value in info_items:
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(0, 8, f"{label}: {value}")

        # 产品特点页
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 18)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(0, 15, "Product Features")
        pdf.ln(5)

        for lang, content in translations.items():
            pdf.set_font("Helvetica", "B", 13)
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(0, 10, f"[{lang.value}]")
            pdf.ln(3)

            pdf.set_font("Helvetica", "", 10)
            for bp in content.bullet_points:
                pdf.set_x(pdf.l_margin)
                pdf.multi_cell(0, 7, f"  - {bp}")
            pdf.ln(5)

        # 安装说明页
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 18)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(0, 15, "Installation Guide")
        pdf.ln(5)

        installation_steps = {
            LanguageCode.EN: [
                "1. Check all parts against the included parts list.",
                "2. Lay out all parts on a clean, flat surface.",
                "3. Follow the step-by-step assembly instructions.",
                "4. Tighten all screws firmly but do not overtighten.",
                "5. Check stability before use.",
            ],
            LanguageCode.DE: [
                "1. Pruefen Sie alle Teile anhand der beiliegenden Teileliste.",
                "2. Legen Sie alle Teile auf eine saubere, ebene Flaeche.",
                "3. Befolgen Sie die schrittweisen Montageanweisungen.",
                "4. Ziehen Sie alle Schrauben fest an, aber ueberziehen Sie sie nicht.",
                "5. Ueberpruefen Sie die Stabilitaet vor der Verwendung.",
            ],
            LanguageCode.JP: [
                "1. 同梱品リストと照合し、部品を確認してください。",
                "2. 清潔で平らな場所にすべての部品を広げてください。",
                "3. ステップごとの組立説明に従って作業してください。",
                "4. すべてのねじをしっかり締めてください。",
                "5. 使用前に安定性を確認してください。",
            ],
            LanguageCode.IT: [
                "1. Controllare tutti i pezzi rispetto all'elenco dei pezzi allegati.",
                "2. Disporre tutti i pezzi su una superficie pulita e piana.",
                "3. Seguire le istruzioni di assemblaggio passo dopo passo.",
                "4. Stringere tutte le viti con fermezza senza eccedere.",
                "5. Verificare la stabilita prima dell'uso.",
            ],
            LanguageCode.FR: [
                "1. Verifiez toutes les pieces par rapport a la liste des pieces incluses.",
                "2. Disposez toutes les pieces sur une surface propre et plane.",
                "3. Suivez les instructions d'assemblage etape par etape.",
                "4. Serrez toutes les vis fermement sans les serrer trop.",
                "5. Verifiez la stabilite avant utilisation.",
            ],
            LanguageCode.ES: [
                "1. Revise todas las piezas segun la lista de piezas incluida.",
                "2. Coloque todas las piezas sobre una superficie limpia y plana.",
                "3. Siga las instrucciones de ensamblaje paso a paso.",
                "4. Apriete todos los tornillos firmemente, pero no en exceso.",
                "5. Verifique la estabilidad antes de usar.",
            ],
        }

        for lang in translations:
            pdf.set_font("Helvetica", "B", 12)
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(0, 10, f"[{lang.value}]")
            pdf.ln(3)

            steps = installation_steps.get(lang, installation_steps[LanguageCode.EN])
            pdf.set_font("Helvetica", "", 10)
            for step in steps:
                if font_added and lang == LanguageCode.JP:
                    pdf.set_font("Chinese", "", 10)
                else:
                    pdf.set_font("Helvetica", "", 10)
                pdf.set_x(pdf.l_margin)
                pdf.multi_cell(0, 7, step)
            pdf.ln(5)

        # 安全警告
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 18)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(0, 15, "Safety Warnings")
        pdf.ln(5)

        warnings_en = [
            "Keep away from heat sources.",
            "Do not exceed weight limits.",
            "Adult assembly required.",
            "Supervise children during use.",
        ]

        warnings_de = [
            "Halten Sie Abstand von Waermequellen.",
            "Ueberschreiten Sie nicht die Gewichtsgrenzen.",
            "Erwachsenenaufsicht beim Aufbau erforderlich.",
            "Ueberwachen Sie Kinder waehrend der Nutzung.",
        ]

        warnings_it = [
            "Tenere lontano da fonti di calore.",
            "Non superare i limiti di peso.",
            "Assemblaggio da parte di adulti obbligatorio.",
            "Supervisionare i bambini durante l'uso.",
        ]

        warnings_fr = [
            "Eloignez des sources de chaleur.",
            "Ne pas depasser les limites de poids.",
            "Assemblage par un adulte requis.",
            "Surveiller les enfants pendant l'utilisation.",
        ]

        warnings_es = [
            "Mantener alejado de fuentes de calor.",
            "No exceder los limites de peso.",
            "Se requiere ensamblaje por un adulto.",
            "Supervisar a los ninos durante el uso.",
        ]

        warnings_jp = [
            "熱源から離してください。",
            "重量制限を超えないでください。",
            "大人の組立が必要です。",
            "使用中は子供の監視をしてください。",
        ]

        all_warnings = [
            ("EN", warnings_en, None),
            ("DE", warnings_de, None),
            ("IT", warnings_it, None),
            ("FR", warnings_fr, None),
            ("ES", warnings_es, None),
        ]
        if font_added:
            all_warnings.append(("JP", warnings_jp, "Chinese"))

        for lang_label, warns, font_name in all_warnings:
            pdf.set_font("Helvetica", "B", 12)
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(0, 10, f"[{lang_label}]")
            if font_name and font_added:
                pdf.set_font(font_name, "", 10)
            else:
                pdf.set_font("Helvetica", "", 10)
            for w in warns:
                pdf.set_x(pdf.l_margin)
                pdf.multi_cell(0, 7, f"  - {w}")
            pdf.ln(5)


        # 保存 PDF
        pdf.output(str(filepath))
        return str(filepath)

    def _generate_text_manual(
        self,
        product: ProductData,
        translations: Dict[LanguageCode, TranslatedContent],
        filepath: Path,
    ) -> str:
        """FPDF 不可用时，生成文本格式的说明书"""
        # 保存为 JSON
        manual_data = {
            "product": {
                "title": product.title,
                "asin": product.asin,
                "price": product.price,
                "brand": product.brand,
                "images": product.images,
            },
            "translations": {},
        }

        for lang, content in translations.items():
            manual_data["translations"][lang.value] = {
                "title": content.title,
                "bullet_points": content.bullet_points,
            }

        json_path = filepath.with_suffix(".json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(manual_data, f, ensure_ascii=False, indent=2)

        # 生成纯文本版本
        txt_path = filepath.with_suffix(".txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("=" * 60 + "\n")
            f.write("PRODUCT MANUAL\n")
            f.write("=" * 60 + "\n\n")

            f.write(f"Title: {product.title}\n")
            f.write(f"ASIN: {product.asin or 'N/A'}\n")
            f.write(f"Price: {product.price or 'N/A'}\n")
            f.write(f"Brand: {product.brand or 'N/A'}\n")
            f.write("\n")

            for lang, content in translations.items():
                f.write("-" * 40 + "\n")
                f.write(f"  {lang.value}\n")
                f.write("-" * 40 + "\n")
                f.write(f"\n  {content.title}\n\n")
                for bp in content.bullet_points:
                    f.write(f"  * {bp}\n")
                f.write("\n")

            f.write("=" * 60 + "\n")
            f.write("INSTALLATION GUIDE\n")
            f.write("=" * 60 + "\n\n")

            installation_steps = {
                LanguageCode.EN: [
                    "1. Check all parts against the included parts list.",
                    "2. Lay out all parts on a clean, flat surface.",
                    "3. Follow the step-by-step assembly instructions.",
                    "4. Tighten all screws firmly but do not overtighten.",
                    "5. Check stability before use.",
                ],
                LanguageCode.DE: [
                    "1. Ueberpruefen Sie alle Teile anhand der beiliegenden Teileliste.",
                    "2. Legen Sie alle Teile auf eine saubere, ebene Flaeche.",
                    "3. Befolgen Sie die schrittweisen Montageanweisungen.",
                    "4. Ziehen Sie alle Schrauben fest an, aber ueberziehen Sie sie nicht.",
                    "5. Ueberpruefen Sie die Stabilitaet vor der Verwendung.",
                ],
                LanguageCode.JP: [
                    "1. 同梱品リストと照合し、部品を確認してください。",
                    "2. 清潔で平らな場所にすべての部品を広げてください。",
                    "3. ステップごとの組立説明に従って作業してください。",
                    "4. すべてのねじをしっかり締めてください。",
                    "5. 使用前に安定性を確認してください。",
                ],
                LanguageCode.IT: [
                    "1. Controllare tutti i pezzi rispetto all'elenco dei pezzi allegati.",
                    "2. Disporre tutti i pezzi su una superficie pulita e piana.",
                    "3. Seguire le istruzioni di assemblaggio passo dopo passo.",
                    "4. Stringere tutte le viti con fermezza senza eccedere.",
                    "5. Verificare la stabilita prima dell'uso.",
                ],
                LanguageCode.FR: [
                    "1. Verifiez toutes les pieces par rapport a la liste des pieces incluses.",
                    "2. Disposez toutes les pieces sur une surface propre et plane.",
                    "3. Suivez les instructions d'assemblage etape par etape.",
                    "4. Serrez toutes les vis fermement sans les serrer trop.",
                    "5. Verifiez la stabilite avant utilisation.",
                ],
                LanguageCode.ES: [
                    "1. Revise todas las piezas segun la lista de piezas incluida.",
                    "2. Coloque todas las piezas sobre una superficie limpia y plana.",
                    "3. Siga las instrucciones de ensamblaje paso a paso.",
                    "4. Apriete todos los tornillos firmemente, pero no en exceso.",
                    "5. Verifique la estabilidad antes de usar.",
                ],
            }

            for lang in translations:
                f.write(f"\n  [{lang.value}]\n")
                steps = installation_steps.get(lang, installation_steps[LanguageCode.EN])
                for step in steps:
                    f.write(f"  {step}\n")

        return str(txt_path)
