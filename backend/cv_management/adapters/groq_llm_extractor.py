import os
import json
import re
import time
from groq import Groq
from typing import Dict, Any
from cv_management.ports.llm_extractor import ILLMExtractor

class GroqLLMExtractor(ILLMExtractor):
    def __init__(self):
        self.client = Groq(api_key=os.environ["GROQ_API_KEY"])
        primary_model = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")
        fallback_models = ["openai/gpt-oss-20b", "qwen/qwen3.8-27b", "qwen/qwen3.6-27b"]
        seen = set()
        self.models = []
        for m in [primary_model] + fallback_models:
            if m not in seen:
                seen.add(m)
                self.models.append(m)
        self.max_retries = 2
        self.timeout = 45  # seconds

    def extract_structured_data(self, raw_text: str) -> Dict[str, Any]:
        system_prompt = """Tu es un assistant expert RH et extracteur de données de CV.
Ta tâche est d'analyser le texte brut d'un CV et d'extraire TOUTES les informations clés sans aucune omission :
- Nom complet, email, téléphone, localisation
- TOUTES les expériences professionnelles (titre, entreprise, dates, description, is_current)
- TOUTE la formation (diplômes, institutions, domaine, dates)
- TOUTES les compétences techniques mentionnées (langages, frameworks, outils, bases de données, DevOps, IA)
- TOUTES les certifications (nom, organisme, date)

Règles importantes :
- Réponds UNIQUEMENT avec un objet JSON valide suivant la structure exacte demandée.
- N'inclus aucun texte explicatif avant ou après le JSON.
- N'omet aucunes compétences ni formations inscrites dans le texte."""

        user_prompt = f"""Voici le texte brut d'un CV :
---
{raw_text}
---

Réponds UNIQUEMENT avec un objet JSON respectant exactement cette structure :
{{
  "full_name": "string",
  "email": "string ou null",
  "phone": "string ou null",
  "location": "string ou null",
  "experiences": [
    {{"title": "string", "company": "string", "start_date": "string", "end_date": "string ou null", "description": "string ou null", "is_current": true ou false}}
  ],
  "education": [
    {{"degree": "string", "institution": "string", "field": "string ou null", "start_date": "string", "end_date": "string ou null"}}
  ],
  "skills": ["string"],
  "certifications": [
    {{"name": "string", "issuer": "string ou null", "date_obtained": "string ou null", "expiry_date": "string ou null"}}
  ]
}}"""

        last_exception = None
        for model in self.models:
            for attempt in range(self.max_retries):
                try:
                    response = self.client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        response_format={"type": "json_object"},
                        max_tokens=4096,
                        temperature=0.1,
                        timeout=self.timeout,
                    )
                    raw_json = response.choices[0].message.content
                    parsed_data = json.loads(raw_json)
                    
                    # Ensure safety fallback enrichment if skills/education are empty
                    parsed_data = self._enrich_fallbacks_if_needed(parsed_data, raw_text)
                    return parsed_data
                except json.JSONDecodeError as e:
                    last_exception = e
                    if attempt < self.max_retries - 1:
                        time.sleep(1)
                        continue
                except Exception as e:
                    last_exception = e
                    if "429" in str(e) or "rate_limit" in str(e).lower():
                        print(f"[GroqLLMExtractor] Model {model} rate-limited, switching to next model...")
                        break
                    if attempt < self.max_retries - 1:
                        time.sleep(1)
                        continue

        raise RuntimeError(f"LLM extraction failed across all models: {str(last_exception)}")

    def _enrich_fallbacks_if_needed(self, data: Dict[str, Any], raw_text: str) -> Dict[str, Any]:
        """Fallback regex extraction to guarantee skills are never missed."""
        if not data.get("skills"):
            tech_keywords = [
                'Java', 'Python', 'JavaScript', 'TypeScript', 'SQL', 'HTML', 'CSS',
                'Spring Boot', 'Angular', 'React', 'Next.js', 'FastAPI', 'Symfony', 'JavaFX',
                'Docker', 'Kubernetes', 'PostgreSQL', 'MySQL', 'MongoDB', 'AWS', 'Azure',
                'Git', 'Jenkins', 'Agile', 'Scrum', 'DevOps', 'NLP', 'LLMs', 'RAG'
            ]
            found_skills = [k for k in tech_keywords if re.search(r'\b' + re.escape(k) + r'\b', raw_text, re.IGNORECASE)]
            if found_skills:
                data["skills"] = list(set(found_skills))
        return data
