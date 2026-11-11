"""Prépare les données géographiques locales de sophia-geo (lancé sur le nœud par fetch-geo-data.sh).

Sources libres, téléchargées depuis le nœud (mise à jour = relancer fetch-geo-data.sh) :
- communes françaises : geo.api.gouv.fr (INSEE, IGN — Licence Ouverte Etalab 2.0) ;
- localités du monde de plus de 1 000 habitants : GeoNames cities1000 (CC BY 4.0), hors France,
  avec leur nom français quand GeoNames en a un (alternateNamesV2, langue « fr » : « Londres »,
  « Munich ») ;
- pays (contours et noms en français) : Natural Earth 1:10 m et 1:50 m (domaine public).

Sortie (gzip JSON, dans le dossier donné) : lieux.json.gz, pays-10m.json.gz, pays-50m.json.gz,
sources.json (URL et date du téléchargement).

    python geo_build.py <dossier de sortie> [<dossier de téléchargement déjà rempli>] [--ban <dép> <dép>…]

--ban : adresses de la Base Adresse Nationale des départements donnés (Licence Ouverte 2.0), dans
ban.sqlite (ban.py). La liste est donnée au lancement et n'est écrite que dans sources.json, sur le volume.
"""
import gzip
import io
import json
import os
import re
import sys
import urllib.request
import zipfile
from datetime import date

import shapefile   # pyshp, seulement au build

import ban         # à côté de ce fichier (fetch-geo-data.sh le monte aussi)

URLS = {
    "communes": "https://geo.api.gouv.fr/communes?fields=nom,code,codesPostaux,centre,population,codeDepartement,departement,region&format=json",
    "villes": "https://download.geonames.org/export/dump/cities1000.zip",
    "admin1": "https://download.geonames.org/export/dump/admin1CodesASCII.txt",
    "noms": "https://download.geonames.org/export/dump/alternateNamesV2.zip",
    "pays-10m": "https://naciscdn.org/naturalearth/10m/cultural/ne_10m_admin_0_countries.zip",
    "pays-50m": "https://naciscdn.org/naturalearth/50m/cultural/ne_50m_admin_0_countries.zip",
}
LATIN = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿŒœ' .-]+$")


def fetch(key: str, cache: str) -> bytes:
    name = os.path.join(cache, os.path.basename(URLS[key].split("?")[0]) if key != "communes" else "communes.json") if cache else None
    if name and os.path.exists(name):
        return open(name, "rb").read()
    req = urllib.request.Request(URLS[key], headers={"User-Agent": "sophia-web-build"})
    return urllib.request.urlopen(req, timeout=300).read()


def rings(shapes, decimals: int) -> list:
    """Anneaux [bbox, coordonnées à plat] ; les anneaux de moins de 3 points distincts sont omis."""
    out = []
    for shp in shapes:
        parts = list(shp.parts) + [len(shp.points)]
        for a, b in zip(parts, parts[1:]):
            pts, flat, last = shp.points[a:b], [], None
            for x, y in pts:
                p = (round(x, decimals), round(y, decimals))
                if p != last:
                    flat += p
                    last = p
            if len(flat) >= 6:
                xs, ys = flat[0::2], flat[1::2]
                out.append([[min(xs), min(ys), max(xs), max(ys)], flat])
    return out


def read_shp(data: bytes):
    z = zipfile.ZipFile(io.BytesIO(data))
    base = next(n[:-4] for n in z.namelist() if n.endswith(".shp"))
    return shapefile.Reader(shp=io.BytesIO(z.read(base + ".shp")), dbf=io.BytesIO(z.read(base + ".dbf")),
                            shx=io.BytesIO(z.read(base + ".shx")), encoding="utf-8")


def fetch_ban(dep: str, cache: str) -> bytes:
    name = os.path.join(cache, f"adresses-{dep}.csv.gz") if cache else None
    if name and os.path.exists(name):
        return open(name, "rb").read()
    req = urllib.request.Request(ban.URL.format(dep=dep), headers={"User-Agent": "sophia-geo-build"})
    return urllib.request.urlopen(req, timeout=600).read()


def main(out: str, cache: str = "", departements: list = ()) -> None:
    os.makedirs(out, exist_ok=True)
    put = lambda name, obj: gzip.open(os.path.join(out, name), "wt", encoding="utf-8").write(
        json.dumps(obj, ensure_ascii=False, separators=(",", ":")))

    # Pays : noms français, code ISO (ISO_A2_EH : la France et la Norvège ont -99 dans ISO_A2)
    noms_pays = {}
    for res in ("10m", "50m"):
        r = read_shp(fetch("pays-" + res, cache))
        fields = [f[0] for f in r.fields[1:]]
        pays = []
        for sr in r.iterShapeRecords():
            rec = dict(zip(fields, sr.record))
            iso = rec.get("ISO_A2_EH") or rec.get("ISO_A2")
            nom = rec.get("NAME_FR") or rec.get("NAME")
            if iso and iso != "-99":
                noms_pays.setdefault(iso, nom)
            pays.append({"iso": iso, "nom": nom, "anneaux": rings([sr.shape], 3 if res == "10m" else 2)})
        put(f"pays-{res}.json.gz", pays)

    lieux = []
    # Communes françaises (officielles)
    for c in json.loads(fetch("communes", cache)):
        if not c.get("centre"):
            continue
        lon, lat = c["centre"]["coordinates"]
        dep = (c.get("departement") or {}).get("nom") or c.get("codeDepartement")
        lieux.append({"id": "insee:" + c["code"], "nom": c["nom"], "autres": [], "lat": round(lat, 5), "lon": round(lon, 5),
                      "pop": c.get("population") or 0, "pays": "FR", "region": dep, "cp": (c.get("codesPostaux") or [])[:3],
                      "source": "geo.api.gouv.fr"})
    # Villes du monde (hors France, couverte par les communes)
    admin1 = {}
    for line in fetch("admin1", cache).decode("utf-8").splitlines():
        f = line.split("\t")
        if len(f) >= 2:
            admin1[f[0]] = f[1]
    z = zipfile.ZipFile(io.BytesIO(fetch("villes", cache)))
    villes = [f for f in (line.split("\t") for line in z.read("cities1000.txt").decode("utf-8").splitlines())
              if len(f) >= 15 and f[8] != "FR"]
    # Noms français étiquetés : lus en flux dans la table de tous les noms (≈ 200 Mo compressés)
    ids, fr = {f[0] for f in villes}, {}
    zn = zipfile.ZipFile(io.BytesIO(fetch("noms", cache)))
    with zn.open("alternateNamesV2.txt") as raw:
        for line in io.TextIOWrapper(raw, encoding="utf-8"):
            g = line.split("\t", 6)
            if len(g) > 4 and g[2] == "fr" and g[1] in ids:
                pref = g[4] == "1"
                if g[1] not in fr or (pref and not fr[g[1]][1]):
                    fr[g[1]] = (g[3], pref)
    for f in villes:
        nom_fr = fr.get(f[0], (None,))[0]
        nom = nom_fr or f[1]
        autres = sorted({a for a in (f[1], f[2]) if a != nom})
        lieux.append({"id": "geonames:" + f[0], "nom": nom, "autres": autres, "lat": float(f[4]), "lon": float(f[5]),
                      "pop": int(f[14] or 0), "pays": f[8], "region": admin1.get(f"{f[8]}.{f[10]}"), "source": "GeoNames"})
    put("lieux.json.gz", {"lieux": lieux, "pays": noms_pays})
    licences = {"geo.api.gouv.fr": "Licence Ouverte Etalab 2.0", "GeoNames": "CC BY 4.0", "Natural Earth": "domaine public"}
    sources = {"date": date.today().isoformat(), "urls": URLS, "licences": licences}
    if departements:
        comptes = ban.construire(out, list(departements), lambda d: fetch_ban(d, cache))
        licences["Base Adresse Nationale"] = "Licence Ouverte 2.0"
        sources["ban"] = {"url": ban.URL, "departements": list(departements)}
        for d, n in comptes.items():
            print(f"BAN {d} : {n} adresses")
        print(f"ban.sqlite : {os.path.getsize(os.path.join(out, ban.FICHIER)) / 1e6:.0f} Mo")
    json.dump(sources, open(os.path.join(out, "sources.json"), "w"), ensure_ascii=False, indent=1)
    print(f"{len(lieux)} lieux, {len(noms_pays)} pays")


if __name__ == "__main__":
    args = sys.argv[1:]
    deps = args[args.index("--ban") + 1:] if "--ban" in args else []
    pos = args[:args.index("--ban")] if "--ban" in args else args
    main(*pos, departements=deps)
