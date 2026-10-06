# ==============================================================================
# ADAPTATEUR REGISTRE DES ENTREPRISES (src/infrastructure/registry_api.py)
# Client asynchrone HTTPX interrogeant l'API publique Recherche Entreprises (SIRENE)
# ==============================================================================

# Importation du module standard de gestion de l'environnement
import os

# Importation des types pour le retour structuré
from typing import Any, Dict

# Importation du client HTTP asynchrone ultra-performant httpx
import httpx

# Importation relative du port d'interrogation de registre
from ..domain.ports import RegistryServicePort


# Implémentation concrète de l'interrogation du registre d'entreprises
class SireneRegistryAPI(RegistryServicePort):
    # Constructeur initialisant l'URL de l'API et le timeout
    def __init__(self, base_url: str = None, timeout: float = 10.0):
        # Configuration de l'URL cible de l'API publique
        self.base_url = base_url or os.getenv(
            "REGISTRY_API_URL", "https://recherche-entreprises.api.gouv.fr"
        )
        # Définition du temps limite de requête HTTP en secondes
        self.timeout = timeout

    # Implémentation de la vérification asynchrone d'un commerçant
    async def verify_merchant(self, query: str) -> Dict[str, Any]:
        # Nettoyage de la chaîne de recherche (suppression des espaces superflus)
        cleaned_query = query.strip()
        # Si la chaîne est vide, renvoyer immédiatement un échec de validation
        if not cleaned_query:
            # Construction d'une réponse de défaut pour requête vide
            return {"is_found": False, "siren": None, "nom_complet": None, "details": "Requête vide"}

        # Construction de l'URL de recherche d'entreprises
        search_endpoint = f"{self.base_url}/search"
        # Préparation des paramètres de requête HTTP GET
        params = {"q": cleaned_query, "per_page": 1}

        # Bloc de capture des exceptions réseau pour garantir la résilience
        try:
            # Ouverture d'une session client asynchrone avec gestion de timeout
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Envoi de la requête GET asynchrone
                response = await client.get(search_endpoint, params=params)
                # Vérification du code HTTP (lève une exception si != 2xx)
                response.raise_for_status()
                # Décodage de la charge utile JSON reçue
                data = response.json()
                # Extraction de la liste des résultats trouvés
                results = data.get("results", [])
                # Vérification de la présence d'au moins une entreprise correspondante
                if results:
                    # Récupération de la première fiche entreprise trouvée
                    top_match = results[0]
                    # Extraction du numéro SIREN (9 chiffres)
                    siren = top_match.get("siren")
                    # Extraction de la dénomination complète officielle
                    nom_complet = top_match.get("nom_complet")
                    # Extraction du statut administratif (A pour Actif)
                    etat_administratif = top_match.get("etat_administratif", "A")
                    # Vérification si l'entreprise est légalement en activité
                    is_active = etat_administratif == "A"
                    # Renvoi des données de validation consolidées
                    return {
                        "is_found": True,
                        "siren": siren,
                        "nom_complet": nom_complet,
                        "is_active": is_active,
                        "raw": top_match,
                    }
                # Cas où aucune entreprise n'a été retournée par le registre
                return {
                    "is_found": False,
                    "siren": None,
                    "nom_complet": None,
                    "is_active": False,
                    "details": "Aucun résultat trouvé dans le registre officiel",
                }
        # Gestion des erreurs de connexion ou d'indisponibilité de l'API
        except Exception as error:
            # Renvoi gracieux d'un rapport d'erreur sans faire crasher le pipeline
            return {
                "is_found": False,
                "siren": None,
                "nom_complet": None,
                "is_active": False,
                "error": str(error),
            }
