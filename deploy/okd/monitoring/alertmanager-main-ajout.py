#!/usr/bin/env python3
"""Ajoute le récepteur du répartiteur à la configuration
de l'Alertmanager principal d'OKD (Secret openshift-monitoring/alertmanager-main, clé alertmanager.yaml).

Lit la configuration sur l'entrée standard, écrit la nouvelle sur la sortie standard. N'enlève et ne
modifie rien : un récepteur « repartiteur » est ajouté, et une route placée EN TÊTE avec continue: true,
si bien que toute alerte suit ensuite exactement le chemin qu'elle suivait avant. Rejouable : si le
récepteur existe déjà, la configuration est rendue telle quelle (code 0, message sur stderr).

    python3 alertmanager-main-ajout.py < avant.yaml > apres.yaml

Demande PyYAML (python3 -m pip install --user pyyaml).
"""
import sys

import yaml

SECRETS = "/etc/alertmanager/secrets/repartiteur-alertes"
RECEPTEUR = {
    "name": "repartiteur",
    "webhook_configs": [{
        "url": "https://repartiteur.sophia-core.svc:8443/v1/alertes",
        "send_resolved": True,
        "max_alerts": 64,
        "http_config": {
            "authorization": {"type": "Bearer", "credentials_file": f"{SECRETS}/jeton"},
            "tls_config": {"ca_file": f"{SECRETS}/service-ca.crt", "server_name": "repartiteur.sophia-core.svc"},
        },
    }],
}
# Avertissements et alertes critiques ; Watchdog et InfoInhibitor (severity none, info) ne passent pas.
ROUTE = {
    "receiver": "repartiteur",
    "matchers": ['severity=~"warning|critical"'],
    "group_by": ["namespace", "alertname"],
    "group_wait": "30s",
    "group_interval": "5m",
    "repeat_interval": "4h",
    "continue": True,
}


def ajouter(cfg: dict) -> bool:
    recepteurs = cfg.setdefault("receivers", [])
    if any(r.get("name") == "repartiteur" for r in recepteurs):
        return False
    if "route" not in cfg:
        raise SystemExit("configuration sans route racine : rien n'est modifié")
    recepteurs.append(RECEPTEUR)
    cfg["route"].setdefault("routes", []).insert(0, ROUTE)
    return True


def main() -> None:
    cfg = yaml.safe_load(sys.stdin.read())
    if not isinstance(cfg, dict):
        raise SystemExit("entrée illisible : rien n'est modifié")
    if not ajouter(cfg):
        print("récepteur « repartiteur » déjà présent : configuration inchangée", file=sys.stderr)
    sys.stdout.write(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True))


if __name__ == "__main__":
    main()
