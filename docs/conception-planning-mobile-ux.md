# Conception technique — simplification du planning mobile

Issue de suivi : #272

## Périmètre de cette première livraison

- Planning uniquement. La prospection n'est pas modifiée dans cette livraison.
- Téléphone prioritaire, avec maintien de l'usage sur ordinateur.
- Aucun changement de schéma de base de données prévu.
- Aucune suppression, fusion ou renommage de planning ou de données existantes.
- Aucun changement de rôles, de permissions ou de règles d'accès.
- Pas de déploiement ni de fusion avant revue de la PR et validation des tests.

## État actuel observé

- La saisie utilisateur est dans `app/routes/planning.py` et `app/templates/saisie_planning.html`.
- Le formulaire `PlanningForm` porte une date de début et sept champs multi-sélection (lundi à dimanche).
- Chaque structure sélectionnée nécessite actuellement un champ texte supplémentaire pour son nom précis.
- La date de début doit être un lundi. La sauvegarde retrouve le planning de l'utilisateur pour cette date et le met à jour, plutôt que de créer systématiquement une nouvelle ligne.
- La visualisation est dans `app/templates/visualiser_planning.html`; les cartes de semaine sont partagées.
- Les tests existants couvrent notamment les jours de la semaine, les règles de génération et certaines règles UX. Ils devront rester verts.

## Proposition UX mobile-first

### Étape 1 — réduire les gestes et erreurs dans la saisie existante

1. Afficher une action principale visible en haut et en bas du formulaire sur téléphone, avec des zones tactiles confortables.
2. Préremplir la date avec le prochain lundi uniquement en création, sans écraser une date explicitement choisie ni la date d'un planning en modification.
3. Rendre la progression plus claire : date de semaine, puis cartes de jours; afficher le nombre de structures sélectionnées par jour et un état vide explicite.
4. Garder les champs de nom précis obligatoires et visibles pour chaque structure sélectionnée. Ne jamais supprimer silencieusement une valeur lors d'un changement de sélection.
5. Conserver les sept jours, y compris samedi et dimanche, ainsi que les sélections et noms déjà enregistrés en mode modification.
6. Ajouter une confirmation légère avant de quitter un formulaire modifié, si elle peut être faite sans bloquer les soumissions valides.

### Étape 2 — réutiliser un planning existant

Après validation de l'étape 1, ajouter une action « Reprendre une semaine » fondée sur les plannings déjà enregistrés par l'utilisateur. Elle copie les valeurs dans le formulaire courant sans enregistrer automatiquement. L'utilisateur choisit la nouvelle date du lundi et confirme lui-même la sauvegarde. La source reste intacte.

Cette étape ne doit pas faire de requête inter-utilisateurs ni exposer les plannings d'un autre utilisateur. Elle ne doit pas ajouter de table ou de colonne.

## Garde-fous de données et règles métier

- Ne pas changer les modèles `Planning` et `Prospection`, ni leurs relations.
- Ne pas modifier la règle d'unicité fonctionnelle utilisateur + date ni la logique de mise à jour existante.
- Ne pas changer les valeurs codées des structures ou la fonction d'encodage/décodage des créneaux.
- Ne pas créer de prospection lors de la saisie du planning.
- Conserver les dates passées autorisées, les semaines commençant le lundi et la prise en charge des sept jours.
- En cas d'erreur de validation, restituer la saisie de l'utilisateur sans perte de valeurs.
- Garder CSRF, permissions, notifications et journal d'audit existants.
- Aucun changement dans AFRIVA.

## Plan de tests avant fusion

### Tests automatisés à ajouter ou compléter

- Création : la date par défaut est le prochain lundi; une date explicitement fournie est conservée.
- Modification : la date et les valeurs existantes ne sont pas écrasées par les valeurs par défaut.
- Mobile/HTML : le formulaire expose des contrôles utilisables sur petit écran, labels accessibles et actions de sauvegarde claires.
- Sélections : ajout/retrait d'une structure conserve les noms déjà saisis pour les structures qui restent sélectionnées.
- Validation : les noms des structures sélectionnées restent obligatoires côté navigateur et côté serveur.
- Persistance : une sauvegarde met à jour le planning existant de l'utilisateur pour la même date; aucune ligne n'est créée en double par le flux normal.
- Isolation : un utilisateur ne peut ni consulter ni modifier le planning d'un autre.
- Régression : semaine commençant lundi, samedi/dimanche, anciennes valeurs, CSRF, notifications et audit.
- Suite complète des tests existants, notamment `test_planning_ux.py`, `test_planning_weekdays.py`, `test_planning_admin_routes.py` et `test_permissions.py`.

### Vérifications manuelles sur téléphone

- Formulaire lisible sans zoom horizontal.
- Sélection de plusieurs structures et saisie des noms sans perte.
- Erreurs affichées près de la saisie ou de façon compréhensible.
- Enregistrement, réouverture et modification d'un planning existant.
- Utilisation sur ordinateur non dégradée.

## Stratégie de livraison

1. Faire les changements ciblés sur la branche `feat/planning-mobile-simplification`.
2. Ajouter les tests de régression avant de modifier les comportements.
3. Exécuter les tests ciblés puis la suite complète; documenter les résultats exacts dans la PR.
4. Ouvrir la PR en brouillon pour revue par le propriétaire et coordination avec Claude.
5. Corriger les remarques et attendre l'approbation explicite avant fusion.
6. Vérifier le déploiement après fusion séparément; aucune modification de production dans cette étape de conception.
