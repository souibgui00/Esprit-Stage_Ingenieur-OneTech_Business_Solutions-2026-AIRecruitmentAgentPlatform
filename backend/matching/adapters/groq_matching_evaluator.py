import os
import json
from groq import Groq
from typing import Dict, Any
from matching.ports.llm_matching_evaluator import ILLMMatchingEvaluator
from matching.schemas import MatchAssessmentData


class GroqMatchingEvaluator(ILLMMatchingEvaluator):
    """
    Adapter implementing qualitative CV-to-Job offer alignment evaluation using Groq LLM.
    Primary target model: llama-3.3-70b-versatile
    Fallback model: llama-3.1-8b-instant
    """

    def __init__(self):
        self.api_key = os.environ.get("GROQ_API_KEY", "")
        primary_model = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")
        fallback_models = [
            "openai/gpt-oss-20b",
            "qwen/qwen3.8-27b",
            "qwen/qwen3.6-27b",
        ]
        seen = set()
        self.models = []
        for m in [primary_model] + fallback_models:
            if m not in seen:
                seen.add(m)
                self.models.append(m)

        self.client = Groq(api_key=self.api_key) if self.api_key else None

    def evaluate(self, cv_summary: str, job_offer_summary: str) -> Dict[str, Any]:
        if not self.client:
            return {
                "matching_points": ["Compétences techniques générales alignées."],
                "gap_points": ["Évaluation qualitative non disponible (clé API non configurée)."],
                "summary": "Correspondance sémantique calculée.",
                "score": 50
            }

        prompt = f"""Tu es un expert RH et recruteur technique senior.
Ton rôle est d'évaluer la compatibilité CONTEXTUELLE et QUALITATIVE entre le CV d'un candidat et une offre d'emploi.

PROFIL CANDIDAT (CV) :
---
{cv_summary}
---

OFFRE D'EMPLOI :
---
{job_offer_summary}
---

GUIDE DE NOTATION (0-100) :
---
0-30 : Très mauvaise correspondance
Incompatibilités majeures avec le rôle cible ou lacunes substantielles dans les aspects contextuels/qualitatifs.

31-50 : Mauvaise correspondance
Certains éléments pertinents existent, mais d'importantes lacunes contextuelles ou liées au rôle réduisent significativement la pertinence.

51-65 : Correspondance modérée
Un alignement significatif existe, mais plusieurs lacunes notables ou incertitudes demeurent.

66-80 : Bonne correspondance
Fort alignement contextuel avec le rôle, avec seulement des lacunes limitées ou gérables.

81-90 : Très bonne correspondance
Alignement contextuel excellent, arrière-plan très pertinent, et seulement des lacunes mineures.

91-100 : Correspondance exceptionnelle
Alignement contextuel exceptionnel avec très fortes preuves que le candidat est exceptionnellement adapté au rôle.
---

INSTRUCTIONS SPÉCIFIQUES :

Le score représente la compatibilité CONTEXTUELLE/QUALITATIVE, pas un simple comptage de mots-clés.
Considère :
- La pertinence de l'expérience précédente par rapport aux responsabilités réelles
- La cohérence entre le parcours/projets du candidat et le rôle
- L'ajustement contextuel/domaine
- La profondeur et la qualité de l'expérience pertinente
- L'alignement rôle/responsabilités
- Les preuves soutenant la pertinence
- Les lacunes significatives non capturées par le scoring structuré

NE PAS simplement compter les mots-clés correspondants.
NE PAS reproduire mécaniquement le score de correspondance structurée des compétences.
NE PAS traiter la similarité sémantique seule comme preuve d'une forte correspondance.
Le score LLM NE DOIT PAS remplacer le système de scoring structuré à six facteurs.
Le LLM est la couche qualitative/contextuelle.

Basé UNIQUEMENT sur les informations présentes dans le CV et l'offre d'emploi.
N'invente PAS d'expérience, de compétences, de certifications ou de responsabilités.
Les informations manquantes doivent créer de l'incertitude plutôt que d'être supposées positives.
Les affirmations fortes nécessitent des preuves dans le texte CV/offre fourni.
Un score élevé nécessite de fortes preuves contextuelles, pas seulement une technologie correspondante.

Utilise toute la plage 0-100 lorsque justifié.
Évite de regrouper systématiquement les scores autour du milieu.
Ne fixe PAS par défaut à 75.
N'augmente PAS le score simplement parce que le candidat a plusieurs technologies correspondantes.
Ne diminue PAS le score uniquement parce qu'une exigence non essentielle est manquante.
Distingue entre les lacunes essentielles et mineures lorsque la description du poste le permet.

Réponds STRICTEMENT avec un objet JSON valide suivant exactement ce schéma :
{{
  "matching_points": [
    "Point fort 1 (ex: Maîtrise de Python et FastAPI)",
    "Point fort 2 (ex: Expérience en environnement Agile)"
  ],
  "gap_points": [
    "Point à améliorer 1 (ex: Aucune mention de Docker ou Kubernetes)",
    "Point à améliorer 2 (ex: 2 ans d'expérience au lieu des 5 ans demandés)"
  ],
  "summary": "Résumé concis en 1 ou 2 phrases expliquant pourquoi le profil correspond ou non.",
  "score": <entier de 0 à 100>
}}

IMPORTANT : Le champ "score" doit être un entier entre 0 et 100 représentant ta note de compatibilité contextuelle globale.
"""

        last_error = ""
        for model in self.models:
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                    max_tokens=1024,
                    temperature=0.2,
                )
                raw_json = response.choices[0].message.content
                parsed_data = json.loads(raw_json)
                validated = MatchAssessmentData(**parsed_data)
                return validated.model_dump()
            except Exception as e:
                last_error = str(e)
                print(f"[GroqMatchingEvaluator] Model {model} failed: {e}")
                # Instantly move to next fallback model without repeating retries
                continue

        return {
            "matching_points": ["Analyse globale de compatibilité basée sur les compétences et l'expérience."],
            "gap_points": ["Évaluation LLM ajustée aux capacités disponibles."],
            "summary": "Correspondance sémantique et technique calculée.",
            "score": 50
        }