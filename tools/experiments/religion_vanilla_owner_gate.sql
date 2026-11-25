-- EXPERIMENT ONLY; do not load in the mod. This globally changes one vanilla
-- definition, although the inverse leader gate is intended to affect only its
-- Alexander instances. Nested sets and owner semantics require in-game proof.
-- Subsequent mods can replace OwnerRequirementSetId and defeat this wrapper.
BEGIN;
CREATE TEMP TABLE REMSELY_ReligionGateCheck (ok INTEGER NOT NULL CHECK(ok=1));
CREATE TEMP TABLE REMSELY_ReligionGateOriginal (set_id TEXT);
INSERT INTO REMSELY_ReligionGateOriginal
SELECT OwnerRequirementSetId FROM Modifiers
WHERE ModifierId='STANDARD_DIPLOMATIC_CONVERTED_CITY';
INSERT INTO REMSELY_ReligionGateCheck
SELECT CASE WHEN COUNT(*)=1 THEN 1 ELSE 0 END FROM REMSELY_ReligionGateOriginal;

-- A missing original set is not equivalent to a NULL original set.
INSERT INTO REMSELY_ReligionGateCheck
SELECT CASE WHEN set_id IS NULL OR EXISTS
  (SELECT 1 FROM RequirementSets WHERE RequirementSetId=set_id) THEN 1 ELSE 0 END
FROM REMSELY_ReligionGateOriginal;
-- Follow every named RequirementSetId argument, including collection count
-- requirements. Missing mandatory REQUIREMENTSET_IS_MET references fail.
-- Unknown engine-specific ways to reference sets are not analysed.
WITH RECURSIVE edges(parent,child) AS (
 SELECT sr.RequirementSetId, ra.Value FROM RequirementSetRequirements sr
 JOIN Requirements r ON r.RequirementId=sr.RequirementId
 LEFT JOIN RequirementArguments ra ON ra.RequirementId=r.RequirementId AND ra.Name='RequirementSetId'
 WHERE ra.Name IS NOT NULL OR r.RequirementType='REQUIREMENT_REQUIREMENTSET_IS_MET'
), reach(node) AS (
 SELECT set_id FROM REMSELY_ReligionGateOriginal WHERE set_id IS NOT NULL
 UNION SELECT e.child FROM edges e JOIN reach p ON e.parent=p.node WHERE e.child IS NOT NULL
), closure(parent,child) AS (
 SELECT e.parent,e.child FROM edges e JOIN reach p ON e.parent=p.node WHERE e.child IS NOT NULL
 UNION SELECT c.parent,e.child FROM closure c JOIN edges e ON e.parent=c.child WHERE e.child IS NOT NULL
)
INSERT INTO REMSELY_ReligionGateCheck
SELECT CASE WHEN NOT EXISTS (
 SELECT 1 FROM edges e JOIN reach r ON r.node=e.parent
 WHERE e.child IS NULL OR NOT EXISTS (SELECT 1 FROM RequirementSets s WHERE s.RequirementSetId=e.child)
) AND NOT EXISTS (SELECT 1 FROM closure WHERE parent=child)
  AND NOT EXISTS (
   SELECT 1 FROM RequirementSetRequirements sr JOIN reach r ON r.node=sr.RequirementSetId
   LEFT JOIN Requirements req ON req.RequirementId=sr.RequirementId WHERE req.RequirementId IS NULL
  ) THEN 1 ELSE 0 END;

INSERT OR IGNORE INTO Types(Type,Kind) VALUES
 ('REQUIREMENT_PLAYER_LEADER_TYPE_MATCHES','KIND_REQUIREMENT'),
 ('REQUIREMENT_REQUIREMENTSET_IS_MET','KIND_REQUIREMENT');
INSERT INTO REMSELY_ReligionGateCheck
SELECT CASE WHEN COUNT(*)=2 THEN 1 ELSE 0 END FROM Types
WHERE Type IN ('REQUIREMENT_PLAYER_LEADER_TYPE_MATCHES','REQUIREMENT_REQUIREMENTSET_IS_MET')
 AND Kind='KIND_REQUIREMENT';

INSERT INTO Requirements(RequirementId,RequirementType,Inverse)
VALUES ('REMSELY_REL_GATE_NOT_LEADER','REQUIREMENT_PLAYER_LEADER_TYPE_MATCHES',1);
INSERT INTO RequirementArguments(RequirementId,Name,Value)
VALUES ('REMSELY_REL_GATE_NOT_LEADER','LeaderType','LEADER_REMSELY_ALEXANDER_II');
INSERT INTO RequirementSets(RequirementSetId,RequirementSetType)
VALUES ('REMSELY_REL_GATE_OWNER','REQUIREMENTSET_TEST_ALL');
INSERT INTO RequirementSetRequirements(RequirementSetId,RequirementId)
VALUES ('REMSELY_REL_GATE_OWNER','REMSELY_REL_GATE_NOT_LEADER');

-- Preserve a pre-existing, potentially mod-defined owner requirement.
INSERT INTO Requirements(RequirementId,RequirementType)
SELECT 'REMSELY_REL_GATE_PREVIOUS','REQUIREMENT_REQUIREMENTSET_IS_MET'
FROM REMSELY_ReligionGateOriginal WHERE set_id IS NOT NULL;
INSERT INTO RequirementArguments(RequirementId,Name,Value)
SELECT 'REMSELY_REL_GATE_PREVIOUS','RequirementSetId',set_id
FROM REMSELY_ReligionGateOriginal WHERE set_id IS NOT NULL;
INSERT INTO RequirementSetRequirements(RequirementSetId,RequirementId)
SELECT 'REMSELY_REL_GATE_OWNER','REMSELY_REL_GATE_PREVIOUS'
FROM REMSELY_ReligionGateOriginal WHERE set_id IS NOT NULL;
UPDATE Modifiers SET OwnerRequirementSetId='REMSELY_REL_GATE_OWNER'
WHERE ModifierId='STANDARD_DIPLOMATIC_CONVERTED_CITY';
DROP TABLE REMSELY_ReligionGateOriginal;
DROP TABLE REMSELY_ReligionGateCheck;
COMMIT;
