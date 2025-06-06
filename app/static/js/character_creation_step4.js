// Functions for Character Creation Step 4: Ability Scores
// This file will handle the logic for determining and assigning ability scores.

// Copied from app/static/js/character_creation.js

function identifyASIs(descriptionText, sourceName, abilityScoreMap) {
    if (IS_CHARACTER_CREATION_DEBUG_ACTIVE && descriptionText) {
        asiDebugTextsCollection.push({
            source: sourceName,
            text: descriptionText
        });
    }
    const identified = {
        fixed: [], // { abilityName: "STR", bonusValue: 1 }
        choices: [] // { id, source, description, number_of_abilities_to_choose, points_per_ability, total_points_to_allocate, options: ["STR", "DEX", ...] }
    };
    if (typeof descriptionText !== 'string') return identified;

    const uniqueAbilityCodes = Object.values(GLOBAL_ABILITY_SCORE_MAP).filter((v, i, a) => a.indexOf(v) === i && v.length === 3);

    // New: Handle compound pattern like "+1 to Dexterity and one other ability score"
    const compoundPattern = /([+-]\d+)\s+to\s+([\w\s]+)\s+and\s+(?:one|an)\s+(?:other|additional)\s+ability\s+score/i;
    let compoundMatch = descriptionText.match(compoundPattern);

    if (compoundMatch) {
        const bonusValueStr = compoundMatch[1]; // e.g., "+1"
        const abilityNameFull = compoundMatch[2].trim().toLowerCase(); // e.g., "dexterity"
        const bonusValue = parseInt(bonusValueStr.replace('+', ''), 10);

        if (abilityScoreMap[abilityNameFull]) {
            identified.fixed.push({ abilityName: abilityScoreMap[abilityNameFull], bonusValue });
        }

        identified.choices.push({
            id: `choice_${sourceName.replace(/[^a-zA-Z0-9]/g, '_')}_compound_${identified.choices.length}`,
            source: sourceName,
            description: `From "${descriptionText}" - choose one other ability score`, // Using full desc for more context
            number_of_abilities_to_choose: 1,
            points_per_ability: bonusValue, // Inferred from the first part
            total_points_to_allocate: bonusValue,
            options: uniqueAbilityCodes
        });
        return identified; // Successfully parsed as a compound, return to avoid other regexes
    }

    // New: Handle Half-Elf-like compound pattern: "Your Charisma score increases by 2, and two other ability scores of your choice increase by 1."
    const halfElfLikeCompoundRegex = /Your (\w+) score increases by (\d+),\s*and\s*(one|two|three|four|five|six)\s+other\s+ability\s+scores(?:\s+of\s+your\s+choice)?\s+increase\s+by\s+(\d+)/i;
    let halfElfMatch = descriptionText.match(halfElfLikeCompoundRegex);

    if (halfElfMatch) {
        // Fixed Part
        const fixedAbilityNameFull = halfElfMatch[1].toLowerCase();
        const fixedBonusValue = parseInt(halfElfMatch[2], 10);
        if (abilityScoreMap[fixedAbilityNameFull]) {
            identified.fixed.push({ abilityName: abilityScoreMap[fixedAbilityNameFull], bonusValue: fixedBonusValue });
        }

        // Choice Part
        const numScoresToChoose = parseWordToNumber(halfElfMatch[3].toLowerCase());
        const choiceBonusValue = parseInt(halfElfMatch[4], 10);

        if (numScoresToChoose > 0 && choiceBonusValue > 0) {
            identified.choices.push({
                id: `choice_${sourceName.replace(/[^a-zA-Z0-9]/g, '_')}_halfelf_${identified.choices.length}`,
                source: sourceName,
                description: halfElfMatch[0], // Full matched string for description
                number_of_abilities_to_choose: numScoresToChoose,
                points_per_ability: choiceBonusValue,
                total_points_to_allocate: numScoresToChoose * choiceBonusValue,
                options: uniqueAbilityCodes
            });
        }
        return identified; // Successfully parsed, return early
    }

    // New Regex for patterns like "+1 to Dexterity" (if not part of the compound pattern handled above)
    const plusValueToAbilityRegex = /([+-]\d+)\s+to\s+([\w\s]+)/gi;
    let matchPlusValue;
    while ((matchPlusValue = plusValueToAbilityRegex.exec(descriptionText)) !== null) {
        const bonusValueStrPM = matchPlusValue[1]; // e.g., "+1" or "-1"
        const abilityNameFullPM = matchPlusValue[2].trim().toLowerCase(); // e.g., "dexterity"
        const bonusValuePM = parseInt(bonusValueStrPM.replace('+', ''), 10);

        if (abilityScoreMap[abilityNameFullPM]) {
            // Avoid double-adding if a more specific regex like "Your X score increases by Y" also matches.
            // This is a simple safeguard. More complex logic might be needed if descriptions become very tricky.
            const alreadyAddedByFixedRegex = identified.fixed.some(
                f => f.abilityName === abilityScoreMap[abilityNameFullPM] &&
                     f.bonusValue === bonusValuePM &&
                     descriptionText.includes(`Your ${abilityNameFullPM} score increases by ${Math.abs(bonusValuePM)}`) // Math.abs for "increases by"
            );
            if (!alreadyAddedByFixedRegex) {
                identified.fixed.push({ abilityName: abilityScoreMap[abilityNameFullPM], bonusValue: bonusValuePM });
            }
        }
    }

    // Regex for "Your X score increases by Y."
    const fixedRegex = /Your (\w+) score increases by (\d+)/gi;
    let match;
    while ((match = fixedRegex.exec(descriptionText)) !== null) {
        const abilityName = match[1].toLowerCase();
        const bonusValue = parseInt(match[2], 10);
        if (abilityScoreMap[abilityName]) {
            identified.fixed.push({ abilityName: abilityScoreMap[abilityName], bonusValue });
        }
    }

    // Regex for "Choose any ability score to increase by X." or "Increase any one ability score by X."
    // Example: "Choose any one ability score to increase by 2."
    // Example: "Increase one ability score of your choice by 2."
    // Example: "one ability score of your choice increases by 2"
    const chooseAnyRegex = /(?:Choose any|Increase) (one|two|three|an) ability score(?: of your choice)? (?:to increase |increases )?by (\d+)/gi;
    while ((match = chooseAnyRegex.exec(descriptionText)) !== null) {
        const numScoresToChoose = parseWordToNumber(match[1] === 'an' ? 'one' : match[1]);
        const bonusValue = parseInt(match[2], 10);
        if (numScoresToChoose > 0 && bonusValue > 0) {
            identified.choices.push({
                id: `choice_${sourceName.replace(/[^a-zA-Z0-9]/g, '_')}_${identified.choices.length}`,
                source: sourceName,
                description: match[0],
                number_of_abilities_to_choose: numScoresToChoose,
                points_per_ability: bonusValue,
                total_points_to_allocate: numScoresToChoose * bonusValue,
                options: uniqueAbilityCodes // Allows choosing from any ability
            });
        }
    }

    // Regex for "Increase one ability score by X and another ability score by Y."
    // Example: "Increase one ability score by 2 and another ability score by 1."
    const increaseTwoDifferentRegex = /Increase one ability score by (\d+) and another ability score by (\d+)/gi;
    while ((match = increaseTwoDifferentRegex.exec(descriptionText)) !== null) {
        const bonus1 = parseInt(match[1], 10);
        const bonus2 = parseInt(match[2], 10);
        // This creates two separate choices, as they are distinct applications.
        // Or, it could be one choice with two parts, but current model is simpler.
        // For now, let's model as two choices of "pick 1, get X" and "pick 1, get Y, must be different"
        // This specific phrasing implies two distinct choices that must target different abilities.
        // A more complex UI might handle this as one "choice group".
        // For now: two distinct choices, UI later needs to enforce "different".
        identified.choices.push({
            id: `choice_${sourceName.replace(/[^a-zA-Z0-9]/g, '_')}_${identified.choices.length}`,
            source: `${sourceName} (Part 1)`,
            description: `Increase one ability score by ${bonus1} (must be different from other choice part)`,
            number_of_abilities_to_choose: 1,
            points_per_ability: bonus1,
            total_points_to_allocate: bonus1,
            options: uniqueAbilityCodes
        });
        identified.choices.push({
            id: `choice_${sourceName.replace(/[^a-zA-Z0-9]/g, '_')}_${identified.choices.length}`,
            source: `${sourceName} (Part 2)`,
            description: `Increase another ability score by ${bonus2} (must be different from other choice part)`,
            number_of_abilities_to_choose: 1,
            points_per_ability: bonus2,
            total_points_to_allocate: bonus2,
            options: uniqueAbilityCodes
        });
    }

    // Regex for "Your X, Y, and Z scores each increase by N."
    const multipleSpecificScoresRegex = /Your ([\w\s,]+(?:and \w+)?) scores each increase by (\d+)/gi;
    while ((match = multipleSpecificScoresRegex.exec(descriptionText)) !== null) {
        const abilitiesListStr = match[1];
        const bonusValue = parseInt(match[2], 10);
        const abilities = parseAbilityList(abilitiesListStr, abilityScoreMap);
        abilities.forEach(abilityName => {
            if (abilityScoreMap[abilityName.toLowerCase()]) { // Ensure mapping before pushing
                 identified.fixed.push({ abilityName: abilityScoreMap[abilityName.toLowerCase()], bonusValue });
            } else if (Object.values(abilityScoreMap).includes(abilityName)) { // If already an ABBR
                 identified.fixed.push({ abilityName: abilityName, bonusValue });
            }
        });
    }


    // Regex for "Choose N ability scores from [list] to increase by Y"
    // Example: "Choose two ability scores from Strength, Dexterity, or Constitution to increase by 1."
    const chooseNFromListRegex = /Choose (one|two|three|four|five|six) ability scores from ([\w\s,]+(?:or \w+)?) to increase by (\d+)/gi;
    while ((match = chooseNFromListRegex.exec(descriptionText)) !== null) {
        const numToChoose = parseWordToNumber(match[1]);
        const abilityListStr = match[2];
        const bonusValue = parseInt(match[3], 10);
        const options = parseAbilityList(abilityListStr, abilityScoreMap);
        if (numToChoose > 0 && bonusValue > 0 && options.length > 0) {
            identified.choices.push({
                id: `choice_${sourceName.replace(/[^a-zA-Z0-9]/g, '_')}_${identified.choices.length}`,
                source: sourceName,
                description: match[0],
                number_of_abilities_to_choose: numToChoose,
                points_per_ability: bonusValue,
                total_points_to_allocate: numToChoose * bonusValue,
                options // This is already filtered by parseAbilityList
            });
        }
    }

    // Regex for "Two ability scores of your choice increase by 1." (general choice)
    // Example: "Two ability scores of your choice increase by 1."
    const NAbilitiesOfChoiceRegex = /(\w+) ability scores of your choice increase by (\d+)/gi;
    while ((match = NAbilitiesOfChoiceRegex.exec(descriptionText)) !== null) {
        const numToChoose = parseWordToNumber(match[1]);
        const bonusValue = parseInt(match[2], 10);
        if (numToChoose > 0 && bonusValue > 0) {
            identified.choices.push({
                id: `choice_${sourceName.replace(/[^a-zA-Z0-9]/g, '_')}_${identified.choices.length}`,
                source: sourceName,
                description: match[0],
                number_of_abilities_to_choose: numToChoose,
                points_per_ability: bonusValue,
                total_points_to_allocate: numToChoose * bonusValue,
                options: uniqueAbilityCodes // Any ability can be chosen
            });
        }
    }

    // Regex for "All of your ability scores increase by 1."
    const allScoresIncreaseRegex = /All (?:of your |your six )?ability scores increase by (\d+)/gi;
    while ((match = allScoresIncreaseRegex.exec(descriptionText)) !== null) {
        const bonusValue = parseInt(match[1], 10);
        uniqueAbilityCodes.forEach(abilityName => { // Iterate over unique codes
            identified.fixed.push({ abilityName, bonusValue });
        });
    }

    // Regex for "Your Charisma score increases by 2, and your Dexterity score increases by 1."
    const specificScoresMixedBonusesRegex = /Your (\w+) score increases by (\d+), and your (\w+) score increases by (\d+)/gi;
    while ((match = specificScoresMixedBonusesRegex.exec(descriptionText)) !== null) {
        const abilityName1 = match[1].toLowerCase();
        const bonusValue1 = parseInt(match[2], 10);
        const abilityName2 = match[3].toLowerCase();
        const bonusValue2 = parseInt(match[4], 10);

        if (abilityScoreMap[abilityName1]) {
            identified.fixed.push({ abilityName: abilityScoreMap[abilityName1], bonusValue: bonusValue1 });
        }
        if (abilityScoreMap[abilityName2]) {
            identified.fixed.push({ abilityName: abilityScoreMap[abilityName2], bonusValue: bonusValue2 });
        }
    }

    // Regex for simple format like "Strength +1, Dexterity +1"
    const simpleFormatRegex = /(\w+)\s*\+\s*(\d+)/gi;
    // Need to be careful this doesn't overlap too much with previous, or run it on segments.
    // For now, assume it's applied to the whole description.
    // To avoid double counting if "Your Strength score increases by 1" (already caught) and "Strength +1" (this regex) are both present
    // this should ideally be run if other patterns *don't* match, or fixed bonuses are stored in a way that prevents duplicates for same stat.
    // Current logic: add all found, then sum up. So duplicates are fine if they mean "total +2 from two sources".
    // But if it's the same sentence rephrased, it's an issue.
    // For now, let's assume descriptions are not intentionally redundant in this way.
    while ((match = simpleFormatRegex.exec(descriptionText)) !== null) {
        const abilityName = match[1].toLowerCase();
        const bonusValue = parseInt(match[2], 10);
        if (abilityScoreMap[abilityName]) {
            // Check if this exact bonus was already added by a more specific regex like "Your X score increases by Y"
            // This is a simple check; a more robust solution might involve processing text in stages or more complex state.
            const alreadyAdded = identified.fixed.some(f => f.abilityName === abilityScoreMap[abilityName] && f.bonusValue === bonusValue && descriptionText.includes(`Your ${match[1]} score increases by ${bonusValue}`));
            if (!alreadyAdded) {
                 identified.fixed.push({ abilityName: abilityScoreMap[abilityName], bonusValue });
            }
        }
    }


    return identified;
}


function getStatBonuses() {
    // Clear existing choices here as per plan, so it's fresh for this calculation run
    characterCreationData.step4_asi_choices = [];
    const bonuses = {
        STR: { race: 0, class: 0, background: 0 }, DEX: { race: 0, class: 0, background: 0 }, CON: { race: 0, class: 0, background: 0 },
        INT: { race: 0, class: 0, background: 0 }, WIS: { race: 0, class: 0, background: 0 }, CHA: { race: 0, class: 0, background: 0 }
    };
    // const abilityScoreMap = GLOBAL_ABILITY_SCORE_MAP; // Use global map

    function processTraits(traits, type, sourceNamePrefix) { // type is 'race' or 'class'
        if (traits && Array.isArray(traits)) {
            traits.forEach(trait => {
                if (trait.name === "Ability Score Increase" && trait.desc) {
                    console.log(`[DEBUG] getStatBonuses/processTraits: Identifying ASIs for ${type} trait '${trait.name}'. Desc:`, trait.desc);
                    const sourceFullName = `${sourceNamePrefix}: ${trait.name}`;
                    const asiResult = identifyASIs(trait.desc, sourceFullName, GLOBAL_ABILITY_SCORE_MAP);
                    console.log(`[DEBUG] getStatBonuses/processTraits: Identified ASIs for ${type} trait '${trait.name}': Fixed:`, JSON.parse(JSON.stringify(asiResult.fixed)), "Choices:", JSON.parse(JSON.stringify(asiResult.choices)));

                    asiResult.fixed.forEach(fixedBonus => {
                        if (bonuses[fixedBonus.abilityName]) {
                            if (type === 'race') bonuses[fixedBonus.abilityName].race += fixedBonus.bonusValue;
                            else if (type === 'class') bonuses[fixedBonus.abilityName].class += fixedBonus.bonusValue;
                        }
                    });
                    characterCreationData.step4_asi_choices.push(...asiResult.choices);
                }
            });
        }
    }

    // Process Race Bonuses from traits
    if (characterCreationData.step1_race_selection) {
        const raceName = characterCreationData.step1_race_selection.name || characterCreationData.step1_race_selection.slug;
        if (characterCreationData.step1_race_selection.traits) {
            processTraits(characterCreationData.step1_race_selection.traits, 'race', `Race (${raceName})`);
        }
    }
    if (characterCreationData.step1_parent_race_selection) {
        const parentRaceName = characterCreationData.step1_parent_race_selection.name || characterCreationData.step1_parent_race_selection.slug;
        if (characterCreationData.step1_parent_race_selection.traits) {
             processTraits(characterCreationData.step1_parent_race_selection.traits, 'race', `Parent Race (${parentRaceName})`);
        }
    }


    // Process Class Bonuses from traits
    if (characterCreationData.step2_selected_base_class) {
        const className = characterCreationData.step2_selected_base_class.name || characterCreationData.step2_selected_base_class.slug;
        if (characterCreationData.step2_selected_base_class.traits) {
            processTraits(characterCreationData.step2_selected_base_class.traits, 'class', `Class (${className})`);
        }
    }
    if (characterCreationData.step2_selected_archetype) {
        const archetypeName = characterCreationData.step2_selected_archetype.name || characterCreationData.step2_selected_archetype.slug;
        if (characterCreationData.step2_selected_archetype.traits) {
            processTraits(characterCreationData.step2_selected_archetype.traits, 'class', `Archetype (${archetypeName})`);
        }
    }


    // Process Background Bonuses
    const backgroundData = characterCreationData.step3_background_selection;
    if (backgroundData) {
        const backgroundName = backgroundData.name || backgroundData.slug || "Unknown Background";

        // Attempt 1: Structured bonuses from backgroundData.data.ability_score_bonuses (if applicable)
        // This existing logic can remain if backgroundData.data is a valid path and distinct source
        if (backgroundData.data && backgroundData.data.ability_score_bonuses && Array.isArray(backgroundData.data.ability_score_bonuses)) {
            console.log(`[DEBUG] getStatBonuses: Processing structured ASIs from backgroundData.data.ability_score_bonuses for ${backgroundName}`);
            backgroundData.data.ability_score_bonuses.forEach(bonus_info => {
                if (bonus_info.ability_score && bonus_info.ability_score.name && bonus_info.bonus) {
                    const abilityName = bonus_info.ability_score.name.toLowerCase();
                    const statAbbr = GLOBAL_ABILITY_SCORE_MAP[abilityName];
                    if (statAbbr && bonuses[statAbbr] && bonuses[statAbbr].background !== undefined) {
                        bonuses[statAbbr].background += parseInt(bonus_info.bonus, 10);
                    } else {
                        console.warn(`Unknown ability name or structure in background structured ASI: ${bonus_info.ability_score.name}`);
                    }
                }
            });
        }

        // NEW: Process ASIs from the benefits array
        let processedBenefitDescs = []; // To track descriptions processed from benefits
        if (backgroundData.benefits && Array.isArray(backgroundData.benefits)) {
            console.log(`[DEBUG] getStatBonuses: Processing ASIs from backgroundData.benefits for ${backgroundName}`);
            backgroundData.benefits.forEach(benefit => {
                if (benefit.type === "ability_score" && benefit.desc) {
                    processedBenefitDescs.push(benefit.desc.trim()); // Track for de-duplication with general text
                    const sourceFullName = `Background Benefit (${backgroundName}): ${benefit.name || 'ASI'}`;
                    console.log(`[DEBUG] getStatBonuses/backgroundBenefits: Identifying ASIs for '${sourceFullName}'. Desc:`, benefit.desc);
                    const benefitAsiResult = identifyASIs(benefit.desc, sourceFullName, GLOBAL_ABILITY_SCORE_MAP);
                    console.log(`[DEBUG] getStatBonuses/backgroundBenefits: Identified ASIs: Fixed:`, JSON.parse(JSON.stringify(benefitAsiResult.fixed)), "Choices:", JSON.parse(JSON.stringify(benefitAsiResult.choices)));

                    benefitAsiResult.fixed.forEach(fixedBonus => {
                        if (bonuses[fixedBonus.abilityName] && bonuses[fixedBonus.abilityName].background !== undefined) {
                            bonuses[fixedBonus.abilityName].background += fixedBonus.bonusValue;
                        } else {
                             console.warn(`[DEBUG] getStatBonuses/backgroundBenefits: bonuses[${fixedBonus.abilityName}] or .background is undefined for fixed bonus. Stat exists: ${!!bonuses[fixedBonus.abilityName]}`);
                        }
                    });
                    benefitAsiResult.choices.forEach(choice => {
                        if (!characterCreationData.step4_asi_choices.find(existingChoice => existingChoice.description === choice.description && existingChoice.source.startsWith(`Background Benefit (${backgroundName})`))) {
                            characterCreationData.step4_asi_choices.push(choice);
                        } else {
                            console.log(`[DEBUG] getStatBonuses/backgroundBenefits: Duplicate choice (from benefit) detected and skipped: ${choice.description}`);
                        }
                    });
                }
            });
        }

        // Attempt 2: Parse from text descriptions (desc and feature_desc from backgroundData.data or backgroundData directly)
        let combinedBackgroundText = "";
        const dataContext = backgroundData.data || backgroundData; // Prefer .data if it exists, else use backgroundData directly

        if (typeof dataContext.desc === 'string') {
            combinedBackgroundText += dataContext.desc + " ";
        }
        // Only add feature_desc if it's different from general desc and not already covered by benefits
        if (typeof dataContext.feature_desc === 'string' && dataContext.feature_desc !== dataContext.desc) {
            // combinedBackgroundText += dataContext.feature_desc + " "; // This line was commented out in thought, let's keep it for broader check unless it causes issues.
        }

        const trimmedCombinedText = combinedBackgroundText.trim();

        if (trimmedCombinedText && !processedBenefitDescs.includes(trimmedCombinedText)) {
            console.log(`[DEBUG] getStatBonuses: Identifying ASIs from background general text for '${backgroundName}'. Combined Text:`, trimmedCombinedText);
            const sourceFullName = `Background Text (${backgroundName})`; // Differentiate source
            const bgTextAsiResult = identifyASIs(trimmedCombinedText, sourceFullName, GLOBAL_ABILITY_SCORE_MAP);
            console.log(`[DEBUG] getStatBonuses/backgroundText: Identified ASIs: Fixed:`, JSON.parse(JSON.stringify(bgTextAsiResult.fixed)), "Choices:", JSON.parse(JSON.stringify(bgTextAsiResult.choices)));

            bgTextAsiResult.fixed.forEach(fixedBonus => {
                if (bonuses[fixedBonus.abilityName] && bonuses[fixedBonus.abilityName].background !== undefined) {
                    bonuses[fixedBonus.abilityName].background += fixedBonus.bonusValue;
                } else {
                     console.warn(`[DEBUG] getStatBonuses/backgroundText: bonuses[${fixedBonus.abilityName}] or .background is undefined for fixed bonus. Stat exists: ${!!bonuses[fixedBonus.abilityName]}`);
                }
            });
            bgTextAsiResult.choices.forEach(choice => {
                // Check against choices from benefits AND from other general text parsing
                if (!characterCreationData.step4_asi_choices.find(existingChoice => existingChoice.description === choice.description && (existingChoice.source.startsWith(`Background Benefit (${backgroundName})`) || existingChoice.source.startsWith(`Background Text (${backgroundName})`)) )) {
                    characterCreationData.step4_asi_choices.push(choice);
                } else {
                    console.log(`[DEBUG] getStatBonuses/backgroundText: Duplicate choice (from text) detected and skipped: ${choice.description}`);
                }
            });
        } else if (trimmedCombinedText && processedBenefitDescs.includes(trimmedCombinedText)) {
            console.log(`[DEBUG] getStatBonuses: General background text for '${backgroundName}' is identical to an already processed ASI benefit. Skipping general text parsing for ASIs.`);
        }
    } else {
        console.log("[DEBUG] getStatBonuses: No backgroundData found for ASI processing.");
    }

    // The old logic for raceData.ability_score_bonuses is now replaced.
    // If the API also provides structured bonuses in `ability_score_bonuses` AND these are meant to be
    // *additional* to what's in traits, then that logic would need to be reinstated or merged carefully.
    // Based on the task, parsing traits is the primary source now.

    console.log("[DEBUG] getStatBonuses: Final bonuses object:", JSON.parse(JSON.stringify(bonuses)));
    console.log("[DEBUG] getStatBonuses: Final step4_asi_choices:", JSON.parse(JSON.stringify(characterCreationData.step4_asi_choices)));
    console.log("[DEBUG] Exiting getStatBonuses.");
    return bonuses;
}

function prepareASIChoiceDataForUI() {
    console.log("[DEBUG] Entering prepareASIChoiceDataForUI. Current step4_asi_choices:", JSON.parse(JSON.stringify(characterCreationData.step4_asi_choices)));
    characterCreationData.step4_unallocated_asi_points = 0;
    characterCreationData.step4_asi_choice_details_for_ui = [];

    if (characterCreationData.step4_asi_choices && characterCreationData.step4_asi_choices.length > 0) {
        characterCreationData.step4_asi_choices.forEach(choice => {
            characterCreationData.step4_unallocated_asi_points += choice.total_points_to_allocate;
            characterCreationData.step4_asi_choice_details_for_ui.push({
                ...choice, // Spread existing choice properties
                allocated_points_for_this_choice: 0 // Initialize points used for this specific choice
            });
        });
    }
    console.log("[DEBUG] prepareASIChoiceDataForUI: Resulting step4_unallocated_asi_points:", characterCreationData.step4_unallocated_asi_points);
    console.log("[DEBUG] prepareASIChoiceDataForUI: Resulting step4_asi_choice_details_for_ui:", JSON.parse(JSON.stringify(characterCreationData.step4_asi_choice_details_for_ui)));
}

function renderASIChoicesUI() {
    console.log("[DEBUG] Entering renderASIChoicesUI.");
    console.log("[DEBUG] renderASIChoicesUI data: step4_asi_choice_details_for_ui:", JSON.parse(JSON.stringify(characterCreationData.step4_asi_choice_details_for_ui)),
                "step4_unallocated_asi_points:", characterCreationData.step4_unallocated_asi_points,
                "step4_allocated_choice_bonuses:", JSON.parse(JSON.stringify(characterCreationData.step4_allocated_choice_bonuses)));
    const asiChoiceListEl = document.getElementById('asi-choice-list');
    const totalRemainingPointsEl = document.getElementById('total-remaining-choice-points');
    console.log("[DEBUG] renderASIChoicesUI: Found #asi-choice-list:", asiChoiceListEl ? 'Yes' : 'No');
    console.log("[DEBUG] renderASIChoicesUI: Found #total-remaining-choice-points:", totalRemainingPointsEl ? 'Yes' : 'No');


    if (!asiChoiceListEl || !totalRemainingPointsEl) {
        console.error("ASI Choice UI elements not found!");
        return;
    }

    asiChoiceListEl.innerHTML = ''; // Clear previous list

    characterCreationData.step4_asi_choice_details_for_ui.forEach(choice => {
        const li = document.createElement('li');
        const pointsRemainingForThis = choice.total_points_to_allocate - choice.allocated_points_for_this_choice;
        li.textContent = `${choice.source}: ${choice.description} (Points remaining for this choice: ${pointsRemainingForThis})`;
        if (pointsRemainingForThis <= 0) {
            li.classList.add('choice-completed');
        }
        asiChoiceListEl.appendChild(li);
    });

    totalRemainingPointsEl.textContent = characterCreationData.step4_unallocated_asi_points;

    // Update displayed choice bonuses on stats
    characterCreationData.step4_ability_scores.forEach(stat => {
        const choiceBonusEl = document.querySelector(`.stat-bonus.choice-bonus[data-stat='${stat}']`);
        if (choiceBonusEl) {
            const bonusValue = characterCreationData.step4_allocated_choice_bonuses[stat] || 0;
            choiceBonusEl.textContent = `+${bonusValue}`;
            choiceBonusEl.style.display = bonusValue > 0 ? 'inline-block' : 'none';
        }
    });
}


function handleAsiAllocateClick(event) {
    const targetStat = event.target.dataset.stat;
    const asiAllocationMessageEl = document.getElementById('asi-allocation-message');

    if (characterCreationData.step4_unallocated_asi_points <= 0) {
        asiAllocationMessageEl.textContent = "No more ASI points to allocate.";
        asiAllocationMessageEl.style.display = 'block';
        return;
    }

    // Find the first available ASI choice to allocate from
    let currentChoiceToAllocateFrom = null;
    for (let i = 0; i < characterCreationData.step4_asi_choice_details_for_ui.length; i++) {
        if (characterCreationData.step4_asi_choice_details_for_ui[i].allocated_points_for_this_choice < characterCreationData.step4_asi_choice_details_for_ui[i].total_points_to_allocate) {
            currentChoiceToAllocateFrom = characterCreationData.step4_asi_choice_details_for_ui[i];
            break;
        }
    }

    if (!currentChoiceToAllocateFrom) {
        asiAllocationMessageEl.textContent = "Error: Unallocated points exist, but no available choice found.";
        asiAllocationMessageEl.style.display = 'block';
        console.error("Mismatch between unallocated_asi_points and available choices.");
        return;
    }

    // Simplified logic: each click allocates +1.
    // More complex logic would be needed to enforce "points_per_ability > 1" for a single click
    // or "number_of_abilities_to_choose" if a choice requires picking multiple distinct abilities.
    // For now, this is a pool of +1s. The description on the choice list item provides context.

    characterCreationData.step4_unallocated_asi_points -= 1;
    currentChoiceToAllocateFrom.allocated_points_for_this_choice += 1;
    characterCreationData.step4_allocated_choice_bonuses[targetStat] = (characterCreationData.step4_allocated_choice_bonuses[targetStat] || 0) + 1;

    asiAllocationMessageEl.textContent = `+1 allocated to ${targetStat} from choice: ${currentChoiceToAllocateFrom.source}.`;
    asiAllocationMessageEl.style.display = 'block';

    renderASIChoicesUI();
    renderMainStatDisplay(); // Update totals which now include choice bonuses
    saveCharacterDataToSession();
    updateAndSaveFinalAbilityScores(); // Recalculate final scores
}


function getVitalStats() {
    let vital = [];
    const raceData = characterCreationData.step1_race_selection;
    const classData = characterCreationData.step2_selected_base_class;
    // const abilityScoreMap = GLOBAL_ABILITY_SCORE_MAP; // Use global map

    // Always suggest Constitution
    if (!vital.includes("CON")) vital.push("CON");

    // From Class
    if (classData) {
        // Primary ability for spellcasters
        if (classData.spellcasting && classData.spellcasting.spellcasting_ability) {
            const primaryCastingStat = GLOBAL_ABILITY_SCORE_MAP[classData.spellcasting.spellcasting_ability.name.toLowerCase()];
            if (primaryCastingStat && !vital.includes(primaryCastingStat)) {
                vital.push(primaryCastingStat);
            }
        }
        // Common key stats for certain class archetypes (heuristic)
        const className = classData.name.toLowerCase();
        if (className.includes("fighter") || className.includes("paladin") || className.includes("barbarian")) {
            if (!vital.includes("STR")) vital.push("STR");
        }
        if (className.includes("ranger") || className.includes("rogue") || className.includes("monk")) {
            if (!vital.includes("DEX")) vital.push("DEX");
        }
        if (className.includes("cleric") || className.includes("druid")) {
            if (!vital.includes("WIS")) vital.push("WIS");
        }
        if (className.includes("wizard")) {
            if (!vital.includes("INT")) vital.push("INT");
        }
        if (className.includes("sorcerer") || className.includes("bard") || className.includes("warlock")) {
            if (!vital.includes("CHA")) vital.push("CHA");
        }
    }

    // From Race (stats that get bonuses)
    if (raceData && raceData.ability_score_bonuses && Array.isArray(raceData.ability_score_bonuses)) {
        raceData.ability_score_bonuses.forEach(bonus => {
            if (bonus.bonus > 0) {
                const statAbbr = GLOBAL_ABILITY_SCORE_MAP[bonus.ability_score.name.toLowerCase()];
                if (statAbbr && !vital.includes(statAbbr)) {
                    vital.push(statAbbr);
                }
            }
        });
    }

    let uniqueVital = [...new Set(vital)]; // Should be redundant if checks are done before pushing

    // Simple prioritization if list is too long (e.g., > 3 prominent stats)
    // This aims to provide the most impactful suggestions.
    if (uniqueVital.length > 3) {
        let prioritizedVital = [];
        // 1. Primary casting stat (if any)
        if (classData && classData.spellcasting && classData.spellcasting.spellcasting_ability) {
            const primaryCastingStat = GLOBAL_ABILITY_SCORE_MAP[classData.spellcasting.spellcasting_ability.name.toLowerCase()];
            if (primaryCastingStat && uniqueVital.includes(primaryCastingStat)) {
                prioritizedVital.push(primaryCastingStat);
            }
        }
        // 2. Constitution
        if (uniqueVital.includes("CON") && !prioritizedVital.includes("CON")) {
            prioritizedVital.push("CON");
        }
        // 3. Other class-suggested stats or major racial bonus stats
        const classSpecificSuggestions = [];
        if (classData) {
            const className = classData.name.toLowerCase();
            if (className.includes("fighter") || className.includes("paladin") || className.includes("barbarian")) classSpecificSuggestions.push("STR");
            if (className.includes("ranger") || className.includes("rogue") || className.includes("monk")) classSpecificSuggestions.push("DEX");
            // Add more as needed
        }
        for (const stat of classSpecificSuggestions) {
            if (prioritizedVital.length < 3 && uniqueVital.includes(stat) && !prioritizedVital.includes(stat)) {
                prioritizedVital.push(stat);
            }
        }
        // Fill with any stat that received a racial bonus > 0
        if (raceData && raceData.ability_score_bonuses) {
            for (const bonus of raceData.ability_score_bonuses) {
                if (prioritizedVital.length < 3 && bonus.bonus > 0) {
                    const statAbbr = GLOBAL_ABILITY_SCORE_MAP[bonus.ability_score.name.toLowerCase()];
                    if (statAbbr && uniqueVital.includes(statAbbr) && !prioritizedVital.includes(statAbbr)) {
                        prioritizedVital.push(statAbbr);
                    }
                }
            }
        }
        // If still not full, take from the remaining uniqueVital
        for (const stat of uniqueVital) {
            if (prioritizedVital.length < 3 && !prioritizedVital.includes(stat)) {
                prioritizedVital.push(stat);
            }
        }
        uniqueVital = prioritizedVital.slice(0, 3); // Ensure it's max 3
    }

    console.log("Determined Vital Stats:", uniqueVital);
    return uniqueVital;
}

function updateDisplayedBonuses() {
    console.log("[DEBUG] Entering updateDisplayedBonuses. Current step4_stat_bonuses:", JSON.parse(JSON.stringify(characterCreationData.step4_stat_bonuses)));
    characterCreationData.step4_ability_scores.forEach(stat => {
        const raceBonusEl = document.querySelector(`.stat-bonus.race-bonus[data-stat='${stat}']`);
        const classBonusEl = document.querySelector(`.stat-bonus.class-bonus[data-stat='${stat}']`);
        const backgroundBonusEl = document.querySelector(`.stat-bonus.background-bonus[data-stat='${stat}']`); // New element

        if (raceBonusEl) {
            raceBonusEl.textContent = `+${(characterCreationData.step4_stat_bonuses[stat] && characterCreationData.step4_stat_bonuses[stat].race) || 0}`;
        }
        if (classBonusEl) {
            classBonusEl.textContent = `+${(characterCreationData.step4_stat_bonuses[stat] && characterCreationData.step4_stat_bonuses[stat].class) || 0}`;
        }
        if (backgroundBonusEl) { // Update background bonus display
            backgroundBonusEl.textContent = `+${(characterCreationData.step4_stat_bonuses[stat] && characterCreationData.step4_stat_bonuses[stat].background) || 0}`;
        }
    });
}

function renderMainStatDisplay() {
    console.log("[DEBUG] Entering renderMainStatDisplay.");
    console.log("[DEBUG] renderMainStatDisplay data: step4_assigned_stats:", JSON.parse(JSON.stringify(characterCreationData.step4_assigned_stats)),
                "step4_stat_bonuses:", JSON.parse(JSON.stringify(characterCreationData.step4_stat_bonuses)),
                "step4_allocated_choice_bonuses:", JSON.parse(JSON.stringify(characterCreationData.step4_allocated_choice_bonuses)));
    characterCreationData.step4_ability_scores.forEach(stat => {
        const assignedValueEl = document.querySelector(`.stat-assigned-value[data-stat='${stat}']`);
        const totalEl = document.querySelector(`.stat-total[data-stat='${stat}']`);

        const assignedValue = characterCreationData.step4_assigned_stats[stat] || '-';
        assignedValueEl.textContent = assignedValue;

        if (assignedValue !== '-') {
            const raceBonus = (characterCreationData.step4_stat_bonuses[stat] && characterCreationData.step4_stat_bonuses[stat].race) || 0;
            const classBonus = (characterCreationData.step4_stat_bonuses[stat] && characterCreationData.step4_stat_bonuses[stat].class) || 0;
            const backgroundBonus = (characterCreationData.step4_stat_bonuses[stat] && characterCreationData.step4_stat_bonuses[stat].background) || 0;
            const choiceBonusTotal = (characterCreationData.step4_allocated_choice_bonuses && characterCreationData.step4_allocated_choice_bonuses[stat]) ?
                parseInt(characterCreationData.step4_allocated_choice_bonuses[stat]) : 0;
            totalEl.textContent = parseInt(assignedValue) + raceBonus + classBonus + backgroundBonus + choiceBonusTotal;
        } else {
            totalEl.textContent = '-';
        }
    });
    updateDisplayedBonuses(); // Ensure bonuses are also up-to-date
    console.log("Main stat display rendered.");
}

function renderAssignableDicePool(diceValues) {
    const assignableDicePool = document.getElementById('assignable-dice-pool');
    assignableDicePool.innerHTML = ''; // Clear existing dice

    // Create a frequency map of assigned dice values
    const assignedValues = Object.values(characterCreationData.step4_assigned_stats);
    const assignedCounts = {};
    assignedValues.forEach(val => {
        if (val !== null) { // only count actual assigned values
            assignedCounts[val] = (assignedCounts[val] || 0) + 1;
        }
    });

    // Create a frequency map of available dice values
    const availableCounts = {};
    diceValues.forEach(val => {
        availableCounts[val] = (availableCounts[val] || 0) + 1;
    });

    // Display each unique dice value, considering how many are used
    const uniqueDiceValues = [...new Set(diceValues)].sort((a, b) => b - a); // Display in descending order

    uniqueDiceValues.forEach(value => {
        const totalAvailable = availableCounts[value] || 0;
        const totalAssignedToThisValue = assignedCounts[value] || 0;
        const numberToDisplay = totalAvailable - totalAssignedToThisValue;

        for (let i = 0; i < numberToDisplay; i++) {
            const diceDiv = document.createElement('div');
            diceDiv.classList.add('dice-value');
            diceDiv.textContent = value;
            if (characterCreationData.step4_selected_dice_value === value && i === 0 && numberToDisplay > 0) { // Highlight only one instance if multiple are same value
                // This simple selection highlight might need refinement if multiple identical values are present
                // and one is selected. For now, highlights the first available one that matches.
                diceDiv.classList.add('selected');
            }
            diceDiv.addEventListener('click', handleDicePoolClick);
            assignableDicePool.appendChild(diceDiv);
        }
    });
    // Add placeholders for any dice that were assigned but now the source (standard/rolled) has changed
    // or if a value was assigned that's not in the current diceValues (should ideally not happen with proper logic)
    Object.entries(characterCreationData.step4_assigned_stats).forEach(([stat, value]) => {
        if (value !== null && !diceValues.includes(value)) {
            // This indicates a mismatch, possibly log an error or handle gracefully
            // For now, we assume assigned_stats are cleared if dice source changes.
        }
    });
}

function handleDicePoolClick(event) {
    const clickedValue = parseInt(event.target.textContent);
    characterCreationData.step4_selected_dice_value = clickedValue;

    // Update visual selection in the pool
    document.querySelectorAll('#assignable-dice-pool .dice-value').forEach(el => el.classList.remove('selected'));
    event.target.classList.add('selected');

    console.log("Selected dice value from pool:", clickedValue);
    saveCharacterDataToSession();
}

function handleRollDiceClick() {
    const rollDiceWarning = document.getElementById('roll-dice-warning'); // Get warning element again
    if (characterCreationData.step4_dice_rolled_once) {
        alert("You have already rolled the dice. You cannot roll again.");
        return;
    }

    if (confirm("Warning: Rolling dice will override the standard array values and can only be done once. Are you sure you want to proceed?")) {
        characterCreationData.step4_rolled_stats = generate4d6DropLowest();
        characterCreationData.step4_dice_rolled_once = true;
        characterCreationData.step4_assigned_stats = {}; // Clear assignments
        characterCreationData.step4_selected_dice_value = null; // Clear selected dice from pool

        document.getElementById('roll-dice-button').disabled = true;
        rollDiceWarning.style.display = 'block'; // Show warning text permanently after roll

        console.log("Dice rolled:", characterCreationData.step4_rolled_stats);
        loadStep4Logic(); // Reload/re-render Step 4 UI with new dice
        // saveCharacterDataToSession(); // loadStep4Logic calls save and also calls updateAndSaveFinalAbilityScores
        updateAndSaveFinalAbilityScores(); // Explicitly call here to ensure scores are reset based on new empty assignments
    }
}

function handleStatAssignmentClick(event) {
    const targetStat = event.target.dataset.stat;
    if (!targetStat) return; // Clicked somewhere else in the block

    const selectedDiceValue = characterCreationData.step4_selected_dice_value;

    if (selectedDiceValue === null) {
        // If a stat is clicked without a dice value selected, and that stat currently has a value,
        // make that value available again in the pool.
        if (characterCreationData.step4_assigned_stats[targetStat] !== null && characterCreationData.step4_assigned_stats[targetStat] !== undefined) {
            console.log(`Unassigning ${characterCreationData.step4_assigned_stats[targetStat]} from ${targetStat}`);
            characterCreationData.step4_assigned_stats[targetStat] = null;
        } else {
            alert("Please select a dice roll from the 'Available Rolls' pool first.");
        }
    } else {
        // If there was a value previously assigned to this stat, make it available again ( conceptually)
        // The renderAssignableDicePool will handle making it visible if it's part of the current source array.
        const oldValue = characterCreationData.step4_assigned_stats[targetStat];
        if (oldValue !== null && oldValue !== undefined) {
        }

        // Check if the selected dice value is already assigned to another stat
        // This simple check prevents direct assignment if already used.
        // More complex logic could allow swapping. For now, user must unassign first.
        let valueAlreadyAssignedElsewhere = false;
        for (const stat in characterCreationData.step4_assigned_stats) {
            if (characterCreationData.step4_assigned_stats[stat] === selectedDiceValue && stat !== targetStat) {
                // A simple count check for available vs assigned of this value
                const sourceStats = characterCreationData.step4_rolled_stats || characterCreationData.step4_standard_stats;
                const countInSource = sourceStats.filter(s => s === selectedDiceValue).length;
                const countAssigned = Object.values(characterCreationData.step4_assigned_stats).filter(s => s === selectedDiceValue).length;

                if (countAssigned >= countInSource) {
                    valueAlreadyAssignedElsewhere = true;
                    break;
                }
            }
        }

        if (valueAlreadyAssignedElsewhere) {
            alert(`The value ${selectedDiceValue} is already assigned as many times as it appears in your rolls/standard array. Please unassign it first if you want to move it.`);
            return;
        }

        characterCreationData.step4_assigned_stats[targetStat] = selectedDiceValue;
        console.log(`Assigned ${selectedDiceValue} to ${targetStat}`);

        // Optional: Clear selected dice from pool after assignment, requiring re-selection for next assignment
        // characterCreationData.step4_selected_dice_value = null;
        // document.querySelectorAll('#assignable-dice-pool .dice-value.selected').forEach(el => el.classList.remove('selected'));
    }

    // Re-render displays
    let currentStatsToUse = characterCreationData.step4_rolled_stats || characterCreationData.step4_standard_stats;
    renderAssignableDicePool(currentStatsToUse);
    renderMainStatDisplay();
    saveCharacterDataToSession();
    updateAndSaveFinalAbilityScores(); // Update final scores after stat assignment changes
}

function loadStep4Logic() {
    console.log("[DEBUG] Entering loadStep4Logic. Current characterCreationData:", JSON.parse(JSON.stringify(characterCreationData)));
    console.log("[DEBUG] loadStep4Logic: Race Selection:", JSON.parse(JSON.stringify(characterCreationData.step1_race_selection)));
    console.log("[DEBUG] loadStep4Logic: Class Selection:", JSON.parse(JSON.stringify(characterCreationData.step2_selected_base_class)));
    console.log("[DEBUG] loadStep4Logic: Background Selection:", JSON.parse(JSON.stringify(characterCreationData.step3_background_selection)));
    console.log("Loading Step 4 logic (Ability Scores)...");
    characterCreationData.step4_allocated_choice_bonuses = { STR: 0, DEX: 0, CON: 0, INT: 0, WIS: 0, CHA: 0 };
    characterCreationData.step4_unallocated_asi_points = 0;
    // characterCreationData.step4_asi_choices is cleared in getStatBonuses

    // Initialize/retrieve DOM elements for step 3
    // const vitalStatsDisplay = document.getElementById('vital-stats-display'); // Moved down
    const standardArrayDisplay = document.getElementById('standard-array-display');
    const rolledDiceDisplay = document.getElementById('rolled-dice-display');
    const rolledDiceValues = document.getElementById('rolled-dice-values');
    const rollDiceButton = document.getElementById('roll-dice-button');
    const rollDiceWarning = document.getElementById('roll-dice-warning'); // Added for the warning message
    const assignableDicePool = document.getElementById('assignable-dice-pool');

    // Initialize stat blocks for assignment listeners
    const statBlocks = document.querySelectorAll('.stat-block .stat-assigned-value');
    const asiAllocateButtons = document.querySelectorAll('.asi-allocate-button');


    // Get the vitalStatsDisplay element
    const vitalStatsDisplay = document.getElementById('vital-stats-display');

    // Calculate and store/update bonuses and vital stats (including ASI choices)
    // Ensure raceData and classData are available in characterCreationData as expected by helper functions
    if (characterCreationData.step1_race_selection && characterCreationData.step2_selected_base_class) {
        characterCreationData.step4_stat_bonuses = getStatBonuses(); // Uses data from characterCreationData
        characterCreationData.step4_vital_stats = getVitalStats();   // Uses data from characterCreationData
    } else {
        // Fallback if race/class data not yet fully loaded or selected
        console.warn("Race or Class data not fully available for Step 4 calculations. Using defaults for bonuses.");
        // Ensure the default structure includes background
        characterCreationData.step4_stat_bonuses = {
            STR: { race: 0, class: 0, background: 0 }, DEX: { race: 0, class: 0, background: 0 }, CON: { race: 0, class: 0, background: 0 },
            INT: { race: 0, class: 0, background: 0 }, WIS: { race: 0, class: 0, background: 0 }, CHA: { race: 0, class: 0, background: 0 }
        };
        characterCreationData.step4_vital_stats = ["CON"]; // Default vital stat
    }
    saveCharacterDataToSession(); // Save after calculating these

    // Display vital stats
    if (vitalStatsDisplay) {
        if (characterCreationData.step4_vital_stats && characterCreationData.step4_vital_stats.length > 0) {
            vitalStatsDisplay.textContent = characterCreationData.step4_vital_stats.join(', ');
        } else {
            vitalStatsDisplay.textContent = "None specific (General: CON)";
        }
    }

    // Display stat bonuses (now using the calculated ones)
    updateDisplayedBonuses(); // This function should read from characterCreationData.step4_stat_bonuses

    // Prepare and Render ASI Choice UI
    prepareASIChoiceDataForUI();
    renderASIChoicesUI();

    // The rest of loadStep3Logic (rendering dice pool, main stat display, button states) follows...
    // Determine which set of stats to use (standard or rolled)
    let currentStatsToDisplay = characterCreationData.step4_rolled_stats || characterCreationData.step4_standard_stats;

    if (characterCreationData.step4_rolled_stats) {
        standardArrayDisplay.style.display = 'none';
        rolledDiceValues.textContent = characterCreationData.step4_rolled_stats.join(', ');
        rolledDiceDisplay.style.display = 'block';
    } else {
        standardArrayDisplay.style.display = 'block';
        rolledDiceDisplay.style.display = 'none';
    }

    // Populate assignable dice pool
    renderAssignableDicePool(currentStatsToDisplay);

    // Update main stat display (assigned values and totals)
    renderMainStatDisplay();

    // Roll Dice Button state and event listener
    if (characterCreationData.step4_dice_rolled_once) {
        rollDiceButton.disabled = true;
        rollDiceWarning.style.display = 'block'; // Show warning if dice already rolled
    } else {
        rollDiceButton.disabled = false;
        rollDiceWarning.style.display = 'none'; // Hide warning if not yet rolled
    }

    // Display ASI Debug Texts if active
    if (IS_CHARACTER_CREATION_DEBUG_ACTIVE) {
        const debugOutputEl = document.getElementById('asi-debug-output');
        if (debugOutputEl) {
            if (asiDebugTextsCollection.length > 0) {
                let formattedDebugText = "";
                asiDebugTextsCollection.forEach(item => {
                    formattedDebugText += `Source: ${item.source}\n`;
                    formattedDebugText += `Text Processed:\n${item.text}\n\n`;
                    formattedDebugText += "------------------------------------\n";
                });
                debugOutputEl.textContent = formattedDebugText;
            } else {
                debugOutputEl.textContent = "No specific ASI-related texts were processed (or debug collection failed).";
            }
        }
    }

    // Remove existing listener to prevent multiple attachments if loadStep4Logic is called again
    const newRollDiceButton = rollDiceButton.cloneNode(true);
    rollDiceButton.parentNode.replaceChild(newRollDiceButton, rollDiceButton);
    newRollDiceButton.addEventListener('click', handleRollDiceClick);

    // Event listeners for stat assignment (on the stat boxes themselves)
    statBlocks.forEach(block => {
        const newBlock = block.cloneNode(true); // Clone to remove old listeners
        block.parentNode.replaceChild(newBlock, block);
        newBlock.addEventListener('click', handleStatAssignmentClick);
    });

    asiAllocateButtons.forEach(button => {
        const newButton = button.cloneNode(true);
        button.parentNode.replaceChild(newButton, button);
        newButton.addEventListener('click', handleAsiAllocateClick);
    });

    console.log("Step 4 characterCreationData:", JSON.parse(JSON.stringify(characterCreationData)));
    saveCharacterDataToSession();
    updateAndSaveFinalAbilityScores(); // Update final scores after Step 4 logic is loaded
}

function updateAndSaveFinalAbilityScores() {
    console.log("Updating and saving final ability scores...");
    const abilities = characterCreationData.step4_ability_scores; // ["STR", "DEX", ...]
    if (!characterCreationData.ability_scores) {
        characterCreationData.ability_scores = {};
    }

    abilities.forEach(stat => {
        let baseValue = characterCreationData.step4_assigned_stats[stat];
        if (baseValue === null || baseValue === undefined || isNaN(parseInt(baseValue))) {
            baseValue = 10; // Default to 10 if not assigned or not a number
        } else {
            baseValue = parseInt(baseValue);
        }

        const raceBonus = (characterCreationData.step4_stat_bonuses[stat] && characterCreationData.step4_stat_bonuses[stat].race) ?
            parseInt(characterCreationData.step4_stat_bonuses[stat].race) : 0;

        const classBonus = (characterCreationData.step4_stat_bonuses[stat] && characterCreationData.step4_stat_bonuses[stat].class) ?
            parseInt(characterCreationData.step4_stat_bonuses[stat].class) : 0;

        const backgroundBonus = (characterCreationData.step4_stat_bonuses[stat] && characterCreationData.step4_stat_bonuses[stat].background) ?
            parseInt(characterCreationData.step4_stat_bonuses[stat].background) : 0;

        const choiceBonus = (characterCreationData.step4_allocated_choice_bonuses && characterCreationData.step4_allocated_choice_bonuses[stat]) ?
            parseInt(characterCreationData.step4_allocated_choice_bonuses[stat]) : 0;

        characterCreationData.ability_scores[stat] = baseValue + raceBonus + classBonus + backgroundBonus + choiceBonus;
    });

    console.log("Final ability_scores calculated (incl choice):", characterCreationData.ability_scores);
    saveCharacterDataToSession();
}

// Helper functions (if any are used by the above and are not global, they should be copied too)
// For example, parseWordToNumber, parseAbilityList, generate4d6DropLowest
// Assuming these are available globally or will be handled in a later step.
// For now, only the explicitly requested functions are copied.
// It's noted that functions like saveCharacterDataToSession(), GLOBAL_ABILITY_SCORE_MAP,
// IS_CHARACTER_CREATION_DEBUG_ACTIVE, asiDebugTextsCollection are used by these functions.
// Their definitions will need to be present in the execution context where step4.js is used.
// Also, `generate4d6DropLowest` is used by `handleRollDiceClick`.
// `parseWordToNumber` and `parseAbilityList` are used by `identifyASIs`.
// These dependencies will need to be addressed.
