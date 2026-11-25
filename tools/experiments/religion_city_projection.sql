-- EXPERIMENT ONLY. Do not add to modinfo. This defines candidates; no trait
-- attaches them and it does not subscribe to events or alter game properties.
-- For an Alexander at player slot N, an adapter would have to attach exactly
-- the six N-specific modifier IDs. Runtime attachment and reloading are NOT
-- verified here. Bit keys match religion_city_projection.lua exactly.
CREATE TEMP TABLE REMSELY_ReligionProjectionRows (
    LeaderSlot INTEGER NOT NULL, Weight INTEGER NOT NULL,
    ModifierId TEXT NOT NULL, RequirementId TEXT NOT NULL,
    RequirementSetId TEXT NOT NULL, PropertyName TEXT NOT NULL,
    PRIMARY KEY (LeaderSlot, Weight)
);
WITH RECURSIVE slots(n) AS (SELECT 0 UNION ALL SELECT n+1 FROM slots WHERE n<63),
weights(w) AS (VALUES (1),(2),(4),(8),(16),(32))
INSERT INTO REMSELY_ReligionProjectionRows
SELECT n,w,
       'REMSELY_REL_PROTOTYPE_' || n || '_MOD_' || w,
       'REMSELY_REL_PROTOTYPE_' || n || '_REQ_' || w,
       'REMSELY_REL_PROTOTYPE_' || n || '_SET_' || w,
       'REMSELY_REL_PROTOTYPE_' || n || '_BIT_' || w
FROM slots CROSS JOIN weights;

-- Both names correspond to native GameCore factories (Base/XP1/XP2), but a
-- particular DB may not have their Types rows yet. Preserve existing rows.
INSERT OR IGNORE INTO Types (Type,Kind) VALUES
    ('COLLECTION_ALL_CAPITAL_CITIES','KIND_COLLECTION'),
    ('REQUIREMENT_PLOT_PROPERTY_MATCHES','KIND_REQUIREMENT'),
    ('EFFECT_DIPLOMACY_SIMPLE_EFFECT','KIND_EFFECT');
-- INSERT OR IGNORE alone would silently accept a pre-existing wrong Kind or
-- a hash collision. Abort before defining modifiers if any type is invalid.
CREATE TEMP TABLE REMSELY_ReligionProjectionTypeCheck (
    ok INTEGER NOT NULL CHECK (ok=1)
);
INSERT INTO REMSELY_ReligionProjectionTypeCheck (ok)
SELECT CASE WHEN
    EXISTS(SELECT 1 FROM Types WHERE Type='COLLECTION_ALL_CAPITAL_CITIES' AND Kind='KIND_COLLECTION') AND
    EXISTS(SELECT 1 FROM Types WHERE Type='REQUIREMENT_PLOT_PROPERTY_MATCHES' AND Kind='KIND_REQUIREMENT') AND
    EXISTS(SELECT 1 FROM Types WHERE Type='EFFECT_DIPLOMACY_SIMPLE_EFFECT' AND Kind='KIND_EFFECT')
    THEN 1 ELSE 0 END;
DROP TABLE REMSELY_ReligionProjectionTypeCheck;
INSERT INTO Types (Type,Kind) VALUES
    ('MODIFIER_REMSELY_REL_PROTOTYPE_CAPITAL_DIPLOMACY','KIND_MODIFIER');
INSERT INTO TypeTags (Type,Tag) VALUES
    ('MODIFIER_REMSELY_REL_PROTOTYPE_CAPITAL_DIPLOMACY','DIPLOMACY_MODIFIER');
INSERT INTO DynamicModifiers (ModifierType,CollectionType,EffectType) VALUES
    ('MODIFIER_REMSELY_REL_PROTOTYPE_CAPITAL_DIPLOMACY',
     'COLLECTION_ALL_CAPITAL_CITIES','EFFECT_DIPLOMACY_SIMPLE_EFFECT');

INSERT INTO Requirements (RequirementId,RequirementType)
SELECT RequirementId,'REQUIREMENT_PLOT_PROPERTY_MATCHES' FROM REMSELY_ReligionProjectionRows;
INSERT INTO RequirementArguments (RequirementId,Name,Value)
SELECT RequirementId,'PropertyName',PropertyName FROM REMSELY_ReligionProjectionRows;
INSERT INTO RequirementArguments (RequirementId,Name,Value)
SELECT RequirementId,'PropertyMinimum','1' FROM REMSELY_ReligionProjectionRows;
INSERT INTO RequirementSets (RequirementSetId,RequirementSetType)
SELECT RequirementSetId,'REQUIREMENTSET_TEST_ALL' FROM REMSELY_ReligionProjectionRows;
INSERT INTO RequirementSetRequirements (RequirementSetId,RequirementId)
SELECT RequirementSetId,RequirementId FROM REMSELY_ReligionProjectionRows;

INSERT INTO Modifiers (ModifierId,ModifierType,SubjectRequirementSetId)
SELECT ModifierId,'MODIFIER_REMSELY_REL_PROTOTYPE_CAPITAL_DIPLOMACY',RequirementSetId
FROM REMSELY_ReligionProjectionRows;
INSERT INTO ModifierArguments (ModifierId,Name,Value)
SELECT ModifierId,'InitialValue',CAST(-Weight AS TEXT) FROM REMSELY_ReligionProjectionRows;
INSERT INTO ModifierArguments (ModifierId,Name,Value)
SELECT ModifierId,'MaxValue',CAST(-Weight AS TEXT) FROM REMSELY_ReligionProjectionRows;
INSERT INTO ModifierArguments (ModifierId,Name,Value)
SELECT ModifierId,'ReductionTurns','0' FROM REMSELY_ReligionProjectionRows;
INSERT INTO ModifierArguments (ModifierId,Name,Value)
SELECT ModifierId,'SimpleModifierDescription','LOC_DIPLO_MODIFIER_REMSELY_REL_PROTOTYPE'
FROM REMSELY_ReligionProjectionRows;

DROP TABLE REMSELY_ReligionProjectionRows;
