// Global list of skills and their corresponding abilities
const SKILL_LIST = {
    'Acrobatics': 'DEX', 'Animal Handling': 'WIS', 'Arcana': 'INT', 'Athletics': 'STR',
    'Deception': 'CHA', 'History': 'INT', 'Insight': 'WIS', 'Intimidation': 'CHA',
    'Investigation': 'INT', 'Medicine': 'WIS', 'Nature': 'INT', 'Perception': 'WIS',
    'Performance': 'CHA', 'Persuasion': 'CHA', 'Religion': 'INT', 'Sleight of Hand': 'DEX',
    'Stealth': 'DEX', 'Survival': 'WIS'
};

// Order of ability scores for display and iteration
const ABILITY_SCORES_ORDER = ['STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA'];
const ABILITY_SCORE_FULL_NAMES = {
    STR: 'Strength', DEX: 'Dexterity', CON: 'Constitution',
    INT: 'Intelligence', WIS: 'Wisdom', CHA: 'Charisma'
};

let step5DebugTextsCollection = []; // Reset or ensure it's managed if loadStep5Logic can be called multiple times

function getAbilityModifier(score) {
    if (typeof score !== 'number' || isNaN(score)) { // Added NaN check
        addStep5DebugMessage("getAbilityModifier", "Invalid score provided, defaulting to 0 modifier.", { score });
        return 0;
    }
    return Math.floor((score - 10) / 2);
}

function renderStep5DebugInfo() {
    const debugOutputEl = document.getElementById('step5-debug-output');
    if (debugOutputEl && typeof IS_CHARACTER_CREATION_DEBUG_ACTIVE !== 'undefined' && IS_CHARACTER_CREATION_DEBUG_ACTIVE) {
        let focusedDebugData = {};

        // Extract skill_proficiencies
        focusedDebugData.skill_proficiencies = characterCreationData.skill_proficiencies || [];

        // Extract saving_throw_proficiencies
        focusedDebugData.saving_throw_proficiencies = characterCreationData.saving_throw_proficiencies || [];

        // Extract race traits relevant to skills
        const raceTraits = characterCreationData.step1_race_selection?.traits || [];
        focusedDebugData.race_skill_traits = raceTraits.filter(trait => trait.desc && trait.desc.toLowerCase().includes("proficiency in"));

        // Include parent race traits if sub-race traits are empty or don't exist
        // This ensures that if a sub-race doesn't define traits, or if the main traits are on the parent, they are still captured.
        if (characterCreationData.step1_parent_race_selection && characterCreationData.step1_parent_race_selection.traits) {
            const parentRaceTraits = characterCreationData.step1_parent_race_selection.traits.filter(trait => trait.desc && trait.desc.toLowerCase().includes("proficiency in"));
            if (parentRaceTraits.length > 0) {
                if (focusedDebugData.race_skill_traits.length === 0) {
                    focusedDebugData.race_skill_traits = parentRaceTraits;
                } else {
                    // Optionally, merge or indicate parent traits separately
                    // For now, let's add them if not already present (e.g. by name) to avoid duplicates if a subrace trait overrides a parent one.
                    parentRaceTraits.forEach(ptrait => {
                        if (!focusedDebugData.race_skill_traits.find(rtrait => rtrait.name === ptrait.name)) {
                            focusedDebugData.race_skill_traits.push(ptrait);
                        }
                    });
                }
            }
        }


        // Extract class prof_saving_throws
        focusedDebugData.class_prof_saving_throws = characterCreationData.step2_selected_base_class?.prof_saving_throws || "";

        // Extract class prof_skills
        focusedDebugData.class_prof_skills = characterCreationData.step2_selected_base_class?.prof_skills || "";

        // Extract background benefits relevant to skills
        const backgroundBenefits = characterCreationData.step3_background_selection?.benefits || [];
        focusedDebugData.background_skill_benefits = backgroundBenefits.filter(benefit => benefit.type === "skill_proficiency");

        // Add Skill Choice Limits and Selections to Debug Info
        focusedDebugData.skill_choice_limits = {
            allowed_skill_choices: characterCreationData.step5_info?.allowed_skill_choices ?? "Not calculated",
            selected_extra_skills_count: characterCreationData.skill_proficiencies?.extra?.length ?? 0,
            selected_extra_skills_list: characterCreationData.skill_proficiencies?.extra || []
        };

        let formattedDebugText = `Focused Character Proficiency Data for Step 5:
${JSON.stringify(focusedDebugData, null, 2)}

`;
        formattedDebugText += "Step 5 Processing Log:\n";
        step5DebugTextsCollection.forEach(item => {
            formattedDebugText += `Timestamp: ${item.timestamp}
Source: ${item.source}
Message: ${item.message}
Details: ${JSON.stringify(item.details, null, 2)}
`;
            formattedDebugText += "------------------------------------\n";
        });
        debugOutputEl.textContent = formattedDebugText;
    } else if (debugOutputEl) {
        // debugOutputEl.style.display = 'none'; // Visibility handled by button
    }
}

function addStep5DebugMessage(source, message, details = {}) {
    if (typeof IS_CHARACTER_CREATION_DEBUG_ACTIVE !== 'undefined' && IS_CHARACTER_CREATION_DEBUG_ACTIVE) {
        step5DebugTextsCollection.push({
            timestamp: new Date().toISOString(),
            source: source,
            message: message,
            details: details
        });
    }
}

// Simple string search for proficiency. More sophisticated parsing might be needed for complex descriptions.
function checkStringForSkillProficiency(text, skillName) {
    if (typeof text !== 'string' || typeof skillName !== 'string') return false;
    // Example: "proficiency in the Stealth skill" or "gain proficiency in Stealth and Intimidation"
    // A simple check, might need to be more robust (e.g., handle plurals, context)
    const regex = new RegExp(`proficiency in (the )?${skillName}( skill)?`, 'i');
    return regex.test(text);
}

// Function to update the skill choice information text display
function updateSkillChoiceInfoText() {
    const skillChoiceInfoEl = document.getElementById('skill-choice-info');
    if (skillChoiceInfoEl) {
        const allowed = characterCreationData.step5_info?.allowed_skill_choices || 0;
        const selected = characterCreationData.skill_proficiencies?.extra?.length || 0;
        skillChoiceInfoEl.textContent = `Skill Proficiencies (Selected ${selected} of ${allowed})`;
        addStep5DebugMessage("updateSkillChoiceInfoText", "Updated skill choice info display.", { allowed, selected });
    } else {
        // This might be logged frequently if the element isn't on other steps' pages, consider severity.
        // addStep5DebugMessage("updateSkillChoiceInfoText", "'skill-choice-info' element not found. Cannot update display.", {}, "INFO");
    }
}

// Function to update skill checkbox states based on selection limits
function updateSkillCheckboxStatesBasedOnLimit() {
    const allowedSkillChoices = characterCreationData.step5_info?.allowed_skill_choices || 0;
    const selectedExtraSkills = characterCreationData.skill_proficiencies?.extra || [];
    const selectedExtraSkillsCount = selectedExtraSkills.length;
    const skillCheckboxes = document.querySelectorAll('#skills-table input[type="checkbox"][data-skill-name]');

    addStep5DebugMessage("updateSkillCheckboxStatesBasedOnLimit", "Updating skill checkbox states.", { allowedSkillChoices, selectedExtraSkillsCount, numberOfCheckboxes: skillCheckboxes.length });

    skillCheckboxes.forEach(checkbox => {
        const skillName = checkbox.dataset.skillName;
        // Check the flag set during checkbox creation
        const isAllowedBySource = checkbox.dataset.initiallyAllowed === 'true';

        if (!isAllowedBySource) {
            checkbox.disabled = true;
            return; // Skill not allowed by any source, always keep disabled
        }

        if (checkbox.checked) { // If it's already checked, it should be enabled (to allow unchecking)
            checkbox.disabled = false;
        } else {
            // If not checked, disable if limit is reached
            if (selectedExtraSkillsCount >= allowedSkillChoices) {
                checkbox.disabled = true;
            } else {
                checkbox.disabled = false; // Enable if limit not reached and allowed by source
            }
        }
    });
    addStep5DebugMessage("updateSkillCheckboxStatesBasedOnLimit", "Finished updating skill checkbox states.");
}


function loadStep5Logic() {
    console.log("Step 5 JS loaded");
    step5DebugTextsCollection = []; // Clear debug messages for this run

    // Initialize full data tables for step 5
    characterCreationData.step5_full_saving_throw_table = [];
    characterCreationData.step5_full_skill_table = [];

    addStep5DebugMessage("loadStep5Logic", "Starting Step 5 logic execution.");
    addStep5DebugMessage("loadStep5Logic", "Initial characterCreationData.step2_selected_base_class", characterCreationData.step2_selected_base_class);


    // Ensure proficiency objects and extra arrays are initialized
    if (!characterCreationData.saving_throw_proficiencies) {
        characterCreationData.saving_throw_proficiencies = {};
    }
    if (!characterCreationData.saving_throw_proficiencies.extra) {
        characterCreationData.saving_throw_proficiencies.extra = [];
    }
    if (!characterCreationData.skill_proficiencies) {
        characterCreationData.skill_proficiencies = {}; // This was an array, should be object to hold 'base' and 'extra'
    }
     // If skill_proficiencies was an array (old structure), migrate or re-initialize
    if (Array.isArray(characterCreationData.skill_proficiencies)) {
        characterCreationData.skill_proficiencies = { base: characterCreationData.skill_proficiencies, extra: [] };
    } else if (!characterCreationData.skill_proficiencies.base) {
        characterCreationData.skill_proficiencies.base = [];
    }
    if (!characterCreationData.skill_proficiencies.extra) {
        characterCreationData.skill_proficiencies.extra = [];
    }

    // Initialize step5_info if it doesn't exist
    if (!characterCreationData.step5_info) {
        characterCreationData.step5_info = {};
    }

    // Calculate allowed skill choices from class
    let allowedSkillChoices = 0;
    const wordToNumberMap = { 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6 };
    const classData = characterCreationData.step2_selected_base_class;

    if (classData && typeof classData.prof_skills === 'string') {
        addStep5DebugMessage("loadStep5Logic", "Processing class prof_skills string for skill choices.", { prof_skills: classData.prof_skills });
        const profSkillsLower = classData.prof_skills.toLowerCase();
        const match = profSkillsLower.match(/choose (one|two|three|four|five|six) from/i);

        if (match && match[1]) {
            const numberWord = match[1];
            const count = wordToNumberMap[numberWord];
            if (typeof count === 'number') {
                allowedSkillChoices += count;
                addStep5DebugMessage("loadStep5Logic", `Derived ${count} skill choice(s) from prof_skills string: "${classData.prof_skills}". New total: ${allowedSkillChoices}.`, { derivedCount: count });
            } else {
                addStep5DebugMessage("loadStep5Logic", `Could not map number word "${numberWord}" from prof_skills to a number.`, { prof_skills: classData.prof_skills });
            }
        } else {
            addStep5DebugMessage("loadStep5Logic", "No choice pattern (e.g., 'Choose X from') found in prof_skills string.", { prof_skills: classData.prof_skills });
        }
    } else {
        addStep5DebugMessage("loadStep5Logic", "Class prof_skills string not found or not a string.", { prof_skills: classData?.prof_skills });
    }

    // Fallback to proficiency_choices if prof_skills parsing yielded 0 choices
    if (allowedSkillChoices === 0) {
        addStep5DebugMessage("loadStep5Logic", "Falling back to proficiency_choices for class skill choices as prof_skills parsing yielded 0.", { currentAllowedChoices: allowedSkillChoices });
        const classProficiencyChoices = classData?.data?.proficiency_choices || classData?.proficiency_choices;

        if (!classProficiencyChoices || classProficiencyChoices.length === 0) {
            let reason = "Not found or empty.";
            if (classData) {
                if (!classProficiencyChoices) reason = "proficiency_choices attribute itself not found on class data object (checked root and .data).";
                else if (classProficiencyChoices.length === 0) reason = "proficiency_choices array is empty.";
            } else {
                reason = "step2_selected_base_class data is missing.";
            }
            addStep5DebugMessage("loadStep5Logic", "No class proficiency_choices available (fallback).", { reason: reason, classData: classData });
        } else {
            addStep5DebugMessage("loadStep5Logic", "Found class proficiency_choices (fallback). Processing for skill choices.", { count: classProficiencyChoices.length, choices: classProficiencyChoices });
            for (const choiceGroup of classProficiencyChoices) {
                let isSkillChoiceGroup = false;
                let reasonForSkillChoice = "N/A";

                if (choiceGroup.desc && choiceGroup.desc.toLowerCase().includes("skill")) {
                    isSkillChoiceGroup = true;
                    reasonForSkillChoice = "Description contains 'skill'";
                    addStep5DebugMessage("loadStep5Logic", `Choice group (fallback) '${choiceGroup.desc}' identified as potential skill choice by description.`, { choiceGroup });
                }

                if (choiceGroup.choose_from && choiceGroup.choose_from.options && choiceGroup.choose_from.options.length > 0) {
                    let foundSkillInOptions = false;
                    for (const option of choiceGroup.choose_from.options) {
                        const optionName = option.item?.name || option.name || "";
                        if (optionName && SKILL_LIST.hasOwnProperty(optionName)) {
                            foundSkillInOptions = true;
                            reasonForSkillChoice = `Option '${optionName}' is a known skill.`;
                            addStep5DebugMessage("loadStep5Logic", `Choice group (fallback) '${choiceGroup.desc || "No Desc"}' confirmed as skill choice. Reason: ${reasonForSkillChoice}`, { choiceGroup });
                            break;
                        }
                    }
                    if (foundSkillInOptions) {
                        isSkillChoiceGroup = true;
                    } else {
                         addStep5DebugMessage("loadStep5Logic", `Choice group (fallback) '${choiceGroup.desc || "No Desc"}' options did not contain any known skills.`, { options: choiceGroup.choose_from.options });
                    }
                } else {
                    addStep5DebugMessage("loadStep5Logic", `Choice group (fallback) '${choiceGroup.desc || "No Desc"}' has no options to check for skills.`, { choiceGroup });
                }

                if (isSkillChoiceGroup) {
                    if (choiceGroup.choose_from && typeof choiceGroup.choose_from.count === 'number') {
                        allowedSkillChoices += choiceGroup.choose_from.count;
                        addStep5DebugMessage("loadStep5Logic", `Incrementing allowedSkillChoices by ${choiceGroup.choose_from.count} for group (fallback) '${choiceGroup.desc || "No Desc"}'. New total: ${allowedSkillChoices}. Reason: ${reasonForSkillChoice}`, { count: choiceGroup.choose_from.count });
                    } else {
                        addStep5DebugMessage("loadStep5Logic", `Skill choice group (fallback) '${choiceGroup.desc || "No Desc"}' lacks valid count. Not adding to total.`, { choiceGroup });
                    }
                } else {
                     addStep5DebugMessage("loadStep5Logic", `Choice group (fallback) '${choiceGroup.desc || "No Desc"}' was NOT identified as a skill choice group.`, { reason: reasonForSkillChoice, choiceGroup });
                }
            }
        }
    } else {
        addStep5DebugMessage("loadStep5Logic", "Skipping proficiency_choices for class skills as prof_skills parsing yielded choices.", { choicesFromProfSkills: allowedSkillChoices });
    }
    addStep5DebugMessage("loadStep5Logic", `Allowed skill choices from class (after prof_skills and potential fallback): ${allowedSkillChoices}`);

    // Calculate allowed skill choices from background benefits
    const backgroundBenefits = characterCreationData.step3_background_selection?.benefits;
    if (backgroundBenefits && backgroundBenefits.length > 0) {
        addStep5DebugMessage("loadStep5Logic", "Processing background benefits for skill choices.", { count: backgroundBenefits.length });
        for (const benefit of backgroundBenefits) {
            if (benefit.type === "skill_proficiency" && benefit.desc) {
                let choicesFromBenefit = 0;
                const descLower = benefit.desc.toLowerCase();

                // Order is important here: more specific phrases should be checked before general ones.
                if (descLower.startsWith("two of your choice")) { // Handles "Two of your choice from all skills"
                    choicesFromBenefit = 2;
                } else if (descLower.startsWith("one of your choice")) { // Handles "One of your choice from all skills"
                    choicesFromBenefit = 1;
                } else if (descLower.includes("choose two from") || descLower.includes("choose two of the following")) {
                    choicesFromBenefit = 2;
                } else if (descLower.includes("choose one from") || descLower.includes("choose one of the following")) {
                    choicesFromBenefit = 1;
                } else if (descLower.includes("choose any two") || descLower.includes("choose two skills")) { // General "choose two"
                    choicesFromBenefit = 2;
                } else if (descLower.includes("choose any one") || descLower.includes("choose one skill")) { // General "choose one"
                    choicesFromBenefit = 1;
                } else if (descLower.includes("either ") && descLower.includes(" or ")) {
                    // Handles cases like:
                    // 1. "SkillA, and either SkillB or SkillC" (grants 1 choice for "either SkillB or SkillC")
                    // 2. "either SkillA or SkillB" (grants 1 choice)
                    if (descLower.includes(", and either ") || descLower.includes(",and either ")) {
                         choicesFromBenefit = 1;
                    } else if (!descLower.includes(",")) { // Ensures it's a simple "either X or Y" and not part of a more complex unhandled list
                         choicesFromBenefit = 1;
                    }
                    // Other complex structures with "or" (e.g., "SkillA, SkillB, or SkillC") are not explicitly handled here
                    // unless they match earlier "choose one from..." patterns.
                    // "X, Y, and choose one from A, B" is handled by "choose one from" or "choose one skill".
                    // "X, and Y" (fixed skills) results in 0 choices, so no explicit handling needed to add to choicesFromBenefit.
                }

                if (choicesFromBenefit > 0) {
                    allowedSkillChoices += choicesFromBenefit;
                    addStep5DebugMessage("loadStep5Logic", `Added ${choicesFromBenefit} skill choice(s) from background benefit: '${benefit.desc}'. New total: ${allowedSkillChoices}`, { benefit });
                } else {
                    addStep5DebugMessage("loadStep5Logic", `Background benefit '${benefit.desc}' did not grant additional skill choices (likely fixed proficiencies).`, { benefit });
                }
            }
        }
    } else {
        addStep5DebugMessage("loadStep5Logic", "No background benefits found or step3_background_selection is missing.");
    }

    // Store the final calculated allowed skill choices
    characterCreationData.step5_info.allowed_skill_choices = allowedSkillChoices;
    addStep5DebugMessage("loadStep5Logic", `Final total allowed skill choices after class and background: ${allowedSkillChoices}`);

    // Update the skill choice information display
    updateSkillChoiceInfoText();


    if (!characterCreationData) {
        addStep5DebugMessage("loadStep5Logic", "characterCreationData is not available. Aborting.", {error: true});
        console.error("characterCreationData is not available for Step 5!");
        renderStep5DebugInfo();
        return;
    }

    const proficiencyBonusValue = characterCreationData.proficiency_bonus || 2;

    // --- SAVING THROWS ---
    const savingThrowsTableBody = document.getElementById('saving-throws-table')?.querySelector('tbody');
    if (!savingThrowsTableBody) {
        addStep5DebugMessage("loadStep5Logic", "Saving throws table body not found.", {error: true});
        console.error("Saving throws table body not found!");
    } else {
        savingThrowsTableBody.innerHTML = ''; // Clear existing rows
        characterCreationData.step5_full_saving_throw_table = []; // Clear previous data
        const classProfSavingThrows = characterCreationData.step2_selected_base_class?.prof_saving_throws || "";
        addStep5DebugMessage("SavingThrowsPopulation", "Class proficient saving throws string.", {prof_saving_throws: classProfSavingThrows});

        ABILITY_SCORES_ORDER.forEach(abilityAbbr => {
            const fullAbilityName = ABILITY_SCORE_FULL_NAMES[abilityAbbr];
            const baseScore = characterCreationData.ability_scores?.[abilityAbbr] || 10;
            const modifier = getAbilityModifier(baseScore);

            let isClassProficient = false; // Renamed for clarity
            if (classProfSavingThrows.toLowerCase().includes(fullAbilityName.toLowerCase())) {
                isClassProficient = true;
            }

            // Determine if extra proficiency is checked
            const isExtraProficient = characterCreationData.saving_throw_proficiencies.extra.includes(fullAbilityName);

            const proficiencyBonusForCalc = (isClassProficient || isExtraProficient) ? proficiencyBonusValue : 0;
            const totalScore = modifier + proficiencyBonusForCalc;
            const classBonusText = isClassProficient ? `Yes (+${proficiencyBonusValue})` : '';

            const row = savingThrowsTableBody.insertRow();
            row.insertCell().textContent = fullAbilityName;
            row.insertCell().textContent = baseScore;
            row.insertCell().textContent = ''; // Race contribution column
            row.insertCell().textContent = classBonusText; // Class contribution column

            // Add Extra Proficiency Checkbox Column
            const extraProfCell = row.insertCell();
            const extraProfCheckbox = document.createElement('input');
            extraProfCheckbox.type = 'checkbox';
            extraProfCheckbox.id = `saving-throw-extra-prof-${abilityAbbr}`;
            // extraProfCheckbox.disabled = true; // Will be handled by logic below
            extraProfCheckbox.dataset.abilityAbbr = abilityAbbr; // Store ability for event listener

            // A saving throw is either proficient by class or can be chosen as extra.
            // It cannot be proficient by class AND selected as an "extra" proficiency from a limited pool.
            // The "extra" checkbox here means "is this saving throw getting proficiency bonus beyond the class default?"
            // For most classes, saving throw proficiencies are fixed. Some features might allow choosing one.
            // For now, let's assume "extra" means the user explicitly checked it, potentially overriding other logic if needed.
            // However, standard D&D 5e doesn't typically allow "extra" saving throw proficiencies like skills.
            // This checkbox might represent a special feature (e.g. Monk's Diamond Soul).
            // Let's assume it's for features that grant additional saving throw profs.
            // If class already grants it, the checkbox being checked doesn't change much unless it implies expertise (not handled here).

            extraProfCheckbox.checked = isExtraProficient;
            extraProfCheckbox.disabled = isClassProficient; // If class provides it, user cannot uncheck it here. Or can they?
                                                        // Let's assume if class provides it, it's fixed.
                                                        // If a feature allows choosing an *additional* one, that's different.
                                                        // For now, if isClassProficient = true, checkbox is checked and disabled.
            if (isClassProficient) {
                extraProfCheckbox.checked = true;
                // If it's a class proficiency, it shouldn't be in the 'extra' list unless a feature specifically adds it redundantly.
                // Let's ensure `extra` only contains truly extra proficiencies.
                // However, the current problem asks to store checkbox state.
            }


            extraProfCheckbox.addEventListener('change', function() {
                const changedAbilityAbbr = this.dataset.abilityAbbr;
                const changedFullAbilityName = ABILITY_SCORE_FULL_NAMES[changedAbilityAbbr];
                const isChecked = this.checked;

                if (isChecked) {
                    if (!characterCreationData.saving_throw_proficiencies.extra.includes(changedFullAbilityName)) {
                        characterCreationData.saving_throw_proficiencies.extra.push(changedFullAbilityName);
                    }
                } else {
                    characterCreationData.saving_throw_proficiencies.extra = characterCreationData.saving_throw_proficiencies.extra.filter(st => st !== changedFullAbilityName);
                }

                // Update the corresponding entry in step5_full_saving_throw_table
                const entryToUpdate = characterCreationData.step5_full_saving_throw_table.find(st => st.name === changedFullAbilityName);
                if (entryToUpdate) {
                    entryToUpdate.extra_proficient = isChecked;
                    const updatedProficiencyBonus = (entryToUpdate.class_proficient || isChecked) ? proficiencyBonusValue : 0;
                    entryToUpdate.total_score = entryToUpdate.modifier + updatedProficiencyBonus;

                    // Also update the table cell directly for immediate visual feedback
                    const specificRow = Array.from(savingThrowsTableBody.rows).find(r => r.cells[0].textContent === changedFullAbilityName);
                    if (specificRow) {
                        specificRow.cells[6].textContent = entryToUpdate.total_score; // Assuming total score is in the 7th cell (index 6)
                    }
                }
                renderStep5DebugInfo(); // Update debug info on change
            });
            extraProfCell.appendChild(extraProfCheckbox);

            row.insertCell().textContent = ''; // Background contribution column (usually none for ST)
            row.insertCell().textContent = totalScore;

            // Populate step5_full_saving_throw_table
            const savingThrowData = {
                name: fullAbilityName,
                ability: abilityAbbr,
                base_score: baseScore,
                modifier: modifier,
                race_bonus: '', // Placeholder
                class_proficient: isClassProficient,
                class_bonus_text: classBonusText,
                background_bonus: '', // Placeholder
                extra_proficient: extraProfCheckbox.checked, // Capture current state
                total_score: totalScore
            };
            characterCreationData.step5_full_saving_throw_table.push(savingThrowData);

            addStep5DebugMessage("SavingThrowsPopulation", `Processed ${fullAbilityName}`, {
                baseScore, modifier, isClassProficient, classProfSavingThrows, proficiencyBonusForCalc, totalScore, rawProfBonus: proficiencyBonusValue, details: savingThrowData
            });
        });
        addStep5DebugMessage("loadStep5Logic", "Saving throws table populated.", { full_table: characterCreationData.step5_full_saving_throw_table });
    }

    // --- SKILLS ---
    const skillsTableBody = document.getElementById('skills-table')?.querySelector('tbody');
    if (!skillsTableBody) {
        addStep5DebugMessage("loadStep5Logic", "Skills table body not found.", {error: true});
        console.error("Skills table body not found!");
    } else {
        skillsTableBody.innerHTML = ''; // Clear existing rows
        characterCreationData.step5_full_skill_table = []; // Clear previous data
        // Ensure 'base' exists for chosen skills
        if (!characterCreationData.skill_proficiencies.base) {
            characterCreationData.skill_proficiencies.base = [];
        }
        const chosenSkillProficiencies = (characterCreationData.skill_proficiencies.base || []).map(s => s.toLowerCase());
        addStep5DebugMessage("SkillsPopulation", "User chosen skill proficiencies (lowercase from base).", {chosenSkillProficiencies});

        for (const skillName in SKILL_LIST) {
            if (SKILL_LIST.hasOwnProperty(skillName)) {
                const skillNameLower = skillName.toLowerCase();
                const abilityAbbr = SKILL_LIST[skillName];
                const baseScore = characterCreationData.ability_scores?.[abilityAbbr] || 10;
                const modifier = getAbilityModifier(baseScore);

                let proficientByRace = false;
                let proficientByClass = false;
                let proficientByBackground = false;

                // Check Race Proficiency from traits
                const raceTraits = characterCreationData.step1_race_selection?.traits || [];
                for (const trait of raceTraits) {
                    if (trait.desc && checkStringForSkillProficiency(trait.desc, skillName)) {
                        proficientByRace = true;
                        addStep5DebugMessage("SkillsPopulation", `Skill proficiency for ${skillName} from race trait: ${trait.name}`, {desc: trait.desc});
                        break;
                    }
                }
                if (!proficientByRace) { // Only check parent if not found in subrace
                    const parentRaceTraits = characterCreationData.step1_parent_race_selection?.traits || [];
                     for (const trait of parentRaceTraits) {
                        if (trait.desc && checkStringForSkillProficiency(trait.desc, skillName)) {
                            proficientByRace = true;
                            addStep5DebugMessage("SkillsPopulation", `Skill proficiency for ${skillName} from parent race trait: ${trait.name}`, {desc: trait.desc});
                            break;
                        }
                    }
                }

                // Check Class Proficiency (from choices stored in characterCreationData.skill_proficiencies)
                if (chosenSkillProficiencies.includes(skillNameLower)) {
                    // We need to determine if this choice was made due to class. This is hard without source tags.
                    // For now, if it's chosen, and the class *offers* it as a choice, we'll mark it.
                    const classSkillOptions = characterCreationData.step2_selected_base_class?.prof_skills || "";
                    if (classSkillOptions.toLowerCase().includes(skillNameLower)) {
                         proficientByClass = true;
                    }
                    // If not set by class options, it could be from another source (background, race choice if race gives choice not direct grant)
                }


                // Check Background Proficiency
                const backgroundBenefits = characterCreationData.step3_background_selection?.benefits || [];
                for (const benefit of backgroundBenefits) {
                    if (benefit.type === "skill_proficiency" && benefit.desc) {
                        // If the skill is directly named as a grant (not a choice from a list)
                        if (benefit.desc.toLowerCase().trim() === skillNameLower || benefit.desc.toLowerCase().startsWith(skillNameLower + ",") || benefit.desc.toLowerCase().includes(" " + skillNameLower + ",")) {
                            proficientByBackground = true; // Direct grant
                            addStep5DebugMessage("SkillsPopulation", `Direct skill grant for ${skillName} from background: ${benefit.name}`, {desc: benefit.desc});
                            break;
                        }
                        // If chosen and the background offered this skill
                        if (chosenSkillProficiencies.includes(skillNameLower) && benefit.desc.toLowerCase().includes(skillNameLower)) {
                            proficientByBackground = true; // Chosen, and background was a potential source
                            break;
                        }
                    }
                }

                // Re-evaluate proficientByClass if proficientByBackground is true and chosenSkillProficiencies includes the skill
                // This attempts to correctly attribute a chosen skill. If background grants it directly or it was chosen via background,
                // then it shouldn't also be marked as proficientByClass unless the class *also* specifically grants it (rare for same skill).
                if (proficientByBackground && chosenSkillProficiencies.includes(skillNameLower)) {
                    const classSkillOptions = characterCreationData.step2_selected_base_class?.prof_skills || "";
                    // If the class *also* lists it as an option, it's ambiguous or user picked it for class.
                    // For simplicity, if background is a clear source, we might unmark class if class was just an option.
                    // This logic is complex due to shared choice pools.
                    // Current approach: if chosen, mark based on whether source *could* provide it.
                    // This means a skill could show Yes for both Class and Background if chosen and offered by both.
                }


                // Determine if extra proficiency is checked for this skill
                const isExtraProficientByChoice = characterCreationData.skill_proficiencies.extra.includes(skillName);

                const isOverallProficient = proficientByRace || proficientByClass || proficientByBackground || isExtraProficientByChoice;
                const overallBonusText = isOverallProficient ? `Yes (+${proficiencyBonusValue})` : '';
                const currentProficiencyBonus = isOverallProficient ? proficiencyBonusValue : 0;
                const totalScore = modifier + currentProficiencyBonus;


                const row = skillsTableBody.insertRow();
                row.insertCell().textContent = skillName;
                row.insertCell().textContent = abilityAbbr;
                row.insertCell().textContent = baseScore;
                row.insertCell().textContent = proficientByRace ? 'Yes' : ''; // Was 'No'

                // Determine proficientByClass based on chosenSkillProficiencies and if class could provide it
                let classActuallyProvidedProficiency = false;
                if (chosenSkillProficiencies.includes(skillNameLower)) {
                    const classSkillOptions = characterCreationData.step2_selected_base_class?.prof_skills || "";
                    if (classSkillOptions.toLowerCase().includes(skillNameLower)) {
                        // This skill was chosen and the class offered it.
                        // This is the most direct way to infer class proficiency from choices.
                        classActuallyProvidedProficiency = true;
                    }
                }
                // proficientByClass was already determined above based on more direct checks if available,
                // this is refining it for the 'Yes'/' ' column.
                // The actual proficientByClass variable might be true due to a direct feature not a choice.
                // For the column, we are showing if the "Class" column should say Yes.
                // Let's stick to the initially determined proficientByClass for this.
                row.insertCell().textContent = proficientByClass ? 'Yes' : ''; // Was 'No'


                // Determine proficientByBackground for the column display
                // proficientByBackground was already determined above.
                row.insertCell().textContent = proficientByBackground ? 'Yes' : '';

                // Add Extra Proficiency Checkbox Column for Skills
                const skillExtraProfCell = row.insertCell();
                const skillExtraProfCheckbox = document.createElement('input');
                skillExtraProfCheckbox.type = 'checkbox';
                skillExtraProfCheckbox.id = `skill-extra-prof-${skillName.replace(/\s+/g, '-')}`;
                // skillExtraProfCheckbox.disabled = true; // Initial disabling will be handled by updateSkillCheckboxStatesBasedOnLimit
                skillExtraProfCheckbox.dataset.skillName = skillName;

                // Determine if checkbox should be initially allowed by sources
                // Enable if skill is granted by race, class, or background options
                let canBeGrantedByRace = false;
                let canBeGrantedByClass = false;
                let canBeGrantedByBackground = false;

                // Check Race: Direct grant or if race offers choices (need to define how race choices are stored)
                // For now, using existing proficientByRace as a proxy for "available from race"
                if (proficientByRace) canBeGrantedByRace = true;
                // TODO: Add specific check for race *options* if characterCreationData.step1_race_selection.skill_proficiency_options exists

                // Check Class: Direct grant or if class offers choices
                const classSkillOptionsText = characterCreationData.step2_selected_base_class?.prof_skills || "";
                // This checks if the skill is part of the general text blob of class skills.
                // A more precise check would be against a list of *choosable* skills if available.
                if (classSkillOptionsText.toLowerCase().includes(skillName.toLowerCase())) {
                    canBeGrantedByClass = true;
                }
                // If class grants specific skill proficiencies (not choices), proficientByClass would be true
                if (proficientByClass) canBeGrantedByClass = true;


                // Check Background: Direct grant or if background offers choices
                // The variable 'backgroundBenefits' is already declared and populated earlier in this loop (around line 268)
                for (const benefit of backgroundBenefits) { // Use existing backgroundBenefits
                    if (benefit.type === "skill_proficiency" && benefit.desc) {
                        if (benefit.desc.toLowerCase().includes(skillName.toLowerCase())) {
                            canBeGrantedByBackground = true;
                            break;
                        }
                    }
                }
                // If background grants specific skill proficiencies, proficientByBackground would be true
                if (proficientByBackground) canBeGrantedByBackground = true;

                let isInitiallyAllowedBySource = (canBeGrantedByRace || canBeGrantedByClass || canBeGrantedByBackground);
                skillExtraProfCheckbox.dataset.initiallyAllowed = isInitiallyAllowedBySource ? 'true' : 'false';


                // Check if already selected as extra (and thus should be checked)
                if (characterCreationData.skill_proficiencies.extra.includes(skillName)) {
                    skillExtraProfCheckbox.checked = true;
                }

                skillExtraProfCheckbox.addEventListener('change', function(event) {
                    const currentSkillName = this.dataset.skillName;
                    const currentAllowedSkillChoices = characterCreationData.step5_info?.allowed_skill_choices || 0;
                    // extraSkills array reference before modification
                    const extraSkillsBeforeChange = [...(characterCreationData.skill_proficiencies.extra || [])];
                    let currentSelectedCount = extraSkillsBeforeChange.length;
                    const isChecked = this.checked;

                    if (isChecked) {
                        if (!extraSkillsBeforeChange.includes(currentSkillName) && currentSelectedCount >= currentAllowedSkillChoices) {
                            addStep5DebugMessage("SkillCheckboxChange", `Attempted to select ${currentSkillName}, but limit (${currentAllowedSkillChoices}) reached. Reverting.`, { currentSelectedCount });
                            this.checked = false;
                            event.preventDefault();
                        } else {
                            if (!extraSkillsBeforeChange.includes(currentSkillName)) {
                                characterCreationData.skill_proficiencies.extra.push(currentSkillName);
                                addStep5DebugMessage("SkillCheckboxChange", `Selected skill ${currentSkillName}.`, { extraSkills: characterCreationData.skill_proficiencies.extra });
                            }
                        }
                    } else {
                        if (extraSkillsBeforeChange.includes(currentSkillName)) {
                            characterCreationData.skill_proficiencies.extra = characterCreationData.skill_proficiencies.extra.filter(sk => sk !== currentSkillName);
                            addStep5DebugMessage("SkillCheckboxChange", `Deselected skill ${currentSkillName}.`, { extraSkills: characterCreationData.skill_proficiencies.extra });
                        }
                    }

                    // Update the corresponding entry in step5_full_skill_table
                    const entryToUpdate = characterCreationData.step5_full_skill_table.find(sk => sk.name === currentSkillName);
                    if (entryToUpdate) {
                        entryToUpdate.extra_proficient = this.checked; // Use current checkbox state after potential revert
                        const newOverallProficient = entryToUpdate.race_proficient || entryToUpdate.class_proficient || entryToUpdate.background_proficient || entryToUpdate.extra_proficient;
                        const newProficiencyBonus = newOverallProficient ? proficiencyBonusValue : 0;
                        entryToUpdate.total_score = entryToUpdate.modifier + newProficiencyBonus;
                        entryToUpdate.is_overall_proficient = newOverallProficient;
                        entryToUpdate.overall_bonus_text = newOverallProficient ? `Yes (+${proficiencyBonusValue})` : '';

                        // Also update the table cell directly for immediate visual feedback
                        const specificRow = Array.from(skillsTableBody.rows).find(r => r.cells[0].textContent === currentSkillName);
                        if (specificRow) {
                            specificRow.cells[7].textContent = entryToUpdate.overall_bonus_text; // Bonus text cell (index 7)
                            specificRow.cells[8].textContent = entryToUpdate.total_score;    // Total score cell (index 8)
                        }
                    }

                    updateSkillChoiceInfoText();
                    updateSkillCheckboxStatesBasedOnLimit();
                    renderStep5DebugInfo();
                });
                skillExtraProfCell.appendChild(skillExtraProfCheckbox);

                row.insertCell().textContent = overallBonusText;
                row.insertCell().textContent = totalScore;

                // Populate step5_full_skill_table
                const skillData = {
                    name: skillName,
                    ability: abilityAbbr,
                    base_score: baseScore,
                    modifier: modifier,
                    race_proficient: proficientByRace,
                    class_proficient: proficientByClass, // This reflects actual class proficiency
                    background_proficient: proficientByBackground,
                    extra_proficient: skillExtraProfCheckbox.checked, // Capture current state
                    is_overall_proficient: isOverallProficient,
                    overall_bonus_text: overallBonusText,
                    total_score: totalScore
                };
                characterCreationData.step5_full_skill_table.push(skillData);

                addStep5DebugMessage("SkillsPopulation", `Processed Skill: ${skillName}`, {
                    details: skillData, chosenSkillProficiencies
                });
            }
        }
        addStep5DebugMessage("loadStep5Logic", "Skills table populated.", { full_table: characterCreationData.step5_full_skill_table });
    }

    updateSkillCheckboxStatesBasedOnLimit(); // Initial call to set checkbox states based on loaded data and limits
    updateSkillChoiceInfoText(); // Ensure info text is correct after initial load & checkbox state update

    renderStep5DebugInfo();
    console.log("Step 5 Logic fully executed. characterCreationData:", JSON.parse(JSON.stringify(characterCreationData)));
}

// Placeholder for the debug toggle function, if not already globally defined
// This should ideally be in a general JS file if used by other steps too.
if (typeof toggleDebugVisibility !== 'function') {
    function toggleDebugVisibility(elementId) {
        const el = document.getElementById(elementId);
        if (el) {
            el.style.display = el.style.display === 'none' ? 'block' : 'none';
        }
    }
}

// Assuming this script is loaded after character_creation.js (which defines characterCreationData)
// and that loadStep5Logic() will be called at the appropriate time by the main character creation script.
