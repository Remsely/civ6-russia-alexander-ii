-- Clone only the three vanilla literal-key rows for this leader.
INSERT OR IGNORE INTO DiplomacyStatements
 (Type, SubType, Initiator, Leader, Mood, StatementText, ReasonText, LeaderAnimation, SceneEffect, Selections)
 SELECT Type, SubType, Initiator, 'LEADER_REMSELY_ALEXANDER_II', Mood, 'LOC_DIPLO_DEAL_LEADER_TRADE_REFUSED_NEUTRAL_1_REMSELY_ALEXANDER_II', ReasonText, LeaderAnimation, SceneEffect, Selections
 FROM DiplomacyStatements WHERE Leader = 'ANY' AND StatementText = 'LOC_DIPLO_DEAL_LEADER_TRADE_REFUSED_NEUTRAL_1';
INSERT OR IGNORE INTO DiplomacyStatements
 (Type, SubType, Initiator, Leader, Mood, StatementText, ReasonText, LeaderAnimation, SceneEffect, Selections)
 SELECT Type, SubType, Initiator, 'LEADER_REMSELY_ALEXANDER_II', Mood, 'LOC_DIPLO_DEAL_LEADER_TRADE_REFUSED_FRIENDLY_1_REMSELY_ALEXANDER_II', ReasonText, LeaderAnimation, SceneEffect, Selections
 FROM DiplomacyStatements WHERE Leader = 'ANY' AND StatementText = 'LOC_DIPLO_DEAL_LEADER_TRADE_REFUSED_FRIENDLY_1';
INSERT OR IGNORE INTO DiplomacyStatements
 (Type, SubType, Initiator, Leader, Mood, StatementText, ReasonText, LeaderAnimation, SceneEffect, Selections)
 SELECT Type, SubType, Initiator, 'LEADER_REMSELY_ALEXANDER_II', Mood, 'LOC_DIPLO_DEAL_LEADER_TRADE_REFUSED_AGGRESSIVE_2_REMSELY_ALEXANDER_II', ReasonText, LeaderAnimation, SceneEffect, Selections
 FROM DiplomacyStatements WHERE Leader = 'ANY' AND StatementText = 'LOC_DIPLO_DEAL_LEADER_TRADE_REFUSED_AGGRESSIVE_2';
