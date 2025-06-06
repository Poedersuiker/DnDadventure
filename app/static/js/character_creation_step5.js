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
    addStep5DebugMessage("loadStep5Logic", "Starting Step 5 logic execution.");

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
    const classData = characterCreationData.step2_selected_base_class;
    if (classData && classData.proficiency_choices) {
        addStep5DebugMessage("loadStep5Logic", "Calculating allowed skill choices from class.", { classProfChoices: classData.proficiency_choices });
        for (const choiceGroup of classData.proficiency_choices) {
            // Heuristic: check if 'desc' mentions skills or if options look like skills
            let isSkillChoiceGroup = false;
            if (choiceGroup.desc && choiceGroup.desc.toLowerCase().includes("skill")) {
                isSkillChoiceGroup = true;
            } else if (choiceGroup.choose_from && choiceGroup.choose_from.options && choiceGroup.choose_from.options.length > 0) {
                // Check if the first option looks like a skill (e.g., exists in SKILL_LIST)
                const firstOption = choiceGroup.choose_from.options[0]?.item?.name || "";
                if (SKILL_LIST.hasOwnProperty(firstOption)) {
                     isSkillChoiceGroup = true;
                }
            }

            if (isSkillChoiceGroup && choiceGroup.choose_from && typeof choiceGroup.choose_from.count === 'number') {
                allowedSkillChoices += choiceGroup.choose_from.count;
                addStep5DebugMessage("loadStep5Logic", `Found skill choice group, adding ${choiceGroup.choose_from.count} to allowedSkillChoices.`, { choiceGroupDesc: choiceGroup.desc, count: choiceGroup.choose_from.count });
            }
        }
    }
    characterCreationData.step5_info.allowed_skill_choices = allowedSkillChoices;
    addStep5DebugMessage("loadStep5Logic", `Total allowed skill choices calculated: ${allowedSkillChoices}`);

    // For UI (placeholder for now - actual DOM element to be added in HTML)
    const skillChoiceInfoEl = document.getElementById('skill-choice-info');
    if (skillChoiceInfoEl) {
        skillChoiceInfoEl.textContent = `You can choose ${allowedSkillChoices} skill proficiencies. Selected: ${characterCreationData.skill_proficiencies.extra.length || 0}.`;
    } else {
        console.log(`UI Placeholder: You can choose ${allowedSkillChoices} skill proficiencies. Selected: ${characterCreationData.skill_proficiencies.extra.length || 0}. ('skill-choice-info' element not found)`);
    }


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
        const classProfSavingThrows = characterCreationData.step2_selected_base_class?.prof_saving_throws || "";
        addStep5DebugMessage("SavingThrowsPopulation", "Class proficient saving throws string.", {prof_saving_throws: classProfSavingThrows});

        ABILITY_SCORES_ORDER.forEach(abilityAbbr => {
            const fullAbilityName = ABILITY_SCORE_FULL_NAMES[abilityAbbr];
            const baseScore = characterCreationData.ability_scores?.[abilityAbbr] || 10;
            const modifier = getAbilityModifier(baseScore);

            let isProficient = false;
            if (classProfSavingThrows.toLowerCase().includes(fullAbilityName.toLowerCase())) {
                isProficient = true;
            }

            const currentProficiencyBonus = isProficient ? proficiencyBonusValue : 0;
            const totalScore = modifier + currentProficiencyBonus;

            const row = savingThrowsTableBody.insertRow();
            row.insertCell().textContent = fullAbilityName;
            row.insertCell().textContent = baseScore;
            row.insertCell().textContent = ''; // Race contribution column
            row.insertCell().textContent = isProficient ? `Yes (+${proficiencyBonusValue})` : ''; // Class contribution column

            // Add Extra Proficiency Checkbox Column
            const extraProfCell = row.insertCell();
            const extraProfCheckbox = document.createElement('input');
            extraProfCheckbox.type = 'checkbox';
            extraProfCheckbox.id = `saving-throw-extra-prof-${abilityAbbr}`;
            extraProfCheckbox.disabled = true; // Disabled by default
            extraProfCheckbox.dataset.ability = abilityAbbr; // Store ability for event listener

            // Check if this saving throw is granted by the class
            if (isProficient) { // isProficient here means class proficiency
                extraProfCheckbox.disabled = false;
            }

            // Check if already selected as extra
            if (characterCreationData.saving_throw_proficiencies.extra.includes(fullAbilityName)) {
                extraProfCheckbox.checked = true;
            }

            extraProfCheckbox.addEventListener('change', function() {
                const abilityFullName = ABILITY_SCORE_FULL_NAMES[this.dataset.ability];
                if (this.checked) {
                    if (!characterCreationData.saving_throw_proficiencies.extra.includes(abilityFullName)) {
                        characterCreationData.saving_throw_proficiencies.extra.push(abilityFullName);
                    }
                } else {
                    characterCreationData.saving_throw_proficiencies.extra = characterCreationData.saving_throw_proficiencies.extra.filter(st => st !== abilityFullName);
                }
                renderStep5DebugInfo(); // Update debug info on change
            });
            extraProfCell.appendChild(extraProfCheckbox);

            row.insertCell().textContent = ''; // Background contribution column (usually none for ST)
            row.insertCell().textContent = totalScore;

            addStep5DebugMessage("SavingThrowsPopulation", `Processed ${fullAbilityName}`, {
                baseScore, modifier, isProficient, classProfSavingThrows, currentProficiencyBonus, totalScore, rawProfBonus: proficiencyBonusValue
            });
        });
        addStep5DebugMessage("loadStep5Logic", "Saving throws table populated.");
    }

    // --- SKILLS ---
    const skillsTableBody = document.getElementById('skills-table')?.querySelector('tbody');
    if (!skillsTableBody) {
        addStep5DebugMessage("loadStep5Logic", "Skills table body not found.", {error: true});
        console.error("Skills table body not found!");
    } else {
        skillsTableBody.innerHTML = ''; // Clear existing rows
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


                const isOverallProficient = proficientByRace || proficientByClass || proficientByBackground;
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

                    if (this.checked) {
                        // If it wasn't in the list before, and we are at the limit, prevent checking.
                        if (!extraSkillsBeforeChange.includes(currentSkillName) && currentSelectedCount >= currentAllowedSkillChoices) {
                            addStep5DebugMessage("SkillCheckboxChange", `Attempted to select ${currentSkillName}, but limit (${currentAllowedSkillChoices}) reached.`, { currentSelectedCount });
                            this.checked = false; // Revert checkbox state
                            event.preventDefault(); // Prevent the default action
                            // Optionally, inform the user (e.g., alert or a status message)
                            // alert(`You cannot select more than ${currentAllowedSkillChoices} skill(s).`);
                        } else {
                            if (!extraSkillsBeforeChange.includes(currentSkillName)) {
                                characterCreationData.skill_proficiencies.extra.push(currentSkillName);
                                addStep5DebugMessage("SkillCheckboxChange", `Selected skill ${currentSkillName}.`, { extraSkills: characterCreationData.skill_proficiencies.extra });
                            }
                        }
                    } else {
                        // If unchecking, remove it from the list
                        if (extraSkillsBeforeChange.includes(currentSkillName)) {
                            characterCreationData.skill_proficiencies.extra = characterCreationData.skill_proficiencies.extra.filter(sk => sk !== currentSkillName);
                            addStep5DebugMessage("SkillCheckboxChange", `Deselected skill ${currentSkillName}.`, { extraSkills: characterCreationData.skill_proficiencies.extra });
                        }
                    }

                    // Update UI for skill choice count
                    const skillChoiceInfoEl = document.getElementById('skill-choice-info');
                    if (skillChoiceInfoEl) {
                        skillChoiceInfoEl.textContent = `You can choose ${currentAllowedSkillChoices} skill proficiencies. Selected: ${characterCreationData.skill_proficiencies.extra.length}.`;
                    }

                    updateSkillCheckboxStatesBasedOnLimit(); // Update all checkbox enable/disable states
                    renderStep5DebugInfo(); // Update general debug info
                });
                skillExtraProfCell.appendChild(skillExtraProfCheckbox);

                row.insertCell().textContent = isOverallProficient ? `Yes (+${proficiencyBonusValue})` : '';
                row.insertCell().textContent = totalScore;

                addStep5DebugMessage("SkillsPopulation", `Processed Skill: ${skillName}`, {
                    abilityAbbr, baseScore, modifier, proficientByRace,
                    proficientByClassDisplay: proficientByClass, // actual boolean used for decision
                    proficientByBackgroundDisplay: proficientByBackground, // actual boolean used for decision
                    isOverallProficient, chosenSkillProficiencies,
                    currentProficiencyBonus, totalScore
                });
            }
        }
        addStep5DebugMessage("loadStep5Logic", "Skills table populated.");
    }

    updateSkillCheckboxStatesBasedOnLimit(); // Initial call to set checkbox states based on loaded data and limits

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
