# MyBB 1.8 — Référence des endpoints front-end (pour LLM)

Ce document décrit l'ensemble des points d'entrée HTTP publics de MyBB (les
scripts `.php` à la racine), le niveau de privilège requis, les paramètres
acceptés et la structure des données renvoyées. Il est destiné à être lu par
un LLM pour raisonner sur l'API HTTP de MyBB.

> Portée : code front-end open-source (GPL) du dépôt. L'ACP (`/admin/`) n'est
> pas couvert. Les noms de colonnes renvoient au schéma
> `inc/schemas/mysql_db_tables.php`.

---

## 1. Conventions communes

### Dispatch
Chaque script lit une action et route via un `switch` :
```php
$mybb->input['action'] = $mybb->get_input('action');
switch($mybb->input['action']) { case "...": ... }
```
Une requête est donc identifiée par `fichier.php` + `action=...`. Certains
scripts n'ont pas d'action et prennent juste un id (`showthread.php?tid=5`).

### Typage des paramètres
`$mybb->get_input($nom, $type)` nettoie et caste l'entrée. Les types :

| Constante | Valeur | Sens |
| --- | --- | --- |
| `MyBB::INPUT_STRING` | 0 | chaîne (défaut) |
| `MyBB::INPUT_INT` | 1 | entier |
| `MyBB::INPUT_ARRAY` | 2 | tableau |
| `MyBB::INPUT_FLOAT` | 3 | flottant |
| `MyBB::INPUT_BOOL` | 4 | booléen |

Dans ce document, un paramètre noté `(int)` est lu avec `INPUT_INT`,
`(array)` avec `INPUT_ARRAY`, sinon c'est une chaîne. GET et POST sont fusionnés
dans `$mybb->input` ; le flux POST est détecté par
`$mybb->request_method == "post"`.

### Protection CSRF
Toute action qui modifie des données en POST exige un jeton `my_post_key`,
vérifié par `verify_post_check($mybb->get_input('my_post_key'))`. Sans jeton
valide, MyBB affiche une page de confirmation au lieu d'exécuter l'action.
Les entrées marquées **POST + my_post_key** dans ce document nécessitent ce
jeton.

### Réponses AJAX
Si `ajax=1` est présent (toujours le cas via `xmlhttp.php`), de nombreuses
actions renvoient du XML ou du JSON au lieu d'une page HTML. Le format exact
est précisé par endpoint.

---

## 2. Modèle de privilèges

Le privilège effectif résulte de trois couches cumulatives.

### 2.1 Groupe d'utilisateur (`mybb_usergroups`)
L'utilisateur courant est `$mybb->user` ; ses permissions agrégées sont dans
`$mybb->usergroup`. Groupes par défaut (`inc/seeds/usergroups.xml`) :

| gid | Groupe | Rôle |
| --- | --- | --- |
| 1 | Guests | visiteurs non connectés |
| 2 | Registered | membres inscrits |
| 3 | Super Moderators | modérateurs globaux |
| 4 | Administrators | administrateurs |
| 5 | Awaiting Activation | compte non activé |
| 6 | Moderators | modérateurs |
| 7 | Banned | bannis |

Un utilisateur est connecté si `$mybb->user['uid'] > 0`. Champs de permission
de groupe les plus utilisés (vrai = `1`) :

`canview`, `canviewthreads`, `canviewprofiles`, `canviewmemberlist`,
`canviewcalendar`, `canviewonline`, `cansearch`, `canusecp` (usercp),
`canusepms`, `cansendpms`, `canpostthreads`, `canpostreplys`, `canpostpolls`,
`canvotepolls`, `canratethreads`, `canratemembers`, `cangivereputations`,
`canbereported`, `caneditposts`, `candeleteposts`, `candeletethreads`,
`caneditprofiles`, `canchangename`, `cansendemail`, `canuploadavatars`,
`canusesig`, `canwarnusers`, `canmodcp`, `cancp` (accès ACP),
`canbeinvisible`, `isbannedgroup`.

### 2.2 Permissions par forum (`mybb_forumpermissions`)
Résolues par `forum_permissions($fid)` et croisées avec le groupe. Elles
peuvent restreindre un forum précis :

`canview`, `canviewthreads`, `canpostthreads`, `canpostreplys`,
`canpostpolls`, `canvotepolls`, `canpostattachments`, `cansearch`,
`canonlyviewownthreads`, `canonlyreplyownthreads`, `caneditposts`,
`candeleteposts`, `candeletethreads`, `canratethreads`,
`canviewdeletionnotice`.

Un forum peut aussi exiger un mot de passe (`forum_password`), vérifié par
`check_forum_password($fid)` (cookie `forumpass[fid]`).

### 2.3 Modération (`mybb_moderators`)
`is_moderator($fid, $permission, $uid)` renvoie vrai si l'utilisateur est
modérateur du forum (ou super-modérateur / admin). Permissions de modérateur :

`caneditposts`, `cansoftdeleteposts`, `canrestoreposts`, `candeleteposts`,
`cansoftdeletethreads`, `canrestorethreads`, `candeletethreads`,
`canviewips`, `canviewunapprove`, `canviewdeleted`,
`canopenclosethreads`, `canstickunstickthreads`, `canapproveunapprovethreads`,
`canapproveunapproveposts`, `canapproveunapproveattachs`, `canmanagethreads`,
`canmanagepolls`, `canpostclosedthreads`, `canmovetononmodforum`,
`canmanageannouncements`, `canmanagereportedposts`, `canusecustomtools`,
`canviewmodlog`.

### Niveaux de privilège utilisés dans ce document
- **Public** : aucune authentification (soumis au `canview` du groupe Guests).
- **Vue forum** : `canview` + `canviewthreads` du forum concerné (+ mot de passe éventuel).
- **Connecté** : `$mybb->user['uid'] > 0`.
- **Permission X** : champ de groupe ou de forum nommé explicitement.
- **Modérateur (perm Y)** : `is_moderator($fid, 'Y')`.
- **Admin** : `cancp == 1`.

---

## 3. Endpoints

<!--SECTIONS-->
