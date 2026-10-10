# ==============================================================================
# ADAPTATEUR OCR (src/infrastructure/ocr_adapter.py)
# Prétraitement d'image avec OpenCV et extraction de texte avec EasyOCR
# ==============================================================================

# Importation du module de manipulation d'images OpenCV
import cv2

# Importation du module EasyOCR pour la reconnaissance de caractères multi-langues
import easyocr

# Importation du module NumPy pour la manipulation des matrices de pixels
import numpy as np

# Importation relative du port abstrait de l'OCR défini dans le domaine
from ..domain.ports import OCREnginePort


# Implémentation concrète de l'OCR utilisant EasyOCR et OpenCV
class EasyOCREngine(OCREnginePort):
    # Constructeur initialisant la configuration des langues
    def __init__(self, languages: list[str] = None):
        # Définition des langues par défaut (français et anglais pour les reçus)
        self.selected_langs = languages if languages is not None else ["fr", "en"]
        # Lecteur initialisé à None pour chargement paresseux ultra-rapide au premier besoin
        self._reader = None

    # Propriété avec chargement à la demande (Lazy Loading) pour éviter de bloquer le démarrage du serveur
    @property
    def reader(self) -> easyocr.Reader:
        # Si le modèle n'a pas encore été chargé en mémoire
        if self._reader is None:
            # Instanciation effective du modèle OCR
            self._reader = easyocr.Reader(self.selected_langs, gpu=False)
        # Renvoi de l'instance du lecteur
        return self._reader

    # Méthode interne de prétraitement d'image pour maximiser la lisibilité OCR
    def _preprocess_image(self, image_bytes: bytes) -> np.ndarray:
        # Conversion du flux binaire en tableau d'octets 1D NumPy
        nparr = np.frombuffer(image_bytes, np.uint8)
        # Décodage du buffer binaire en image couleur BGR OpenCV
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        # Vérification si l'image a été correctement décodée
        if image is None:
            # Levée d'erreur explicite en cas de format d'image non valide
            raise ValueError("Impossible de décoder le fichier image fourni.")
        # Conversion de l'image couleur en niveaux de gris
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        # Réduction du bruit numérique par flou gaussien léger
        denoised = cv2.GaussianBlur(gray, (3, 3), 0)
        # Binarisation adaptative pour améliorer le contraste du texte sur fond thermique
        thresholded = cv2.adaptiveThreshold(
            denoised,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            11,
            2,
        )
        # Renvoi de l'image prétraitée sous forme de matrice NumPy
        return thresholded

    # Implémentation de la méthode d'extraction de texte requise par le port OCREnginePort
    def extract_text(self, image_bytes: bytes) -> str:
        # Prétraitement de l'image brute via OpenCV
        preprocessed_img = self._preprocess_image(image_bytes)
        # Exécution de la détection et reconnaissance OCR sur l'image traitée
        results = self.reader.readtext(preprocessed_img, detail=0)
        # Concaténation de toutes les lignes de texte détectées séparées par un saut de ligne
        full_text = "\n".join(results)
        # Nettoyage des espaces superflus en début et fin de chaîne
        return full_text.strip()
