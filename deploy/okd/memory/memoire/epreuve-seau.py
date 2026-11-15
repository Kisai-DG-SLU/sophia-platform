"""Épreuve de la politique du seau de la mémoire, depuis le pod du service et avec SA propre identité S3.

Lire le code du stockage ne remplace pas l'épreuve : sans le refus de toute suppression sous valide/, on s'arrête
et on passe à deux seaux. Lancée par l'administrateur, avant tout dépôt (README.md, étape 5 bis) :
    oc -n sophia-memory exec -i deploy/sophia-memoire -- python3 - < epreuve-seau.py
N'affiche aucune valeur (ni clé, ni contenu) ; écrit deux témoins de quelques octets sous `epreuve/`, l'un effacé,
l'autre (sous valide/) laissé tel quel puisque le service ne peut pas l'effacer : c'est la preuve.
"""
import os
import sys
import uuid

import botocore.config
import botocore.session
from botocore.exceptions import ClientError

client = botocore.session.get_session().create_client(
    "s3", endpoint_url=os.environ["S3_URL"], region_name="us-east-1", aws_access_key_id=os.environ["S3_CLE"],
    aws_secret_access_key=os.environ["S3_SECRET"], verify=os.environ.get("S3_CA", True),
    config=botocore.config.Config(signature_version="s3v4", s3={"addressing_style": "path"},
                                  request_checksum_calculation="when_required",
                                  response_checksum_validation="when_required"))
SEAU = "memoire"
ecarts = []


def code(e: Exception) -> str:
    return e.response.get("Error", {}).get("Code", "?") if isinstance(e, ClientError) else type(e).__name__


def doit_refuser(libelle: str, appel) -> None:
    try:
        r = appel()
    except ClientError as e:
        if code(e) in ("AccessDenied", "403"):
            print(f"{libelle} : refusé : ok")
            return
        ecarts.append(libelle)
        print(f"{libelle} : erreur inattendue {code(e)} : ÉCART")
        return
    # Une suppression groupée répond 200 et range le refus dans « Errors ».
    erreurs = (r or {}).get("Errors") or []
    if erreurs and all(x.get("Code") == "AccessDenied" for x in erreurs):
        print(f"{libelle} : refusé (dans Errors) : ok")
        return
    ecarts.append(libelle)
    print(f"{libelle} : PERMIS : ÉCART")


def doit_permettre(libelle: str, appel):
    try:
        r = appel()
        print(f"{libelle} : permis : ok")
        return r
    except ClientError as e:
        ecarts.append(libelle)
        print(f"{libelle} : refusé ({code(e)}) : ÉCART")
        return None


try:
    statut = client.get_bucket_versioning(Bucket=SEAU).get("Status")
    print(f"versionnement : {statut} : {'ok' if statut == 'Enabled' else 'ÉCART'}")
    if statut != "Enabled":
        ecarts.append("versionnement")
except ClientError as e:
    print(f"versionnement : lecture refusée à cette identité ({code(e)}) ; voir le journal du Job s3-init-memoire")

temoin = f"valide/epreuve/{uuid.uuid4()}.txt"
r = doit_permettre("écrire sous valide/", lambda: client.put_object(Bucket=SEAU, Key=temoin, Body=b"epreuve"))
version = (r or {}).get("VersionId")
if version and version != "null":
    doit_refuser("supprimer une version sous valide/",
                 lambda: client.delete_object(Bucket=SEAU, Key=temoin, VersionId=version))
    doit_refuser("supprimer une version sous valide/ (suppression groupée)",
                 lambda: client.delete_objects(Bucket=SEAU, Delete={"Objects": [{"Key": temoin, "VersionId": version}]}))
    doit_refuser("poser un marqueur de suppression sous valide/", lambda: client.delete_object(Bucket=SEAU, Key=temoin))
    reste = client.list_object_versions(Bucket=SEAU, Prefix=temoin).get("Versions") or []
    print(f"témoin sous valide/ toujours là : {'ok' if any(v.get('VersionId') == version for v in reste) else 'ÉCART'}")
    if not any(v.get("VersionId") == version for v in reste):
        ecarts.append("témoin disparu")
else:
    ecarts.append("version du témoin")
    print("version S3 du témoin absente (seau non versionné ?) : ÉCART")

doit_refuser("suspendre le versionnement", lambda: client.put_bucket_versioning(
    Bucket=SEAU, VersioningConfiguration={"Status": "Suspended"}))
doit_refuser("poser un cycle de vie", lambda: client.put_bucket_lifecycle_configuration(
    Bucket=SEAU, LifecycleConfiguration={"Rules": [{"ID": "epreuve", "Status": "Enabled", "Filter": {"Prefix": ""},
                                                    "NoncurrentVersionExpiration": {"NoncurrentDays": 1}}]}))
doit_refuser("changer la politique", lambda: client.delete_bucket_policy(Bucket=SEAU))

attente = f"attente/epreuve/{uuid.uuid4()}.txt"
r = doit_permettre("écrire sous attente/", lambda: client.put_object(Bucket=SEAU, Key=attente, Body=b"epreuve"))
if r and r.get("VersionId") not in (None, "null"):
    doit_permettre("supprimer une version sous attente/",
                   lambda: client.delete_object(Bucket=SEAU, Key=attente, VersionId=r["VersionId"]))

print("politique du seau : conforme" if not ecarts else f"politique du seau : {len(ecarts)} ÉCART(S), s'arrêter")
sys.exit(1 if ecarts else 0)
