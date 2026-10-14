# MyBB 1.8 — Référence des endpoints front-end (pour LLM)

Ce document décrit l'ensemble des points d'entrée HTTP publics de MyBB (les
scripts `.php` à la racine), le niveau de privilège requis, les paramètres
acceptés et la structure des données renvoyées. Il est destiné à être lu par
un LLM pour raisonner sur l'API HTTP de MyBB.

> Portée : code front-end open-source (GPL) du dépôt. L'ACP (`/admin/`) n'est
> pas couvert. Les noms de colonnes renvoient au schéma
> `inc/schemas/mysql_db_tables.php`. Vérifié sur le code présent dans ce dépôt
> (rendu des pages via Twig `\MyBB\View\template('...twig', [...])`).

---

## 1. Conventions communes

### Dispatch
Chaque script lit une action et route via un `switch` (ou une chaîne de `if`) :
```php
$mybb->input['action'] = $mybb->get_input('action');
switch($mybb->input['action']) { case "...": ... }
```
Une requête est donc identifiée par `fichier.php` + `action=...`. Certains
scripts n'ont pas d'action et prennent juste un id (`showthread.php?tid=5`).

### Typage des paramètres
`$mybb->get_input($nom, $type)` nettoie et caste l'entrée.

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
Toute action qui modifie des données en POST exige en principe un jeton
`my_post_key`, vérifié par `verify_post_check($mybb->get_input('my_post_key'))`.
Sans jeton valide, MyBB affiche une page de confirmation. Les entrées marquées
**POST + my_post_key** le nécessitent. Exceptions notables qui s'appuient sur un
CAPTCHA/anti-bot au lieu du jeton : `member.php` `do_register`,
`do_resendactivation`, `do_lostpw`, et `private.php` `do_search`.

### Réponses AJAX
`xmlhttp.php` charge un noyau allégé et répond en JSON ou en fragment HTML.
Convention JSON de `xmlhttp.php` : la chaîne JSON `"true"` signifie succès ;
toute autre chaîne JSON est un message d'erreur ; les erreurs structurées sont
`{"errors":[...]}` (via `xmlhttp_error()`, `Content-type: application/json`).
Plusieurs actions de `misc.php`, `reputation.php` et `report.php` renvoient un
fragment de gabarit (paramètres `ajax` / `nomodal` / `no_modal` / `modal`).

---

## 2. Modèle de privilèges

Le privilège effectif résulte de trois couches cumulatives.

### 2.1 Groupe d'utilisateur (`mybb_usergroups`)
`$mybb->user` est l'utilisateur courant ; ses permissions agrégées sont dans
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

Connecté = `$mybb->user['uid'] > 0` (invité = `uid == 0`). Champs de permission
de groupe les plus utilisés (vrai = `1`) : `canview`, `canviewthreads`,
`canviewprofiles`, `canviewmemberlist`, `canviewcalendar`, `canviewonline`,
`cansearch`, `canusercp`, `canusepms`, `cansendpms`, `cantrackpms`,
`candenypmreceipts`, `canpostthreads`, `canpostreplys`, `canpostpolls`,
`canvotepolls`, `canundovotes`, `canratethreads`, `canratemembers`,
`cangivereputations`, `candeletereputations`, `canbereported`, `caneditposts`,
`candeleteposts`, `candeletethreads`, `caneditprofiles`, `canchangename`,
`canchangewebsite`, `cancustomtitle`, `candisplaygroup`, `cansendemail`,
`cansendemailoverride`, `canuploadavatars`, `canusesig`, `canusesigxposts`,
`canwarnusers`, `canreceivewarnings`, `canmodcp`, `canmanageannounce`,
`canmanagemodqueue`, `canmanagereportedcontent`, `canviewmodlogs`,
`canviewwarnlogs`, `canuseipsearch`, `canbanusers`, `canbeinvisible`,
`cancp` (accès ACP), `issupermod`, `isbannedgroup`.

### 2.2 Permissions par forum (`mybb_forumpermissions`)
Résolues par `forum_permissions($fid)`. Peuvent restreindre un forum précis :
`canview`, `canviewthreads`, `canpostthreads`, `canpostreplys`, `canpostpolls`,
`canvotepolls`, `canpostattachments`, `candlattachments`, `cansearch`,
`canonlyviewownthreads`, `canonlyreplyownthreads`, `caneditposts`,
`candeleteposts`, `candeletethreads`, `canratethreads`,
`canviewdeletionnotice`. Un forum peut aussi exiger un mot de passe,
vérifié par `check_forum_password($fid)` (cookie `mybb[forumpass][fid]`).

### 2.3 Modération (`mybb_moderators`)
`is_moderator($fid, $permission, $uid)` : vrai si modérateur du forum (ou
super-modérateur / admin). Permissions : `caneditposts`, `cansoftdeleteposts`,
`canrestoreposts`, `candeleteposts`, `cansoftdeletethreads`,
`canrestorethreads`, `candeletethreads`, `canviewips`, `canviewunapprove`,
`canviewdeleted`, `canopenclosethreads`, `canstickunstickthreads`,
`canapproveunapprovethreads`, `canapproveunapproveposts`,
`canapproveunapproveattachs`, `canmanagethreads`, `canmanagepolls`,
`canpostclosedthreads`, `canmovetononmodforum`, `canmanageannouncements`,
`canmanagereportedposts`, `canusecustomtools`, `canviewmodlog`.

> Attention aux paires voisines : la garde globale d'annonces utilise le champ
> de groupe `canmanageannounce` mais le contrôle par forum utilise
> `is_moderator($fid, "canmanageannouncements")`. De même, groupe
> `canmanagereportedcontent` vs forum `canmanagereportedposts`, et groupe
> `canviewmodlogs` vs forum `canviewmodlog`.

### Niveaux de privilège utilisés ci-dessous
- **Public** : aucune authentification (soumis au `canview` des invités).
- **Vue forum** : `canview` + `canviewthreads` du forum (+ mot de passe éventuel).
- **Connecté** : `$mybb->user['uid'] > 0`.
- **Permission X** : champ de groupe ou de forum nommé explicitement.
- **Modérateur (perm Y)** : `is_moderator($fid, 'Y')`.
- **Admin** : `cancp == 1`.

Format de chaque entrée : **Nom** · `URL` · méthode · privilège · paramètres ·
données renvoyées.

---

## 3. Authentification et inscription — `member.php`

Public. Pas de `switch` unique : chaîne de `if($mybb->input['action'] == ...)`.
Garde pré-dispatch pour `register`/`do_register` (si `cancp != 1`) : bloque si
`disableregs`, si déjà connecté, et applique l'anti-flood
`maxregsbetweentime` via `users.regip`.

#### Inscrire un nouvel utilisateur (traitement)
`member.php?action=do_register` · POST (pas de my_post_key, anti-bot
`regtime`+captcha caché) · invité uniquement, honore `disableregs` ·
params : `username`, `password`, `password2`, `email`, `email2`, `referrername`,
`timezoneoffset`, `language`, `profile_fields`(array), `coppa`(int),
`allownotices`/`hideemail`/`receivepms`/`pmnotice`/`pmnotify`/`invisible`(int),
`question_id`, `answer`, `regtime`(int) · insère dans `users` via
`UserDataHandler::insert_user()` (+ `awaitingactivation` selon `regtype`), puis
message/redirection selon `regtype` (none/verify/randompass/admin/both/coppa).

#### Afficher le formulaire d'inscription
`member.php?action=register` · GET · invité · params : `bday1/2/3`(int), `step`,
`agree`, `coppa`(int), `profile_fields`(array) · rend `register_coppa.twig`,
`register_agreement.twig` ou `register.twig` (fuseaux, champs du cache
`profilefields`, captcha, question de sécurité).

#### Afficher le formulaire de consentement COPPA
`member.php?action=coppa_form` · GET · public · aucun paramètre · rend
`coppa_form.twig`.

#### Activer un compte via code d'activation
`member.php?action=activate` · GET · public · params : `uid`(int), `code`,
`username` · valide `awaitingactivation` (types r/e/b) ; passe `users.usergroup`
à 2, applique un changement d'email ou la validation admin, puis redirige.
Sinon rend `activate.twig`.

#### Afficher la page de renvoi de l'email d'activation
`member.php?action=resendactivation` · GET · public (erreur si `regtype==admin`
ou déjà activé) · rend `resendactivation.twig`.

#### Renvoyer l'email d'activation (traitement)
`member.php?action=do_resendactivation` · POST (pas de my_post_key) · public ·
param : `email` · pour un compte `usergroup==5`, régénère et renvoie le code
(`awaitingactivation`), puis redirige vers l'index.

#### Demander la réinitialisation du mot de passe perdu (traitement)
`member.php?action=do_lostpw` · POST (captcha, pas de my_post_key) · public ·
params : `email` + captcha · insère `awaitingactivation` type `p`, envoie le
code par email, `log_security_action('lost_password')`, redirige.

#### Afficher le formulaire de mot de passe perdu
`member.php?action=lostpw` · GET · public · param : `email` · rend
`lostpw.twig` (captcha, erreurs).

#### Réinitialiser le mot de passe via code
`member.php?action=resetpassword` · GET (traite si `code` présent) · public ·
params : `uid`(int), `code`, `username` · valide le code type `p`, génère un
mot de passe, `update_user()`, l'envoie par email,
`log_security_action('reset_password')`. Sinon rend `resetpassword.twig`.

#### Authentifier l'utilisateur (connexion)
`member.php?action=do_login` · **POST + my_post_key** · invité · params :
`username`, `password`, `remember`, `imagestring`, `url`, variantes
`quick_username`/`quick_password`/`quick_remember` · `LoginDataHandler` →
`complete_login()` et redirection vers `url` assaini ou l'index ; en échec,
incrémente `users.loginattempts` et peut déclencher un captcha.

#### Afficher le formulaire de connexion
`member.php?action=login` · GET · public · params : `username`, `password`
(repopulés en erreur) · rend `login.twig`.

#### Déconnecter l'utilisateur
`member.php?action=logout` · GET · connecté (valide `sid`/`logoutkey`) · efface
les cookies, supprime la ligne `sessions`, met à jour `users.lastvisit`,
redirige.

#### Consulter les notes d'un membre (modérateurs)
`member.php?action=viewnotes` · GET · connecté + `canmodcp` · param : `uid`(int)
· rend `viewnotes.twig` affichant `users.usernotes`.

#### Afficher le profil public d'un membre
`member.php?action=profile` · GET · `canviewprofiles` · param : `uid`(int,
défaut = soi) · agrège la ligne `users`, permissions, groupe d'affichage, stats,
présence (`sessions`), champs perso (`userfields`), réputation, niveau
d'avertissement, état ban/ami/ignoré. Rend `profile.twig`.

#### Envoyer un email à un membre (traitement)
`member.php?action=do_emailuser` · **POST + my_post_key** · `cansendemail`
(+ `maxemails`/`emailfloodtime`) · params : `uid`(int), `subject`, `message`,
`fromname`/`fromemail` (invités), captcha · `my_mail()`, journalise dans
`maillogs` (type 1), redirige vers le profil.

#### Afficher le formulaire d'envoi d'email à un membre
`member.php?action=emailuser` · GET · `cansendemail` (bloqué si dans
l'`ignorelist` du destinataire sauf `cansendemailoverride`) · param : `uid`(int)
· rend `emailuser.twig`.

#### Lister les utilisateurs parrainés par un membre
`member.php?action=referrals` · GET · accès page (gated par `usereferrals`) ·
params : `uid`(int, requis), `page`(int) · compte `users WHERE referrer=uid`,
`get_user_referrals()`, rend `referrals/referrals.twig`.

#### Rediriger vers l'index (aucune action)
`member.php` · GET · public · `Location: index.php`.

---

## 4. Espace membre — `usercp.php`

Garde globale : `uid != 0 && canusercp == 1` pour toutes les actions. Les
`do_*` en POST appellent `verify_post_check`.

#### Afficher l'accueil du panneau membre (défaut)
`usercp.php` · GET · `canusercp` · agrège messages/jour, réputation, derniers
avertissements, abonnements avec nouveaux messages, derniers sujets. Rend
`usercp/home.twig`.

#### Enregistrer les modifications du profil
`usercp.php?action=do_profile` · POST + my_post_key · `canusercp` (`website`
si `canchangewebsite`, `usertitle` si `cancustomtitle`) · params : `away`(int),
`awayday/month/year`(int), `awayreason`, `bday1/2/3`(int), `birthdayprivacy`,
`profile_fields`(array), `website`, `usertitle`, `reverttitle` · `update_user()`
sur `users`, redirige vers `action=profile`.

#### Afficher le formulaire d'édition du profil
`usercp.php?action=profile` · GET · `canusercp` · rend `usercp/profile.twig`
(champs requis/perso du cache `profilefields`, titres).

#### Enregistrer les préférences / options
`usercp.php?action=do_options` · POST + my_post_key · `canusercp` (`invisible`
si `canbeinvisible`) · params : `style`(int), `dateformat`(int),
`timeformat`(int), `timezoneoffset`, `language`, et de nombreux booléens
(`allownotices`, `hideemail`, `subscriptionmethod`, `showsigs`, `showavatars`,
`showquickreply`, `receivepms`, `pmnotice`, `pmnotify`, `showredirect`,
`classicpostbit`…), `tpp`(int), `ppp`(int) · `update_user()`.

#### Afficher les options du compte
`usercp.php?action=options` · GET · `canusercp` · rend `usercp/options.twig`
(formats de date/heure, fuseaux, langues, styles).

#### Modifier l'adresse email
`usercp.php?action=do_email` · POST + my_post_key · `canusercp` + mot de passe
courant · params : `password`, `email`, `email2` · `update_user()` ou
`awaitingactivation` type `e`/`b` + email ; `log_security_action('changed_email')`.

#### Afficher le formulaire de changement d'email
`usercp.php?action=email` · GET · `canusercp` · rend `usercp/email.twig`.

#### Modifier le mot de passe
`usercp.php?action=do_password` · POST + my_post_key · `canusercp` +
`oldpassword` valide · params : `oldpassword`, `password`, `password2` ·
`update_user()`, réinitialise le cookie `mybbuser`, envoie un email,
`log_security_action('changed_password')`.

#### Afficher le formulaire de changement de mot de passe
`usercp.php?action=password` · GET · `canusercp` · rend `usercp/password.twig`.

#### Changer le nom d'utilisateur
`usercp.php?action=do_changename` · POST + my_post_key · `canusercp` +
`canchangename` + mot de passe · params : `password`, `username` ·
`update_user()` sur `users.username`.

#### Afficher le formulaire de changement de nom
`usercp.php?action=changename` · GET · `canusercp` + `canchangename` · rend
`usercp/changename.twig`.

#### Lister les sujets suivis
`usercp.php?action=subscriptions` · GET · `canusercp` · param : `page`(int) ·
`threadsubscriptions` JOIN `threads`/`users`, rend
`usercp/subscribed_threads.twig`.

#### Modifier/supprimer des abonnements aux sujets
`usercp.php?action=do_subscriptions` · POST + my_post_key · `canusercp` ·
params : `check`(array tids), `do` (delete / no_notification /
email_notification / pm_notification) · met à jour/supprime
`threadsubscriptions.notification`.

#### Lister les forums suivis
`usercp.php?action=forumsubscriptions` · GET · `canusercp` ·
`forumsubscriptions` JOIN `forums`/`threads`, rend
`usercp/subscribed_forums.twig`.

#### S'abonner à un sujet (traitement direct)
`usercp.php?action=do_addsubscription` · POST + my_post_key · `canusercp` +
perms forum + `check_forum_password` · params : `tid`, `notification`(int),
`referrer` · `add_subscribed_thread()`.

#### S'abonner à un sujet ou un forum
`usercp.php?action=addsubscription` (`type=forum` → forum) · GET/POST +
my_post_key · `canusercp` + perms forum · params : `type`, `fid`(int),
`tid`(int) · forum : `add_subscribed_forum()` ; sujet : rend
`usercp/subscribe_thread.twig`.

#### Se désabonner d'un sujet ou forum
`usercp.php?action=removesubscription` · POST (ou GET avec my_post_key valide) ·
`canusercp` + perms forum · params : `type`, `fid`(int), `tid`(int) ·
`remove_subscribed_forum()`/`remove_subscribed_thread()`. Sans jeton valide en
GET, rend un gabarit de confirmation (`removesubscription_forum/thread.twig`).

#### Supprimer tous les abonnements
`usercp.php?action=removesubscriptions` · POST + my_post_key · `canusercp` ·
param : `type` · supprime tous les `forumsubscriptions`/`threadsubscriptions`.

#### Enregistrer la signature
`usercp.php?action=do_editsig` · POST + my_post_key · `canusercp` (bloqué si
signature suspendue) · params : `signature`, `updateposts`, `preview` · met à
jour `users.signature` (et éventuellement `posts.includesig`). Un bloc amont
pré-valide via `verify_signature()`.

#### Afficher l'éditeur de signature
`usercp.php?action=editsig` · GET · `canusercp` + `canusesig` (et
`canusesigxposts` ≤ postnum) · rend `usercp/editsig.twig`.

#### Modifier / supprimer l'avatar
`usercp.php?action=do_avatar` · POST + my_post_key · `canusercp` (upload si
`canuploadavatars`, distant si `allowremoteavatars`) · params : `remove`,
`$_FILES['avatarupload']`, `avatarurl` · met à jour `users.avatar*`.

#### Afficher le formulaire d'avatar
`usercp.php?action=avatar` · GET · `canusercp` · rend `usercp/avatar.twig`.

#### Accepter une demande d'ami
`usercp.php?action=acceptrequest` · POST + my_post_key · `canusercp` (requête
ciblant soi) · param : `id`(int) · met à jour les deux `users.buddylist`, PM,
supprime la requête.

#### Refuser une demande d'ami
`usercp.php?action=declinerequest` · POST + my_post_key · `canusercp` · param :
`id`(int) · supprime la ligne `buddyrequests`.

#### Annuler une demande d'ami envoyée
`usercp.php?action=cancelrequest` · POST + my_post_key · `canusercp` · param :
`id`(int) · supprime la ligne `buddyrequests`.

#### Gérer les listes d'amis / ignorés (traitement)
`usercp.php?action=do_editlists` · POST + my_post_key · `canusercp` · params :
`manage` (buddy/ignored), `add_username`, `delete`(int), `ajax` · met à jour
`users.buddylist`/`ignorelist`. En AJAX, renvoie du JS (`text/javascript`).

#### Afficher les listes d'amis / ignorés
`usercp.php?action=editlists` · GET (ou fragment AJAX) · `canusercp` · params :
`manage`, `ajax` · rend `usercp/editlists.twig` (ou un sous-gabarit en AJAX).

#### Lister les brouillons
`usercp.php?action=drafts` · GET · `canusercp` · `posts` (visible=-2) JOIN
`threads`/`forums`, rend `usercp/drafts.twig`.

#### Supprimer les brouillons sélectionnés
`usercp.php?action=do_drafts` · POST + my_post_key · `canusercp` · param :
`deletedraft`(array id→post|thread) · supprime les `threads`/`posts`
brouillons de l'utilisateur.

#### Rejoindre / quitter / changer de groupe
`usercp.php?action=usergroups` · GET (affichage) / POST + my_post_key
(mutations) · `canusercp` · params : `displaygroup`(int), `leavegroup`(int),
`joingroup`(int), `reason`, `acceptinvite`(int) · met à jour
`users.displaygroup`, `join_usergroup`/`leave_usergroup`, `joinrequests`. Rend
`usercp/usergroups.twig` ou `joingroup.twig`.

#### Lister les pièces jointes de l'utilisateur
`usercp.php?action=attachments` · GET · `canusercp` + `enableattachments` ·
param : `page`(int) · `attachments` JOIN `posts`/`threads`, calcule le quota,
rend `usercp/attachments.twig`.

#### Supprimer les pièces jointes sélectionnées
`usercp.php?action=do_attachments` · POST + my_post_key · `canusercp` · param :
`attachments`(array aid) · `remove_attachment()`.

#### Consulter son journal d'avertissements
`usercp.php?action=warninglog` · GET · `canusercp` + `warningpoints` > 0 ·
param : `page`(int) · `warnings` LEFT JOIN `warningtypes`, rend
`usercp/warninglog.twig`.

#### Consulter le journal de sécurité
`usercp.php?action=securitylog` · GET · `canusercp` · param : `page`(int|last) ·
`securitylog` (type, ipaddress, dateline), rend `usercp/securitylog.twig`.

#### Enregistrer le bloc-notes personnel
`usercp.php?action=do_notepad` · POST + my_post_key · `canusercp` · param :
`notepad` (≤ 60000) · met à jour `users.notepad`.

#### Accuser réception d'un avertissement
`usercp.php?action=do_acknowledge` · POST + my_post_key · `canusercp` (son
propre avertissement) · param : `wid`(int) · `acknowledge_warning()`.

---

## 5. Consultation du contenu

Toutes GET. Socle de permission : `forum_permissions()`
(`canview`/`canviewthreads`/`canonlyviewownthreads`) + `check_forum_password()`
+ visibilité modérateur via `is_moderator()`.

### index.php

#### Afficher la liste des forums (accueil)
`index.php` · public (accès board) · aucun paramètre lu · `sessions`+`users`
(qui est en ligne), `forums`+`forumsread`+`users` pour `build_forumbits()`,
caches (usergroups, birthdays, stats, mostonline, moderators, spiders). Rend
`index/index.twig`.

### forumdisplay.php

#### Rediriger les fid spéciaux négatifs
`forumdisplay.php?fid=-1…-5` · public · param : `fid`(int) · redirige
(-1 index, -2 search, -3 usercp, -4 private, -5 online).

#### Afficher un forum et ses sujets paginés
`forumdisplay.php?fid=2&page=3` · vue forum (`canview`+`canviewthreads`,
`canonlyviewownthreads`, mot de passe) · params : `fid`(int, requis),
`page`(int), `datecut`(int), `prefix`(int), `order`, `sortby`
(subject/replies/views/username/dateline, défaut lastpost) · `threads t` JOIN
`users` (starter + lastposter) → `tid, subject, replies, views, lastpost,
prefix, visible…` ; annonces (`announcements`+`users`) ; sessions des lecteurs.
Rend `forumdisplay/forumdisplay.twig`.

### showthread.php

#### Afficher un sujet et ses réponses paginées (défaut `thread`)
`showthread.php?tid=5&page=3` ou `?pid=123` · vue forum + visibilité
unapproved/deleted · params : `tid`(int) ou `pid`(int), `page`(int|last),
`mode` (linear/threaded), `highlight` · `get_thread()` → ligne `threads` ;
sondage (`polls`+`pollvotes`) ; `posts p` JOIN `users`/`userfields`/
`reportedcontent` rendus par `build_postbit()` ; `attachments` par pid ;
sujets similaires (fulltext). Rend `showthread/showthread.twig`.

#### Aller au premier message non lu (`newpost`)
`showthread.php?tid=5&action=newpost` · vue forum · param : `tid`(int) · lit
`threadsread`/`forumsread`, trouve le premier `posts.pid` plus récent, redirige.

#### Aller au dernier message (`lastpost`)
`showthread.php?tid=5&action=lastpost` · vue forum · param : `tid`(int) ·
redirige vers le dernier `posts.pid`.

#### Aller au sujet suivant plus récent (`nextnewest`)
`showthread.php?tid=5&action=nextnewest` · vue forum · param : `tid`(int) ·
`threads` où `lastpost > thread.lastpost`, redirige (erreur si aucun).

#### Aller au sujet suivant plus ancien (`nextoldest`)
`showthread.php?tid=5&action=nextoldest` · vue forum · param : `tid`(int) ·
`threads` où `lastpost < thread.lastpost`, redirige (erreur si aucun).

### portal.php

#### Afficher le portail
`portal.php?page=2` · public (erreur si `portal==0`) · param : `page`(int,
pagine les annonces) · blocs selon réglages : bienvenue (compteurs depuis
`lastvisit`), MP, stats (cache `stats`), qui est en ligne, dernières discussions
(`threads`+`users`), annonces (`posts`+`threads`+`users` du forum
`portal_announcementsfid`). Rend `portal/portal.twig`.

### announcements.php

#### Afficher une annonce de forum
`announcements.php?aid=7` · vue forum si `fid>0` sinon public ; dans la fenêtre
`startdate`/`enddate` · param : `aid`(int) · `announcements a` JOIN
`users`/`userfields`, rendu via `build_postbit(..., 3)`. Rend
`announcements/announcements.twig`.

### printthread.php

#### Afficher la version imprimable d'un sujet
`printthread.php?tid=5&page=2` · vue forum + visibilité · params : `tid`(int),
`page`(int) · `get_thread()` + `posts p` JOIN `users` parsés via
`parse_message`, `attachments` par pid. Rend `printthread/printthread.twig`.

### online.php

Garde : `canviewonline == 1`.

#### Afficher les utilisateurs en ligne (défaut)
`online.php?page=2&sortby=username` · `canviewonline` (invisibles masqués sauf
`canviewwolinvis`/soi) · params : `sortby` (username/location), `page`(int) ·
`sessions s` JOIN `users u` dédupliqués, activité via `fetch_wol_activity()`.
Rend `online/online.twig`.

#### Afficher les membres actifs des dernières 24h (`today`)
`online.php?action=today&page=2` · `canviewonline` · param : `page`(int) ·
`users` où `lastactive > now-86400`. Rend `online/today.twig`.

### stats.php

#### Afficher les statistiques du forum
`stats.php` · public (erreur si `statsenabled != 1`) · aucun paramètre · cache
`stats` + ratios, âge du board (`users.regdate` min), caches
`most_replied_threads`/`most_viewed_threads`/`statistics`, top forum. Rend
`stats/stats.twig`.

---

## 6. Création et édition de contenu

### newthread.php

Garde : forum ouvert, `type=="f"`, `canview`+`canpostthreads`,
`check_forum_password`, quota `maxposts`/jour.

#### Afficher le formulaire de création d'un sujet (défaut)
`newthread.php?fid=X` · GET · `canpostthreads` · params : `fid`(int),
`posthash`, `previewpost`, `threadprefix`(int), `icon`(int), `subject`,
`message`, `postoptions[]` (signature, disablesmilies), `postpoll`(int),
`numpolloptions`(int), `attachmentaid`(int) · rend `newthread/newthread.twig`
(prefixes, icônes, pièces jointes, captcha invités, aperçu via
`build_postbit`).

#### Modifier un brouillon de sujet
`newthread.php?action=editdraft&tid=X` · GET · connecté + propriétaire du
brouillon + `canpostthreads` · params : `tid`(int), `pid`(int) · préremplit
depuis le post brouillon.

#### Publier un nouveau sujet (enregistrement)
`newthread.php?action=do_newthread` · **POST + my_post_key** · `canpostthreads`
(invités : StopForumSpam + captcha ; sondage : `canpostpolls`) · params :
`subject`, `message`, `threadprefix`(int), `icon`(int), `username` (invité),
`posthash`, `postoptions[]` (signature, subscriptionmethod, disablesmilies),
`modoptions[]`(array), `savedraft`, `postpoll`(int), `_FILES['attachments']` ·
`PostDataHandler("insert")` → `insert_thread()` (insère `threads` + premier
`posts`), garde anti-doublon 600 s. Redirige (brouillon → drafts ; sondage →
polls ; sinon lien du sujet).

> Sous-chemins pièces jointes (toute action, avant dispatch) :
> `add_attachments()` / `remove_attachment()` (`attachmentaid`(int),
> `attachmentact=remove`), my_post_key requis, JSON si `ajax=1`.

### newreply.php

Garde : forum ouvert `type=="f"`, `canview`+`canpostreplys`,
`canonlyviewownthreads`/`canonlyreplyownthreads`, sujet non fermé (sauf
`canpostclosedthreads`), quota `maxposts`/jour.

#### Afficher le formulaire de réponse (défaut)
`newreply.php?tid=X&replyto=PID` · GET · `canpostreplys` · params : `tid`(int),
`replyto`(int), `posthash`, `previewpost`, `subject`, `message`, `icon`(int),
`postoptions[]`, `quoted_ids`(int), `method=quickreply` · rend
`newreply/newreply.twig` (multiquote, revue du sujet, pièces jointes, captcha,
aperçu).

#### Modifier un brouillon de réponse
`newreply.php?action=editdraft&pid=X` · GET · connecté + propriétaire +
`canpostreplys` · params : `pid`(int), `tid`(int) · préremplit depuis le
brouillon.

#### Publier une réponse (enregistrement)
`newreply.php?action=do_newreply` · **POST + my_post_key** · `canpostreplys`
(invités : StopForumSpam + captcha ; sujet non fermé) · params : `tid`(int),
`replyto`(int), `subject`, `message`, `icon`(int), `username` (invité),
`posthash`, `pid`(int, brouillon), `savedraft`, `postoptions[]`, `modoptions[]`,
`quoted_ids`, `ajax`, `lastpid`(int), `_FILES['attachments']` ·
`PostDataHandler("insert")` → `insert_post()` (insère `posts`, met à jour les
compteurs `threads`), anti-doublon 600 s. Réponse rapide AJAX : JSON du postbit.

### editpost.php

Invités bloqués. Charge `get_post($pid)`, `$thread`, `$forum`.

#### Afficher le formulaire de modification d'un message (défaut)
`editpost.php?pid=X` · GET (POST en aperçu) · `is_moderator($fid,"caneditposts")`
OU (`caneditposts` forum + propriétaire + dans `edittimelimit` + non
unapproved/deleted) · params : `pid`(int), `previewpost`, `threadprefix`(int),
`subject`, `message`, `editreason`, `icon`(int), `postoptions[]`, `postpoll`(int)
· charge la ligne `posts` (message, subject, editreason, icon, uid). Rend
`editpost/editpost.twig`.

#### Enregistrer la modification d'un message
`editpost.php?action=do_editpost` · **POST + my_post_key** · même permission
d'édition · params : `pid`(int), `threadprefix`(int), `subject`, `icon`(int),
`message`, `editreason`, `postoptions[]`, `postpoll`(int) ·
`PostDataHandler("update")` → `update_post()` (met à jour `posts`, et `threads`
si premier message).

#### Supprimer un message
`editpost.php?action=deletepost&pid=X` · **POST + my_post_key** · premier
message : mod `candeletethreads`/`cansoftdeletethreads` ou (`candeletethreads`
forum + propriétaire) ; réponse : `candeleteposts`/`cansoftdeleteposts` · params :
`pid`(int), `delete`(int=1), `ajax` · classe `Moderation` (soft/hard delete),
`mark_reports`, modlog. JSON si `ajax`.

#### Restaurer un message supprimé
`editpost.php?action=restorepost&pid=X` · **POST + my_post_key** · mod
`canrestorethreads` (premier) / `canrestoreposts` (réponse), post `visible==-1`
· params : `pid`(int), `restore`(int=1), `ajax` · `restore_threads`/
`restore_posts`, modlog.

### polls.php

#### Afficher le formulaire de création d'un sondage
`polls.php?action=newpoll&tid=X` · GET · auteur du sujet OU
`is_moderator($fid,"canmanagepolls")` ; `canview`+`canpostthreads`+
`canpostpolls` ; pas de sondage existant ; `polltimelimit` · params : `tid`(int),
`polloptions`/`numpolloptions`(int), `question`, `options[]`, `postoptions[]`
(multiple, public), `timeout`(int), `maxoptions`(int) · rend
`polls/newpoll.twig`.

#### Créer un sondage (enregistrement)
`polls.php?action=do_newpoll` · **POST + my_post_key** · idem newpoll · params :
`tid`(int), `polloptions`(int), `question`, `options[]`, `postoptions[]`,
`timeout`(int), `maxoptions`(int) · insère dans `polls` (options jointes par
`||~|~||`), met à jour `threads.poll`.

#### Afficher le formulaire de modification d'un sondage
`polls.php?action=editpoll&pid=X` · GET · `is_moderator($fid,"canmanagepolls")`
· param : `pid`(int) · charge la ligne `polls`. Rend `polls/editpoll.twig`.

#### Enregistrer la modification d'un sondage
`polls.php?action=do_editpoll&pid=X` · **POST + my_post_key** ·
`is_moderator(..,"canmanagepolls")` · params : `pid`(int), `numoptions`(int),
`question`, `postoptions[]` (multiple, public, closed), `options[]`, `votes[]`,
`timeout`(int), `maxoptions`(int) · `update_query("polls", ...)`, modlog.

#### Afficher les résultats d'un sondage
`polls.php?action=showresults&pid=X` · GET · `canviewthreads`+`canview`
(+ `canonlyviewownthreads`) ; liste des votants seulement si `poll.public` ou
mod · param : `pid`(int) · agrège `pollvotes`+`users`. Rend
`polls/showresults.twig`.

#### Voter dans un sondage
`polls.php?action=vote&pid=X` · **POST + my_post_key** · `canvotepolls` ;
sondage/sujet ouvert et non expiré ; pas déjà voté · params : `pid`,
`option`(int pour simple / array pour multiple) · insère dans `pollvotes`,
recalcule `polls.votes`/`numvotes`.

#### Annuler son vote dans un sondage
`polls.php?action=do_undovote&pid=X` · POST (my_post_key) · `canundovotes` ;
non expiré ; a voté · param : `pid`(int) · supprime de `pollvotes`, décrémente
les compteurs.

---

## 7. Modération

### moderation.php

Invités bloqués. Garde POST globale : toute action sauf `getip`, `getpmip`,
`cancel_delayedmoderation`, `delayedmoderation`, `threadnotes`, `purgespammer`,
`viewthreadnotes` exige `request_method=="post"` ; quasi toutes appellent
`verify_post_check`. Les actions inline lisent les ids via les cookies
`inlinemod_*` (`getids()`), supportent `inlinetype=search`+`searchid`(int).

#### Annuler une action de modération différée
`moderation.php?action=cancel_delayedmoderation&did=D&tid=T` · POST+jeton ·
`is_moderator($fid,"canmanagethreads")` · params : `did`(int), `tid` · supprime
`delayedmoderation`.

#### Planifier une action de modération différée (form + exécution)
`moderation.php?action=delayedmoderation&tid=T` (+ `do_delayedmoderation`) ·
POST+jeton · `is_moderator($fid,"canmanagethreads")` + sous-permission par type ·
params : `tid`/`tids`, `fid`, `inlinetype`, `searchid`(int), `type`,
`date_day/month/year`(int), `date_time`, `delayedmoderation[]` (method,
new_forum, redirect_expire, subject, threadurl) · insère `delayedmoderation`
ou rend `moderation/delayedmoderation.twig`.

#### Ouvrir ou fermer un sujet
`moderation.php?action=openclosethread&tid=T` · POST+jeton ·
`is_moderator($fid,"canopenclosethreads")` · param : `tid` · bascule
`threads.closed`.

#### Épingler ou désépingler un sujet
`moderation.php?action=stick&tid=T` · POST+jeton ·
`is_moderator($fid,"canstickunstickthreads")` · bascule `threads.sticky`.

#### Supprimer les redirections vers un sujet
`moderation.php?action=removeredirects&tid=T` · POST+jeton ·
`is_moderator($fid,"canmanagethreads")` · `remove_redirects`.

#### Supprimer un sujet (confirmation / exécution)
`moderation.php?action=deletethread&tid=T` · GET (form) / `do_deletethread`
POST+jeton · `is_moderator($fid,"candeletethreads")` OU (`candeletethreads`
forum + propriétaire) · `delete_thread` (+ `posts`), `mark_reports`. Redirige
vers le forum.

#### Supprimer un sondage (confirmation / exécution)
`moderation.php?action=deletepoll&tid=T` · GET (form) / `do_deletepoll`
POST+jeton (input `delete`) · `is_moderator($fid,"canmanagepolls")` OU
(`candeletethreads` + propriétaire) · `delete_poll($pid)` (supprime `polls`+
`pollvotes`, vide `threads.poll`).

#### Approuver / Désapprouver un sujet
`moderation.php?action=approvethread|unapprovethread&tid=T` · POST+jeton ·
`is_moderator($fid,"canapproveunapprovethreads")` · `threads.visible` 1/0.

#### Restaurer / Supprimer temporairement un sujet
`moderation.php?action=restorethread|softdeletethread&tid=T` · POST+jeton ·
`is_moderator($fid,"canrestorethreads"|"cansoftdeletethreads")` ·
`threads.visible` ±1.

#### Déplacer / copier un sujet (form / exécution)
`moderation.php?action=move&tid=T` · GET (form) / `do_move` POST+jeton ·
`is_moderator($fid,"canmanagethreads")` ET (`is_moderator($moveto,
"canmanagethreads")` OU `canmovetononmodforum`) · params : `moveto`(int),
`method` (move/redirect/copy), `redirect_expire`(int) · `move_thread`.

#### Consulter les notes de modération d'un sujet
`moderation.php?action=viewthreadnotes&tid=T` · GET · `is_moderator($fid)` ·
rend `moderation/viewthreadnotes.twig`.

#### Modifier les notes de modération d'un sujet
`moderation.php?action=threadnotes&tid=T` · GET (form) / `do_threadnotes`
POST+jeton · `is_moderator($fid,"canmanagethreads")` · param : `threadnotes` ·
met à jour `threads.notes`.

#### Afficher l'adresse IP d'un message
`moderation.php?action=getip&pid=P` · GET · `is_moderator($fid,"canviewips")` ·
rend `moderation/getip.twig` ou `getip_modal.twig`.

#### Afficher l'adresse IP d'un message privé
`moderation.php?action=getpmip&pmid=M` · GET · `issupermod` · param : `pmid`(int)
· rend `moderation/getpmip.twig`.

#### Fusionner deux sujets (form / exécution)
`moderation.php?action=merge&tid=T` · GET (form) / `do_merge` POST+jeton ·
`is_moderator($fid,"canmanagethreads")` sur les deux forums · params :
`threadurl`, `subject` · `merge_threads()`.

#### Scinder un sujet (sélection / exécution)
`moderation.php?action=split&tid=T` · GET (form) / `do_split` POST+jeton ·
`is_moderator($fid,"canmanagethreads")` · params : `splitpost[]`(array),
`moveto`(int), `newsubject` · `split_posts()`.

#### Supprimer les abonnements à un sujet
`moderation.php?action=removesubscriptions&tid=T` · POST+jeton ·
`is_moderator($fid,"canmanagethreads")` · `remove_thread_subscriptions`.

#### Actions inline multi-sujets
`moderation.php?action=multi*threads` · POST+jeton (sauf formulaires
`multideletethreads`/`multimovethreads` en GET) · perm par action via
`is_moderator`/`is_moderator_by_tids` · ids via `threads` (liste) ou cookies :
- `multideletethreads` / `do_multideletethreads` — Supprimer plusieurs sujets (`candeletethreads`).
- `multiopenthreads` / `multiclosethreads` — Ouvrir / Fermer (`canopenclosethreads`).
- `multiapprovethreads` / `multiunapprovethreads` — Approuver / Désapprouver (`canapproveunapprovethreads`).
- `multirestorethreads` / `multisoftdeletethreads` — Restaurer / Supprimer temporairement (`canrestorethreads`/`cansoftdeletethreads`).
- `multistickthreads` / `multiunstickthreads` — Épingler / Désépingler (`canstickunstickthreads`).
- `multimovethreads` / `do_multimovethreads` — Déplacer (`canmanagethreads`) ; params `moveto`(int), `method`, `redirect_expire`(int).

#### Actions inline multi-messages
`moderation.php?action=multi*posts` · POST+jeton (formulaires en GET) · perm via
`is_moderator_by_pids` · param `posts` (liste pid) :
- `multideleteposts` / `do_multideleteposts` — Supprimer plusieurs messages (`candeleteposts`).
- `multimergeposts` / `do_multimergeposts` — Fusionner (`canmanagethreads`) ; `mergepost[]`, `sep`.
- `multisplitposts` / `do_multisplitposts` — Scinder vers un nouveau sujet (`canmanagethreads`) ; `moveto`(int), `newsubject`.
- `multimoveposts` / `do_multimoveposts` — Déplacer vers un autre sujet (`canmanagethreads`) ; `threadurl`.
- `multiapproveposts` / `multiunapproveposts` — Approuver / Désapprouver (`canapproveunapproveposts`).
- `multirestoreposts` / `multisoftdeleteposts` — Restaurer / Supprimer temporairement (`canrestoreposts`/`cansoftdeleteposts`).

#### Purger un spammeur
`moderation.php?action=purgespammer&uid=U` · GET (confirm) / `do_purgespammer`
POST+jeton · `is_member(purgespammergroups)` + `purgespammer_show()` · param :
`uid`(int) · `UserDataHandler('delete')` (ban + suppression contenu ou
suppression totale), option StopForumSpam, modlog.

#### Exécuter un outil de modération personnalisé (défaut)
`moderation.php?action=<id>&modtype=thread|inlinethread|post|inlinepost` ·
POST+jeton · `is_member(tool.groups)` + `is_moderator_by_*(.., "canusecustomtools")`
· params : `action`(int, id d'outil), `modtype`, `tid`/`pid`/`fid`,
`inlinetype`, `searchid`(int), `confirm` · `CustomModeration->execute()`.

### modcp.php

Garde : `uid != 0 && canmodcp == 1`. Pour les non super-mods, listes de forums
par permission construites via `is_moderator()`.

#### Afficher l'accueil du panneau de modération (défaut)
`modcp.php` · GET · `canmodcp` · agrège files d'attente, derniers
`moderatorlog`, bans à expirer, `modnotes`. Rend `modcp/home.twig`.

#### Afficher les contenus signalés en attente
`modcp.php?action=reports` · GET · `canmanagereportedcontent` (+ compteur par
forum) · param : `page`(int) · `reportedcontent` JOIN `users`/`reportreasons`.
Rend `modcp/reports.twig`.

#### Marquer les contenus signalés comme traités
`modcp.php?action=do_reports` · POST+jeton · `canmanagereportedcontent` ·
params : `reports`(array), `page`(int) · `reportedcontent.reportstatus=1`.

#### Afficher l'historique de tous les signalements
`modcp.php?action=allreports` · GET · `canmanagereportedcontent` · params :
`page`(int|last), `rid`(int) · rend `modcp/allreports.twig`.

#### Consulter le journal des actions de modération
`modcp.php?action=modlogs` · GET · `canviewmodlogs` (+ par forum
`canviewmodlog`) · params : `perpage`(int), `uid`(int), `fid`(int), `sortby`,
`order`, `page`(int|last) · `moderatorlog` JOIN `users`/`threads`/`forums`/
`posts`. Rend `modcp/modlogs.twig`.

#### Lister les annonces
`modcp.php?action=announcements` · GET · `canmanageannounce` · `announcements`,
`fetch_forum_announcements()`. Rend `modcp/announcements.twig`.

#### Créer une annonce (form / exécution)
`modcp.php?action=new_announcement` · GET (form) / `do_new_announcement`
POST+jeton · `canmanageannounce` + (`issupermod` ou
`is_moderator($fid,"canmanageannouncements")`) · params : `fid`(int), `title`,
`message`, `starttime_*`, `endtime_*`, `allowhtml`/`allowmycode`/`allowsmilies`
(int), `preview` · insère `announcements`, modlog.

#### Modifier une annonce (form / exécution)
`modcp.php?action=edit_announcement` · GET (form) / `do_edit_announcement`
POST+jeton · `canmanageannounce` + par forum · params : `aid`(int) + champs
ci-dessus · met à jour `announcements`.

#### Supprimer une annonce (confirmation / exécution)
`modcp.php?action=delete_announcement` · GET (form) / `do_delete_announcement`
POST+jeton · `canmanageannounce` + par forum · param : `aid` · supprime
`announcements`, modlog.

#### Afficher la file de modération
`modcp.php?action=modqueue` (`type`=threads/posts/attachments) · GET ·
`canmanagemodqueue` (+ compteurs par type) · param : `page`(int|last) · contenus
`visible=0`. Rend `modcp/modqueue_*.twig`.

#### Traiter la file de modération
`modcp.php?action=do_modqueue` · POST+jeton · `canmanagemodqueue` · params :
`threads`/`posts`/`attachments` (arrays id→approve/delete) · classe
`Moderation`, modlog.

#### Rechercher / lister les utilisateurs à modérer
`modcp.php?action=finduser` · GET · `caneditprofiles` · params : `perpage`(int),
`username`, `sortby`, `order`, `page`(int|last) · `users` LIKE username. Rend
`modcp/finduser.twig`.

#### Afficher le formulaire d'édition de profil membre
`modcp.php?action=editprofile` · GET · `caneditprofiles` +
`modcp_can_manage_user(uid)` · param : `uid`(int) · `users`+`userfields`. Rend
`modcp/editprofile.twig`.

#### Enregistrer les modifications du profil d'un membre
`modcp.php?action=do_editprofile` · POST+jeton · `caneditprofiles` +
`modcp_can_manage_user` · params : `uid`, `profile_fields`(array), `website`,
`signature`, `usernotes`, `away`(int), `bday*`(int), `usertitle`, options de
sanction (`suspendsignature`/`moderateposting`/`suspendposting`/`suspendpm`/
`suspendavatar` + `*_period`/`*_time`) · `update_user()` + suspensions, modlog.

#### Consulter le journal des avertissements (tous membres)
`modcp.php?action=warninglogs` · GET · `canviewwarnlogs` · param : `filter`
(array : username, uid, mod_username, mod_uid, reason, sortby, order, per_page),
`page`(int) · `warnings` JOIN `users`/`warningtypes`. Rend
`modcp/warninglogs.twig`.

#### Rechercher des messages et membres par IP
`modcp.php?action=ipsearch` · GET · `canuseipsearch` · params : `ipaddress`,
`search_posts`, `search_users`, `perpage`(int), `page`(int|last) · cherche
`posts.ipaddress` et `users.regip/lastip` (plages via `fetch_ip_range`). Rend
`modcp/ipsearch.twig`.

#### Résoudre la localisation et le nom d'hôte d'une IP
`modcp.php?action=iplookup` (`modal=1`) · GET · `canuseipsearch` · params :
`ipaddress`, `modal`(int) · GeoIP + `gethostbyaddr`. Rend
`modcp/iplookup[_modal].twig`.

#### Lister les utilisateurs bannis
`modcp.php?action=banning` · GET · `canbanusers` · param : `page`(int|last) ·
`banned` JOIN `users`. Rend `modcp/banning.twig`.

#### Bannir un utilisateur (form / exécution)
`modcp.php?action=banuser` · GET (form) / `do_banuser` POST+jeton ·
`canbanusers` · params : `username`, `usergroup`(int, groupe banni),
`liftafter`, `banreason` · `validate_ban()`+`insert_ban()` (écrit `banned`),
modlog.

#### Modifier un bannissement (form / exécution)
`modcp.php?action=editban` · GET (form) / `do_editban` POST+jeton ·
`canbanusers` + créateur du ban ou `issupermod`/`cancp` · params : `uid`(int),
`usergroup`(int), `liftafter`, `banreason` · `update_ban()`, modlog.

#### Lever un bannissement
`modcp.php?action=liftban` · POST+jeton · `canbanusers` + créateur ou
`issupermod`/`cancp` · param : `uid`(int) · `lift_ban()`, modlog.

#### Enregistrer les notes partagées de modération
`modcp.php?action=do_modnotes` · POST+jeton · `canmodcp` · param : `modnotes` ·
écrit le cache `modnotes`.

### warnings.php

Garde : `enablewarningsystem==1` ; expiration via `expire_warnings()`. Toutes
exigent `canwarnusers` ; cible avec `canreceivewarnings` et
`modcp_can_manage_user()`.

#### Lister les avertissements d'un utilisateur (défaut)
`warnings.php?uid=U` · GET · `canwarnusers` · params : `uid`(int), `page`(int) ·
`warnings` JOIN `warningtypes`/`users`/`posts`. Rend `warnings/warnings.twig`.

#### Afficher le formulaire d'avertissement
`warnings.php?action=warn&uid=U` · GET · `canwarnusers` ; plafond
`maxwarningsday` ; pas soi ; sous `maxwarningpoints` · params : `uid`(int),
`pid`(int), `type` · charge `warningtypes`/`warninglevels`. Rend
`warnings/warn.twig`.

#### Infliger un avertissement
`warnings.php?action=do_warn&uid=U` · POST+jeton · `canwarnusers` (post :
`canview` forum) · params : `uid`(int), `notes`, `type` (ou `custom`),
`custom_reason`, `custom_points`(int), `expires`(int), `expires_period`,
`requiresacknowledgement`(int), `pid`(int), `send_pm`(int), `pm_subject`,
`pm_message`, `pm_anonymous`(int) · `validate_warning()`+`insert_warning()`,
PM optionnelle.

#### Afficher le détail d'un avertissement
`warnings.php?action=view&wid=W` · GET · `canwarnusers` · param : `wid`(int) ·
`warnings` JOIN `warningtypes`/`users`/`posts`. Rend `warnings/view.twig`.

#### Révoquer un avertissement
`warnings.php?action=do_revoke&wid=W` · POST+jeton · `canwarnusers` ; non déjà
révoqué · params : `wid`(int), `reason` (requis) · `update_warning()`.

---

## 8. Social et profils

### private.php (messagerie privée)

Garde : `enablepms==1`, connecté, `canusepms != 0`. `fid` = dossier (1 Inbox,
2 Sent, 3 Drafts, 4 Trash). Table `privatemessages` (pmid, uid, fromid, toid,
subject, message, folder, status, receipt, dateline, readtime, deletetime).

#### Lister les messages privés d'un dossier (défaut)
`private.php?fid=F` · GET · `canusepms` · params : `fid`(int), `order`,
`sortby` (subject/username/dateline), `page`(int) · rend `private/private.twig`.

#### Rechercher dans les messages privés
`private.php?action=do_search` · POST (**pas** de my_post_key) · `canusepms`
(+ anti-flood) · params : `keywords`, `subject`(int), `message`(int), `sender`,
`status[]`, `folder[]`, `sort`, `sortordr` · insère un `searchlog`, redirige
vers `action=results`.

#### Afficher les résultats de recherche de messages
`private.php?action=results&sid=S` · GET · `canusepms` ; `searchlog` = sid+uid ·
params : `sid`, `order`, `sortby`, `page`(int) · rend `private/results.twig`.

#### Afficher la recherche avancée des MP
`private.php?action=advanced_search` · GET · `canusepms` · rend
`private/advanced_search.twig`.

#### Masquer la notification de nouveau MP
`private.php?action=dismiss_notice` · POST+jeton · `canusepms` (si `pmnotice==2`)
· param : `ajax` · met `users.pmnotice=1`.

#### Envoyer un message privé
`private.php?action=do_send` · POST+jeton · `canusepms` + `cansendpms` (bloqué
si `suspendpm` ; accusé requiert `cantrackpms`) · params : `to` (noms séparés
par virgule), `bcc`, `subject`, `message`, `icon`(int), `do`
(reply/forward/replyall), `pmid`(int), `options[]` (signature, disablesmilies,
savecopy, readreceipt), `saveasdraft` · `PMDataHandler->insert_pm()`,
anti-doublon.

#### Composer / répondre / transférer un message privé
`private.php?action=send` (`&pmid=`, `&do=reply|replyall|forward`, `&uid=`) ·
GET · `canusepms` + `cansendpms` · params : `pmid`(int), `do`, `uid`(int), `to`,
`bcc`, `subject`, `message`, `icon`(int), `options[]`, `preview` · rend
`private/send.twig`.

#### Lire un message privé
`private.php?action=read&pmid=P` · GET · `canusepms` ; MP appartenant à soi ·
params : `pmid`(int), `denyreceipt`(int, requiert `candenypmreceipts`) · marque
`status=1`, pose `readtime`. Rend `private/read.twig`.

#### Consulter le suivi des accusés de lecture
`private.php?action=tracking` · GET · `canusepms` + `cantrackpms` · params :
`read_page`, `unread_page` (int|last) · rend `private/tracking.twig`.

#### Gérer le suivi des messages
`private.php?action=do_tracking` · POST+jeton · `canusepms` · params :
`readcheck[]`, `unreadcheck[]`, drapeaux `stoptracking`/`cancel` · met
`receipt=0` ou supprime les MP non lus suivis.

#### Arrêter tout le suivi
`private.php?action=stopalltracking` · POST+jeton · `canusepms` · met
`receipt=0` sur tous les MP envoyés suivis.

#### Afficher la gestion des dossiers
`private.php?action=folders` · GET · `canusepms` · rend `private/folders.twig`.

#### Enregistrer / renommer les dossiers
`private.php?action=do_folders` · POST+jeton · `canusepms` · param : `folder[]`
(id→nom) · reconstruit `users.pmfolders`.

#### Afficher la page de vidage des dossiers
`private.php?action=empty` · GET · `canusepms` (erreur si aucun MP) · rend
`private/empty.twig`.

#### Vider des dossiers de messages
`private.php?action=do_empty` · POST+jeton · `canusepms` · params : `empty[]`
(dossier→1), `keepunread`(int) · supprime les MP des dossiers choisis.

#### Déplacer ou supprimer des messages en masse
`private.php?action=do_stuff` · POST+jeton · `canusepms` · params : `moveto`,
`delete`, `check[]`, `fromfid` · déplace vers un dossier ou corbeille (dossier 4).

#### Supprimer un message privé
`private.php?action=delete&pmid=P` · POST+jeton · `canusepms` ; MP à soi ·
param : `pmid`(int) · suppression définitive si déjà corbeille, sinon dossier 4.

#### Afficher / exporter les messages privés
`private.php?action=export` (form) / `do_export` POST+jeton · `canusepms` ·
params : `pmid`(int) OU `exportfolders[]`+`daycut`(int)+`dayway`+
`exportunread`(int), `exporttype` (html/csv/txt), `deletepms`(int) · rend un
téléchargement `private/export/{html,csv,txt}.twig`.

### reputation.php

Garde : `enablereputation==1`, `canview==1`, cible `uid` requise, fusion
`user_permissions($uid)`. Table `reputation` (rid, uid, adduid, pid, reputation,
comments, dateline).

#### Afficher les réputations reçues (défaut)
`reputation.php?uid=U` · GET · `canviewprofiles != 0` + cible
`usereputationsystem==1` · params : `uid`(int), `show`
(all/positive/neutral/negative), `sort` (username/dateline), `page`(int) ·
stats + lignes `reputation` JOIN `users`. Rend `reputation/reputation.twig`.

#### Afficher le formulaire pour donner une réputation
`reputation.php?action=add&uid=U` · GET · `cangivereputations` + cible
`usereputationsystem` + pas soi · params : `uid`(int), `pid`(int), `nomodal` ·
rend `reputation/add.twig` (ou `add_error[_nomodal].twig`).

#### Donner ou modifier un point de réputation
`reputation.php?action=do_add&uid=U` · POST+jeton · `cangivereputations` ;
cible `usereputationsystem` ; pas soi ; plafonné par `reputationpower` ; quotas
`maxreputationsday`/`peruser`/`perthread` · params : `uid`(int), `pid`(int),
`reputation`(int), `comments`, `delete`, `nomodal` · insère/met à jour
`reputation`, resynchronise `users.reputation`. Rend `reputation/added.twig` ou
`deleted.twig`.

#### Supprimer une réputation
`reputation.php?action=delete&uid=U&rid=R` · POST+jeton · `issupermod` OU
(`candeletereputations` + `adduid`==soi) · params : `uid`(int), `rid`(int) ·
supprime la ligne, resynchronise, modlog.

### report.php

Garde : connecté. `type` (post/profile/reputation) détermine ce que `pid`
désigne. Table `reportedcontent` (id, id2, id3, uid, reasonid, reason,
reporters, reportstatus, type).

#### Afficher le formulaire de signalement (défaut)
`report.php?type=T&pid=X` (`no_modal=1`) · GET · connecté (+ `canview`/
`canbereported` pour les posts) · params : `type`, `pid`(int), `no_modal` ·
charge les raisons (`reportreasons`). Rend `report/report.twig` ou
`report_reasons.twig` (no_modal).

#### Signaler un message, profil ou commentaire de réputation
`report.php?action=do_report&type=T&pid=X` · POST+jeton · connecté ; pour
`type=post` : `canview` + mot de passe forum ; cible `canbereported` · params :
`type`, `pid`(int), `reason`(int), `comment` (≥3 si la raison l'exige),
`no_modal` · `add_report()` ou `update_report()` (ajoute à `reporters` si
doublon). Rend `report/report_thanks.twig` + script inline.

### memberlist.php

Garde : `enablememberlist==1` + `canviewmemberlist != 0`.

#### Lister les membres (défaut)
`memberlist.php?sort=..&order=..&letter=A&username=..` · GET ·
`canviewmemberlist` · params : `sort`
(regdate/lastvisit/reputation/postnum/threadnum/referrals/username),
`order` (ascending/descending), `perpage`(int 1–500), `page`(int), `letter`,
`username`+`username_match` (begins/contains/exact), `website` · `users u` JOIN
`userfields f`. Rend `memberlist/memberlist.twig`.

#### Afficher le formulaire de recherche de membres
`memberlist.php?action=search` · GET · `canviewmemberlist` · rend
`memberlist/search.twig`.

### showteam.php

#### Afficher l'équipe du forum (défaut)
`showteam.php` · GET · `enableshowteam==1` (pas de flag par utilisateur) ·
groupes `usergroups` où `showforumteam=1`, modérateurs `moderators` JOIN
`forums`/`users`, dirigeants `groupleaders`. Rend `showteam/showteam.twig`.

### managegroup.php

Garde : `gid` valide ; appelant dirigeant de groupe (`groupleaders`) ou
`cancp==1`. Capacités dans la ligne `groupleaders` (`canmanagemembers`,
`caninvitemembers`, `canmanagerequests`).

#### Afficher la gestion du groupe (défaut)
`managegroup.php?gid=G` · GET · dirigeant de groupe · param : `gid`(int),
`page`(int) · dirigeants + membres (`additionalgroups` ou `usergroup=gid`). Rend
`managegroup/managegroup.twig`.

#### Ajouter un utilisateur au groupe
`managegroup.php?action=do_add&gid=G` · POST+jeton · `canmanagemembers` · param :
`username` · `join_usergroup()`, supprime `joinrequests`.

#### Inviter un utilisateur à rejoindre le groupe
`managegroup.php?action=do_invite&gid=G` · POST+jeton · `caninvitemembers` ·
param : `inviteusername` · insère `joinrequests` (invite=1), envoie une PM.

#### Lister les demandes d'adhésion en attente
`managegroup.php?action=joinrequests&gid=G` · GET · dirigeant · param : `gid`(int)
· `joinrequests` JOIN `users`. Rend `managegroup/joinrequests.twig`.

#### Accepter ou refuser les demandes d'adhésion
`managegroup.php?action=do_joinrequests&gid=G` · POST+jeton · `canmanagerequests`
· param : `request[]` (uid→accept|decline) · `join_usergroup()` pour les
acceptés, supprime les demandes.

#### Retirer des utilisateurs du groupe
`managegroup.php?action=do_manageusers&gid=G` · POST+jeton · `canmanagemembers` ·
param : `removeuser[]` (uids) · `leave_usergroup()`.

---

## 9. API AJAX et recherche

### xmlhttp.php (API AJAX de MyBB)

Noyau allégé. Erreurs via `xmlhttp_error()` → `{"errors":[...]}`. Le board fermé
bloque tout sauf `refresh_captcha`/`validate_captcha` sauf `canviewboardclosed`.

#### Récupérer des noms d'utilisateur pour l'autocomplétion
`xmlhttp.php?action=get_users` · GET · public · params : `query` (≥2 car.,
requis), `search_type`(int : 0 commence / 1 finit / 2 contient), `getone`(int) ·
JSON : objet `{uid,id,text}` si `getone`, sinon tableau de tels objets.

#### Éditer en ligne le sujet d'un fil (quick edit)
`xmlhttp.php?action=edit_subject` · **POST + my_post_key** ·
`is_moderator($fid,"caneditposts")` OU (auteur + non fermé + forum ouvert +
`caneditposts` + dans `edittimelimit`) · params : `tid`(int), `value` (≤120) ·
`PostDataHandler("update")`. JSON `{"subject":"<a ...>...</a>"}`.

#### Récupérer / mettre à jour un message en ligne (quick edit)
`xmlhttp.php?action=edit_post` (`do=get_post|update_post`) · GET (get) / POST +
my_post_key (update) · post `visible != -1` + mot de passe forum + même double
contrôle que edit_subject · params : `pid`(int), `do`, `value`, `editreason` ·
`get_post` → chaîne JSON du message brut ; `update_post` → `{"message":"<HTML>",
"editedmsg":null}` (ou objet de modération si non approuvé).

#### Récupérer les messages multi-cités (multiquote)
`xmlhttp.php?action=get_multiquoted` · GET · public (filtrage visibilité) ·
params : cookie `multiquote` (requis), `tid`(int), `load_all` · JSON
`{"message":"<citations>"}`.

#### Rafraîchir le CAPTCHA image
`xmlhttp.php?action=refresh_captcha` · POST/GET · public · param : `imagehash` ·
remplace la ligne `captcha`. JSON `{"imagehash":"<newhash>"}`.

#### Valider la réponse CAPTCHA
`xmlhttp.php?action=validate_captcha` · GET · public · params : `imagehash`,
`imagestring` · JSON `"true"` si correct, sinon chaîne d'erreur.

#### Rafraîchir la question de sécurité
`xmlhttp.php?action=refresh_question` · GET (si `securityquestion`) · public ·
param : `question_id` (sid) · JSON `{"question":"<HTML>","sid":"<newsid>"}`.

#### Valider la réponse à la question de sécurité
`xmlhttp.php?action=validate_question` · GET · public · params : `question`
(sid), `answer` · JSON `"true"` si correct, sinon chaîne d'erreur.

#### Vérifier la complexité d'un mot de passe
`xmlhttp.php?action=complex_password` · GET · public · param : `password` ·
JSON `"true"` si conforme (longueur + chiffre + minuscule + majuscule).

#### Vérifier la disponibilité d'un nom d'utilisateur
`xmlhttp.php?action=username_availability` · **POST + my_post_key** · public ·
param : `username` · JSON `"true"` si disponible, sinon chaîne d'erreur
(`username_taken`, `banned_username`…).

#### Vérifier la disponibilité d'une adresse e-mail
`xmlhttp.php?action=email_availability` · **POST + my_post_key** · public ·
param : `email` · JSON `"true"` si valide/disponible, sinon chaîne d'erreur.

#### Récupérer le sélecteur de liste d'amis
`xmlhttp.php?action=get_buddyselect` · GET · connecté avec `buddylist` non vide ·
`text/plain` : fragment `xmlhttp/buddyselect.twig`.

#### Récupérer les parrainages d'un utilisateur
`xmlhttp.php?action=get_referrals` · GET · public · param : `uid`(int, requis) ·
`text/plain` : fragment `referrals/referrals_popup.twig` (compte + liste des
utilisateurs parrainés avec liens de profil et date d'inscription).

### search.php

Garde : `cansearch == 0` → refus pour toutes les actions. Les actions de
recherche créent une ligne `searchlog` (sid, uid, dateline, ipaddress, threads,
posts, resulttype, querycache, keywords) puis redirigent vers `action=results`.

#### Afficher la page de recherche (défaut)
`search.php` · GET · `cansearch` · rend `search/search.twig`.

#### Effectuer une recherche
`search.php?action=do_search` · POST · `cansearch` (+ anti-flood
`searchfloodtime`) · params : `keywords`, `author`, `postthread`(int),
`matchusername`(int), `postdate`(int), `pddir`(int), `forums` (array/single),
`numreplies`(int), `threadprefix`(array), `showresults`, `sortby`, `sortordr`,
`visible`(int, mods) · moteur fulltext ou LIKE ; insère `searchlog`, redirige.

#### Afficher les résultats de recherche
`search.php?action=results&sid=S` · GET · `cansearch` ; sid valide · params :
`sid`, `sortby`, `order`, `page`(int), `uid`(int) · rend
`search/results_threads.twig` ou `results_posts.twig`.

#### Rechercher dans un fil précis
`search.php?action=thread&tid=T` · GET · `cansearch` + vue forum · params :
`tid`(int), `keywords` · `searchlog` (posts), redirige.

#### Trouver les messages d'un invité
`search.php?action=findguest` · GET · `cansearch` · aucun (uid=0) · `searchlog`
(posts), redirige.

#### Trouver les messages d'un utilisateur
`search.php?action=finduser&uid=U` · GET · `cansearch` · param : `uid`(int) ·
`searchlog` (posts), redirige.

#### Trouver les fils d'un utilisateur
`search.php?action=finduserthreads&uid=U` · GET · `cansearch` · param :
`uid`(int) · `searchlog` (threads), redirige.

#### Trouver les nouveaux messages depuis la dernière visite
`search.php?action=getnew` · GET · `cansearch` · params : `fid`(int) ou `fids` ·
WHERE `lastpost >= lastvisit`, `searchlog` (threads), redirige.

#### Trouver les fils des N derniers jours
`search.php?action=getdaily` · GET · `cansearch` · params : `days`(int),
`fid`/`fids` · WHERE `lastpost >= now-86400*days`, redirige.

### misc.php

Divers utilitaires. Le paramètre `ajax` bascule des réponses texte brut.

#### Basculer l'heure d'été (DST)
`misc.php?action=dstswitch` · POST · connecté · param : `ajax` · bascule
`users.dst` (si `dstcorrection==2`).

#### Marquer un forum / tous les forums comme lus
`misc.php?action=markread` · GET/POST (my_post_key pour connectés) · tout ·
params : `fid`, `ajax` · `mark_forum_read`/`mark_all_forums_read`.

#### Effacer le mot de passe de forum mémorisé
`misc.php?action=clearpass` · POST + my_post_key · tout · param : `fid`(int) ·
supprime le cookie `forumpass[fid]`.

#### Afficher les règles d'un forum
`misc.php?action=rules&fid=F` · GET · `canview` forum · param : `fid`(int) ·
rend `misc/rules.twig`.

#### Effectuer une recherche dans l'aide
`misc.php?action=do_helpsearch` · POST · `helpsearch==1` (+ anti-flood) ·
params : `keywords`, `name`(int), `document`(int) · `searchlog`, redirige vers
`helpresults`.

#### Afficher les résultats de recherche d'aide
`misc.php?action=helpresults&sid=S` · GET · `helpsearch==1` ; sid+uid · params :
`sid`, `page`(int) · rend `misc/helpresults.twig`.

#### Afficher un document ou l'index d'aide
`misc.php?action=help` · GET · public · params : `hid`(int), `highlight` · rend
`misc/help_helpdoc.twig` ou `help.twig`.

#### Fenêtre popup de la liste d'amis
`misc.php?action=buddypopup` · GET (POST pour retrait) · connecté · param :
`removebuddy`(int, my_post_key) · rend `misc/buddypopup.twig` (amis en
ligne/hors ligne).

#### Qui a posté dans un fil
`misc.php?action=whoposted&tid=T` · GET · vue forum · params : `tid`(int),
`modal`(int), `sort` · comptes par utilisateur. Rend
`misc/whoposted[_modal].twig`.

#### Afficher la liste des émoticônes
`misc.php?action=smilies` · GET · public · params : `popup`, `editor` · rend
`misc/smilies[_modal].twig`.

#### Configurer un flux de syndication
`misc.php?action=syndication` · GET · public (forums non visibles exclus) ·
params : `fid`(int), `version` (json/atom1.0/rss2.0), `forums`(array|all),
`limit`(int 1–50) · construit une URL de flux. Rend `misc/syndication.twig`.

#### Effacer tous les cookies MyBB
`misc.php?action=clearcookies` · POST + my_post_key · tout · supprime
l'ensemble des cookies MyBB, redirige.

---

## 10. Fichiers, flux et utilitaires

### attachment.php

#### Télécharger une pièce jointe
`attachment.php?aid=12` (ou `?pid=34`, ou `?thumbnail=12`) · GET · post chargé
via `get_post` ; sauf brouillon : `canview`+`canviewthreads`+
`canonlyviewownthreads` + `candlattachments` (hors miniature) ; pièce jointe
visible/approuvée sauf mod `canviewunapprove` ; type réservé possible
(`is_member(attachtype.groups)`) · params : `aid`(int), `pid`(int),
`thumbnail`(int) · diffuse les octets par blocs de 8192. Fichier complet :
`Content-type` = `attachments.filetype` (inline pour pdf/images/texte sauf
`forcedownload`), incrémente `downloads`. Miniature : type dérivé de
l'extension, sans incrément. Ligne `attachments` (aid, pid, uid, filename,
filetype, filesize, attachname, thumbnail, visible, downloads).

### calendar.php

Gardes : `enablecalendar==1` + `canviewcalendar`. Permissions par calendrier via
`get_calendar_permissions($cid)` (`canviewcalendar`, `canaddevents`,
`canmoderateevents`). Table `events` (eid, cid, uid, name, description, visible,
private, starttime, endtime, repeats, timezone…).

#### Afficher le calendrier mensuel (défaut)
`calendar.php?calendar=2&year=2026&month=3` · GET · `canviewcalendar` · params :
`calendar`(int), `year`(int 1901..+5), `month`(int 1–12) · grille de 6 semaines,
évènements via `get_events()`, anniversaires. Rend `calendar/calendar.twig`.

#### Afficher les évènements d'une semaine
`calendar.php?action=weekview&calendar=2&week=TS` · GET · `canviewcalendar` ·
params : `calendar`(int), `week`(int, timestamp) · rend `calendar/weekview.twig`.

#### Afficher les évènements d'un jour
`calendar.php?action=dayview&calendar=2&year=&month=&day=` · GET ·
`canviewcalendar` · params : `calendar`(int), `year`/`month`/`day`(int) · rend
`calendar/dayview.twig` (évènements + anniversaires avec âge).

#### Afficher un évènement
`calendar.php?action=event&eid=3` · GET · `canviewcalendar` ; privé → seul le
propriétaire ; caché → `canmoderateevents` · param : `eid`(int) · `events e`
JOIN `users`. Rend `calendar/event.twig`.

#### Afficher le formulaire d'ajout d'évènement
`calendar.php?action=addevent&calendar=2` · GET · `canviewcalendar` +
`canaddevents` · param : `calendar`(int) + préremplissage · rend
`calendar/addevent.twig`.

#### Ajouter un évènement
`calendar.php?action=do_addevent` · POST + my_post_key · `canviewcalendar` +
`canaddevents` · params : `calendar`(int), `name`, `description`, `private`(int),
`type` (single/ranged), dates (`single_*` ou `start_*`/`end_*` + `start_time`/
`end_time`), `timezone`, `ignoretimezone`(int), `repeats`(1–5) + champs par type
· `EventDataHandler("insert")->insert_event()`.

#### Afficher le formulaire de modification d'un évènement
`calendar.php?action=editevent&eid=3` · GET · `canviewcalendar` + `canaddevents`
+ (propriétaire OU `canmoderateevents`) · param : `eid`(int) · rend
`calendar/editevent.twig`.

#### Modifier un évènement
`calendar.php?action=do_editevent` · POST + my_post_key · idem editevent ·
params : `eid`(int) + mêmes champs que do_addevent · `update_event()`.

#### Supprimer un évènement
`calendar.php?action=do_deleteevent` · POST + my_post_key · propriétaire OU
`canmoderateevents` · params : `eid`(int), `delete`(int=1) · `DELETE FROM
events`.

#### Déplacer un évènement (form / exécution)
`calendar.php?action=move&eid=3` · GET (form) / `do_move` POST + my_post_key ·
`canviewcalendar` + `canmoderateevents` (source et destination) · params :
`eid`(int), `new_calendar`(int) · met à jour `events.cid`.

#### Approuver / Désapprouver un évènement
`calendar.php?action=approve|unapprove&eid=3` · GET/POST (my_post_key) ·
`canviewcalendar` + `canmoderateevents` · param : `eid`(int) · met
`events.visible` 1/0.

### contact.php

#### Envoyer le formulaire de contact
`contact.php` · GET (form) / POST (envoi) · `contact==1` (invités exclus si
`contact_guests==1`) ; limites `maxemails`/`emailfloodtime` ; POST + my_post_key ;
invités : captcha + StopForumSpam · params : `subject`, `message`, `email`,
`from`, captcha · `my_mail()` vers `contactemail`, journalise `maillogs`
(type 3), redirige. Sinon rend `contact/contact.twig`.

### sendthread.php

#### Recommander un sujet par email (form / envoi)
`sendthread.php?tid=42` (form) / `?action=do_sendtofriend` (POST) · GET/POST ·
sujet `visible==1` + vue forum + `check_forum_password` + `cansendemail` ;
limites email ; POST + my_post_key ; invités : captcha · params : `tid`(int),
`email`, `message`, `subject`, `fromname`/`fromemail` (invités) · `my_mail()`
avec lien du sujet, journalise `maillogs` (type 2). Sinon rend
`sendthread/sendthread.twig`.

### rss.php

#### Rediriger l'ancienne URL RSS vers syndication.php
`rss.php?fid=2` · GET · public (ne charge pas MyBB) · `Location:
syndication.php?<query string>`.

### syndication.php

#### Générer le flux de syndication (RSS/Atom) d'un ou plusieurs forums
`syndication.php?fid=2&type=rss2.0&limit=15` (ou `?portal=1`) · GET · public ;
forums non visibles/inactifs exclus ; `canonlyviewownthreads` restreint aux
siens · params : `fid` (liste séparée par virgule), `type` (rss2.0/atom1.0…),
`limit`(int 1–50, défaut 15), `portal` · XML via `FeedGenerator->output_feed()`.
Items = sujets (`threads` visible, `moved=0`) : titre = subject, lien =
`get_thread_link`, description = premier `posts.message` parsé (pièces jointes
incluses), auteur = username.

### css.php

#### Servir une ou plusieurs feuilles de style de thème
`css.php?stylesheet[]=5&stylesheet[]=8` · GET · public (charge `inc/init.php`) ·
param : `stylesheet`(array d'ids `sid`) · `Content-type: text/css` ; concatène
la colonne `stylesheet` de `themestylesheets` dans l'ordre demandé,
éventuellement minifiée (`minifycss`).

### captcha.php

#### Générer l'image captcha
`captcha.php?imagehash=<hash>` · GET · public ; hash présent et `used=0` (marqué
`used=1` ensuite, usage unique) · param : `imagehash` (requis) ·
`Content-type: image/png` ; PNG 200×60 rendu avec GD (texte `captcha.imagestring`
en polices TTF de `inc/captcha_fonts/`, bruit lignes/cercles/carrés + points +
bordure noire). *(C'est l'endpoint ciblé par le solver du dossier
`captcha_solver/`.)*

### task.php

#### Exécuter les tâches planifiées (cron)
`task.php` (web/beacon) ou CLI `php task.php [tid]` · GET / CLI · **sans
authentification** ; protection implicite : `run_task()` sans argument ne lance
qu'une tâche `enabled=1 AND nextrun <= TIME_NOW`, verrouillée 5 min · params :
aucun en web (l'`id` n'est pas lu ici) ; CLI : `argv[1]` = `tid`(int) · web :
GIF transparent 1×1 (`image/gif`) + exécution via `run_task()` ; CLI : exécute
la tâche, effets internes (journalisation en base).

---

## 11. Notes transversales pour le LLM

- **Pattern de recherche** : chaque recherche (forum ou MP ou aide) écrit une
  ligne `searchlog` identifiée par un `sid` md5, puis redirige en 302 vers la
  page de résultats qui lit cette ligne.
- **Convention JSON xmlhttp** : `"true"` = succès ; autre chaîne JSON = message
  d'erreur ; `{"errors":[...]}` = erreurs structurées.
- **Endpoints AJAX renvoyant du HTML** (pas du JSON) : `get_buddyselect`,
  `get_referrals` (xmlhttp, `text/plain`), et les actions modales de `misc.php`,
  `reputation.php`, `report.php`.
- **Sans authentification** : `syndication.php`, `css.php`, `captcha.php`,
  `rss.php`, le beacon web de `task.php`. Le contrôle d'accès y est lié au
  contenu (visibilité forum en SQL, hash captcha à usage unique, verrou de
  tâche) et non à une session.
- **Rendu** : toutes les pages passent par Twig
  `\MyBB\View\template('...twig', [...])` fourni à `output_page(...)`.
