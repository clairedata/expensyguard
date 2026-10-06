# ==============================================================================
# FICHIER D'INITIALISATION DE LA COUCHE INFRASTRUCTURE (src/infrastructure/__init__.py)
# ==============================================================================

# Importation relative de l'adaptateur de base de données SQLite
from .db_repository import SQLiteReceiptRepository

# Importation relative de l'adaptateur LLM compatible OpenAI / Ollama
from .llm_adapter import OpenAILLMExtractor

# Importation relative de l'adaptateur OCR OpenCV + EasyOCR
from .ocr_adapter import EasyOCREngine

# Importation relative de l'adaptateur pour l'API Recherche Entreprises
from .registry_api import SireneRegistryAPI

# Exposition des adaptateurs d'infrastructure
__all__ = [
    "SQLiteReceiptRepository",
    "OpenAILLMExtractor",
    "EasyOCREngine",
    "SireneRegistryAPI",
]
