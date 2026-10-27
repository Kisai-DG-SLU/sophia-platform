#!/usr/bin/env python3
"""Ajoute la notification Telegram de l'administrateur à la configuration générale d'un Alertmanager d'OKD :
`main` (Secret openshift-monitoring/alertmanager-main : alertes de la plateforme) ou `user-workload`
(Secret openshift-user-workload-monitoring/alertmanager-user-workload : alertes des namespaces SophIA).

Lit la configuration sur l'entrée standard, écrit la nouvelle sur la sortie standard. Un récepteur
« admin-telegram » est ajouté, et une route placée EN TÊTE avec continue: true :
- rien n'est enlevé ; toute alerte suit ensuite le chemin qu'elle suivait avant ;
- `user-workload` : une règle d'inhibition « critique masque l'avertissement de même nom » est ajoutée,
  comme celle que la plateforme a déjà ;
- `main` : deux alertes permanentes, sans action possible, sont exclues par leur nom (EXCLUES).
Option `--telegram-seul <récepteur>` (avec `main`) : retire ce récepteur par courriel et les clés smtp_*
de global, et rend « aucun » (sans intégration) récepteur par défaut ; toute autre structure (autre
récepteur par défaut, sous-route qui le cite, autre récepteur par courriel) arrête le script sans rien écrire.
Rejouable : un second passage rend la même configuration (message sur stderr).

Aucune valeur de la configuration n'est écrite sur stderr : seulement des noms de clés et de récepteurs.
`masque` réécrit une configuration en masquant les valeurs sensibles (clés smtp_*, mots de passe, jetons,
adresses des courriels), pour comparer avant et après sans rien afficher :

    python3 alertes-telegram-ajout.py masque < avant.yaml > avant-masque.yaml

Le jeton du bot n'est jamais dans la configuration : il est lu dans le Secret alertes-telegram, monté par
l'opérateur sous /etc/alertmanager/secrets/alertes-telegram/ (00- et 01-…-config.yaml). La conversation
et le lien de la console viennent de l'environnement :

    ALERTES_CHAT_ID=<id> CONSOLE_URL=https://console.example.org \\
      python3 alertes-telegram-ajout.py main < avant.yaml > apres.yaml

Demande PyYAML (python3 -m pip install --user pyyaml).
"""
import os
import sys

import yaml

NOM = "admin-telegram"
# Heures à Paris (fuseaux présents dans l'image d'Alertmanager d'OKD) ; date ajoutée si le début a plus de
# 12 h. Durée arrondie à la minute (« 35 min », « 1 h 5 min »). Dans un groupe, une ligne par alerte avec son
# heure ; le résumé n'est répété que s'il change.
MESSAGE = (
    '{{ $prec := "" }}{{ range .Alerts }}'
    '{{ $debut := .StartsAt | tz "Europe/Paris" }}'
    '{{ $heure := $debut | date "15 h 04" }}'
    '{{ $jour := "" }}{{ if gt (since .StartsAt).Hours 12.0 }}{{ $jour = printf "le %s à " ($debut | date "02/01") }}{{ end }}'
    '{{ if eq .Status "firing" }}🔴 Alerte{{ else }}✅ Résolue{{ end }} : '
    "{{ .Labels.alertname }} ({{ .Labels.severity }}{{ with .Labels.namespace }}, {{ . }}{{ end }}), "
    '{{ if eq .Status "firing" }}depuis {{ $jour }}{{ $heure }}{{ else }}'
    "{{ $d := ((.EndsAt.Sub .StartsAt).Round 60000000000).String }}"
    '{{ $d = reReplaceAll "^0s$" "moins d\'une minute" $d }}'
    '{{ $d = reReplaceAll "h0m0s$" " h" $d }}'
    '{{ $d = reReplaceAll "m0s$" " min" $d }}'
    '{{ $d = reReplaceAll "([0-9])h([0-9])" "$1 h $2" $d }}'
    "commencée {{ if $jour }}{{ $jour }}{{ else }}à {{ end }}{{ $heure }}, durée {{ $d }}{{ end }}\n"
    "{{ $resume := .Annotations.summary }}{{ if not $resume }}{{ $resume = .Annotations.description }}{{ end }}"
    "{{ if and $resume (ne $resume $prec) }}{{ $resume }}\n{{ end }}{{ $prec = $resume }}"
    "{{ end }}Console : CONSOLE_URL/monitoring/alerts"
)
# Watchdog (none), UpdateAvailable et InfoInhibitor (info) ne passent pas : seulement warning et critical.
# Alertes de la plateforme permanentes ou sans action possible, relevées sur 7 jours :
# - GPUOperatorOpenshiftDriverToolkitEnabledNfdTooOld : en continu, sans effet relevé ;
# - TelemeterClientFailures : envoi de télémétrie vers l'éditeur, sans objet pour SophIA.
EXCLUES = ["GPUOperatorOpenshiftDriverToolkitEnabledNfdTooOld", "TelemeterClientFailures"]
# Un message par problème : groupe par namespace et nom d'alerte ; rappel une fois par jour s'il dure.
ROUTE = {
    "receiver": NOM,
    "matchers": ['severity=~"warning|critical"'],
    "group_by": ["namespace", "alertname"],
    "group_wait": "30s",
    "group_interval": "5m",
    "repeat_interval": "24h",
    "continue": True,
}
# Récepteur sans intégration : avec --telegram-seul, une alerte qui n'est pas pour Telegram n'est envoyée
# nulle part (elle reste visible dans la console).
VIDE = "aucun"
SENSIBLES = ("password", "secret", "token", "api_key", "credentials")
INHIBITION = {
    "source_matchers": ["severity = critical"],
    "target_matchers": ["severity = warning"],
    "equal": ["namespace", "alertname"],
}


def recepteur() -> dict:
    chat, console = os.environ.get("ALERTES_CHAT_ID", ""), os.environ.get("CONSOLE_URL", "").rstrip("/")
    if not chat.lstrip("-").isdigit() or not console.startswith("https://"):
        raise SystemExit("ALERTES_CHAT_ID (nombre) et CONSOLE_URL (https://…) sont requis : rien n'est modifié")
    return {
        "name": NOM,
        "telegram_configs": [{
            "bot_token_file": "/etc/alertmanager/secrets/alertes-telegram/jeton",
            "chat_id": int(chat),
            "parse_mode": "HTML",
            "send_resolved": True,
            "message": MESSAGE.replace("CONSOLE_URL", console),
        }],
    }


def recepteurs_cites(route: dict) -> list:
    cites = [route["receiver"]] if "receiver" in route else []
    for sous in route.get("routes") or []:
        cites += recepteurs_cites(sous)
    return cites


def telegram_seul(cfg: dict, ancien: str) -> list:
    """main : retire le courriel (récepteur `ancien`, clés smtp_* de global). Rend les noms retirés."""
    retires = []
    if cfg["route"].get("receiver") not in (ancien, VIDE):
        raise SystemExit(f"main : récepteur par défaut inattendu (ni « {ancien} » ni « {VIDE} ») : rien n'est modifié")
    if ancien in recepteurs_cites({"routes": cfg["route"].get("routes") or []}):
        raise SystemExit(f"main : une sous-route cite « {ancien} » : rien n'est modifié")
    autres = [r.get("name") for r in cfg["receivers"] if r.get("name") != ancien and r.get("email_configs")]
    if autres:
        raise SystemExit(f"main : autre récepteur par courriel ({', '.join(map(str, autres))}) : rien n'est modifié")
    globales = cfg.get("global") or {}
    for cle in [c for c in globales if str(c).startswith("smtp_")]:
        del globales[cle]
        retires.append(f"global.{cle}")
    if any(r.get("name") == ancien for r in cfg["receivers"]):
        cfg["receivers"] = [r for r in cfg["receivers"] if r.get("name") != ancien]
        retires.append(f"récepteur {ancien}")
    if not any(r.get("name") == VIDE for r in cfg["receivers"]):
        cfg["receivers"].append({"name": VIDE})
    cfg["route"]["receiver"] = VIDE
    return retires


def ajouter(cfg: dict, instance: str, ancien: str | None) -> bool:
    cfg.setdefault("receivers", [])
    if "route" not in cfg:
        raise SystemExit("configuration sans route racine : rien n'est modifié")
    nouveau = recepteur()
    if ancien:
        for nom in telegram_seul(cfg, ancien):
            print(f"retiré : {nom}", file=sys.stderr)
    if any(r.get("name") == NOM for r in cfg["receivers"]):
        return False
    route = dict(ROUTE)
    if instance == "main":
        route["matchers"] = ROUTE["matchers"] + ['alertname!~"' + "|".join(EXCLUES) + '"']
    cfg["receivers"].append(nouveau)
    cfg["route"].setdefault("routes", []).insert(0, route)
    if instance == "user-workload":
        regles = cfg.setdefault("inhibit_rules", [])
        if not any(r.get("source_matchers") == INHIBITION["source_matchers"] for r in regles):
            regles.append(INHIBITION)
    return True


def masquer(noeud, cle: str = ""):
    sensible = cle.startswith("smtp_") or (any(m in cle for m in SENSIBLES) and not cle.endswith("_file"))
    if isinstance(noeud, dict):
        return {k: masquer(v, "email_configs" if cle == "email_configs" else str(k)) for k, v in noeud.items()}
    if isinstance(noeud, list):
        return [masquer(v, cle) for v in noeud]
    return "<masqué>" if (sensible or cle == "email_configs") and noeud not in (None, "") else noeud


def main() -> None:
    args = sys.argv[1:]
    ancien = None
    if len(args) == 3 and args[0] == "main" and args[1] == "--telegram-seul":
        ancien = args[2]
    elif len(args) != 1 or args[0] not in ("main", "user-workload", "masque"):
        raise SystemExit("usage : alertes-telegram-ajout.py main [--telegram-seul <récepteur>]|user-workload|masque"
                         " < avant.yaml > apres.yaml")
    cfg = yaml.safe_load(sys.stdin.read())
    if not isinstance(cfg, dict):
        raise SystemExit("entrée illisible : rien n'est modifié")
    if args[0] == "masque":
        sys.stdout.write(yaml.safe_dump(masquer(cfg), sort_keys=False, allow_unicode=True))
        return
    if not ajouter(cfg, args[0], ancien):
        print(f"récepteur « {NOM} » déjà présent : configuration inchangée", file=sys.stderr)
    sys.stdout.write(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True))


if __name__ == "__main__":
    main()
