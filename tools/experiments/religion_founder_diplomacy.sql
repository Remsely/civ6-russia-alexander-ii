-- Detached experiment: no trait or runtime attachment. Each Alexander slot
-- has four independent modifiers, connected to the founder's capital property.
-- Weight levels 2+4+8+16 cover the component's moderate 0..30 even scores.
-- Native factories and property mechanics are documented in
-- docs/religion-capital-jump-native.ru.md; runtime behaviour remains unverified.
CREATE TEMP TABLE REMSELY_RivalryRows (
    LeaderSlot INTEGER NOT NULL, Weight INTEGER NOT NULL,
    ModifierId TEXT NOT NULL, RequirementId TEXT NOT NULL,
    RequirementSetId TEXT NOT NULL, PropertyName TEXT NOT NULL,
    PRIMARY KEY (LeaderSlot, Weight)
);
WITH RECURSIVE slots(n) AS (SELECT 0 UNION ALL SELECT n+1 FROM slots WHERE n<63),
weights(w) AS (VALUES (2),(4),(8),(16))
INSERT INTO REMSELY_RivalryRows
SELECT n,w,
       'REMSELY_REL_RIVALRY_' || n || '_MOD_' || w,
       'REMSELY_REL_RIVALRY_' || n || '_REQ_' || w,
       'REMSELY_REL_RIVALRY_' || n || '_SET_' || w,
       'REMSELY_REL_RIVALRY_' || n || '_BIT_' || w
FROM slots CROSS JOIN weights;

INSERT OR IGNORE INTO Types (Type,Kind) VALUES
    ('COLLECTION_ALL_CAPITAL_CITIES','KIND_COLLECTION'),
    ('REQUIREMENT_PLOT_PROPERTY_MATCHES','KIND_REQUIREMENT'),
    ('EFFECT_DIPLOMACY_SIMPLE_EFFECT','KIND_EFFECT');
CREATE TEMP TABLE REMSELY_RivalryTypeCheck (ok INTEGER NOT NULL CHECK (ok=1));
INSERT INTO REMSELY_RivalryTypeCheck (ok)
SELECT CASE WHEN
    EXISTS(SELECT 1 FROM Types WHERE Type='COLLECTION_ALL_CAPITAL_CITIES' AND Kind='KIND_COLLECTION') AND
    EXISTS(SELECT 1 FROM Types WHERE Type='REQUIREMENT_PLOT_PROPERTY_MATCHES' AND Kind='KIND_REQUIREMENT') AND
    EXISTS(SELECT 1 FROM Types WHERE Type='EFFECT_DIPLOMACY_SIMPLE_EFFECT' AND Kind='KIND_EFFECT')
    THEN 1 ELSE 0 END;
DROP TABLE REMSELY_RivalryTypeCheck;
INSERT INTO Types (Type,Kind) VALUES ('MODIFIER_REMSELY_REL_RIVALRY_CAPITAL','KIND_MODIFIER');
INSERT INTO TypeTags (Type,Tag) VALUES ('MODIFIER_REMSELY_REL_RIVALRY_CAPITAL','DIPLOMACY_MODIFIER');
INSERT INTO DynamicModifiers (ModifierType,CollectionType,EffectType) VALUES
    ('MODIFIER_REMSELY_REL_RIVALRY_CAPITAL','COLLECTION_ALL_CAPITAL_CITIES','EFFECT_DIPLOMACY_SIMPLE_EFFECT');
INSERT INTO Requirements (RequirementId,RequirementType)
SELECT RequirementId,'REQUIREMENT_PLOT_PROPERTY_MATCHES' FROM REMSELY_RivalryRows;
INSERT INTO RequirementArguments (RequirementId,Name,Value)
SELECT RequirementId,'PropertyName',PropertyName FROM REMSELY_RivalryRows;
INSERT INTO RequirementArguments (RequirementId,Name,Value)
SELECT RequirementId,'PropertyMinimum','1' FROM REMSELY_RivalryRows;
INSERT INTO RequirementSets (RequirementSetId,RequirementSetType)
SELECT RequirementSetId,'REQUIREMENTSET_TEST_ALL' FROM REMSELY_RivalryRows;
INSERT INTO RequirementSetRequirements (RequirementSetId,RequirementId)
SELECT RequirementSetId,RequirementId FROM REMSELY_RivalryRows;
INSERT INTO Modifiers (ModifierId,ModifierType,SubjectRequirementSetId)
SELECT ModifierId,'MODIFIER_REMSELY_REL_RIVALRY_CAPITAL',RequirementSetId FROM REMSELY_RivalryRows;
INSERT INTO ModifierArguments (ModifierId,Name,Value)
SELECT ModifierId,'InitialValue',CAST(-Weight AS TEXT) FROM REMSELY_RivalryRows;
INSERT INTO ModifierArguments (ModifierId,Name,Value)
SELECT ModifierId,'MaxValue',CAST(-Weight AS TEXT) FROM REMSELY_RivalryRows;
INSERT INTO ModifierArguments (ModifierId,Name,Value)
SELECT ModifierId,'ReductionTurns','0' FROM REMSELY_RivalryRows;
INSERT INTO ModifierArguments (ModifierId,Name,Value)
SELECT ModifierId,'SimpleModifierDescription','LOC_DIPLO_MODIFIER_REMSELY_REL_RIVALRY' FROM REMSELY_RivalryRows;
INSERT INTO ModifierStrings (ModifierId,Context,Text)
SELECT ModifierId,'Sample','LOC_TOOLTIP_SAMPLE_DIPLOMACY_ALL' FROM REMSELY_RivalryRows;
DROP TABLE REMSELY_RivalryRows;
