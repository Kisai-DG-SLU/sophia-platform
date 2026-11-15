-- Étape 2 bis, contrôle du rôle memoire (README.md) : propriétaire du schéma memoire, rien d'autre.
-- Lu par psql après le mot de passe, sur une connexion TCP authentifiée (règle md5 de pg_hba).
-- Attendu : current_user, puis CREATE TABLE et ROLLBACK (rien ne reste), puis deux refus « permission denied ».
select current_user, current_database();
begin;
create table memoire.essai_droits (i int);
rollback;
begin;
select count(*) from sophia.audit_log;
rollback;
begin;
create table sophia.essai_droits (i int);
rollback;
