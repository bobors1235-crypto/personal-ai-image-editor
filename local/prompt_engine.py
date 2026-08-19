"""
Local Prompt Engine for Personal AI Image Editor.
Runs on CPU on the local machine with zero GPU overhead.
Provides Arabic/English understanding, multi-category classification,
conflict-free 'Preserve vs Change' logic, and structured prompt generation.
"""

import re
import unicodedata
from typing import List, Dict, Set, Tuple, Any
from shared.schemas import PromptAnalysis


class PromptEngine:
    """Intelligent rule-based prompt enhancement engine."""

    # Arabic category keywords
    AR_KEYWORDS = {
        "OUTFIT": [
            r"لبس", r"ملابس", r"بدل[ةه]", r"قميص", r"جاكيت", r"فستان", r"بنطلون", r"تيشرت",
            r"هودي", r"كوت", r"معطف", r"كاجوال", r"رسمي", r"عباي[ةه]", r"ثوب", r"بلوفر",
            r"بدلة سودا", r"بدلة كحلي", r"جاكيت جلد", r"بدل", r"غير لبسه", r"غير اللبس",
            r"لبسه", r"لبسها", r"زي", r"ملبس"
        ],
        "BACKGROUND": [
            r"خلفي[ةه]", r"مكان", r"شارع", r"بحر", r"شاطئ", r"غروب", r"شمس", r"باريس",
            r"نيويورك", r"مكتب", r"غرف[ةه]", r"طبيع[ةه]", r"جبل", r"جبال", r"فندق",
            r"مطعم", r"كافي[ةه]", r"استوديو", r"مدينة", r"حديق[ةه]", r"ليل", r"نهار",
            r"سماء", r"صحراء", r"قصر", r"فيلا", r"غير الخلفية", r"خلي الخلفية", r"واقف في", r"على البحر"
        ],
        "POSE": [
            r"وضعي[ةه]", r"واقف", r"قاعد", r"جالس", r"ماشي", r"يجري", r"نايم",
            r"رافع", r"ينظر", r"يلتفت", r"حرك[ةه]", r"وضعية الجسم", r"غير الوضعية",
            r"خليه قاعد", r"خليه واقف", r"خليه ماشي", r"ابتسم", r"مبتسم"
        ],
        "CAMERA": [
            r"زاوي[ةه]", r"تصوير", r"كاميرا", r"لقط[ةه]", r"سينمائي", r"سينمائية",
            r"زاوية منخفضة", r"زاوية مرتفعة", r"كلوز اب", r"شوت", r"بورتريه",
            r"واسع[ةه]", r"low angle", r"high angle", r"close up", r"wide shot", r"بوكيه", r"عزل"
        ],
        "LIGHTING": [
            r"إضاء[ةه]", r"اضاء[ةه]", r"نور", r"شمس", r"ظل", r"ظلال", r"نيون",
            r"درامي[ةه]", r"ساعة ذهبي[ةه]", r"ليلية", r"نهارية", r"استوديو", r"مظلم", r"ساطع"
        ],
        "OBJECT": [
            r"ضيف", r"شيل", r"احذف", r"امسح", r"نظار[ةه]", r"ساع[ةه]", r"شنط[ةه]",
            r"كاس", r"كوب", r"موبايل", r"تلفون", r"هاتف", r"سيار[ةه]", r"كتاب",
            r"قلم", r"اكسسوار", r"خاتم", r"سلسلة", r"حط", r"امسك", r"ماسك"
        ],
        "HAIR": [
            r"شعر", r"تسريح[ةه]", r"قص[ةه]", r"طويل", r"قصير", r"كيرلي", r"ناعم",
            r"أصلع", r"اصلع", r"لحية", r"دقن", r"شنب", r"شارب", r"أشقر", r"اسود", r"بني"
        ],
        "FACE": [
            r"وج[ةه]", r"ملامح", r"عين", r"عيون", r"مكياج", r"شفاه", r"بشر[ةه]",
            r"نضار[ةه]", r"تجاعيد", r"نظرة", r"تعبير"
        ],
        "STYLE": [
            r"ستايل", r"انمي", r"كرتون", r"رسم", r"لوح[ةه]", r"زيتي", r"سينما",
            r"فينتاج", r"ابيض واسود", r"أبيض وأسود", r"ثلاثي الابعاد", r"3d"
        ]
    }

    # English category keywords
    EN_KEYWORDS = {
        "OUTFIT": [
            r"\boutfit\b", r"\bclothing\b", r"\bclothes\b", r"\bsuit\b", r"\btuxedo\b",
            r"\bshirt\b", r"\bt-shirt\b", r"\bdress\b", r"\bjacket\b", r"\bcoat\b",
            r"\bpants\b", r"\btrousers\b", r"\bjeans\b", r"\bhoodie\b", r"\bsweater\b",
            r"\bleather jacket\b", r"\bformal wear\b", r"\bcasual\b", r"\buniform\b",
            r"\bblazer\b", r"\bchange outfit\b", r"\bwear\b", r"\bwearing\b"
        ],
        "BACKGROUND": [
            r"\bbackground\b", r"\bscene\b", r"\benvironment\b", r"\bstreet\b", r"\bbeach\b",
            r"\bsunset\b", r"\bparis\b", r"\bnew york\b", r"\btokyo\b", r"\broom\b",
            r"\boffice\b", r"\bnature\b", r"\bmountain\b", r"\bforest\b", r"\bhotel\b",
            r"\brestaurant\b", r"\bcafe\b", r"\bstudio\b", r"\bcity\b", r"\burban\b",
            r"\bnight\b", r"\bdaylight\b", r"\bdesert\b", r"\bluxury\b", r"\bindoor\b", r"\boutdoor\b"
        ],
        "POSE": [
            r"\bpose\b", r"\bposture\b", r"\bstanding\b", r"\bsitting\b", r"\bseated\b",
            r"\bwalking\b", r"\brunning\b", r"\bleaning\b", r"\blooking\b", r"\bgesture\b",
            r"\bholding hands\b", r"\bturning\b", r"\bsmiling\b", r"\blaughing\b"
        ],
        "CAMERA": [
            r"\bcamera\b", r"\bcamera angle\b", r"\blow-angle\b", r"\blow angle\b",
            r"\bhigh-angle\b", r"\bhigh angle\b", r"\bcinematic shot\b", r"\bclose-up\b",
            r"\bclose up\b", r"\bwide shot\b", r"\bfull body\b", r"\bportrait shot\b",
            r"\bdepth of field\b", r"\bbokeh\b", r"\bfocal length\b", r"\btelephoto\b"
        ],
        "LIGHTING": [
            r"\blighting\b", r"\blight\b", r"\bsunlight\b", r"\bgolden hour\b", r"\bdramatic lighting\b",
            r"\bneon light\b", r"\bstudio lighting\b", r"\bsoft light\b", r"\brim light\b",
            r"\bshadows\b", r"\breflections\b", r"\bnight illumination\b", r"\bcinematic light\b"
        ],
        "OBJECT": [
            r"\badd\b", r"\bremove\b", r"\bdelete\b", r"\bholding\b", r"\bglasses\b",
            r"\bsunglasses\b", r"\bwatch\b", r"\bhandbag\b", r"\bbag\b", r"\bcup\b",
            r"\bglass\b", r"\bphone\b", r"\bcar\b", r"\bcoffee\b", r"\baccessory\b", r"\bring\b"
        ],
        "HAIR": [
            r"\bhair\b", r"\bhairstyle\b", r"\bhaircut\b", r"\blong hair\b", r"\bshort hair\b",
            r"\bcurly\b", r"\bstraight\b", r"\bblonde\b", r"\bbrunette\b", r"\bbald\b",
            r"\bbeard\b", r"\bmustache\b"
        ],
        "FACE": [
            r"\bface\b", r"\bfacial\b", r"\beyes\b", r"\bmakeup\b", r"\blips\b",
            r"\bskin\b", r"\bsmile\b", r"\bexpression\b"
        ],
        "STYLE": [
            r"\bstyle\b", r"\banime\b", r"\bcartoon\b", r"\boil painting\b", r"\bvintage\b",
            r"\bblack and white\b", r"\bmonochrome\b", r"\b3d render\b", r"\bdigital art\b"
        ]
    }

    # Arabic translations / expansions for specific patterns
    ARABIC_INTENT_MAP = [
        (r"غير (?:اللبس|الملابس|لبسه|لبسها) (?:ل|إلى )?(بدل[ةه] سودا|بدلة سوداء)", "Replace the subject's outfit with an elegant tailored black suit and dress shirt"),
        (r"غير (?:اللبس|الملابس|لبسه|لبسها) (?:ل|إلى )?(جاكيت جلد|جاكيت كاجوال)", "Replace the subject's outfit with a high-end stylish black leather jacket"),
        (r"غير (?:اللبس|الملابس|لبسه|لبسها) (?:ل|إلى )?(قميص أبيض|قميص ابيض)", "Replace the subject's outfit with a clean, fitted white dress shirt"),
        (r"غير (?:اللبس|الملابس|لبسه|لبسها) (?:ل|إلى )?(فستان سهرة|فستان)", "Replace the subject's outfit with an exquisite evening dress"),
        (r"(?:خلي|اجعل) (?:التصوير|اللقطة) (?:في )?(شارع في نيويورك بالليل|نيويورك بالليل)", "Set the scene on a vibrant New York City street at night with glowing city lights"),
        (r"(?:خلي|اجعل) (?:التصوير|اللقطة|الخلفية) (?:على |في )?(بحر وقت الغروب|البحر وقت الغروب|الشاطئ)", "Set the scene at a serene beach during sunset with warm golden hour light"),
        (r"(?:خلي|اجعل) (?:التصوير|اللقطة) (?:في )?(باريس|برج ايفل)", "Set the scene in Paris with classic Parisian architecture"),
        (r"(?:خلي|اجعل) (?:التصوير|اللقطة) (?:في )?(فندق فاخر|فندق|لوبي فندق)", "Set the scene inside a luxurious 5-star hotel lobby with upscale ambient lighting"),
        (r"(?:خلي|اجعل) (?:التصوير|اللقطة) (?:في )?(مكتب حديث|مكتب عمل|استوديو)", "Set the scene in a modern corporate office interior with architectural design"),
        (r"(?:خلي|اجعل) (?:وضعيته|الوضعية) (واقف|جالس|قاعد|ماشي)", "Adjust the subject's pose naturally"),
        (r"(?:خلي|اجعل) (?:التصوير|الكاميرا) (low angle|زاوية منخفضة|سينمائي)", "Capture the scene in a dramatic low-angle cinematic camera perspective")
    ]

    @classmethod
    def detect_language(cls, text: str) -> str:
        """Detect whether input is predominantly Arabic or English."""
        arabic_chars = len(re.findall(r'[\u0600-\u06FF]', text))
        total_chars = len(re.findall(r'[a-zA-Z\u0600-\u06FF]', text))
        if total_chars == 0:
            return "en"
        return "ar" if (arabic_chars / total_chars) > 0.3 else "en"

    @classmethod
    def classify_categories(cls, text: str, lang: str) -> List[str]:
        """Classify prompt into target editing categories."""
        categories = []
        lower_text = text.lower()

        keywords_dict = cls.AR_KEYWORDS if lang == "ar" else cls.EN_KEYWORDS
        # Check both to support mixed Arabic/English
        all_dicts = [cls.AR_KEYWORDS, cls.EN_KEYWORDS]

        for kdict in all_dicts:
            for cat, patterns in kdict.items():
                if cat in categories:
                    continue
                for pattern in patterns:
                    if re.search(pattern, lower_text, re.IGNORECASE):
                        categories.append(cat)
                        break

        if not categories:
            categories.append("GENERAL")
        return categories

    @classmethod
    def resolve_preserve_vs_change(cls, categories: List[str]) -> Tuple[List[str], List[str]]:
        """
        Determine which elements should be changed and which must be preserved.
        Crucial Rule: Never tell the model to preserve an element that the user wants to change.
        """
        change_targets = []
        preserve_targets = []

        # Map categories to change target tags
        cat_to_change = {
            "OUTFIT": "clothing & outfit",
            "BACKGROUND": "background & scene environment",
            "POSE": "body pose & posture",
            "CAMERA": "camera angle & perspective",
            "LIGHTING": "lighting & illumination",
            "OBJECT": "specific objects/accessories",
            "HAIR": "hair & hairstyle",
            "FACE": "facial expression / makeup",
            "STYLE": "visual rendering style",
            "GENERAL": "specified edit"
        }

        for cat in categories:
            if cat in cat_to_change:
                change_targets.append(cat_to_change[cat])

        # Baseline preserve elements unless explicitly modified
        if "FACE" not in categories and "STYLE" not in categories:
            preserve_targets.append("exact facial identity, facial structure, eye shape, nose, and recognizable facial features")
            preserve_targets.append("natural skin tone, apparent age, and realistic skin texture")

        if "HAIR" not in categories:
            preserve_targets.append("exact hairstyle, hair color, and hairline")

        if "POSE" not in categories and "CAMERA" not in categories:
            preserve_targets.append("original body pose and posture")

        if "OUTFIT" not in categories:
            preserve_targets.append("current clothing and outfit details")

        if "BACKGROUND" not in categories:
            preserve_targets.append("original background environment and surroundings")

        # Always preserve anatomy and realism
        preserve_targets.append("photorealistic rendering, natural proportions, and anatomically correct hands and fingers")

        return change_targets, preserve_targets

    @classmethod
    def translate_arabic_intents(cls, text: str) -> str:
        """Translate common Arabic editing phrases into detailed English instructions."""
        translated = text
        for pattern, replacement in cls.ARABIC_INTENT_MAP:
            if re.search(pattern, translated, re.IGNORECASE):
                translated = re.sub(pattern, replacement, translated, flags=re.IGNORECASE)

        # Basic direct word replacements if still contains Arabic
        arabic_replacements = {
            "بدلة سودا": "tailored black suit",
            "بدلة سوداء": "tailored black suit",
            "بدلة كحلي": "navy blue suit",
            "جاكيت جلد": "black leather jacket",
            "قميص ابيض": "white dress shirt",
            "قميص أبيض": "white dress shirt",
            "شارع في نيويورك بالليل": "New York City street at night",
            "في باريس": "in Paris",
            "على البحر": "on the beach",
            "وقت الغروب": "during golden hour sunset",
            "في فندق": "in a luxury hotel lobby",
            "في مكتب": "in a modern executive office",
            "واقف": "standing naturally",
            "قاعد": "sitting comfortably",
            "جالس": "sitting comfortably",
            "زاوية منخفضة": "low-angle shot",
            "لقطة سينمائية": "cinematic photography shot",
            "غير": "change",
            "خلي": "set",
            "ضيف": "add",
            "شيل": "remove"
        }
        for ar_term, en_term in arabic_replacements.items():
            translated = translated.replace(ar_term, en_term)

        return translated

    @classmethod
    def build_structured_prompt(
        cls,
        user_prompt: str,
        lang: str,
        categories: List[str],
        change_targets: List[str],
        preserve_targets: List[str],
        identity_strength: str = "high",
        quality: str = "high"
    ) -> Tuple[str, Dict[str, str]]:
        """Construct a structured, professional-grade image editing prompt."""

        sections = {}

        # 1. ACTION
        if lang == "ar":
            action_desc = cls.translate_arabic_intents(user_prompt)
            sections["ACTION"] = f"Execute edit instruction: {action_desc} (User request: '{user_prompt}')."
        else:
            sections["ACTION"] = f"Execute edit instruction: {user_prompt.strip()}."

        # 2. SUBJECT & IDENTITY PRESERVATION
        if identity_strength == "high":
            sections["SUBJECT & IDENTITY"] = (
                "Maintain strict facial identity consistency. "
                "Preserve exact facial bone structure, eyes, eyebrows, nose, mouth contours, skin texture, and true likeness. "
                "Do NOT alter the person's identity, age, or natural ethnicity."
            )
        elif identity_strength == "normal":
            sections["SUBJECT & IDENTITY"] = (
                "Preserve recognizable facial features, facial structure, skin tone, and overall person identity."
            )
        else:
            sections["SUBJECT & IDENTITY"] = (
                "Keep the subject harmonious while allowing flexible stylistic adjustments."
            )

        # 3. REQUESTED MODIFICATIONS
        mods = []
        if "OUTFIT" in categories:
            mods.append("Seamlessly replace the subject's clothing with the requested outfit, ensuring realistic fabric drape, tailored fit, natural folds, and contact shadows on the body.")
        if "BACKGROUND" in categories:
            mods.append("Seamlessly replace the background environment with the requested setting, with coherent depth of field, authentic perspective, and matching environmental light bounce on the subject.")
        if "POSE" in categories:
            mods.append("Adjust the subject's pose naturally with anatomically correct body alignment, weight distribution, and realistic limbs.")
        if "CAMERA" in categories:
            mods.append("Reframe the composition according to the requested camera angle and focal perspective with professional lens rendering.")
        if "LIGHTING" in categories:
            mods.append("Apply realistic lighting that realistically matches the desired ambiance, casting accurate highlights, rim light, and soft contact shadows.")
        if "OBJECT" in categories:
            mods.append("Integrate or remove the specified objects naturally with correct occlusions, reflections, and hand interactions if applicable.")
        if "HAIR" in categories:
            mods.append("Modify hair styling naturally, preserving realistic individual strands, volume, and scalp boundaries.")

        if mods:
            sections["SPECIFIC MODIFICATIONS"] = " ".join(mods)

        # 4. STRICT PRESERVATION (CONFLICT-FREE)
        if preserve_targets:
            preserved_list = "\n- " + "\n- ".join(preserve_targets)
            sections["PRESERVE UNCHANGED"] = f"Strictly keep untouched:{preserved_list}"

        # 5. QUALITY & PHOTOREALISM
        if quality == "high":
            sections["QUALITY & AESTHETICS"] = (
                "Masterpiece professional photography, 8k resolution, authentic skin micro-textures, "
                "physically accurate lighting, crisp details, zero artifacts, anatomically flawless."
            )
        else:
            sections["QUALITY & AESTHETICS"] = (
                "High quality photorealistic rendering with natural balance and clean details."
            )

        # Format full enhanced prompt
        formatted_lines = []
        for sec_name, sec_content in sections.items():
            formatted_lines.append(f"[{sec_name}]\n{sec_content}\n")

        enhanced_prompt = "\n".join(formatted_lines).strip()
        return enhanced_prompt, sections

    @classmethod
    def enhance_edit_prompt(
        cls,
        prompt: str,
        identity_strength: str = "high",
        quality: str = "high"
    ) -> PromptAnalysis:
        """
        Main entry point for local prompt analysis & expansion.
        """
        raw_prompt = prompt.strip()
        lang = cls.detect_language(raw_prompt)
        categories = cls.classify_categories(raw_prompt, lang)
        change_targets, preserve_targets = cls.resolve_preserve_vs_change(categories)

        enhanced_prompt, sections = cls.build_structured_prompt(
            user_prompt=raw_prompt,
            lang=lang,
            categories=categories,
            change_targets=change_targets,
            preserve_targets=preserve_targets,
            identity_strength=identity_strength,
            quality=quality
        )

        return PromptAnalysis(
            original_prompt=raw_prompt,
            language=lang,
            categories=categories,
            change_targets=change_targets,
            preserve_targets=preserve_targets,
            enhanced_prompt=enhanced_prompt,
            structured_sections=sections
        )
