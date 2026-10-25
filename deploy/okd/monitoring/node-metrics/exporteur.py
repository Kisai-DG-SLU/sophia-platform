"""Exporteur de métriques du nœud pour SophIA : GPU par NVML et fichiers .prom du nœud.

- GPU : NVML lu par ctypes dans la bibliothèque du pilote montée depuis le nœud, sans
  outil NVIDIA ni opérateur. Mémoire, utilisation, température, puissance. Échec NVML → gpu_nvml_ok 0.
- Fichiers *.prom déposés par les scripts du nœud dans /var/lib/sophia/metrics (lecture seule),
  par exemple wg_filter.prom, écrit par le garde-fou du filtre VPN.
- Occupation des volumes du nœud : chaque LV monté sous /var/mnt, et /var (volumes en hostPath dans
  /var/lib/sophia). Les métriques du node-exporter de la plateforme portent son propre namespace,
  qu'une règle d'un namespace SophIA ne peut pas lire.
Sert GET /metrics sur le port 9400. Bibliothèque standard seulement.
"""
import ctypes
import glob
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LIB = os.environ.get("NVML_LIB", "/opt/nvidia-libs/libnvidia-ml.so.1")
REP = os.environ.get("METRIQUES_NOEUD", "/var/lib/sophia/metrics")
PORT = int(os.environ.get("PORT", "9400"))
HOTE_MNT = os.environ.get("HOTE_MNT", "/hote/var/mnt")       # /var/mnt du nœud, en lecture seule
HOTE_VAR = os.environ.get("HOTE_VAR", "/hote/var/lib/sophia")  # un répertoire de /var du nœud


class _Memoire(ctypes.Structure):
    _fields_ = [("total", ctypes.c_ulonglong), ("free", ctypes.c_ulonglong), ("used", ctypes.c_ulonglong)]


class _Utilisation(ctypes.Structure):
    _fields_ = [("gpu", ctypes.c_uint), ("memory", ctypes.c_uint)]


def gpu() -> list[str]:
    # Format d'exposition : chaque famille sous sa ligne « # TYPE », ses séries regroupées dessous.
    familles: dict = {n: [] for n in ("sophia_gpu_memoire_utilisee_octets", "sophia_gpu_memoire_totale_octets",
                                      "sophia_gpu_utilisation_ratio", "sophia_gpu_temperature_celsius",
                                      "sophia_gpu_puissance_watts")}
    try:
        nv = ctypes.CDLL(LIB)
        if nv.nvmlInit_v2() != 0:
            raise OSError("nvmlInit")
        try:
            n = ctypes.c_uint()
            nv.nvmlDeviceGetCount_v2(ctypes.byref(n))
            for i in range(n.value):
                h = ctypes.c_void_p()
                if nv.nvmlDeviceGetHandleByIndex_v2(i, ctypes.byref(h)) != 0:
                    continue
                m, u, t, p = _Memoire(), _Utilisation(), ctypes.c_uint(), ctypes.c_uint()
                lab = f'{{gpu="{i}"}}'
                if nv.nvmlDeviceGetMemoryInfo(h, ctypes.byref(m)) == 0:
                    familles["sophia_gpu_memoire_utilisee_octets"].append(f"{lab} {m.used}")
                    familles["sophia_gpu_memoire_totale_octets"].append(f"{lab} {m.total}")
                if nv.nvmlDeviceGetUtilizationRates(h, ctypes.byref(u)) == 0:
                    familles["sophia_gpu_utilisation_ratio"].append(f"{lab} {u.gpu / 100}")
                if nv.nvmlDeviceGetTemperature(h, 0, ctypes.byref(t)) == 0:   # 0 = capteur du GPU
                    familles["sophia_gpu_temperature_celsius"].append(f"{lab} {t.value}")
                if nv.nvmlDeviceGetPowerUsage(h, ctypes.byref(p)) == 0:     # milliwatts
                    familles["sophia_gpu_puissance_watts"].append(f"{lab} {p.value / 1000}")
        finally:
            nv.nvmlShutdown()
        ok = 1
    except OSError as e:
        print(f"NVML indisponible : {e}", file=sys.stderr)
        ok = 0
    lignes = []
    for nom, series in familles.items():
        if series:
            lignes += [f"# TYPE {nom} gauge"] + [nom + x for x in series]
    return lignes + ["# TYPE sophia_gpu_nvml_ok gauge", f"sophia_gpu_nvml_ok {ok}"]


def fichiers_noeud() -> list[str]:
    lignes = []
    for f in sorted(glob.glob(os.path.join(REP, "*.prom"))):
        try:
            with open(f) as fh:
                lignes += [l.rstrip("\n") for l in fh if l.strip()]
        except OSError as e:
            print(f"{f} illisible : {e}", file=sys.stderr)
    return lignes


def volumes() -> list[str]:
    """Octets totaux et libres (pour un utilisateur non root) de /var et de chaque point de montage
    de /var/mnt. Un répertoire de /var/mnt qui n'est pas un montage (même périphérique que son parent)
    est ignoré : il compterait /var une seconde fois."""
    points = []
    if os.path.isdir(HOTE_VAR):
        points.append(("/var", HOTE_VAR))
    if os.path.isdir(HOTE_MNT):
        parent = os.stat(HOTE_MNT).st_dev
        for nom in sorted(os.listdir(HOTE_MNT)):
            chemin = os.path.join(HOTE_MNT, nom)
            try:
                if os.path.isdir(chemin) and os.stat(chemin).st_dev != parent:
                    points.append((f"/var/mnt/{nom}", chemin))
            except OSError:
                continue
    total, libres = ["# TYPE sophia_volume_octets_total gauge"], ["# TYPE sophia_volume_octets_libres gauge"]
    for point, chemin in points:
        try:
            v = os.statvfs(chemin)
        except OSError as e:
            print(f"{chemin} illisible : {e}", file=sys.stderr)
            continue
        total.append(f'sophia_volume_octets_total{{point="{point}"}} {v.f_blocks * v.f_frsize}')
        libres.append(f'sophia_volume_octets_libres{{point="{point}"}} {v.f_bavail * v.f_frsize}')
    return total + libres if len(total) > 1 else []


class Gestionnaire(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path not in ("/metrics", "/metrics/"):
            self.send_response(404)
            self.end_headers()
            return
        corps = ("\n".join(gpu() + volumes() + fichiers_noeud()) + "\n").encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", PORT), Gestionnaire).serve_forever()
