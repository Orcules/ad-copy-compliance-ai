import os
import json
import logging
import pandas as pd
from pathlib import Path
from openai import OpenAI
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Create prompts log directory if it doesn't exist
PROMPTS_LOG_DIR = Path(__file__).resolve().parent / 'logs'
PROMPTS_LOG_DIR.mkdir(exist_ok=True)
PROMPTS_LOG_FILE = PROMPTS_LOG_DIR / 'openai_prompts.log'

class OpenAIClient:
    def __init__(self):
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        self.client = OpenAI(api_key=api_key)
        self.model = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
        self.moderation_model = os.getenv('OPENAI_MODERATION_MODEL', 'omni-moderation-latest')
        self.use_responses = os.getenv('OPENAI_USE_RESPONSES', '1').lower() == '1'
        
        # Load policy content
        self.policy_content = self._load_policy_content()
        
        # Localized CTA labels per language code
        self.cta_translations = {
            'en': ["Learn More","Shop Now","Sign Up","Get Offer","Contact Us","Get Started"],
            'he': ["למידע נוסף","קנו עכשיו","הירשמו","קבלו הצעה","צרו קשר","התחילו"],
            'ar': ["اعرف المزيد","تسوق الآن","سجّل","احصل على العرض","اتصل بنا","ابدأ الآن"],
            'ru': ["Узнать больше","Купить сейчас","Зарегистрироваться","Получить предложение","Связаться с нами","Начать"],
            'es': ["Más información","Comprar ahora","Regístrate","Obtener oferta","Contáctanos","Comenzar"],
            'fr': ["En savoir plus","Acheter maintenant","S'inscrire","Obtenir l'offre","Nous contacter","Commencer"],
        }
    
    def _log_prompt_to_file(self, prompt_type: str, system_message: str, user_message: str, model: str):
        """Log prompts to a dedicated log file"""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = f"""
{'='*100}
TIMESTAMP: {timestamp}
PROMPT TYPE: {prompt_type}
MODEL: {model}
{'='*100}

SYSTEM MESSAGE:
{system_message}

{'='*100}
USER MESSAGE (PROMPT):
{user_message}

{'='*100}

"""
            with open(PROMPTS_LOG_FILE, 'a', encoding='utf-8') as f:
                f.write(log_entry)
            
            logger.info(f"Logged {prompt_type} prompt to {PROMPTS_LOG_FILE}")
        except Exception as e:
            logger.error(f"Failed to log prompt to file: {e}")
    
    def _tone_guidelines(self, tone: str, language_code: str) -> str:
        """Return tone-specific style directives. Written in English; output language is controlled elsewhere."""
        t = (tone or "").strip().lower()
        if t == 'professional':
            return (
                "- Use clear, concise, and formal phrasing\n"
                "- Avoid slang and excessive punctuation\n"
                "- Focus on value, outcomes, and credibility\n"
                "- Prefer neutral adjectives over superlatives"
            )
        if t == 'friendly':
            return (
                "- Use warm, approachable language\n"
                "- Prefer short sentences; sound conversational\n"
                "- Use inclusive words (you/your/let’s)\n"
                "- Keep enthusiasm modest; avoid exaggeration"
            )
        if t == 'urgent':
            return (
                "- Convey time sensitivity without fear-mongering\n"
                "- Use action verbs and clear next steps\n"
                "- Limit exclamation marks to at most 1 per variant\n"
                "- Keep sentences short and directive"
            )
        if t == 'playful':
            return (
                "- Use light, upbeat wording\n"
                "- May include gentle wordplay; keep it tasteful\n"
                "- Avoid sarcasm; stay brand-safe\n"
                "- Keep punctuation moderate"
            )
        # Neutral or unknown
        return (
            "- Use clear and neutral wording\n"
            "- Avoid slang and exclamation marks\n"
            "- Emphasize benefits succinctly"
        )
    
    def generate_ads(self, platform: str, geo: str, language: str, tone: str, 
                     keywords: str, constraints: str, n_variants: int, localization_notes: str = "") -> Dict[str, Any]:
        """Generate ad copy variants"""
        try:
            # Build prompt
            prompt = self._build_prompt(platform, geo, language, tone, keywords, 
                                       constraints, n_variants, localization_notes)
            
            # Generate using appropriate API
            if self.use_responses:
                return self._generate_with_responses_api(prompt, n_variants, language, tone)
            else:
                return self._generate_with_chat_completions(prompt, n_variants, language, tone)
                
        except Exception as e:
            logger.error(f"Ad generation failed: {e}")
            return {"ok": False, "error": str(e)}
    
    def generate_headlines(self, templates: List[Dict], article_data: Dict, n_variants: int) -> Dict[str, Any]:
        """Generate headlines using templates and article data - PARALLEL PROCESSING"""
        try:
            import concurrent.futures
            import threading
            
            results = []
            
            def process_template(template):
                """Process a single template - thread-safe"""
                try:
                    # Build prompt for this template
                    prompt = self._build_headline_prompt(template, article_data, n_variants)
                    
                    # Generate headlines for this template
                    template_result = self._generate_headlines_for_template(prompt, template, n_variants, article_data['language_code'])
                    
                    if template_result.get('ok'):
                        return template_result.get('headlines', [])
                    else:
                        logger.warning(f"Template {template.get('name', 'Unknown')} failed: {template_result.get('error', 'Unknown error')}")
                        return []
                except Exception as e:
                    logger.error(f"Error processing template {template.get('name', 'Unknown')}: {e}")
                    return []
            
            # Process templates in parallel with ThreadPoolExecutor
            logger.info(f"🚀 Processing {len(templates)} templates in PARALLEL...")
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(16, len(templates))) as executor:
                # Submit all templates for processing
                future_to_template = {executor.submit(process_template, template): template for template in templates}
                
                # Collect results as they complete
                for future in concurrent.futures.as_completed(future_to_template):
                    template = future_to_template[future]
                    try:
                        template_headlines = future.result()
                        results.extend(template_headlines)
                        logger.info(f"✅ Template '{template.get('name', 'Unknown')}' completed: {len(template_headlines)} headlines")
                    except Exception as e:
                        logger.error(f"❌ Template '{template.get('name', 'Unknown')}' failed: {e}")
            
            logger.info(f"🎉 PARALLEL processing completed: {len(results)} total headlines from {len(templates)} templates")
            
            return {
                "ok": True,
                "headlines": results,
                "article_title": article_data.get('title', ''),
                "article_language": article_data.get('language', ''),
                "templates_used": [t['name'] for t in templates]
            }
            
        except Exception as e:
            logger.error(f"Error generating headlines: {e}")
            return {"ok": False, "error": str(e)}
    
    def _build_prompt(self, platform: str, geo: str, language: str, tone: str, 
                     keywords: str, constraints: str, n_variants: int, localization_notes: str) -> str:
        """Build the generation prompt"""
        language_names = {
            'he': 'Hebrew',
            'en': 'English', 
            'ar': 'Arabic',
            'ru': 'Russian',
            'es': 'Spanish',
            'fr': 'French'
        }
        
        lang_name = language_names.get(language, language)
        localized_ctas = self._get_localized_ctas(language)
        cta_list_str = ", ".join(localized_ctas)
        tone_guide = self._tone_guidelines(tone, language)
        
        return f"""Generate {n_variants} ad copy variants for {platform} targeting {geo} in {lang_name}.

Platform: {platform}
Target Geography: {geo}
Language: {lang_name} (code: {language})
Tone: {tone}
Keywords: {keywords}
Constraints: {constraints}
Localization notes: {localization_notes}

Requirements:
- Headlines: max 70 characters, compelling and platform-appropriate
- Primary text: max 200 characters, natural and engaging
- Description: max 200 characters, supporting details (optional)
- CTA: must be one of (localized to the output language): {cta_list_str}
- All text must be in {lang_name}
- Avoid absolute claims and risky terms
- Make each variant unique but consistent with the brand voice
- Ensure compliance with {platform} advertising policies

 Style and Tone Guide (MANDATORY):
 {tone_guide}
 - Do not deviate from the specified tone even if keywords suggest otherwise
 - Keep tone consistent across headline, primary text, description

Generate exactly {n_variants} variants with diverse approaches while maintaining consistency."""

    def _build_headline_prompt(self, template: Dict, article_data: Dict, n_variants: int) -> str:
        """Build headline generation prompt using template and article data"""
        language_code = article_data.get('language_code', 'en')
        language_name = self._get_language_name(language_code)
        
        # Extract year from article content
        article_year = self._extract_year_from_article(article_data)
        
        # Log for debugging
        logger.info(f"Building prompt for language: {language_code} ({language_name})")
        logger.info(f"Article title: {article_data.get('title', '')}")
        logger.info(f"Extracted year from article: {article_year}")
        
        # Get compliance constraints
        compliance_rules = self._get_compliance_rules(language_code)
        
        # Build prompt in target language when possible, fallback to English for complex instructions
        if language_code == 'he':
            return self._build_hebrew_prompt(template, article_data, n_variants, compliance_rules)
        elif language_code == 'ar':
            return self._build_arabic_prompt(template, article_data, n_variants, compliance_rules)
        elif language_code == 'ru':
            return self._build_russian_prompt(template, article_data, n_variants, compliance_rules)
        elif language_code == 'es':
            return self._build_spanish_prompt(template, article_data, n_variants, compliance_rules)
        elif language_code == 'fr':
            return self._build_french_prompt(template, article_data, n_variants, compliance_rules)
        elif language_code == 'de':
            return self._build_german_prompt(template, article_data, n_variants, compliance_rules)
        elif language_code == 'ko':
            return self._build_korean_prompt(template, article_data, n_variants, compliance_rules)
        else:
            # Default English prompt for other languages
            return self._build_english_prompt(template, article_data, n_variants, compliance_rules, language_name)

    def _extract_year_from_article(self, article_data: Dict) -> str:
        """Extract the most relevant year from article content"""
        import re
        from datetime import datetime
        
        current_year = datetime.now().year
        
        # Combine title and content for year detection
        text = f"{article_data.get('title', '')} {article_data.get('content', '')[:3000]}"
        
        # Find all 4-digit years between 2020 and current_year+1
        years = re.findall(r'\b(20[2-9][0-9])\b', text)
        
        if not years:
            # No year found, use current year
            logger.info(f"No year found in article, using current year: {current_year}")
            return str(current_year)
        
        # Count occurrences
        year_counts = {}
        for year in years:
            year_int = int(year)
            # Only count years between 2020 and current_year+1
            if 2020 <= year_int <= current_year + 1:
                year_counts[year] = year_counts.get(year, 0) + 1
        
        if not year_counts:
            return str(current_year)
        
        # Prefer the most mentioned year
        most_common_year = max(year_counts.keys(), key=lambda y: year_counts[y])
        
        # If 2026 appears but 2025 is more common or article is clearly about 2025, prefer 2025
        if most_common_year == '2026' and '2025' in year_counts:
            # Check if 2025 is in the title (stronger signal)
            if '2025' in article_data.get('title', ''):
                most_common_year = '2025'
            # Or if 2025 appears at least half as often
            elif year_counts.get('2025', 0) >= year_counts.get('2026', 0) / 2:
                most_common_year = '2025'
        
        logger.info(f"Year counts in article: {year_counts}, selected: {most_common_year}")
        return most_common_year

    def _get_language_name(self, language_code: str) -> str:
        """Get language name from code using comprehensive mapping"""
        language_names = {
            'he': 'Hebrew',
            'en': 'English', 
            'ar': 'Arabic',
            'ru': 'Russian',
            'es': 'Spanish',
            'fr': 'French',
            'de': 'German',
            'it': 'Italian',
            'pt': 'Portuguese',
            'ko': 'Korean',
            'ja': 'Japanese',
            'zh': 'Chinese',
            'sv': 'Swedish',
            'da': 'Danish',
            'no': 'Norwegian',
            'fi': 'Finnish',
            'pl': 'Polish',
            'nl': 'Dutch',
            'cs': 'Czech',
            'hu': 'Hungarian',
            'ro': 'Romanian',
            'bg': 'Bulgarian',
            'el': 'Greek',
            'tr': 'Turkish',
            'uk': 'Ukrainian',
            'hr': 'Croatian',
            'sr': 'Serbian',
            'sl': 'Slovenian',
            'sk': 'Slovak',
            'lt': 'Lithuanian',
            'lv': 'Latvian',
            'et': 'Estonian',
            'th': 'Thai',
            'vi': 'Vietnamese',
            'hi': 'Hindi',
            'bn': 'Bengali',
            'ur': 'Urdu',
            'fa': 'Persian',
            'id': 'Indonesian',
            'ms': 'Malay'
        }
        return language_names.get(language_code.lower(), language_code.title())

    def _build_hebrew_prompt(self, template: Dict, article_data: Dict, n_variants: int, compliance_rules: str) -> str:
        """Build prompt in Hebrew"""
        # Get more content for better context
        content_preview = article_data.get('content', '')[:2500]  # Increased from 1000 to 2500
        article_year = self._extract_year_from_article(article_data)
        
        return f"""חובה: צור {n_variants} כותרות מושכות בעברית בלבד באמצעות התבנית והמידע על הכתבה הבאים.

⚠️ הוראה קריטית לגבי שנה: השתמש בשנה {article_year} בלבד! אל תשתמש בשנה 2026 אלא אם הכתבה עוסקת במפורש ב-2026.

=== פרטי התבנית ===
שם התבנית: {template['name']}
תיאור התבנית: {template['description']}

=== מידע מפורט על הכתבה ===
כותרת מקורית: {article_data.get('title', '')}
URL המקור: {article_data.get('url', '')}
שפה מזוהה: {article_data.get('language', '')} ({article_data.get('language_code', '')})
מדינה מזוהה: {article_data.get('detected_country', 'לא זוהתה')}

תוכן הכתבה המלא:
{content_preview}
{'...' if len(article_data.get('content', '')) > 2500 else ''}

=== דרישות טכניות חובה ===
- צור בדיוק {n_variants} כותרות ייחודיות ושונות זו מזו
- כל כותרת חייבת להיות עד 70 תווים (כולל רווחים)
- כל הכותרות חייבות להיות בעברית בלבד - אסור לערבב שפות
- עקוב בדיוק אחר סגנון התבנית וגישתה
- הפוך את הכותרות למושכות, מעניינות ומעוררות סקרנות
- ודא שהכותרות רלוונטיות ומדויקות לתוכן הכתבה
- שמור על הקשר התרבותי והלשוני הישראלי
- הכותרות צריכות לעודד קליק אבל ללא clickbait מוגזם

=== פוליסי פרסום מלא ומפורט ===
{compliance_rules}

=== הוראות התבנית המפורטות והמלאות ===
{template['prompt']}

=== הוראות יצירה סופיות ===
1. קרא בעיון את כל תוכן הכתבה, הפוליסי והוראות התבנית
2. הבן את מטרת התבנית וסגנונה המדויק
3. צור {n_variants} כותרות שונות שעוקבות בדיוק אחר התבנית
4. ודא שכל כותרת רלוונטית לתוכן, מושכת לקריאה ועומדת בפוליסי
5. בדוק שכל כותרת עומדת בכל כללי התאימות והפוליסי המפורטים
6. החזר את התוצאות בפורמט JSON: {{"headlines": ["כותרת 1", "כותרת 2", ...]}}

חשוב ביותר: כל הכותרות חייבות להיות בעברית בלבד, לעקוב בדיוק אחר הוראות התבנית המלאות, ולעמוד בכל כללי הפוליסי המפורטים לעיל."""

    def _build_arabic_prompt(self, template: Dict, article_data: Dict, n_variants: int, compliance_rules: str) -> str:
        """Build prompt in Arabic"""
        article_year = self._extract_year_from_article(article_data)
        return f"""إلزامي: أنشئ {n_variants} عناوين جذابة باللغة العربية فقط باستخدام القالب ومعلومات المقال التالية.

⚠️ تعليمات السنة الحاسمة: استخدم السنة {article_year} فقط! لا تستخدم 2026 إلا إذا كان المقال يتحدث صراحة عن 2026.

القالب: {template['name']}
وصف القالب: {template['description']}
تعليمات القالب: {template['prompt']}

معلومات المقال:
العنوان الأصلي: {article_data.get('title', '')}
ملخص المحتوى: {article_data.get('content', '')[:1000]}...

المتطلبات الإلزامية:
- أنشئ بالضبط {n_variants} عناوين فريدة
- يجب أن يكون كل عنوان بحد أقصى 70 حرفاً
- جميع العناوين يجب أن تكون باللغة العربية فقط
- اتبع أسلوب القالب ونهجه
- اجعل العناوين جذابة ومثيرة للاهتمام
- تأكد من أن العناوين ذات صلة بمحتوى المقال
- حافظ على السياق الثقافي واللغوي للمقال الأصلي

قواعد الامتثال (إلزامية):
- تجنب الادعاءات المطلقة والمبالغات (الأفضل، المثالي، المضمون إلخ)
- لا ادعاءات طبية أو صحية بدون تحفظات مناسبة
- تجنب إثارة الخوف أو الضغط العاجل المفرط
- لا معلومات مضللة أو كاذبة
- احترم الحساسيات الثقافية
- اتبع معايير الإعلان واللوائح
- حافظ على المحتوى المناسب للعائلة

تعليمات القالب:
{template['prompt']}

مهم: أنشئ {n_variants} عناوين تتبع أسلوب القالب وذات صلة بمحتوى المقال. جميع العناوين يجب أن تكون باللغة العربية."""

    def _build_russian_prompt(self, template: Dict, article_data: Dict, n_variants: int, compliance_rules: str) -> str:
        """Build prompt in Russian"""
        article_year = self._extract_year_from_article(article_data)
        return f"""Обязательно: Создайте {n_variants} привлекательных заголовков только на русском языке, используя следующий шаблон и информацию о статье.

⚠️ КРИТИЧЕСКАЯ ИНСТРУКЦИЯ ПО ГОДУ: Используйте только год {article_year}! НЕ используйте 2026, если статья не посвящена явно 2026 году.

Шаблон: {template['name']}
Описание шаблона: {template['description']}
Инструкции шаблона: {template['prompt']}

Информация о статье:
Оригинальный заголовок: {article_data.get('title', '')}
Краткое содержание: {article_data.get('content', '')[:1000]}...

Обязательные требования:
- Создайте ровно {n_variants} уникальных заголовков
- Каждый заголовок должен быть максимум 70 символов
- ВСЕ заголовки ДОЛЖНЫ быть написаны только на русском языке
- Следуйте стилю и подходу шаблона
- Сделайте заголовки привлекательными и интересными
- Убедитесь, что заголовки соответствуют содержанию статьи
- Сохраняйте культурный и языковой контекст оригинальной статьи

Правила соответствия (обязательно):
- Избегайте абсолютных утверждений и превосходных степеней (лучший, идеальный, гарантированный и т.д.)
- Никаких медицинских или оздоровительных утверждений без соответствующих оговорок
- Избегайте нагнетания страха или чрезмерного срочного давления
- Никакой вводящей в заблуждение или ложной информации
- Уважайте культурные особенности
- Следуйте рекламным стандартам и правилам
- Поддерживайте семейный контент

Инструкции шаблона:
{template['prompt']}

Важно: Создайте {n_variants} заголовков, которые следуют стилю шаблона и соответствуют содержанию статьи. Все заголовки должны быть на русском языке."""

    def _build_spanish_prompt(self, template: Dict, article_data: Dict, n_variants: int, compliance_rules: str) -> str:
        """Build prompt in Spanish"""
        article_year = self._extract_year_from_article(article_data)
        return f"""Obligatorio: Crea {n_variants} titulares atractivos solo en español usando la siguiente plantilla e información del artículo.

⚠️ INSTRUCCIÓN CRÍTICA SOBRE EL AÑO: ¡Usa el año {article_year} ÚNICAMENTE! NO uses 2026 a menos que el artículo trate explícitamente sobre 2026.

Plantilla: {template['name']}
Descripción de la plantilla: {template['description']}
Instrucciones de la plantilla: {template['prompt']}

Información del artículo:
Título original: {article_data.get('title', '')}
Resumen del contenido: {article_data.get('content', '')[:1000]}...

Requisitos obligatorios:
- Crea exactamente {n_variants} titulares únicos
- Cada titular debe tener máximo 70 caracteres
- TODOS los titulares DEBEN estar escritos solo en español
- Sigue el estilo y enfoque de la plantilla
- Haz que los titulares sean atractivos e interesantes
- Asegúrate de que los titulares sean relevantes al contenido del artículo
- Mantén el contexto cultural y lingüístico del artículo original

Reglas de cumplimiento (obligatorio):
- Evita afirmaciones absolutas y superlativos (mejor, perfecto, garantizado, etc.)
- No hagas afirmaciones médicas o de salud sin las advertencias apropiadas
- Evita generar miedo o presión urgente excesiva
- No incluyas información engañosa o falsa
- Respeta las sensibilidades culturales
- Sigue los estándares publicitarios y regulaciones
- Mantén el contenido apropiado para familias

Instrucciones de la plantilla:
{template['prompt']}

Importante: Crea {n_variants} titulares que sigan el estilo de la plantilla y sean relevantes al contenido del artículo. Todos los titulares deben estar en español."""

    def _build_french_prompt(self, template: Dict, article_data: Dict, n_variants: int, compliance_rules: str) -> str:
        """Build prompt in French"""
        article_year = self._extract_year_from_article(article_data)
        return f"""Obligatoire: Créez {n_variants} titres attrayants uniquement en français en utilisant le modèle et les informations d'article suivants.

⚠️ INSTRUCTION CRITIQUE SUR L'ANNÉE: Utilisez l'année {article_year} UNIQUEMENT! N'utilisez PAS 2026 sauf si l'article traite explicitement de 2026.

Modèle: {template['name']}
Description du modèle: {template['description']}
Instructions du modèle: {template['prompt']}

Informations sur l'article:
Titre original: {article_data.get('title', '')}
Résumé du contenu: {article_data.get('content', '')[:1000]}...

Exigences obligatoires:
- Créez exactement {n_variants} titres uniques
- Chaque titre doit faire maximum 70 caractères
- TOUS les titres DOIVENT être écrits uniquement en français
- Suivez le style et l'approche du modèle
- Rendez les titres attrayants et intéressants
- Assurez-vous que les titres sont pertinents au contenu de l'article
- Maintenez le contexte culturel et linguistique de l'article original

Règles de conformité (obligatoire):
- Évitez les affirmations absolues et les superlatifs (meilleur, parfait, garanti, etc.)
- Pas d'affirmations médicales ou de santé sans avertissements appropriés
- Évitez de susciter la peur ou une pression urgente excessive
- Pas d'informations trompeuses ou fausses
- Respectez les sensibilités culturelles
- Suivez les normes publicitaires et réglementations
- Maintenez un contenu approprié pour les familles

Instructions du modèle:
{template['prompt']}

Important: Créez {n_variants} titres qui suivent le style du modèle et sont pertinents au contenu de l'article. Tous les titres doivent être en français."""

    def _build_german_prompt(self, template: Dict, article_data: Dict, n_variants: int, compliance_rules: str) -> str:
        """Build prompt in German"""
        article_year = self._extract_year_from_article(article_data)
        return f"""Verpflichtend: Erstellen Sie {n_variants} ansprechende Schlagzeilen nur auf Deutsch unter Verwendung der folgenden Vorlage und Artikelinformationen.

⚠️ KRITISCHE JAHRESANWEISUNG: Verwenden Sie NUR das Jahr {article_year}! Verwenden Sie NICHT 2026, es sei denn, der Artikel behandelt ausdrücklich 2026.

Vorlage: {template['name']}
Vorlagenbeschreibung: {template['description']}
Vorlagenanweisungen: {template['prompt']}

Artikelinformationen:
Originaltitel: {article_data.get('title', '')}
Inhaltszusammenfassung: {article_data.get('content', '')[:1000]}...

Verpflichtende Anforderungen:
- Erstellen Sie genau {n_variants} einzigartige Schlagzeilen
- Jede Schlagzeile muss maximal 70 Zeichen haben
- ALLE Schlagzeilen MÜSSEN nur auf Deutsch geschrieben werden
- Folgen Sie dem Stil und Ansatz der Vorlage
- Machen Sie die Schlagzeilen ansprechend und interessant
- Stellen Sie sicher, dass die Schlagzeilen zum Artikelinhalt passen
- Bewahren Sie den kulturellen und sprachlichen Kontext des ursprünglichen Artikels

Compliance-Regeln (verpflichtend):
- Vermeiden Sie absolute Behauptungen und Superlative (beste, perfekt, garantiert, etc.)
- Keine medizinischen oder gesundheitlichen Behauptungen ohne entsprechende Vorbehalte
- Vermeiden Sie Angstmacherei oder übermäßigen dringenden Druck
- Keine irreführenden oder falschen Informationen
- Respektieren Sie kulturelle Empfindlichkeiten
- Befolgen Sie Werbestandards und Vorschriften
- Halten Sie den Inhalt familienfreundlich

Vorlagenanweisungen:
{template['prompt']}

Wichtig: Erstellen Sie {n_variants} Schlagzeilen, die dem Vorlagenstil folgen und zum Artikelinhalt passen. Alle Schlagzeilen müssen auf Deutsch sein."""

    def _build_korean_prompt(self, template: Dict, article_data: Dict, n_variants: int, compliance_rules: str) -> str:
        """Build prompt in Korean"""
        content_preview = article_data.get('content', '')[:2500]
        article_year = self._extract_year_from_article(article_data)
        
        return f"""필수: 다음 템플릿과 기사 정보를 사용하여 한국어로만 {n_variants}개의 매력적인 헤드라인을 생성하세요.

⚠️ 중요한 연도 지침: {article_year}년만 사용하세요! 기사가 명시적으로 2026년에 대해 논의하지 않는 한 2026을 사용하지 마세요.

=== 템플릿 세부정보 ===
템플릿 이름: {template['name']}
템플릿 설명: {template['description']}

=== 상세한 기사 정보 ===
원본 제목: {article_data.get('title', '')}
출처 URL: {article_data.get('url', '')}
감지된 언어: {article_data.get('language', '')} ({article_data.get('language_code', '')})
감지된 국가: {article_data.get('detected_country', '감지되지 않음')}

전체 기사 내용:
{content_preview}
{'...' if len(article_data.get('content', '')) > 2500 else ''}

=== 필수 기술 요구사항 ===
- 정확히 {n_variants}개의 고유하고 다른 헤드라인을 생성하세요
- 각 헤드라인은 최대 70자(공백 포함)여야 합니다
- 모든 헤드라인은 반드시 한국어로만 작성되어야 합니다
- 영어를 사용하거나 언어를 혼합하지 마세요
- 템플릿 스타일과 접근 방식을 정확히 따르세요
- 헤드라인을 매력적이고 흥미롭고 호기심을 유발하도록 만드세요
- 헤드라인이 기사 내용과 관련성이 있고 정확한지 확인하세요
- 한국의 문화적, 언어적 맥락을 유지하세요
- 헤드라인은 클릭을 유도해야 하지만 과도한 클릭베이트는 피하세요

=== 규정 준수 및 광고 정책 (절대 필수) ===
{compliance_rules}

=== 상세한 템플릿 지침 ===
{template['prompt']}

=== 최종 생성 지침 ===
1. 전체 기사 내용과 맥락을 주의 깊게 읽으세요
2. 템플릿의 목적과 스타일을 이해하세요
3. 템플릿을 따라 {n_variants}개의 다른 헤드라인을 생성하세요
4. 각 헤드라인이 내용과 관련이 있고 읽기에 매력적인지 확인하세요
5. 각 헤드라인이 모든 규정 준수 규칙을 충족하는지 확인하세요
6. JSON 형식으로 결과를 반환하세요: {{"headlines": ["헤드라인 1", "헤드라인 2", ...]}}

가장 중요: 모든 헤드라인은 한국어로만 작성되어야 하며 위에 자세히 설명된 모든 규정 준수 및 정책 규칙을 준수해야 합니다."""

    def _build_english_prompt(self, template: Dict, article_data: Dict, n_variants: int, compliance_rules: str, language_name: str) -> str:
        """Build prompt in English for other languages"""
        # Get more content for better context
        content_preview = article_data.get('content', '')[:2500]  # Increased from 1000 to 2500
        article_year = self._extract_year_from_article(article_data)
        
        return f"""CRITICAL: Generate {n_variants} compelling headlines EXCLUSIVELY in {language_name} language. DO NOT use English or any other language. Write ONLY in {language_name}.

⚠️ CRITICAL YEAR INSTRUCTION: Use year {article_year} ONLY! Do NOT use 2026 unless the article explicitly discusses 2026 content.

=== TEMPLATE DETAILS ===
Template Name: {template['name']}
Template Description: {template['description']}
Template Instructions: {template['prompt']}

=== DETAILED ARTICLE INFORMATION ===
Original Title: {article_data.get('title', '')}
Source URL: {article_data.get('url', '')}
Detected Language: {article_data.get('language', '')} ({article_data.get('language_code', '')})
Detected Country: {article_data.get('detected_country', 'Not detected')}

Full Article Content:
{content_preview}
{'...' if len(article_data.get('content', '')) > 2500 else ''}

=== MANDATORY TECHNICAL REQUIREMENTS ===
- Generate exactly {n_variants} unique and different headlines
- Each headline must be maximum 70 characters (including spaces)
- ALL headlines MUST be written in {language_name} language ONLY
- Do NOT use English or mix languages if target language is different
- Follow the template style and approach precisely
- Make headlines compelling, interesting and curiosity-inducing
- Ensure headlines are relevant and accurate to the article content
- Maintain the cultural and linguistic context of the target language
- Headlines should encourage clicks but avoid excessive clickbait

=== COMPLIANCE AND ADVERTISING POLICY (ABSOLUTELY MANDATORY) ===
Forbidden Words and Phrases:
- Avoid absolute claims: "best", "perfect", "100% guaranteed", "cheapest"
- Don't claim: "completely free", "no cost", "free" (unless truly free)
- Avoid: "revolutionary", "miracle", "magic", "secret", "exclusive"
- Forbidden: "instant", "within minutes", "now or never", "last chance"

Medical and Health Claims:
- No medical claims without proper disclaimers
- Don't promise health or medical results
- Avoid claims about healing, treatment or medical effects

Ethical Principles:
- No misleading, false or exaggerated information
- Avoid fear-mongering, anxiety or excessive psychological pressure
- Respect cultural, religious and ethnic sensitivities
- Keep content family-friendly and appropriate for all ages
- Follow local and international advertising standards
- Avoid political or controversial content

=== DETAILED TEMPLATE INSTRUCTIONS ===
{template['prompt']}

=== FINAL GENERATION INSTRUCTIONS ===
1. Read the entire article content and context carefully
2. Understand the template's purpose and style
3. Generate {n_variants} different headlines following the template
4. Ensure each headline is relevant to content and attractive to read
5. Check that each headline meets all compliance rules
6. Return results in JSON format: {{"headlines": ["headline 1", "headline 2", ...]}}

MOST IMPORTANT: All headlines must be in {language_name} language only and comply with all compliance and policy rules detailed above."""

    def _load_policy_content(self) -> str:
        """Load policy content from policy.xlsx"""
        try:
            policy_path = Path(__file__).resolve().parent / 'policy.xlsx'
            if not policy_path.exists():
                logger.warning(f"Policy file not found: {policy_path}")
                return self._get_default_policy()
            
            df = pd.read_excel(str(policy_path))
            
            # Combine all policy content from both columns
            policy_parts = []
            for col in df.columns:
                for value in df[col].dropna():
                    if isinstance(value, str) and len(value.strip()) > 10:
                        policy_parts.append(value.strip())
            
            full_policy = "\n\n".join(policy_parts)
            logger.info(f"Loaded policy content: {len(full_policy)} characters")
            return full_policy
            
        except Exception as e:
            logger.error(f"Failed to load policy content: {e}")
            return self._get_default_policy()
    
    def _get_default_policy(self) -> str:
        """Default policy rules if file is not available"""
        return """GOOGLE ADS TRAFFIC SOURCE CREATIVE POLICY
Ad content must be clear, honest, and compliant with all advertising standards.

STRICT POLICY REQUIREMENTS:
1. Clear and Honest Communication
2. No Misleading Claims
3. Appropriate Content Standards
4. Cultural Sensitivity
5. Legal Compliance
6. Family-Friendly Content

PROHIBITED CONTENT:
- Absolute claims (best, perfect, guaranteed)
- Medical claims without disclaimers
- Fear-mongering tactics
- Misleading information
- Adult content
- Political content
- Discriminatory content

REQUIRED STANDARDS:
- Truthful advertising
- Clear value propositions
- Appropriate language
- Cultural respect
- Legal compliance
- Ethical practices"""

    def _get_compliance_rules(self, language_code: str) -> str:
        """Get comprehensive compliance rules including policy content"""
        return self.policy_content

    def _generate_headlines_for_template(self, prompt: str, template: Dict, n_variants: int, language_code: str) -> Dict[str, Any]:
        """Generate headlines for a specific template"""
        try:
            # Get language name from article data or normalize the code
            language_name = self._get_language_name(language_code)
            system_message = f"You are an expert multilingual headline writer specializing in creating compelling, compliant headlines in {language_name}. You MUST write headlines in {language_name} language only. Always respond with valid JSON using EXACTLY this format: {{\"headlines\": [\"headline1\", \"headline2\", ...]}}. Use the English word 'headlines' as the JSON key, but write the actual headline content in {language_name}."
            
            # Log prompt to file
            self._log_prompt_to_file(
                prompt_type="HEADLINE_GENERATION",
                system_message=system_message,
                user_message=prompt,
                model=self.model
            )
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": system_message
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.8,
                max_tokens=1000
            )
            
            content = response.choices[0].message.content
            logger.info(f"OpenAI raw response: {content[:500]}...")
            
            try:
                data = json.loads(content)
                logger.info(f"Parsed JSON keys: {list(data.keys())}")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                logger.error(f"Raw content: {content}")
                return {"ok": False, "error": f"Invalid JSON response from OpenAI: {e}"}
            
            # Extract headlines from response (try multiple possible keys)
            headlines = []
            headlines_data = None
            
            # Try different possible keys for headlines
            possible_keys = ['headlines', 'titulares', 'títulos', 'manchetes', 'rubriques', 'titoli', 'schlagzeilen', 'koppen', 'rubriker', 'overskrifter']
            
            for key in possible_keys:
                if key in data and isinstance(data[key], list):
                    headlines_data = data[key]
                    logger.info(f"Found headlines under key: '{key}'")
                    break
            
            if headlines_data:
                logger.info(f"Processing {len(headlines_data)} headlines from OpenAI")
                for i, headline in enumerate(headlines_data[:n_variants]):
                    if headline and str(headline).strip():  # Skip empty headlines
                        headlines.append({
                            'headline': str(headline).strip(),
                            'template': template['name'],
                            'template_id': template['id'],
                            'language_code': language_code,
                            'character_count': len(str(headline).strip())
                        })
                logger.info(f"Successfully extracted {len(headlines)} valid headlines")
            else:
                logger.warning(f"No headlines found in response. Available keys: {list(data.keys())}")
                logger.warning(f"Full response data: {data}")
                return {"ok": False, "error": "No headlines found in OpenAI response"}
            
            return {
                "ok": True,
                "headlines": headlines
            }
                
        except Exception as e:
            logger.error(f"Failed to generate headlines for template {template['name']}: {e}")
            return {"ok": False, "error": str(e)}

    def _get_localized_ctas(self, language_code: str) -> List[str]:
        return self.cta_translations.get(language_code, self.cta_translations['en'])

    def _normalize_cta(self, cta_value: str, language_code: str) -> str:
        if not cta_value:
            return self._get_localized_ctas(language_code)[0]
        localized = self._get_localized_ctas(language_code)
        english = self.cta_translations['en']
        # Exact or case-insensitive match in localized list
        for opt in localized:
            if cta_value.strip().lower() == opt.lower():
                return opt
        # If it matches an English option, map by index
        for idx, opt in enumerate(english):
            if cta_value.strip().lower() == opt.lower():
                return localized[idx] if idx < len(localized) else localized[0]
        # Fallback to first localized
        return localized[0]
    
    def _generate_with_responses_api(self, prompt: str, n_variants: int, language: str, tone: str) -> Dict[str, Any]:
        """Generate using Responses API with structured outputs"""
        # This would use the Responses API when available
        # For now, fall back to Chat Completions
        return self._generate_with_chat_completions(prompt, n_variants, language, tone)
    
    def _generate_with_chat_completions(self, prompt: str, n_variants: int, language: str, tone: str) -> Dict[str, Any]:
        """Generate using Chat Completions with JSON format"""
        try:
            system_message = "You are an expert copywriter specializing in multi-platform advertising. Generate ad copy that is compliant, engaging, and platform-appropriate. Always respond with valid JSON matching the required schema."
            
            # Log prompt to file
            self._log_prompt_to_file(
                prompt_type="AD_GENERATION",
                system_message=system_message,
                user_message=prompt,
                model=self.model
            )
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": system_message
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.7,
                max_tokens=2000
            )
            
            content = response.choices[0].message.content
            data = json.loads(content)
            
            # Validate and normalize response
            if 'ad_assets' in data and isinstance(data['ad_assets'], list):
                normalized_assets = []
                for asset in data['ad_assets'][:n_variants]:
                    asset = dict(asset)
                    asset['cta'] = self._normalize_cta(asset.get('cta', ''), language)
                    asset.setdefault('language_code', language)
                    asset.setdefault('tone', tone)
                    normalized_assets.append(asset)
                return {
                    "ok": True,
                    "ad_assets": normalized_assets
                }
            else:
                # If response doesn't match expected format, try to extract ads
                return self._extract_ads_from_response(content, n_variants, language, tone)
                
        except Exception as e:
            logger.error(f"Chat Completions error: {e}")
            return {"ok": False, "error": f"Generation failed: {str(e)}"}
    
    def _extract_ads_from_response(self, content: str, n_variants: int, language: str, tone: str) -> Dict[str, Any]:
        """Extract ad assets from response if schema doesn't match"""
        try:
            # Try to parse as JSON first
            data = json.loads(content)
            
            # Look for common patterns
            if isinstance(data, list):
                ad_assets = data[:n_variants]
            elif isinstance(data, dict) and 'ads' in data:
                ad_assets = data['ads'][:n_variants]
            elif isinstance(data, dict) and 'variants' in data:
                ad_assets = data['variants'][:n_variants]
            else:
                # Create a single ad from the response
                ad_assets = [{
                    "headline": str(data.get('headline', 'Generated Ad')),
                    "primary_text": str(data.get('primary_text', 'Generated content')),
                    "description": str(data.get('description', '')),
                    "cta": data.get('cta', 'Learn More'),
                    "language_code": data.get('language_code', 'en'),
                    "tone": data.get('tone', 'Neutral')
                }]
            
            # Normalize CTAs and metadata
            normalized_assets = []
            for asset in ad_assets[:n_variants]:
                asset = dict(asset)
                asset['cta'] = self._normalize_cta(asset.get('cta', ''), language)
                asset.setdefault('language_code', language)
                asset.setdefault('tone', tone)
                normalized_assets.append(asset)
            return {
                "ok": True,
                "ad_assets": normalized_assets
            }
            
        except Exception as e:
            logger.error(f"Failed to extract ads from response: {e}")
            return {"ok": False, "error": f"Failed to parse response: {str(e)}"}
    
    def check_moderation(self, ad_asset: Dict[str, Any]) -> Dict[str, Any]:
        """Check content moderation using OpenAI's moderation API"""
        try:
            # Combine all text fields
            combined_text = f"{ad_asset.get('headline', '')} {ad_asset.get('primary_text', '')} {ad_asset.get('description', '')}"
            
            if not combined_text.strip():
                return {"flagged": False, "categories": {}}
            
            response = self.client.moderations.create(
                input=combined_text,
                model=self.moderation_model
            )
            
            result = response.results[0]
            return {
                "flagged": result.flagged,
                "categories": {
                    category: getattr(result.categories, category) 
                    for category in ['hate', 'hate_threatening', 'self_harm', 'sexual', 'sexual_minors', 
                                   'violence', 'violence_graphic', 'harassment', 'harassment_threatening']
                }
            }
            
        except Exception as e:
            logger.error(f"Moderation check failed: {e}")
            return {"flagged": False, "categories": {}, "error": str(e)}

