# VPN WireGuard — accès unique à la plateforme (nœud OKD)

**Principe :** la plateforme ne se joint que par le VPN, depuis le réseau local comme depuis l'extérieur ; le réseau local n'est **jamais** joignable depuis le VPN. Les noms des services pointent vers l'adresse VPN du serveur (voir `../../ingress/`). Le VPN est donc aussi le **seul chemin d'administration** : rien de ce qui suit ne doit le couper.

## Variables

Aucune valeur de l'installation de référence n'est donnée ici : choisissez les vôtres.

| Variable | Rôle | Exemple de forme |
|---|---|---|
| `${VPN_NETWORK}` | réseau du VPN, un /24 privé qui ne recouvre ni le réseau local, ni les réseaux des pods et des Services | `a.b.c.0/24` |
| `${VPN_SERVER_IP}` | adresse du serveur sur le VPN, aussi externalIP de Forgejo et cible des noms DNS | `a.b.c.1` |
| `${VPN_ADMIN_RANGE}` | plage des appareils d'administration : tout le nœud, Forgejo SSH et web | `a.b.c.x-a.b.c.y` |
| `${VPN_PREFIX}`, `${VPN_HOST_MIN}`, `${VPN_HOST_MAX}` | contrôles de `add-peer.sh` : préfixe `a.b.c` et dernier octet attribuable | — |
| `${VPN_PORT}` | port UDP d'écoute, redirigé par la box ou le pare-feu en amont | — |
| `${LAN_NETWORK}` | réseau local du nœud, à ne jamais router dans le VPN | — |
| `${GIT_SSH_PORT}`, `${GIT_HTTP_PORT}` | ports de Forgejo exposés sur l'externalIP | — |

Toute adresse hors de `${VPN_ADMIN_RANGE}` est un appareil **utilisateur** : HTTP/HTTPS seulement.

## Fichiers

| Fichier | Rôle |
|---|---|
| `wg-filter.nft` | gabarit de la table nftables `inet sophia_wg`, indépendante d'OVN-Kubernetes : **administration** → tout le nœud + Forgejo ; **utilisateurs** → 80/443 seulement ; **rien n'est relayé** vers le réseau local, les pods ou les Services, hors Forgejo pour l'administration |
| `sophia-wg-filter.service` | charge le filtre au démarrage, avant le réseau, puis lance le garde-fou |
| `wg-filter-check.sh` | **garde-fou** : relit tout le ruleset avec le nft d'OVN-Kubernetes ; illisible → supprime la table et alerte dans le journal (le cluster prime, le VPN n'est **jamais** coupé) |
| `sophia-wg-filter-check.{service,timer}` | relance le garde-fou 3 min après le démarrage puis toutes les 15 min (mises à jour d'OKD) |
| `test-garde-fou-metrique.sh` | banc local, **sous Linux seulement** : compare l'ancien et le nouveau garde-fou avec de faux `crictl`, `podman`, `nft` et `logger` |
| `test-nft-ovn.sh` | teste expression par expression ce que le nft d'OVN sait relire (tables sans hook, supprimées aussitôt) |
| `add-peer.sh` | ajoute un appareil : nom, adresse, **clé publique** ; contrôles (format, doublons, plage), sauvegarde du profil, application sans couper les tunnels |

## 1. Interface côté serveur

`wg0` est une interface **noyau** gérée par **NetworkManager** (profil `/etc/NetworkManager/system-connections/wg0.nmconnection`, mode 600) ; aucun paquet supplémentaire n'est nécessaire sur le nœud.

| Élément | Valeur |
|---|---|
| Adresse | `${VPN_SERVER_IP}/24` |
| Port | UDP `${VPN_PORT}`, redirigé depuis l'adresse publique (box, pare-feu) |
| Clé privée | générée **sur le nœud**, jamais copiée ailleurs ; seule la clé publique est diffusée aux appareils |
| Pairs | un par appareil, `allowed-ips` = son adresse en /32 |
| FORWARD d'OKD | politique **DROP** : seuls les réseaux des pods et des Services sont relayés, le réseau local est déjà injoignable |
| Forgejo | externalIP `${VPN_SERVER_IP}` sur `${GIT_SSH_PORT}` et `${GIT_HTTP_PORT}`, DNAT vers son Service |

Sans filtre, **tout pair joint tous les ports du nœud** (SSH, API du cluster, kubelet, etcd, serveur de configuration des machines, API des agents…), et les pods et Services en direct s'il élargit ses `AllowedIPs` : d'où la section 3.

**À la maison**, le tunnel passe par l'adresse publique (`Endpoint`) : la box doit renvoyer le trafic vers l'intérieur (*hairpin NAT*). À vérifier avec le premier appareil sur le Wi-Fi.

## 2. Ajouter un appareil

1. Sur l'appareil, application **WireGuard** → *Ajouter un tunnel* → *Créer à partir de rien* : l'application **génère la clé** ; noter la **clé publique** affichée (jamais la privée).
2. Sur le nœud :
   ```bash
   sudo VPN_PREFIX=<a.b.c> VPN_HOST_MIN=<min> VPN_HOST_MAX=<max> \
     ./add-peer.sh <nom-appareil> <adresse VPN> '<clé publique>'
   ```
3. Sur l'appareil, compléter le tunnel :
   ```ini
   [Interface]
   PrivateKey = (générée par l'application)
   Address = <adresse VPN>/32
   [Peer]
   PublicKey = <clé publique du serveur>
   Endpoint = <adresse publique>:${VPN_PORT}
   AllowedIPs = ${VPN_NETWORK}
   PersistentKeepalive = 25
   ```
   Pas de `DNS =` : le DNS public répond déjà `${VPN_SERVER_IP}`. `AllowedIPs` limité au réseau du VPN : le réseau local de l'appareil n'est pas détourné.
4. iOS : *Activation à la demande* sur Wi-Fi **et** cellulaire. Android : *Paramètres → Réseau → VPN → ⚙ → VPN permanent*.

Consigner chaque appareil dans le commentaire du pair (fait par `add-peer.sh`) ; garder les adresses d'administration pour les seuls postes d'administration.

## 3. Filtre (administrateur, sur le nœud)

Depuis un poste d'**administration** (la session reste ouverte quoi qu'il arrive).

```bash
# rendu du gabarit (liste EXPLICITE : les « $ » du code nft ne sont pas touchés)
export VPN_SERVER_IP=… VPN_ADMIN_RANGE=… GIT_SSH_PORT=… GIT_HTTP_PORT=…
envsubst '$VPN_SERVER_IP $VPN_ADMIN_RANGE $GIT_SSH_PORT $GIT_HTTP_PORT' < wg-filter.nft > wg-filter.rendu.nft
grep -n '\${' wg-filter.rendu.nft && echo "⚠ variable non rendue" || echo "rendu complet"
# copie vers le nœud : wg-filter.rendu.nft, wg-filter-check.sh, test-nft-ovn.sh, les trois unités systemd
# sur le nœud
sudo nft list ruleset > ~/backup-nft-$(date +%Y%m%d).txt          # sauvegarde
sudo bash test-nft-ovn.sh                                          # compatibilité avec le nft d'OVN
sudo mkdir -p /etc/sophia
sudo install -m 644 wg-filter.rendu.nft /etc/sophia/wg-filter.nft && sudo install -m 755 wg-filter-check.sh /etc/sophia/
sudo nft -c -f /etc/sophia/wg-filter.nft && echo "syntaxe OK"         # contrôle, n'applique rien
# interrupteur automatique : la table saute dans 3 min si on n'annule pas (le tunnel n'est pas touché)
sudo systemd-run --unit=wg-filter-deadman --on-active=180 /usr/sbin/nft delete table inet sophia_wg
sudo nft -f /etc/sophia/wg-filter.nft && sudo /etc/sophia/wg-filter-check.sh; echo "garde-fou=$?"   # doit être 0
# → depuis le poste d'administration : NOUVELLE session SSH, git fetch, interface web ; puis :
sudo systemctl stop wg-filter-deadman.timer
sudo install -m 644 sophia-wg-filter.service sophia-wg-filter-check.service sophia-wg-filter-check.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable sophia-wg-filter sophia-wg-filter-check.timer
sudo systemctl restart sophia-wg-filter && sudo systemctl start sophia-wg-filter-check.timer
systemctl is-active sophia-wg-filter; journalctl -t sophia-wg-filter -n 5
```

**Vérification :**
- poste d'administration : SSH, `git fetch` sur `${GIT_SSH_PORT}`, interface web ;
- appareil utilisateur : l'interface répond ; un port hors 80/443 du serveur (l'API des agents, par exemple) **ne répond pas** (la page charge sans fin), et le compteur augmente :
  ```bash
  sudo nft list chain inet sophia_wg input | grep counter
  ```

**Retour arrière :** `sudo nft delete table inet sophia_wg` (immédiat) ; `sudo systemctl disable --now sophia-wg-filter` (définitif).

Une règle iptables `FORWARD` qui accepterait un port relayé « pour `wg0` » est à proscrire : elle ouvre ce port à **tous** les pairs dès que la table est absente. Le DNAT de l'externalIP vers le réseau des Services est déjà accepté par OKD.

## 4. Compatibilité avec OVN-Kubernetes

**Incident (OKD 4.21) :** après une coupure de courant, plus aucun pod n'avait de réseau (`ovnkube-node` en CrashLoopBackOff, multus en timeout), donc plus de Forgejo, donc plus rien de ce qui en dépend. `ovnkube-controller` relit **tout le ruleset** au démarrage avec le nft de son image (**1.0.9**, contre 1.1.5 sur l'hôte) et faisait une segfault (code 139) sur la table `inet sophia_wg`. Avant la coupure, tout marchait parce que la table avait été chargée **après** le démarrage d'OVN : le défaut n'apparaît qu'au redémarrage.

**Cause isolée** avec `test-nft-ovn.sh` (une table de test par expression, **sans chaîne de base**, donc sans effet sur le trafic, supprimée aussitôt) : **tout set nommé** (`set admins { … }`, `@admins`), avec ou sans intervalles, en famille `inet` comme `ip`. L'expression d'abord soupçonnée (`ct original ip daddr`) est lisible. Correctif : plage d'administration écrite en dur dans les règles, intentions de sécurité inchangées.

**Garde-fou :** `wg-filter-check.sh` relit tout le ruleset avec le nft d'OVN — `crictl exec` dans le conteneur `ovn-controller` quand il tourne, sinon `podman` avec la dernière image vue (au démarrage du nœud, CRI-O n'est pas encore là). Codes : 0 lisible ; 1 illisible → **table supprimée**, alerte `crit` dans le journal, service en échec ; 2 vérification impossible → table conservée, avertissement. Le choix est délibéré : en cas de doute, **le cluster et l'accès d'administration priment**, le VPN reste ouvert sans filtre le temps de corriger ; couper le VPN priverait l'administrateur de son seul chemin d'accès.

**Après chaque mise à jour d'OKD** (le nft de l'image OVN peut changer) :

```bash
sudo /etc/sophia/wg-filter-check.sh; echo $?          # 0 attendu ; 2 = OVN pas joignable
systemctl status sophia-wg-filter sophia-wg-filter-check.timer
journalctl -t sophia-wg-filter -n 20                  # « ALERTE … SUPPRIMÉE » = filtre retiré
sudo bash test-nft-ovn.sh                             # si alerte : quelles expressions posent problème
```

Si le garde-fou a retiré la table : le cluster tourne mais **le VPN n'est plus filtré** — corriger `wg-filter.nft` d'après `test-nft-ovn.sh`, puis reprendre la section 3.

**Règles à retenir :** ne jamais lancer `nft flush ruleset` ; ne jamais toucher aux tables d'OVN ni d'OpenShift ; tout test nftables se fait dans une table **sans hook**, supprimée dans la foulée ; tout chargement d'un filtre se fait sous interrupteur automatique.

## 5. Garde-fou en métrique

À chaque passage, le garde-fou écrit son code (0 lisible, 1 table retirée, 2 vérification impossible) et un horodatage dans `/var/lib/sophia/metrics/wg_filter.prom`, que lit l'exporteur du nœud ([`../../monitoring/`](../../monitoring/)). Trois alertes en découlent : filtre retiré, vérification impossible, garde-fou muet depuis plus de 45 minutes. L'écriture est atomique (fichier temporaire, puis `mv`) et **toute erreur est ignorée** : ni les décisions, ni les actions, ni les codes de sortie du garde-fou ne changent.

C'est le seul chemin d'administration : un changement du garde-fou s'installe avec la même prudence que le filtre.

1. **Banc, avant toute installation** : `bash deploy/okd/host/wireguard/test-garde-fou-metrique.sh <copie de l'ancien script>`, à la racine du dépôt, sous Linux. Il croise 5 scénarios d'OVN-Kubernetes et 3 états du fichier de métrique (inscriptible, absent, en erreur) ; le code de sortie et la suite exacte des actions doivent être identiques. Attendu : `AUCUN ÉCART (15 cas)` ; sinon, on n'installe pas. Le banc refuse de tourner sans `sed` GNU (code 2) : le garde-fou utilise `\+` dans ses expressions, que le `sed` BSD ne comprend pas, et un banc lancé ailleurs ne prouverait pas le comportement du nœud.
2. **Installation**, hors de l'heure d'usage, la session d'administration restant ouverte : `bash -n`, ancien script mis de côté sur le nœud, installation, puis **un passage identique à celui de la minuterie**, sans recharger le filtre ni redémarrer `sophia-wg-filter.service`. Attendu : `garde-fou=0`, `sophia_wg_filter_code 0` et un horodatage dans le fichier, table présente ; au passage suivant de la minuterie, l'horodatage avance.
3. **Retour arrière en une commande** : réinstaller l'ancien script mis de côté et le lancer une fois.

## Points ouverts

- Plus propre à terme : livrer ces fichiers par une `MachineConfig`, comme le reste de la configuration du nœud. Sur un nœud unique, appliquer une MachineConfig **redémarre le nœud** : à planifier.
- Le garde-fou alerte dans le journal du nœud et en métrique (section 5) ; le relais des alertes vers le répartiteur, puis vers l'administrateur, est prévu avec le workflow « incident ».
