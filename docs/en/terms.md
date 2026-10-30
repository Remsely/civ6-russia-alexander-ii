# Game Terms Glossary (EN ↔ RU)

The source of truth for all mod texts and documents. The Russian file is the working copy: [`../ru/terms.md`](../ru/terms.md).

**Where terms come from: only the game's and the mod's own files — never memory or literal translation.** Official Russian names live in `reference/vanilla/Base/Text/Vanilla_ru_RU.xml` and `reference/vanilla/Expansion2/Text/Expansion2_Translations_ConfigText.xml` (expansions); the EN↔RU pairs below were extracted from those files and from the mod's texts (`mod/Text/*.xml`). Which expansion terms appear in `reference/game-db/DebugLocalization.sqlite` depends on the last-loaded ruleset — the files are more reliable.

The letter "ё" is not used (matching the game's official Russian text). Declension format and translation experience: the `civ6-leaders-mods-ru-localization` repository (`docs/TRANSLATION_GUIDE.md`).

## Name declensions (Russian)

`LOC_{LEADER,UNIT,BUILDING,DISTRICT,IMPROVEMENT,CIVILIZATION}_*_NAME` tags carry six forms separated by `|` (nominative, genitive, dative, accusative, instrumental, prepositional) plus `<Gender>` / `<Plurality>`. All other texts (abilities, agendas, descriptions) are plain strings.

## Eras (`LOC_ERA_*_NAME`)

| EN | RU |
|---|---|
| Ancient Era | Древний мир |
| Classical Era | Античность |
| Medieval Era | Средневековье |
| Renaissance Era | Возрождение |
| Industrial Era | Промышленная эра |
| Modern Era | Новое время |
| Atomic Era | Эпоха атома |
| Information Era | Информационная эра |
| Future Era (Gathering Storm only) | Эпоха будущего |

## Districts (`LOC_DISTRICT_*_NAME`)

| EN | RU |
|---|---|
| City Center | Центр города |
| Holy Site | Священное место |
| Campus | Кампус |
| Commercial Hub | Центр коммерции |
| Harbor | Гавань |
| Encampment | Военный лагерь |
| Theater Square | Театральная площадь |
| Industrial Zone | Промышленная зона |
| Neighborhood | Пригород |
| Aqueduct | Акведук |
| Entertainment Complex | Развлекательный комплекс |
| Aerodrome | Аэродром |
| Spaceport | Космопорт |
| Diplomatic Quarter (Gathering Storm) | Дипломатический квартал * |
| Lavra (Russian unique) | Лавра |
| Mbanza (Kongo unique) | Мбанза |
| Hansa (German unique) | Ганза |
| Acropolis (Greek unique) | Акрополь |
| Bath (Roman unique) | Бани |
| Royal Navy Dockyard (English unique) | Верфи Королевского флота |
| Street Carnival (Brazilian unique) | Уличный карнавал |

\* Ethiopia pack (New Frontier); absent from local `ru_RU` files — confirmed via Russian-language game sources; re-verify when the DB cache refreshes.

## Entities and concepts

| EN | RU | Where |
|---|---|---|
| Builder | Строители (declined tag) | `LOC_UNIT_BUILDER_NAME` |
| Farm | Ферма | `LOC_IMPROVEMENT_FARM_NAME` |
| Pasture | Пастбище | `LOC_IMPROVEMENT_PASTURE_NAME` |
| Professional Army (policy) | «Продвинутая армия» | `LOC_POLICY_PROFESSIONAL_ARMY_NAME` |
| Governor | Губернатор | `LOC_GOVERNOR_*` |
| Loyalty | лояльность | `LOC_CIVILIZATION_PRESLAV_BONUS_XP1` |
| Food / Production / Gold / Culture | пища / производство / золото / культура | mod texts, checked against the game |
| Great Scientist | Великий ученый | game texts |
| Spy | Шпион | game texts |
| Trade route | Торговый путь | game texts |

Russia | Россия, Peter the Great | Петр Великий — from `LOC_CIVILIZATION_RUSSIA_NAME`, `LOC_LEADER_PETER_GREAT_NAME`.

## Mod terms (fixed in the mod's texts)

| EN | RU |
|---|---|
| The Great Reforms | Великие реформы |
| Emancipation of the Serfs | Освобождение крестьян |
| Zemstvo Reform | Земства |
| Military Reform | Военная реформа |
| The Liberator | Освободитель |
| Emperor and Autocrat of All Russia, Tsar of Poland, Grand Duke of Finland | Император и самодержец Всероссийский, царь Польский, великий князь Финляндский |

Mod city names — pairs from `mod/Text/{en_US,ru_RU}.xml` (Kharkov/Харьков, Rostov-on-Don/Ростов-на-Дону, Baku/Баку, Riga/Рига and the rest; full list in section 5 of the [design doc](design.md)).
