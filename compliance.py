import re
import logging
from typing import Dict, List, Any, Tuple
from pathlib import Path
import pandas as pd

logger = logging.getLogger(__name__)

class ComplianceChecker:
    def __init__(self):
        # Base term lists for compliance checking
        self.english_terms = {
            'strong': ['free', 'guaranteed', 'best', '#1', 'always', 'never', 'life-changing', 'miracle', 'risk-free'],
            'absolute': ['best', '#1', 'always', 'never', 'cheapest', 'lowest price'],
            'risky': ['affordable', 'cheap', 'reliable', 'proven', 'trusted', 'leading']
        }
        
        self.hebrew_terms = {
            'strong': ['חינם', 'חינמי', 'חינמית', 'מובטח', 'הכי טוב', 'מספר 1', 'תמיד', 'לעולם לא', 'משנה חיים', 'פלא', 'ללא סיכון'],
            'absolute': ['הכי טוב', 'מספר 1', 'תמיד', 'לעולם לא', 'הזול ביותר', 'המחיר הנמוך ביותר'],
            'risky': ['זול', 'אמין', 'מוכח', 'מוביל', 'מקצועי']
        }
        
        # Platform-specific terms
        self.platform_terms = {
            'Facebook': {
                'en': ['click here', 'click now', 'limited time'],
                'he': ['קליק כאן', 'לחץ כאן', 'זמן מוגבל']
            },
            'Google': {
                'en': ['ad', 'advertisement', 'promo'],
                'he': ['פרסומת', 'קידום', 'הנחה']
            },
            'Instagram': {
                'en': ['swipe up', 'link in bio'],
                'he': ['החלק למעלה', 'קישור בביוגרפיה']
            }
        }
        
        # Load policy workbook if available
        self.policy_df = self._load_policy_workbook()

        # Risk scoring weights
        self.risk_weights = {
            'strong': 25,
            'absolute': 20,
            'risky': 10
        }
        
        # Safe alternatives for suggestions
        self.suggestions = {
            'free': 'limited-time offer',
            'חינם': 'הצעה מיוחדת',
            'guaranteed': 'proven track record',
            'מובטח': 'ניסיון מוכח',
            'best': 'leading',
            'הכי טוב': 'מוביל',
            '#1': 'top-rated',
            'מספר 1': 'דירוג גבוה',
            'always': 'consistently',
            'תמיד': 'באופן עקבי',
            'never': 'rarely',
            'לעולם לא': 'לעיתים רחוקות',
            'cheap': 'affordable',
            'זול': 'במחיר סביר',
            'lowest price': 'competitive pricing',
            'המחיר הנמוך ביותר': 'תמחור תחרותי'
        }
    
    def check_compliance(self, ad_asset: Dict[str, Any], platform: str, geo: str, language: str) -> Dict[str, Any]:
        """Run comprehensive compliance check on ad asset"""
        try:
            # Extract text fields
            text_fields = {
                'headline': ad_asset.get('headline', ''),
                'primary_text': ad_asset.get('primary_text', ''),
                'description': ad_asset.get('description', ''),
                'cta': ad_asset.get('cta', '')
            }
            
            # Check each field
            highlights = {}
            all_flags = []
            total_risk_score = 0
            
            for field_name, text in text_fields.items():
                field_flags, field_highlights, field_risk = self._check_text_field(
                    text, platform, geo, language
                )
                
                highlights[field_name] = field_highlights
                all_flags.extend(field_flags)
                total_risk_score += field_risk
            
            # Clamp risk score to 0-100
            risk_score = min(100, max(0, total_risk_score))
            
            # Generate suggestions
            suggestions = self._generate_suggestions(all_flags, language)

            # Fetch relevant policy excerpts
            policy_refs = self._get_policy_references(
                flags=all_flags,
                platform=platform,
                geo=geo,
                language=language,
                limit=5
            )
            
            return {
                "risk_score": risk_score,
                "flags": list(set(all_flags)),  # Remove duplicates
                "highlights": highlights,
                "suggestions": suggestions,
                "policy_references": policy_refs,
                "platform": platform,
                "geo": geo,
                "language": language
            }
            
        except Exception as e:
            logger.error(f"Compliance check failed: {e}")
            return {
                "risk_score": 0,
                "flags": [],
                "highlights": {},
                "suggestions": [],
                "policy_references": [],
                "platform": platform,
                "geo": geo,
                "language": language,
                "error": str(e)
            }
    
    def _check_text_field(self, text: str, platform: str, geo: str, language: str) -> Tuple[List[str], List[Dict], int]:
        """Check a single text field for compliance issues"""
        if not text:
            return [], [], 0
        
        flags = []
        highlights = []
        risk_score = 0
        
        # Get appropriate term lists
        terms = self.english_terms if language == 'en' else self.hebrew_terms
        platform_terms = self.platform_terms.get(platform, {}).get(language, [])
        
        # Check each category of terms
        for category, term_list in terms.items():
            for term in term_list:
                if self._find_term_in_text(text, term):
                    flags.append(term)
                    highlights.append({
                        "term": term,
                        "start": text.lower().find(term.lower()),
                        "end": text.lower().find(term.lower()) + len(term)
                    })
                    risk_score += self.risk_weights[category]
        
        # Check platform-specific terms
        for term in platform_terms:
            if self._find_term_in_text(text, term):
                flags.append(term)
                highlights.append({
                    "term": term,
                    "start": text.lower().find(term.lower()),
                    "end": text.lower().find(term.lower()) + len(term)
                })
                risk_score += 5  # Lower weight for platform terms
        
        return flags, highlights, risk_score
    
    def _find_term_in_text(self, text: str, term: str) -> bool:
        """Find term in text with case-insensitive matching"""
        if not text or not term:
            return False
        
        # Use word boundaries for better matching
        pattern = r'\b' + re.escape(term.lower()) + r'\b'
        return bool(re.search(pattern, text.lower()))
    
    def _generate_suggestions(self, flags: List[str], language: str) -> List[str]:
        """Generate suggestions for flagged terms"""
        suggestions = []
        
        for flag in flags:
            if flag in self.suggestions:
                suggestion = f"Avoid '{flag}' → try '{self.suggestions[flag]}'"
                suggestions.append(suggestion)
            else:
                # Generic suggestion
                if language == 'he':
                    suggestion = f"שקול להחליף את '{flag}' במילים פחות מוחלטות"
                else:
                    suggestion = f"Consider replacing '{flag}' with less absolute terms"
                suggestions.append(suggestion)
        
        return suggestions

    # ------------------------- Policy Integration -------------------------
    def _load_policy_workbook(self) -> pd.DataFrame:
        """Attempt to load policy.xlsx and return a unified DataFrame.
        Heuristics:
        - Read all sheets and concatenate rows.
        - Normalize column names to lowercase for matching.
        Returns empty DataFrame if file is missing or unreadable.
        """
        try:
            policy_path = Path(__file__).resolve().parent / 'policy.xlsx'
            if not policy_path.exists():
                logger.warning(f"Policy file not found: {policy_path}")
                return pd.DataFrame()
            xls = pd.ExcelFile(str(policy_path))
            frames: List[pd.DataFrame] = []
            for sheet in xls.sheet_names:
                try:
                    df = pd.read_excel(str(policy_path), sheet_name=sheet)
                    df.columns = [str(c).strip() for c in df.columns]
                    frames.append(df)
                except Exception as e:
                    logger.warning(f"Failed reading sheet '{sheet}' in policy.xlsx: {e}")
            if not frames:
                return pd.DataFrame()
            full = pd.concat(frames, ignore_index=True)
            # Add lowercase helper columns for robust matching
            for col in list(full.columns):
                full[f"__lc__{col}"] = full[col].astype(str).str.lower()
            return full
        except Exception as e:
            logger.error(f"Failed to load policy workbook: {e}")
            return pd.DataFrame()

    def _get_policy_references(self, flags: List[str], platform: str, geo: str, language: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Return relevant policy excerpts prioritized by:
        1) Rows matching platform / geo / language (if columns exist)
        2) Rows whose text contains any flagged terms
        3) Fallback: top rows with any policy-like text
        Output format: [{excerpt, sheet, row_index, matched_terms, columns_used}]
        """
        try:
            if self.policy_df is None or self.policy_df.empty:
                return []

            df = self.policy_df
            candidates = df.copy()

            # Identify likely columns
            col_names = [str(c) for c in candidates.columns]
            lc_cols = [c for c in col_names if c.startswith("__lc__")]
            # Heuristic finders
            def find_cols(keywords: List[str]) -> List[str]:
                found = []
                for c in col_names:
                    lc = c.lower()
                    if any(k in lc for k in keywords) and not c.startswith("__lc__"):
                        found.append(c)
                return found

            platform_cols = find_cols(['platform', 'channel'])
            geo_cols = find_cols(['geo', 'country', 'market', 'region'])
            lang_cols = find_cols(['language', 'lang', 'שפה'])
            text_cols = find_cols(['policy', 'rule', 'guideline', 'text', 'description', 'notes', 'requirement'])
            if not text_cols:
                # Fallback: all non-helper columns are potential text columns
                text_cols = [c for c in col_names if not c.startswith("__lc__")]

            # Apply filters for platform / geo / language where possible
            def apply_filter(cols: List[str], value: str, frame: pd.DataFrame) -> pd.DataFrame:
                if not cols or not value:
                    return frame
                v = str(value).strip().lower()
                mask = None
                for c in cols:
                    lc_c = f"__lc__{c}"
                    if lc_c in frame.columns:
                        col_mask = frame[lc_c].str.contains(re.escape(v), na=False)
                        mask = col_mask if mask is None else (mask | col_mask)
                return frame[mask] if mask is not None else frame

            filtered = apply_filter(platform_cols, platform, candidates)
            filtered = apply_filter(geo_cols, geo, filtered)
            filtered = apply_filter(lang_cols, language, filtered)

            # Score by presence of flagged terms in text columns
            def row_score(row) -> Tuple[int, List[str]]:
                matched = set()
                text_blob = " \n ".join(str(row.get(c, "")) for c in text_cols)
                lc_blob = text_blob.lower()
                for term in flags:
                    t = str(term).strip().lower()
                    if t and re.search(r"\b" + re.escape(t) + r"\b", lc_blob):
                        matched.add(term)
                return (len(matched), sorted(list(matched)))

            scored_rows: List[Tuple[int, int, List[str]]] = []  # (score, index, matched_terms)
            for idx, row in filtered.iterrows():
                s, matched_terms = row_score(row)
                scored_rows.append((s, idx, matched_terms))

            # Sort by score desc, keep top N
            scored_rows.sort(key=lambda x: x[0], reverse=True)
            top_rows = scored_rows[:limit]

            # If not enough high-score rows, backfill from unfiltered
            if len(top_rows) < limit:
                for idx, row in candidates.iterrows():
                    s, matched_terms = row_score(row)
                    if s == 0:
                        continue
                    if all(idx != r[1] for r in top_rows):
                        top_rows.append((s, idx, matched_terms))
                        if len(top_rows) >= limit:
                            break

            # Build references
            references: List[Dict[str, Any]] = []
            for score, idx, matched_terms in top_rows:
                if idx not in candidates.index:
                    continue
                row = candidates.loc[idx]
                excerpt_parts = []
                for c in text_cols:
                    val = row.get(c)
                    if isinstance(val, str) and val.strip():
                        excerpt_parts.append(f"{c}: {val.strip()}")
                excerpt = " \n ".join(excerpt_parts)[:1000]  # cap length
                references.append({
                    "row_index": int(idx),
                    "matched_terms": matched_terms,
                    "columns_used": text_cols[:],
                    "excerpt": excerpt
                })

            return references[:limit]
        except Exception as e:
            logger.error(f"Failed to derive policy references: {e}")
            return []

