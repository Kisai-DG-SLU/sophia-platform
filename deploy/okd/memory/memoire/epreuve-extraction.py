"""Épreuve de l'isolement de l'extraction, lancée DANS le pod d'extraction par l'administrateur (commande complète
dans README.md, étape 6), avec en arguments les adresses à essayer sans DNS (`adresse:port`, lues par oc au moment
de l'épreuve).

Ce qu'un code malveillant exécuté dans l'extraction essaierait : lire l'environnement de tous les processus
visibles, le jeton du compte de service, et joindre Qdrant, le service mémoire, Keycloak, LiteLLM, le DNS,
l'API du cluster et Internet. Les essais par nom échouent d'abord au DNS : seuls les essais par adresse
prouvent l'absence de sortie. N'affiche aucune valeur : des noms de variables, des adresses et des verdicts.
Attendu : chaque ligne d'essai finit par « ok », et la dernière est « D2 : conforme ».

La résolution d'un nom est bornée à RESOLUTION_DELAI secondes, dans un fil à part : le délai de create_connection ne
borne pas getaddrinfo, et avec le DNS refusé chaque nom attendrait les délais du résolveur (ndots 5, suffixes de
recherche, plusieurs essais), une minute ou plus par nom (relevé à une épreuve en service). Un nom non résolu
dans ce délai compte comme injoignable, avec le libellé « DNS refusé ».
"""
import os
import socket
import sys
import threading

# Noms des réglages sensibles du service mémoire et familles de noms de secrets. Pas « KEY » seul : l'image de
# base porte GPG_KEY (empreinte publique de la clé de signature de Python), qui donnerait un faux écart.
SENSIBLES = ("QDRANT", "LITELLM", "_CLE", "API_KEY", "TOKEN", "SECRET", "PASSWORD", "PASSWD", "VALIDEUR", "OIDC",
             "JWKS")
# Au moins : Qdrant, service mémoire, Keycloak, LiteLLM, API par son Service, API sur le nœud, DNS.
ADRESSES_MIN = 7
RESOLUTION_DELAI = 5
CONNEXION_DELAI = 3
ecarts = 0


def verdict(ligne: str, bon: bool) -> None:
    global ecarts
    ecarts += not bon
    print(f"{ligne} : {'ok' if bon else 'ÉCART'}")


noms = set()
pids = [p for p in os.listdir("/proc") if p.isdigit()]
for pid in pids:
    try:
        with open(f"/proc/{pid}/environ", "rb") as f:
            noms |= {v.split(b"=", 1)[0].decode(errors="replace") for v in f.read().split(b"\0") if v}
    except OSError:
        pass
trouves = sorted(n for n in noms if any(s in n.upper() for s in SENSIBLES))
print(f"variables présentes (noms seuls) : {', '.join(sorted(noms)) or 'aucune'}")
verdict(f"processus visibles : {len(pids)} ; variables sensibles : {trouves or 'aucune'}", not trouves)
verdict("jeton de compte de service monté", not os.path.exists("/var/run/secrets/kubernetes.io/serviceaccount"))

cibles = {
    "Qdrant (nom)": ("qdrant-svc.sophia-memory.svc.cluster.local", 6333),
    "service mémoire (nom)": ("sophia-memoire.sophia-memory.svc.cluster.local", 8080),
    "Keycloak (nom)": ("sophia-keycloak-service.sophia-identity.svc.cluster.local", 8080),
    "LiteLLM (nom)": ("litellm-svc.sophia-core.svc.cluster.local", 4000),
    "API du cluster (nom)": ("kubernetes.default.svc", 443),
    "Internet (adresse)": ("1.1.1.1", 443),
}
adresses = [a for a in sys.argv[1:] if ":" in a]
verdict(f"essais par adresse : {len(adresses)}, {ADRESSES_MIN} au moins", len(adresses) >= ADRESSES_MIN)
for a in adresses:
    hote, port = a.rsplit(":", 1)
    cibles[a] = (hote, int(port))
def resoudre(hote: str, port: int):
    """Les adresses de `hote`, ou None s'il n'est pas résolu en RESOLUTION_DELAI secondes (le fil est abandonné)."""
    sortie = {}

    def chercher():
        try:
            sortie["adresses"] = socket.getaddrinfo(hote, port, type=socket.SOCK_STREAM)
        except OSError:
            sortie["adresses"] = []
    fil = threading.Thread(target=chercher, daemon=True)
    fil.start()
    fil.join(RESOLUTION_DELAI)
    return sortie.get("adresses") or None


def joindre(adresses) -> bool:
    for famille, type_, proto, _, adresse in adresses:
        try:
            with socket.socket(famille, type_, proto) as s:
                s.settimeout(CONNEXION_DELAI)
                s.connect(adresse)
                return True
        except OSError:
            continue
    return False


for nom, (hote, port) in cibles.items():
    adresses = resoudre(hote, port)
    if adresses is None:
        verdict(f"{nom} injoignable (DNS refusé)", True)
        continue
    verdict(f"{nom} injoignable", not joindre(adresses))
print("D2 : conforme" if not ecarts else f"D2 : {ecarts} écart(s)")
