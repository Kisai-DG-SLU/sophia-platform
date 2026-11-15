-- Étape 2 bis, contrôle du rôle memoire_audit (README.md) : lu par psql après le mot de passe et le tenant
-- (variable t), sur une connexion TCP authentifiée (règle md5 de pg_hba, pas 127.0.0.1 en trust).
-- Attendu : current_user, INSERT puis ROLLBACK (rien ne reste), puis cinq refus « permission denied ».
select current_user, current_database();
begin;
insert into sophia.audit_log (id, tenant_id, actor_id, action, resource_type, resource_id, details)
    values (uuid_generate_v4(), :'t', null, 'access'::sophia.audit_action, null, null, '{"issue": "essai"}');
rollback;
begin;
select count(*) from sophia.audit_log;
rollback;
begin;
update sophia.audit_log set details = details where false;
rollback;
begin;
delete from sophia.audit_log where false;
rollback;
begin;
select count(*) from sophia.documents;
rollback;
begin;
select count(*) from memoire.versions;
rollback;
