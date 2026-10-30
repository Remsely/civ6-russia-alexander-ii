# Глоссарий игровых терминов (EN ↔ RU)

Источник истины для всех текстов и документов мода. Английское зеркало: [`../en/terms.md`](../en/terms.md).

**Где брать термины: только файлы игры и мода, не память и не дословный перевод.** Русские официальные названия — `reference/vanilla/Base/Text/Vanilla_ru_RU.xml` и `reference/vanilla/Expansion2/Text/Expansion2_Translations_ConfigText.xml` (дополнения); пары EN↔RU ниже выгружены из этих файлов и из текстов мода (`mod/Text/*.xml`). Появление терминов из дополнений в `reference/game-db/DebugLocalization.sqlite` зависит от последнего загруженного набора правил — файлы надёжнее.

Буква «ё» не используется (как в официальном тексте игры). Форму записи падежей и опыт перевода см. в репозитории `civ6-leaders-mods-ru-localization` (`docs/TRANSLATION_GUIDE.md`).

## Падежи у названий

Теги `LOC_{LEADER,UNIT,BUILDING,DISTRICT,IMPROVEMENT,CIVILIZATION}_*_NAME` пишутся шестью формами через `|` (именительный, родительный, дательный, винительный, творительный, предложный) и с `<Gender>` / `<Plurality>`. Остальные тексты (способности, повестки, описания) — обычные строки.

## Эпохи (`LOC_ERA_*_NAME`)

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
| Future Era (только Gathering Storm) | Эпоха будущего |

## Районы (`LOC_DISTRICT_*_NAME`)

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
| Lavra (уник. России) | Лавра |
| Mbanza (уник. Конго) | Мбанза |
| Hansa (уник. Германии) | Ганза |
| Acropolis (уник. Греции) | Акрополь |
| Bath (уник. Рима) | Бани |
| Royal Navy Dockyard (уник. Англии) | Верфи Королевского флота |
| Street Carnival (уник. Бразилии) | Уличный карнавал |

\* Пакет «Эфиопия» (New Frontier); в локальных файлах `ru_RU` отсутствует — подтверждено русскоязычными источниками по игре; при обновлении кэша баз сверить.

## Сущности и понятия

| EN | RU | Где |
|---|---|---|
| Builder | Строители (тег с падежами) | `LOC_UNIT_BUILDER_NAME` |
| Farm | Ферма | `LOC_IMPROVEMENT_FARM_NAME` |
| Pasture | Пастбище | `LOC_IMPROVEMENT_PASTURE_NAME` |
| Professional Army (политика) | **Продвинутая армия** (не «Профессиональная») | `LOC_POLICY_PROFESSIONAL_ARMY_NAME` |
| Governor | Губернатор | `LOC_GOVERNOR_*` |
| Loyalty | лояльность, «ед. лояльности» | `LOC_CIVILIZATION_PRESLAV_BONUS_XP1` |
| Food / Production / Gold / Culture | пища / производство / золото / культура | тексты мода, сверены по игре |
| Great Scientist | Великий ученый | тексты игры |
| Spy | Шпион | тексты игры |
| Trade route | Торговый путь | тексты игры |

Россия | Russia, Петр Великий | Peter the Great — из `LOC_CIVILIZATION_RUSSIA_NAME`, `LOC_LEADER_PETER_GREAT_NAME`.

## Термины мода (зафиксированы в текстах мода)

| EN | RU |
|---|---|
| The Great Reforms | Великие реформы |
| Emancipation of the Serfs | Освобождение крестьян |
| Zemstvo Reform | Земства |
| Military Reform | Военная реформа |
| The Liberator | Освободитель |
| Emperor and Autocrat of All Russia, Tsar of Poland, Grand Duke of Finland | Император и самодержец Всероссийский, царь Польский, великий князь Финляндский |

Названия городов мода — пары из `mod/Text/{en_US,ru_RU}.xml` (Kharkov/Харьков, Rostov-on-Don/Ростов-на-Дону, Baku/Баку, Riga/Рига и остальные; полный список — раздел 5 [дизайн-документа](design.md)).
