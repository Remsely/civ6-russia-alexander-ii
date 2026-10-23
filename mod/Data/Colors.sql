--==========================================================================================================================
-- COLORS: black / gold / ivory (Russian imperial)
--==========================================================================================================================
INSERT INTO Colors
		(Type, Color)
VALUES	('COLOR_PLAYER_REMSELY_ALEXANDER_II_PRIMARY',   '28,28,28,255'),
		('COLOR_PLAYER_REMSELY_ALEXANDER_II_SECONDARY', '212,160,23,255');

-- Same shape as vanilla PlayerColors (Base/Assets/UI/Colors/PlayerColors.xml): there is no TextColor column, and the Alt1-3 pairs
-- are used by the game when another player's colors are too close. They are copied from Peter, as the JFD Elisabeth mod does.
INSERT INTO PlayerColors
		(Type, Usage, PrimaryColor, SecondaryColor, Alt1PrimaryColor, Alt1SecondaryColor, Alt2PrimaryColor, Alt2SecondaryColor, Alt3PrimaryColor, Alt3SecondaryColor)
SELECT	'LEADER_REMSELY_ALEXANDER_II', 'Unique', 'COLOR_PLAYER_REMSELY_ALEXANDER_II_PRIMARY', 'COLOR_PLAYER_REMSELY_ALEXANDER_II_SECONDARY',
		Alt1PrimaryColor, Alt1SecondaryColor, Alt2PrimaryColor, Alt2SecondaryColor, Alt3PrimaryColor, Alt3SecondaryColor
FROM PlayerColors WHERE Type = 'LEADER_PETER_GREAT';
