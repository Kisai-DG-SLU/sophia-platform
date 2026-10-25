"""Exporteur de métriques du nœud pour SophIA : GPU par NVML et fichiers .prom du nœud.

- GPU : NVML lu par ctypes dans la bibliothèque du pilote montée depuis le nœud, sans
  outil NVIDIA ni opérateur. Mémoire, utilisation, température, puissance. Échec NVML → gpu_nvml_ok 0.
- Fichiers *.prom déposés par les scripts du nœud dans /var/lib/sophia/metrics (lecture seule),
  par exemple wg_filter.prom, écrit par le garde-fou du filtre VPN.
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


class Gestionnaire(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path not in ("/metrics", "/metrics/"):
            self.send_response(404)
            self.end_headers()
            return
        corps = ("\n".join(gpu() + fichiers_noeud()) + "\n").encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", PORT), Gestionnaire).serve_forever()
