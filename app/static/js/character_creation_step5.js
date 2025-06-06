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


function loadStep5Logic() {
    console.log("Step 5 JS loaded");
    step5DebugTextsCollection = []; // Clear debug messages for this run
    addStep5DebugMessage("loadStep5Logic", "Starting Step 5 logic execution.");

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
            row.insertCell().textContent = ''; // Was 'N/A' for Race
            row.insertCell().textContent = isProficient ? `Yes (+${proficiencyBonusValue})` : ''; // Was 'No' for Class
            row.insertCell().textContent = ''; // Was 'N/A' for Background
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
        const chosenSkillProficiencies = (characterCreationData.skill_proficiencies || []).map(s => s.toLowerCase());
        addStep5DebugMessage("SkillsPopulation", "User chosen skill proficiencies (lowercase).", {chosenSkillProficiencies});

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
                row.insertCell().textContent = proficientByBackground ? 'Yes' : ''; // Was 'No'

                row.insertCell().textContent = isOverallProficient ? `Yes (+${proficiencyBonusValue})` : ''; // Was 'No'
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
