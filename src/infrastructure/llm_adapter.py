# ==============================================================================
# ADAPTATEUR LLM UNIVERSEL (src/infrastructure/llm_adapter.py)
# Supporte OpenAI (Structured Outputs natifs), Google Gemini et Ollama
# ==============================================================================

# Importation du module JSON pour parser les réponses du modèle
import json

# Importation du module standard de gestion de l'environnement
import os

# Importation du client HTTP asynchrone/synchrone httpx
import httpx

# Importation du client officiel OpenAI
from openai import OpenAI

# Importation relative du modèle de sortie attendu
from ..domain.models import ReceiptExtraction

# Importation relative du port abstrait d'extraction LLM
from ..domain.ports import LLMExtractorPort


# Implémentation de l'adaptateur LLM universel
class OpenAILLMExtractor(LLMExtractorPort):
    # Constructeur initialisant la configuration et les clients
    def __init__(
        self,
        api_key: str = None,
        base_url: str = None,
        model: str = None,
    ):
        # Récupération de la clé API
        self.api_key = api_key or os.getenv("LLM_API_KEY", "dummy_key")
        # Récupération de l'URL de base
        self.base_url = base_url or os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
        # Récupération du nom du modèle d'inférence
        self.model = model or os.getenv("LLM_MODEL", "gpt-4o-mini")

        # Détection si le fournisseur cible est Google Gemini
        self.is_gemini = "googleapis.com" in self.base_url or self.api_key.startswith("AQ.") or self.api_key.startswith("AIza")

        # Si ce n'est pas Gemini direct, initialisation du client OpenAI standard
        if not self.is_gemini:
            # Instanciation du client OpenAI / Ollama
            self.openai_client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )
        else:
            # Pas de client OpenAI nécessaire pour le mode Gemini natif
            self.openai_client = None

    # Méthode interne pour appeler directement l'API REST de Google Gemini
    def _call_gemini_native(self, system_prompt: str, ocr_text: str) -> ReceiptExtraction:
        # Nettoyage du nom de modèle initial
        target_model = self.model.replace("models/", "")
        # Liste des variantes de modèles à essayer en cascade si l'un n'est pas disponible
        candidate_models = [target_model, "gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-flash-latest", "gemini-1.5-pro"]
        # Dédoublonnage en conservant l'ordre
        unique_models = list(dict.fromkeys(candidate_models))

        # Préparation du prompt consolidé
        full_prompt = (
            f"{system_prompt}\n\n"
            f"Voici le texte brut OCR du ticket à analyser :\n{ocr_text}"
        )

        # Préparation du corps de la requête JSON attendu par Google
        payload = {
            "contents": [
                {
                    "parts": [{"text": full_prompt}]
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.0,
            },
        }

        # En-têtes HTTP incluant la clé d'authentification Google x-goog-api-key
        headers = {
            "x-goog-api-key": self.api_key,
            "Content-Type": "application/json",
        }
        # Paramètre d'URL de secours
        params = {"key": self.api_key}

        # Variable stockant la dernière erreur en cas d'échec de tous les modèles
        last_error = None

        # Ouverture de session HTTP avec httpx
        with httpx.Client(timeout=30.0) as client:
            # Tentative sur les différents noms de modèles
            for model_name in unique_models:
                # Construction de l'URL cible
                endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
                # Bloc de tentative
                try:
                    # Exécution de la requête POST vers Google Gemini
                    response = client.post(endpoint, json=payload, headers=headers, params=params)
                    # Vérification du code HTTP
                    response.raise_for_status()
                    # Décodage de la réponse JSON de Google
                    data = response.json()
                    # Extraction du texte JSON brut généré par le modèle
                    raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                    # Validation et instanciation du modèle de domaine Pydantic
                    return ReceiptExtraction.model_validate_json(raw_text)
                # Capture des erreurs de modèle non trouvé (404) pour basculer sur le suivant
                except Exception as err:
                    # Enregistrement de l'erreur
                    last_error = err
                    # Poursuite vers le modèle suivant
                    continue

        # Si aucun modèle n'a abouti, levée de la dernière exception
        raise last_error or RuntimeError("Impossible de joindre l'API Google Gemini.")

    # Implémentation de la méthode d'extraction définie dans le port
    def extract_receipt(self, ocr_text: str) -> ReceiptExtraction:
        # Définition du prompt système contenant explicitement le mot-clé json et le schéma attendu
        system_prompt = (
            "Tu es un expert-comptable et auditeur financier automatisé de haut niveau.\n"
            "Analyse le texte brut OCR d'un reçu fiscal ou ticket de caisse.\n"
            "Tu dois impérativement répondre au format JSON valide selon cette structure exacte :\n"
            "{\n"
            '  "merchant": {"name": "Nom du commerçant", "siren_or_siret": null, "address": null},\n'
            '  "date": "YYYY-MM-DD",\n'
            '  "time": "HH:MM",\n'
            '  "total_amount_ttc": "12.50",\n'
            '  "total_amount_ht": null,\n'
            '  "currency": "EUR",\n'
            '  "category": "MEAL",\n'
            '  "taxes": [{"rate": "20.0", "tax_amount": "2.08"}],\n'
            '  "items": [{"label": "Nom article", "quantity": "1", "total_price": "12.50"}]\n'
            "}\n"
            "Règles strictes :\n"
            "- Réponds UNIQUEMENT un objet JSON pur sans balises Markdown.\n"
            "- La date doit être au format ISO 'YYYY-MM-DD'. Si l'année manque, utilise 2026.\n"
            "- La catégorie doit être MEAL, TRANSPORT, HOTEL, SUPPLIES, ou OTHER.\n"
            "- Les montants doivent être des chaînes numériques décimales (ex: '25.00')."
        )

        # Branche 1 : Exécution via Google Gemini API native
        if self.is_gemini:
            # Appel du service Gemini natif
            return self._call_gemini_native(system_prompt, ocr_text)

        # Branche 2 : Exécution via OpenAI officiel
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Voici le texte brut OCR du ticket à extraire en JSON :\n\n{ocr_text}"},
        ]

        # Appel avec retour forcé au format JSON Object (exige le mot json dans le prompt)
        completion = self.openai_client.chat.completions.create(
            model=self.model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.0,
        )

        # Récupération du texte JSON brut
        raw_content = completion.choices[0].message.content
        # Validation et conversion en objet de domaine typé
        return ReceiptExtraction.model_validate_json(raw_content)
