"""Ordre CREATE ROLE avec un vérificateur SCRAM-SHA-256 calculé ici : le mot de passe n'atteint jamais le serveur.

Le mot de passe est lu sur l'entrée standard (48 caractères hexadécimaux, tels que rangés dans le Secret) ;
l'ordre SQL part sur la sortie standard, vers psql. Même en cas d'erreur journalisée par Postgres
(log_min_error_statement), seul le vérificateur apparaît, comme dans pg_authid.
Usage : … | python3 role-scram.py NOM_DU_ROLE | psql …
"""
import base64
import hashlib
import hmac
import os
import re
import sys

ITERATIONS = 4096  # scram_iterations par défaut de Postgres


def verificateur(mot_de_passe: str, sel: bytes, iterations: int = ITERATIONS) -> str:
    sale = hashlib.pbkdf2_hmac("sha256", mot_de_passe.encode(), sel, iterations)
    cle_client = hmac.new(sale, b"Client Key", hashlib.sha256).digest()
    cle_stockee = hashlib.sha256(cle_client).digest()
    cle_serveur = hmac.new(sale, b"Server Key", hashlib.sha256).digest()
    b64 = lambda b: base64.b64encode(b).decode()
    return f"SCRAM-SHA-256${iterations}:{b64(sel)}${b64(cle_stockee)}:{b64(cle_serveur)}"


def main() -> None:
    if len(sys.argv) != 2 or not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", sys.argv[1]):
        raise SystemExit("usage : … | python3 role-scram.py NOM_DU_ROLE (minuscules, chiffres, _)")
    mot_de_passe = sys.stdin.read()
    # Hexadécimal seul : pas de SASLprep à appliquer, aucune ambiguïté de codage.
    if not re.fullmatch(r"[0-9a-f]{48}", mot_de_passe):
        raise SystemExit("mot de passe attendu : 48 caractères hexadécimaux sur l'entrée standard")
    print(f"CREATE ROLE {sys.argv[1]} LOGIN PASSWORD '{verificateur(mot_de_passe, os.urandom(16))}';")
    print("vérificateur SCRAM-SHA-256 calculé localement", file=sys.stderr)


if __name__ == "__main__":
    main()
