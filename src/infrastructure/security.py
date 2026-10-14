# ==============================================================================
# SÉCURITÉ & AUTHENTIFICATION JWT (src/infrastructure/security.py)
# Gestion des jetons d'accès, des rôles (admin / user) et du hachage de mots de passe
# ==============================================================================

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt
from pydantic import BaseModel

# Clé secrète de signature JWT et configuration
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "expensyguard_ultra_secret_jwt_key_2026_qra")
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 heures de validité


# Modèle pour les données de retour d'authentification
class UserPublic(BaseModel):
    username: str
    name: str
    email: str
    role: str  # 'admin' ou 'user'


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


# Fonction utilitaire pour hacher un mot de passe avec sel cryptographique
def hash_password(password: str, salt: Optional[str] = None) -> str:
    if not salt:
        salt = secrets.token_hex(16)
    # Hachage PBKDF2-HMAC-SHA256 standard
    hashed = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100000,
    ).hex()
    return f"{salt}${hashed}"


# Vérification de mot de passe sécurisée
def verify_password(plain_password: str, stored_hash: str) -> bool:
    if "$" not in stored_hash:
        return plain_password == stored_hash
    salt, _ = stored_hash.split("$", 1)
    return hash_password(plain_password, salt) == stored_hash


# Référentiel des utilisateurs prédéfinis avec leurs rôles
USERS_DB: Dict[str, Dict[str, Any]] = {
    "admin": {
        "username": "admin",
        "name": "Alexandre Dupont (Admin)",
        "email": "admin@expensyguard.com",
        "role": "admin",
        "password_hash": hash_password("admin123", "fixed_salt_admin"),
    },
    "user": {
        "username": "user",
        "name": "Sophie Martin (Collaborateur)",
        "email": "user@expensyguard.com",
        "role": "user",
        "password_hash": hash_password("user123", "fixed_salt_user"),
    },
}


# Création d'un token d'accès JWT
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": now})
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


# Vérification et décodage d'un jeton JWT
def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except Exception:
        return None


# Authentification d'un utilisateur par identifiant / mot de passe
def authenticate_user(username: str, password: str) -> Optional[UserPublic]:
    user_record = USERS_DB.get(username.strip().lower())
    if not user_record:
        return None
    if not verify_password(password, user_record["password_hash"]):
        return None
    return UserPublic(
        username=user_record["username"],
        name=user_record["name"],
        email=user_record["email"],
        role=user_record["role"],
    )
