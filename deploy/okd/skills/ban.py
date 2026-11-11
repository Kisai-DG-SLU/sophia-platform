"""Adresses de la Base Adresse Nationale en local : préparation de ban.sqlite et recherche de candidats.

Partagé par geo_build.py (préparation sur le nœud) et par l'application (route /api/adresse/candidats), pour que
le texte indexé et le texte cherché soient normalisés de la même façon. Ce n'est pas comprendre une intention :
un appariement de mots sur une adresse saisie, dont la personne choisit ensuite le bon résultat.

Rien n'est journalisé ici : ni l'adresse cherchée ni les résultats.
"""
import csv
import gzip
import io
import os
import re
import sqlite3
import unicodedata

FICHIER = "ban.sqlite"
# Départements acceptés : 01 à 95 (sauf 20), 2A, 2B, 971 à 976. Une liste donnée au lancement, jamais versionnée.
DEPARTEMENT = re.compile(r"^(0[1-9]|1[0-9]|[3-8][0-9]|9[0-5]|2[1-9]|2A|2B|97[1-6])$")
URL = "https://adresse.data.gouv.fr/data/ban/adresses/latest/csv/adresses-{dep}.csv.gz"

# Abréviations de voie, table fermée, appliquée au texte indexé comme au texte cherché.
ABREVIATIONS = {"r": "rue", "av": "avenue", "ave": "avenue", "bd": "boulevard", "bld": "boulevard",
                "boul": "boulevard", "pl": "place", "imp": "impasse", "all": "allee", "che": "chemin",
                "chem": "chemin", "rte": "route", "sq": "square", "crs": "cours", "fg": "faubourg",
                "qu": "quai", "res": "residence", "lot": "lotissement", "st": "saint", "ste": "sainte"}
# Mots vides retirés de la recherche (gardés dans l'index) : « rue de la paix » trouve « rue paix ».
VIDES = {"de", "la", "le", "les", "du", "des", "l", "d", "a", "au", "aux", "et", "en"}
REPETITIONS = {"bis", "ter", "quater", "quinquies", "a", "b", "c", "d"}


def mots(s: str) -> list:
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return [ABREVIATIONS.get(m, m) for m in re.sub(r"[^a-z0-9]+", " ", s).split()]


# --- Préparation (geo_build.py, sur le nœud) -------------------------------------------------------------------

def construire(out: str, departements: list, lire) -> dict:
    """Construit out/ban.sqlite depuis les CSV de la BAN. `lire(dep)` rend les octets du fichier .csv.gz.
    Rend {dep: nombre d'adresses}. Une erreur arrête tout : geo_build.py ne remplace alors rien."""
    for d in departements:
        if not DEPARTEMENT.match(d):
            raise ValueError(f"département invalide : {d!r}")
    chemin = os.path.join(out, FICHIER)
    if os.path.exists(chemin):
        os.remove(chemin)
    db = sqlite3.connect(chemin)
    db.executescript("""
        PRAGMA journal_mode = OFF; PRAGMA synchronous = OFF;
        CREATE TABLE adresse (id INTEGER PRIMARY KEY, numero INTEGER, rep TEXT, voie TEXT, lieu_dit TEXT,
                              cp TEXT, insee TEXT, commune TEXT, lat REAL, lon REAL, dep TEXT);
        CREATE VIRTUAL TABLE adresse_fts USING fts5(texte, content='', tokenize='unicode61');
        CREATE TABLE meta (cle TEXT PRIMARY KEY, valeur TEXT);
    """)
    comptes = {}
    for dep in departements:
        n = 0
        texte = io.TextIOWrapper(gzip.GzipFile(fileobj=io.BytesIO(lire(dep))), encoding="utf-8")
        for r in csv.DictReader(texte, delimiter=";"):
            try:
                lat, lon = float(r["lat"]), float(r["lon"])
                numero = int(r["numero"]) if (r.get("numero") or "").isdigit() and r["numero"] != "99999" else None
            except (KeyError, ValueError):
                continue
            voie, ld = (r.get("nom_voie") or "").strip(), (r.get("nom_ld") or "").strip()
            cur = db.execute("INSERT INTO adresse (numero, rep, voie, lieu_dit, cp, insee, commune, lat, lon, dep) "
                             "VALUES (?,?,?,?,?,?,?,?,?,?)",
                             (numero, (r.get("rep") or "").strip().lower() or None, voie, ld or None,
                              r.get("code_postal"), r.get("code_insee"), r.get("nom_commune"),
                              round(lat, 6), round(lon, 6), dep))
            db.execute("INSERT INTO adresse_fts (rowid, texte) VALUES (?, ?)",
                       (cur.lastrowid, " ".join(mots(f"{voie} {ld} {r.get('nom_commune')} {r.get('code_postal')}"))))
            n += 1
        if not n:
            raise ValueError(f"département {dep} : aucune adresse lue")
        comptes[dep] = n
    db.execute("CREATE INDEX adresse_cp ON adresse (cp)")
    db.execute("INSERT INTO meta VALUES ('departements', ?)", (",".join(departements),))
    db.commit()
    db.execute("INSERT INTO adresse_fts (adresse_fts) VALUES ('optimize')")
    db.commit()
    db.execute("VACUUM")
    db.close()
    return comptes


# --- Recherche (application) ----------------------------------------------------------------------------------

def ouvrir(geo_dir: str):
    chemin = os.path.join(geo_dir, FICHIER)
    if not os.path.exists(chemin):
        return None
    return sqlite3.connect(f"file:{chemin}?mode=ro&immutable=1", uri=True)


def etat(geo_dir: str) -> dict:
    db = ouvrir(geo_dir)
    if db is None:
        return {"charge": False, "departements": []}
    try:
        deps = (db.execute("SELECT valeur FROM meta WHERE cle = 'departements'").fetchone() or [""])[0]
        n = db.execute("SELECT count(*) FROM adresse").fetchone()[0]
    finally:
        db.close()
    return {"charge": True, "departements": [d for d in deps.split(",") if d], "adresses": n}


def _analyse(q: str):
    """Numéro et indice de répétition en tête, code postal, et les autres mots (sans mots vides)."""
    ms = mots(q)
    numero, rep, cp, reste = None, None, None, []
    for i, m in enumerate(ms):
        if i == 0 and m.isdigit() and len(m) <= 4:
            numero = int(m)
        elif i == 1 and numero is not None and m in REPETITIONS:
            rep = m
        elif len(m) == 5 and m.isdigit() and cp is None:
            cp = m
        elif m not in VIDES:
            reste.append(m)
    return numero, rep, cp, reste


def candidats(geo_dir: str, q: str, nombre: int = 5) -> dict:
    """Adresses candidates pour le texte saisi, les meilleures d'abord. Classement déterministe : code postal
    saisi, numéro exact (puis le plus proche dans la même voie), rang BM25 du texte."""
    q = (q or "")[:200]
    nombre = max(1, min(int(nombre or 5), 10))
    numero, rep, cp, reste = _analyse(q)
    if not reste:
        return {"candidats": [], "info": "adresse trop courte : une voie ou un lieu-dit est attendu"}
    db = ouvrir(geo_dir)
    if db is None:
        return {"candidats": [], "info": "adresses locales non chargées"}
    # Chaque mot doit être présent ; le dernier peut être un début de mot (saisie en cours).
    requete = " ".join(f'"{m}"' for m in reste[:-1]) + f' "{reste[-1]}"*'
    try:
        rows = db.execute(
            "SELECT a.numero, a.rep, a.voie, a.lieu_dit, a.cp, a.insee, a.commune, a.lat, a.lon, bm25(adresse_fts) "
            "FROM adresse_fts JOIN adresse a ON a.id = adresse_fts.rowid "
            "WHERE adresse_fts MATCH ? ORDER BY bm25(adresse_fts) LIMIT 400", (requete,)).fetchall()
    finally:
        db.close()
    meilleurs = {}
    for num, r_, voie, ld, cp_, insee, commune, lat, lon, rang in rows:
        s = 0.5 + (0.2 if cp and cp_ == cp else 0 if cp else 0.1)
        if numero is not None and num is not None:
            s += 0.3 if num == numero and (rep or None) == r_ else 0.25 if num == numero else \
                0.15 / (1 + abs(num - numero))
        cle = (voie, ld, insee)
        if numero is None:                 # sans numéro : une proposition par voie
            num, r_ = None, None
        if cle not in meilleurs or s > meilleurs[cle][0]:
            meilleurs[cle] = (s, rang, num, r_, voie, ld, cp_, insee, commune, lat, lon)
    tri = sorted(meilleurs.values(), key=lambda m: (-m[0], m[1]))[:nombre]
    out = []
    for s, _, num, r_, voie, ld, cp_, insee, commune, lat, lon in tri:
        rue = " ".join(x for x in (str(num) if num is not None else "", r_ or "", voie or ld or "") if x)
        out.append({"libelle": f"{rue}, {cp_} {commune}", "numero": num, "repetition": r_, "voie": voie or None,
                    "lieu_dit": ld, "code_postal": cp_, "code_insee": insee, "commune": commune,
                    "latitude": lat, "longitude": lon, "score": round(min(s, 1.0), 2)})
    return {"candidats": out}
