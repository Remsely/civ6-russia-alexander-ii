--==========================================================================================================================
-- CONFIG DATA (front end): leader selection screen
-- Leader icon is our own (Data/Icons.sql); the card portrait is a separate crop (LEADER_..._SELECT: the card shows a ~517 px window from the left edge, the loading screen uses LEADER_..._NEUTRAL); the card background is Peter's vanilla map (vanilla leaders leave PortraitBackground NULL and the UI falls back to <LeaderType>_BACKGROUND, so it has to be set explicitly).
--==========================================================================================================================
INSERT OR REPLACE INTO Players
		(Domain, CivilizationType, LeaderType, LeaderName, LeaderIcon, CivilizationName, CivilizationIcon, LeaderAbilityName, LeaderAbilityDescription, LeaderAbilityIcon, CivilizationAbilityName, CivilizationAbilityDescription, CivilizationAbilityIcon, Portrait, PortraitBackground)
SELECT	Domain, 'CIVILIZATION_RUSSIA', 'LEADER_REMSELY_ALEXANDER_II', 'LOC_LEADER_REMSELY_ALEXANDER_II_NAME', 'ICON_LEADER_REMSELY_ALEXANDER_II', CivilizationName, CivilizationIcon, 'LOC_TRAIT_LEADER_REMSELY_ALEXANDER_II_REFORMS_NAME', 'LOC_TRAIT_LEADER_REMSELY_ALEXANDER_II_REFORMS_DESCRIPTION', LeaderAbilityIcon, CivilizationAbilityName, CivilizationAbilityDescription, CivilizationAbilityIcon, 'LEADER_REMSELY_ALEXANDER_II_SELECT', 'LEADER_PETER_GREAT_BACKGROUND'
FROM Players WHERE CivilizationType = 'CIVILIZATION_RUSSIA' AND LeaderType = 'LEADER_PETER_GREAT';

-- Unique items shown on the selection screen (copied from Peter)
INSERT OR REPLACE INTO PlayerItems
		(Domain, CivilizationType, LeaderType, Type, Icon, Name, Description, SortIndex)
SELECT	Domain, CivilizationType, 'LEADER_REMSELY_ALEXANDER_II', Type, Icon, Name, Description, SortIndex
FROM PlayerItems WHERE CivilizationType = 'CIVILIZATION_RUSSIA' AND LeaderType = 'LEADER_PETER_GREAT';
