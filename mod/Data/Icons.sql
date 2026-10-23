--==========================================================================================================================
-- ICONS: leader icon (ICON_<LeaderType> is the name the UI looks up for a leader)
--==========================================================================================================================
INSERT INTO IconTextureAtlases
		(Name,		IconSize,	IconsPerRow,	IconsPerColumn,	Filename)
VALUES
		('ICON_ATLAS_REMSELY_ALEXANDER_II',	256,	1,	1,	'RemselysAlexanderII_Icon256.dds'),
		('ICON_ATLAS_REMSELY_ALEXANDER_II',	80,	1,	1,	'RemselysAlexanderII_Icon80.dds'),
		('ICON_ATLAS_REMSELY_ALEXANDER_II',	64,	1,	1,	'RemselysAlexanderII_Icon64.dds'),
		('ICON_ATLAS_REMSELY_ALEXANDER_II',	55,	1,	1,	'RemselysAlexanderII_Icon55.dds'),
		('ICON_ATLAS_REMSELY_ALEXANDER_II',	50,	1,	1,	'RemselysAlexanderII_Icon50.dds'),
		('ICON_ATLAS_REMSELY_ALEXANDER_II',	48,	1,	1,	'RemselysAlexanderII_Icon48.dds'),
		('ICON_ATLAS_REMSELY_ALEXANDER_II',	45,	1,	1,	'RemselysAlexanderII_Icon45.dds'),
		('ICON_ATLAS_REMSELY_ALEXANDER_II',	32,	1,	1,	'RemselysAlexanderII_Icon32.dds');

INSERT INTO IconDefinitions
		(Name,	Atlas,	'Index')
VALUES	('ICON_LEADER_REMSELY_ALEXANDER_II',	'ICON_ATLAS_REMSELY_ALEXANDER_II',	0);
