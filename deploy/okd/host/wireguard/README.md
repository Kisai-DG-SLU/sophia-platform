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
| `${JVB_UDP_PORT}` | port UDP du média de la visio, exposé sur la même externalIP (section 6) | — |
| `${DEV_GATEWAY_VPN_PORT}` | port SSH de la passerelle de dev sur la même externalIP, réservé à l'administration (section 7) | — |
| `${SOPHIA_VAR_DIR}` | répertoire de la plateforme sur `/var` du nœud, où le garde-fou garde l'image OVN vue et écrit sa métrique (`wg-filter-check.sh`) ; le même que pour la [métrologie](../../monitoring/README.md) | `/var/lib/sophia` |
| `${LAN_NODE_IP}` | adresse du nœud sur le réseau local : secours d'administration hors VPN (section 7) | — |

Toute adresse hors de `${VPN_ADMIN_RANGE}` est un appareil **utilisateur** : HTTP/HTTPS seulement.

## Fichiers

| Fichier | Rôle |
|---|---|
| `wg-filter.nft` | gabarit de la table nftables `inet sophia_wg`, indépendante d'OVN-Kubernetes : **administration** → tout le nœud + Forgejo ; **utilisateurs** → 80/443 seulement ; **rien n'est relayé** vers le réseau local, les pods ou les Services, hors Forgejo pour l'administration (et les règles ajoutées aux sections 6 et 7) |
| `sophia-wg-filter.service` | charge le filtre au démarrage, avant le réseau, puis lance le garde-fou |
| `wg-filter-check.sh` | **garde-fou** : relit tout le ruleset avec le nft d'OVN-Kubernetes ; illisible → supprime la table et alerte dans le journal (le cluster prime, le VPN n'est **jamais** coupé) |
| `sophia-wg-filter-check.{service,timer}` | relance le garde-fou 3 min après le démarrage puis toutes les 15 min (mises à jour d'OKD) |
| `test-garde-fou-metrique.sh` | banc local, **sous Linux seulement** : compare l'ancien et le nouveau garde-fou avec de faux `crictl`, `podman`, `nft` et `logger` |
| `test-nft-ovn.sh` | teste expression par expression ce que le nft d'OVN sait relire (tables sans hook, supprimées aussitôt) |
| `add-peer.sh` | ajoute un appareil : nom, adresse, **clé publique** ; contrôles (format, doublons, plage), sauvegarde du profil, application sans couper les tunnels ; si l'application échoue, s'arrête (code 2) avec le pair écrit dans le profil, **sans jamais relancer `wg0`** |

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

### Appareils iOS : la visio et le réseau par défaut

Sur un iPhone ou un iPad, le profil ajoute **`8.8.8.8/32`** :

```ini
AllowedIPs = ${VPN_NETWORK}, 8.8.8.8/32
```

**Pourquoi** : le WebRTC de WebKit sur iOS (Safari, et Chrome, qui utilise le même moteur) n'énumère que l'interface réseau « par défaut », et libwebrtc la détermine en ouvrant une socket UDP vers `8.8.8.8`, sans rien envoyer. Avec le profil de base, cette interface est le Wi-Fi ou le réseau mobile : l'appareil ne propose que cette adresse comme candidat, et le média de la visio ne passe jamais par le tunnel, alors que ses pages y passent. Avec la route vers `8.8.8.8` dans le tunnel, le VPN devient l'interface « par défaut » pour WebRTC ; le reste d'Internet reste hors du tunnel. Cas réel : sans ce réglage, la visio s'ouvrait sur la tablette, mais l'image et le son n'arrivaient jamais au pont ([module Communication](../../../../docs/modules/communication/documentation.md#média-de-la-visio--trois-causes-en-chaîne)).

- **Effet de bord** : une application qui interroge directement `8.8.8.8` comme serveur DNS passe par le tunnel, où le filtre la refuse ; le DNS du système n'est pas touché.
- **IPv6** : pas d'équivalent nécessaire tant que le pont n'annonce qu'une adresse IPv4 et que le tunnel n'a pas d'IPv6.
- **Android** : profil de base. Chrome sous Android énumère toutes les interfaces, VPN compris, une fois la caméra ou le micro autorisés (à confirmer par l'essai de chaque appareil) ; on n'ajoute `8.8.8.8/32` que s'il l'exige : avec le DNS privé d'Android réglé sur ce fournisseur, tout le DNS du téléphone serait refusé.
- **Essai de chaque appareil**, à la maison puis sur le réseau mobile : une page de diagnostic servie par la visio liste les candidats ICE de l'appareil (caméra autorisée le temps de les démasquer) ; on attend un candidat `host` dans `${VPN_NETWORK}`. La page est retirée une fois tous les appareils essayés.

## 3. Filtre (administrateur, sur le nœud)

Depuis un poste d'**administration** (la session reste ouverte quoi qu'il arrive).

```bash
# rendu du gabarit (liste EXPLICITE : les « $ » du code nft ne sont pas touchés)
export VPN_SERVER_IP=… VPN_ADMIN_RANGE=… GIT_SSH_PORT=… GIT_HTTP_PORT=… SOPHIA_VAR_DIR=…
envsubst '$VPN_SERVER_IP $VPN_ADMIN_RANGE $GIT_SSH_PORT $GIT_HTTP_PORT' < wg-filter.nft > wg-filter.rendu.nft
grep -n '\${' wg-filter.rendu.nft && echo "⚠ variable non rendue" || echo "rendu complet"
envsubst '$SOPHIA_VAR_DIR' < wg-filter-check.sh > wg-filter-check.rendu.sh   # le garde-fou est aussi un gabarit
# copie vers le nœud : wg-filter.rendu.nft, wg-filter-check.rendu.sh, test-nft-ovn.sh, les trois unités systemd
# sur le nœud
sudo nft list ruleset > ~/backup-nft-$(date +%Y%m%d).txt          # sauvegarde
sudo bash test-nft-ovn.sh                                          # compatibilité avec le nft d'OVN
sudo mkdir -p /etc/sophia
sudo install -m 644 wg-filter.rendu.nft /etc/sophia/wg-filter.nft && sudo install -m 755 wg-filter-check.rendu.sh /etc/sophia/wg-filter-check.sh
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

À chaque passage, le garde-fou écrit son code (0 lisible, 1 table retirée, 2 vérification impossible) et un horodatage dans `${SOPHIA_VAR_DIR}/metrics/wg_filter.prom`, que lit l'exporteur du nœud ([`../../monitoring/`](../../monitoring/)). Trois alertes en découlent : filtre retiré, vérification impossible, garde-fou muet depuis plus de 45 minutes. L'écriture est atomique (fichier temporaire, puis `mv`) et **toute erreur est ignorée** : ni les décisions, ni les actions, ni les codes de sortie du garde-fou ne changent.

C'est le seul chemin d'administration : un changement du garde-fou s'installe avec la même prudence que le filtre.

1. **Banc, avant toute installation** : `bash deploy/okd/host/wireguard/test-garde-fou-metrique.sh <copie de l'ancien script>`, à la racine du dépôt, sous Linux. Il croise 5 scénarios d'OVN-Kubernetes et 3 états du fichier de métrique (inscriptible, absent, en erreur) ; le code de sortie et la suite exacte des actions doivent être identiques. Attendu : `AUCUN ÉCART (15 cas)` ; sinon, on n'installe pas. Le banc refuse de tourner sans `sed` GNU (code 2) : le garde-fou utilise `\+` dans ses expressions, que le `sed` BSD ne comprend pas, et un banc lancé ailleurs ne prouverait pas le comportement du nœud.
2. **Installation**, hors de l'heure d'usage, la session d'administration restant ouverte : `bash -n`, ancien script mis de côté sur le nœud, installation, puis **un passage identique à celui de la minuterie**, sans recharger le filtre ni redémarrer `sophia-wg-filter.service`. Attendu : `garde-fou=0`, `sophia_wg_filter_code 0` et un horodatage dans le fichier, table présente ; au passage suivant de la minuterie, l'horodatage avance.
3. **Retour arrière en une commande** : réinstaller l'ancien script mis de côté et le lancer une fois.

## 6. Média de la visio

La visio du [module Communication](../../../../docs/modules/communication/documentation.md) (installée, en recette) fait passer son média par **un seul port UDP**, exposé comme Forgejo par une externalIP sur `${VPN_SERVER_IP}`, et non par un NodePort : un NodePort serait joignable depuis le réseau local, et le pont n'y verrait que l'adresse de jonction d'OVN-Kubernetes. La recette du service est dans [`../../office/`](../../office/README.md#chat-permanent-et-visio).

Une règle, ouverte à **tous** les appareils du VPN (utilisateurs compris), à placer avant le `counter drop` de `forward` :

```
ct original ip daddr ${VPN_SERVER_IP} udp dport ${JVB_UDP_PORT} counter accept comment "visio : média"
```

Ajouter `$JVB_UDP_PORT` à la liste explicite d'`envsubst`, puis charger le filtre comme à la section 3 : contrôle `nft -c`, **interrupteur automatique de 3 minutes**, qui recharge l'ancien filtre (ou retire la table), garde-fou à 0, nouvelle session d'administration, puis arrêt de l'interrupteur. Les réponses du pont vers les appareils passent par `ct state established,related`.

**Le compteur de cette règle n'est pas un contrôle** : il est resté à zéro pendant une visio dont le média était établi. Le chemin a depuis été mesuré (section 7.1) : le trafic redirigé traverse bien la chaîne `forward` et la règle compte ses paquets, mais un compteur à zéro ne prouve pas l'absence de média, et un compteur qui monte ne prouve pas qu'il passe. Ce qui fait foi :

- l'état de débogage du pont média (participants `iceConnected`, paquets reçus et émis) ;
- la table de suivi des connexions du nœud (`/proc/net/nf_conntrack`) : une entrée par appareil vers `${VPN_SERVER_IP}:${JVB_UDP_PORT}`, sans `[UNREPLIED]`.

Côté cluster, le pod du pont voit une source réécrite par la masquerade de l'hôte : sa NetworkPolicy admet le groupe `host-network` sur ce port (voir la [recette](../../office/README.md#chat-permanent-et-visio)). Les appareils iOS ont besoin de leur profil propre (section 2).

## 7. Exposition hors VPN : ce que la revue du filtre a mesuré et corrigé

Une revue du filtre a posé deux questions : un appareil du VPN peut-il joindre, par une externalIP, un service que le filtre lui refuse ? Et un service est-il joignable sans passer par le VPN ? Mesures en lecture seule sur le nœud (`nft list ruleset`, `ip route get`, `ovs-ofctl dump-flows br-ex`, compteurs du filtre), puis deux gestes.

### 7.1 Mesuré : le filtre voit le trafic redirigé, avec le port du Service

Avec la passerelle partagée d'OVN-Kubernetes, le DNAT d'une externalIP est fait **par le noyau, en prérouting** (table `ip nat`, chaîne `OVN-KUBE-EXTERNALIP`), donc **avant le routage**. Le paquet traduit est ensuite routé vers `br-ex` : il est relayé, et traverse la chaîne `forward` de `inet sophia_wg`. Pendant une visio, la règle du média compte ses paquets, et les refus de « rien de relayé » montent pour ce qui n'est pas admis.

Conséquences :

- **pas de contournement par le VPN** : un appareil utilisateur ne joint ni Forgejo ni un autre service publié sur `${VPN_SERVER_IP}` hors règle ; un filtre placé en prérouting n'est pas nécessaire ;
- **le port vu par `forward` est celui du Service après DNAT**, pas celui de l'appareil ni du pod : une règle se rédige sur le port du Service (`port`), qui doit être différent pour chaque Service publié sur la même adresse.

### 7.2 Piège corrigé : un NodePort est servi sur le réseau local

Un NodePort est traduit pour **toute adresse locale du nœud** (`fib daddr type local`), donc aussi pour son adresse sur le réseau local. La chaîne `forward` du filtre ne regarde que ce qui entre par `wg0` : un NodePort échappe à « accès par le VPN seulement ». C'était le cas de la passerelle SSH de développement.

Correctif : le NodePort est remplacé par **un Service à externalIP sur `${VPN_SERVER_IP}`**, comme Forgejo et la visio ([`../../pod-bases/dev-bastion/dev-gateway-service.yaml`](../../pod-bases/dev-bastion/dev-gateway-service.yaml)) :

- deux Services : `dev-gateway`, en ClusterIP seule, et `dev-gateway-vpn`, qui porte l'externalIP. Une externalIP vaut pour **tous** les ports d'un Service, et le port SSH du pod est peut-être déjà pris sur `${VPN_SERVER_IP}` par Forgejo : deux traductions pour la même adresse et le même port, l'une gagnerait au hasard ;
- le port de `dev-gateway-vpn` est **réservé à la plage d'administration** par une règle de plus, avant le `counter drop` de `forward` :

```
ip saddr ${VPN_ADMIN_RANGE} ct original ip daddr ${VPN_SERVER_IP} tcp dport ${DEV_GATEWAY_VPN_PORT} counter accept comment "administration : passerelle de dev"
```

Ordre : le filtre d'abord (sa règle est sans objet tant que le Service n'existe pas), chargé comme à la section 3, sous interrupteur automatique ; puis les Services (`oc diff`, `apply --dry-run=server`, application). Contrôles : SSH vers la passerelle par le VPN depuis un poste d'administration, et le compteur de la règle qui monte (ici, il prouve le chemin) ; depuis le réseau local, `nc -vz ${LAN_NODE_IP} <ancien NodePort>` répond `Connection refused`.

**Inventaire à faire sur toute installation** : `oc get svc -A --field-selector spec.type=NodePort` et les Services `LoadBalancer`. Chacun est servi sur le réseau local.

### 7.3 Admission des externalIPs limitée à l'adresse du VPN

Par défaut (`network.config` `cluster`, `spec.externalIP.policy: {}`), **toute adresse** est admise comme externalIP : un compte administrateur de son seul namespace pourrait publier un Service sur une adresse du réseau local. On limite l'admission à l'adresse du VPN :

```bash
oc patch network.config cluster --type=merge -p '{"spec":{"externalIP":{"policy":{"allowedCIDRs":["${VPN_SERVER_IP}/32"]}}}}' --dry-run=server -o jsonpath='{.spec.externalIP}'
```

puis le même patch sans `--dry-run`. Retour arrière : `allowedCIDRs: null`, jamais `policy: null` (qui refuserait toute externalIP, Forgejo compris).

Deux nuances :

- **un compte `cluster-admin` n'est pas soumis à cette admission**. Un essai sous son propre compte admin, avec un Service d'essai sur une adresse du réseau local, est donc admis et ne prouve rien. L'essai se fait sous un compte limité, en `--dry-run=server` : `oc apply --dry-run=server --as=system:serviceaccount:<namespace>:<compte admin de ce namespace> -f <service d'essai>`, refus `Forbidden` attendu ; les Services existants (Forgejo, visio, passerelle) restent admis. Ce qui reste hors restriction : les comptes liés à `cluster-admin`, à garder rares ;
- le changement produit **une nouvelle révision du kube-apiserver**. Sur un nœud unique, l'API ne répond plus pendant quelques minutes : `oc` échoue, et tout outil qui en dépend aussi (agents, consoles). Les pods, le VPN, SSH, Forgejo et la visio continuent. Avant ce geste : prévenir qu'on perd la main, donner d'avance le retour arrière et le secours de la section 7.4, et choisir un moment calme.

### 7.4 Secours d'administration par le réseau local, hors VPN

Le VPN est le seul chemin d'administration. S'il tombe, `${VPN_SERVER_IP}` (l'adresse de `wg0`) peut disparaître : la viser depuis le réseau local ne sert à rien. Le secours vise **le nœud directement**, sur `${LAN_NODE_IP}`, en SSH par clé : sshd du nœud écoute sur toutes les adresses, et la table `inet sophia_wg` ne filtre que `wg0`. Depuis le nœud, on rebondit vers la ClusterIP de la passerelle de dev ou vers tout service interne.

C'est une exception voulue et étroite : le réseau local de la maison, SSH par clé, vers le nœud seul. Elle s'éprouve **avant** tout geste sur le filtre, les Services ou l'API (VPN coupé sur le poste d'essai, connexion au nœud, rebond vers la passerelle), et ne se retire jamais sans un autre secours en place.

## Points ouverts

- Plus propre à terme : livrer ces fichiers par une `MachineConfig`, comme le reste de la configuration du nœud. Sur un nœud unique, appliquer une MachineConfig **redémarre le nœud** : à planifier.
- La NetworkPolicy de la passerelle de dev admet son port SSH depuis tout le cluster : à resserrer.
- OVS sait aussi livrer `${VPN_SERVER_IP}` arrivée par la carte du réseau local, si une machine de ce réseau route cette adresse vers le nœud. Exposition faible, non éprouvée, compteurs à zéro.
- Le garde-fou alerte dans le journal du nœud et en métrique (section 5) ; ses alertes `warning` et `critical` partent vers l'administrateur hors de la plateforme, par la route générale de l'Alertmanager ([`../../monitoring/`](../../monitoring/)) ; le workflow « incident » reste prévu.
