// Define standard D&D 5e skills and their associated abilities
const SKILL_DEFINITIONS = {
    "Acrobatics": "Dexterity",
    "Animal Handling": "Wisdom",
    "Arcana": "Intelligence",
    "Athletics": "Strength",
    "Deception": "Charisma",
    "History": "Intelligence",
    "Insight": "Wisdom",
    "Intimidation": "Charisma",
    "Investigation": "Intelligence",
    "Medicine": "Wisdom",
    "Nature": "Intelligence",
    "Perception": "Wisdom",
    "Performance": "Charisma",
    "Persuasion": "Charisma",
    "Religion": "Intelligence",
    "Sleight of Hand": "Dexterity",
    "Stealth": "Dexterity",
    "Survival": "Wisdom"
};

// Define standard D&D 5e saving throws
const SAVING_THROW_DEFINITIONS = [
    "Strength", "Dexterity", "Constitution", "Intelligence", "Wisdom", "Charisma"
];

// Helper function to calculate ability modifier
function getAbilityModifier(score) {
    if (typeof score !== 'number' || isNaN(score)) return 0;
    return Math.floor((score - 10) / 2);
}

// Global variable to store chosen skills for this step
let chosen_skills_for_step5 = new Set();
let number_of_allowed_skill_choices = 0;

function loadStep5Logic() {
    console.log("Step 5 JS loaded: Skills & Proficiencies");

    // Ensure character_data exists and initialize proficiencies if not present
    window.character_data = window.character_data || {};
    window.character_data.ability_scores = window.character_data.ability_scores || {
        Strength: 10, Dexterity: 10, Constitution: 10, Intelligence: 10, Wisdom: 10, Charisma: 10
    };
    window.character_data.class_data = window.character_data.class_data || {
        name: "Fighter", // Default for testing
        saving_throw_proficiencies: ["Strength", "Constitution"],
        proficiencies: [], // e.g., "Armor", "Weapons" - not skills directly from here usually
        skill_choices: { // This structure is an assumption, adjust based on actual class data
            choose: 0,
            from: []
        }
    };
    window.character_data.race_data = window.character_data.race_data || {
        name: "Human", // Default for testing
        proficiencies: []
    };
    window.character_data.background_data = window.character_data.background_data || {
        name: "Soldier", // Default for testing
        proficiencies: ["Athletics", "Intimidation"]
    };
    window.character_data.proficiency_bonus = window.character_data.proficiency_bonus || 2;

    // Initialize/clear step-specific chosen skills and overall character proficiencies for skills
    chosen_skills_for_step5 = new Set();
    // This will store ALL skill proficiencies (race, class, background, choice)
    window.character_data.skill_proficiencies = window.character_data.skill_proficiencies || [];

    const ability_scores = window.character_data.ability_scores;
    const class_data = window.character_data.class_data;
    const race_data = window.character_data.race_data;
    const background_data = window.character_data.background_data;
    const proficiency_bonus = window.character_data.proficiency_bonus;

    // Determine number of allowed skill choices (e.g., from class)
    // This needs to be derived from actual class data structure
    number_of_allowed_skill_choices = class_data.skill_choices ? class_data.skill_choices.choose : 0;
    // If background also grants choices, this logic would need to be expanded.
    // For now, assuming choices primarily come from class.

    populateSavingThrowsTable(ability_scores, class_data.saving_throw_proficiencies || [], proficiency_bonus);
    populateSkillsTable(ability_scores, class_data, race_data, background_data, proficiency_bonus);
    updateSkillChoiceInfo(); // Initial update
    // Persist initial proficiencies from race, class (if any direct), background
    persistInitialProficiencies();

    // Display Skills & Proficiencies Debug Texts if active
    if (typeof IS_CHARACTER_CREATION_DEBUG_ACTIVE !== 'undefined' && IS_CHARACTER_CREATION_DEBUG_ACTIVE) {
        const debugContainer = document.getElementById('skills-proficiencies-debug-container');
        const debugOutputEl = document.getElementById('skills-proficiencies-debug-output');

        if (debugContainer && debugOutputEl) {
            debugContainer.style.display = 'block';
            let debugTexts = "Debug Data for Skills & Proficiencies:\n";
            debugTexts += "=======================================\n\n";

            const ccData = window.character_data || {}; // Use character_data as per step5.js context

            debugTexts += "Race Data Related:\n";
            // In step5.js, race data is usually under window.character_data.race_data
            // However, characterCreationData structure might place it under step1_race_selection
            // Let's try to access it from common locations within window.character_data
            const raceDataSource = ccData.step1_race_selection || ccData.race_data || {};
            debugTexts += "  Race: " + (raceDataSource.name || 'Unknown Race') + "\n";
            if (raceDataSource.proficiencies && raceDataSource.proficiencies.length > 0) {
                debugTexts += "  Proficiencies Granted by Race (from .proficiencies list):\n";
                raceDataSource.proficiencies.forEach(prof => {
                    debugTexts += "    - " + (typeof prof === 'string' ? prof : JSON.stringify(prof)) + "\n";
                });
            } else {
                debugTexts += "  No specific proficiencies listed under race_data.proficiencies.\n";
            }
            const raceTraits = raceDataSource.traits || [];
            if (raceTraits.length > 0) {
                 debugTexts += "  Race Traits (text implying skills/proficiencies):\n";
                 let foundRelevantTrait = false;
                 raceTraits.forEach(trait => {
                    if (trait.name && trait.desc && (trait.desc.toLowerCase().includes('skill') || trait.desc.toLowerCase().includes('proficien'))) {
                        debugTexts += "    - Trait: " + trait.name + ": " + trait.desc + "\n";
                        foundRelevantTrait = true;
                    }
                 });
                 if (!foundRelevantTrait) {
                    debugTexts += "    No traits found with descriptions explicitly mentioning 'skill' or 'proficien'.\n";
                 }
            } else {
                debugTexts += "  No traits listed for the race.\n";
            }
            debugTexts += "\n";

            debugTexts += "Class Data Related:\n";
            const classDataSource = ccData.step2_selected_base_class || ccData.class_data || {};
            debugTexts += "  Class: " + (classDataSource.name || 'Unknown Class') + "\n";

            // Fixed proficiencies directly from class
            const classFixedProficiencies = (classDataSource.proficiencies || []).filter(p => SKILL_DEFINITIONS[p]); // Filter for actual skills
            if (classFixedProficiencies && classFixedProficiencies.length > 0) {
                debugTexts += "  Fixed Skill Proficiencies Granted by Class (from .proficiencies list that are skills):\n";
                classFixedProficiencies.forEach(prof => {
                    debugTexts += "    - " + (typeof prof === 'string' ? prof : JSON.stringify(prof)) + "\n";
                });
            } else {
                debugTexts += "  No fixed SKILL proficiencies listed under class_data.proficiencies.\n";
            }

            // Other proficiencies (armor, weapons, tools) from class_data.proficiencies
            const otherClassProficiencies = (classDataSource.proficiencies || []).filter(p => !SKILL_DEFINITIONS[p]);
             if (otherClassProficiencies && otherClassProficiencies.length > 0) {
                debugTexts += "  Other Proficiencies (Armor, Weapons, Tools) from Class:\n";
                otherClassProficiencies.forEach(prof => {
                    debugTexts += "    - " + (typeof prof === 'string' ? prof : JSON.stringify(prof)) + "\n";
                });
            }

            const skillChoicesSource = classDataSource.skill_choices || (classDataSource.data ? classDataSource.data.skill_choices : null);
            if (skillChoicesSource) {
                debugTexts += "  Skill Choices from Class:\n";
                debugTexts += "    Choose: " + (skillChoicesSource.choose !== undefined ? skillChoicesSource.choose : 'N/A') + "\n";
                debugTexts += "    From: [" + (skillChoicesSource.from || []).join(", ") + "]\n";
                if (skillChoicesSource.desc) { // If there's a description for the choice block
                     debugTexts += "    Choice Description: " + skillChoicesSource.desc + "\n";
                }
            } else {
                debugTexts += "  No skill_choices section found for the class.\n";
            }

            const savingThrowsSource = classDataSource.saving_throw_proficiencies || (classDataSource.data ? classDataSource.data.saving_throw_proficiencies : []);
            if (savingThrowsSource && savingThrowsSource.length > 0) {
                debugTexts += "  Saving Throw Proficiencies: [" + savingThrowsSource.join(", ") + "]\n";
            } else {
                debugTexts += "  No saving throw proficiencies listed for the class.\n";
            }

            const archetypeDataSource = ccData.step2_selected_archetype || {};
            if (archetypeDataSource.name) {
                debugTexts += "  Archetype: " + (archetypeDataSource.name || 'Unknown Archetype') + "\n";
                const archetypeFixedProficiencies = (archetypeDataSource.proficiencies || []).filter(p => SKILL_DEFINITIONS[p]);
                if (archetypeFixedProficiencies && archetypeFixedProficiencies.length > 0) {
                    debugTexts += "  Fixed Skill Proficiencies Granted by Archetype:\n";
                    archetypeFixedProficiencies.forEach(prof => {
                        debugTexts += "    - " + (typeof prof === 'string' ? prof : JSON.stringify(prof)) + "\n";
                    });
                }
                const otherArchetypeProficiencies = (archetypeDataSource.proficiencies || []).filter(p => !SKILL_DEFINITIONS[p]);
                if (otherArchetypeProficiencies && otherArchetypeProficiencies.length > 0) {
                    debugTexts += "  Other Proficiencies (Armor, Weapons, Tools) from Archetype:\n";
                    otherArchetypeProficiencies.forEach(prof => {
                        debugTexts += "    - " + (typeof prof === 'string' ? prof : JSON.stringify(prof)) + "\n";
                    });
                }
                const archetypeTraits = archetypeDataSource.traits || [];
                if (archetypeTraits.length > 0) {
                    debugTexts += "  Archetype Traits (text implying skills/proficiencies):\n";
                    let foundRelevantArchetypeTrait = false;
                    archetypeTraits.forEach(trait => {
                        if (trait.name && trait.desc && (trait.desc.toLowerCase().includes('skill') || trait.desc.toLowerCase().includes('proficien'))) {
                            debugTexts += "    - Trait: " + trait.name + ": " + trait.desc + "\n";
                            foundRelevantArchetypeTrait = true;
                        }
                    });
                    if (!foundRelevantArchetypeTrait) {
                        debugTexts += "    No archetype traits found with descriptions explicitly mentioning 'skill' or 'proficien'.\n";
                    }
                }
            }
            debugTexts += "\n";

            debugTexts += "Background Data Related:\n";
            const backgroundDataSource = ccData.step3_background_selection || ccData.background_data || {};
            debugTexts += "  Background: " + (backgroundDataSource.name || 'Unknown Background') + "\n";

            const backgroundSkillProficiencies = (backgroundDataSource.proficiencies || []).filter(p => SKILL_DEFINITIONS[p]);
            if (backgroundSkillProficiencies && backgroundSkillProficiencies.length > 0) {
                debugTexts += "  Skill Proficiencies Granted by Background:\n";
                backgroundSkillProficiencies.forEach(prof => {
                    debugTexts += "    - " + (typeof prof === 'string' ? prof : JSON.stringify(prof)) + "\n";
                });
            } else {
                debugTexts += "  No SKILL proficiencies listed under background_data.proficiencies.\n";
            }
            const otherBackgroundProficiencies = (backgroundDataSource.proficiencies || []).filter(p => !SKILL_DEFINITIONS[p]);
            if (otherBackgroundProficiencies && otherBackgroundProficiencies.length > 0) {
                debugTexts += "  Other Proficiencies (Tools, Languages) from Background:\n";
                otherBackgroundProficiencies.forEach(prof => {
                    debugTexts += "    - " + (typeof prof === 'string' ? prof : JSON.stringify(prof)) + "\n";
                });
            }

            const backgroundDataContext = backgroundDataSource.data || backgroundDataSource;
            if (backgroundDataContext.desc) {
                debugTexts += "  Background Description (desc field): " + backgroundDataContext.desc + "\n";
            }
            if (backgroundDataContext.feature_name && backgroundDataContext.feature_desc) {
                debugTexts += "  Background Feature ("+ backgroundDataContext.feature_name +"): " + backgroundDataContext.feature_desc + "\n";
            }
            const backgroundBenefits = backgroundDataContext.benefits || [];
            if (backgroundBenefits.length > 0) {
                debugTexts += "  Background Benefits (text implying skills/proficiencies):\n";
                let foundRelevantBenefit = false;
                backgroundBenefits.forEach(benefit => {
                    if (benefit.name && benefit.desc && (benefit.desc.toLowerCase().includes('skill') || benefit.desc.toLowerCase().includes('proficien') || benefit.type === 'skill' || benefit.type === 'proficiency')) {
                        debugTexts += "    - Benefit: " + benefit.name + " (Type: " + (benefit.type || 'N/A') + "): " + benefit.desc + "\n";
                        foundRelevantBenefit = true;
                    }
                });
                if (!foundRelevantBenefit) {
                    debugTexts += "    No benefits found with descriptions/types explicitly mentioning skills or proficiencies.\n";
                }
            }
            debugTexts += "\n";

            debugTexts += "Current Character Skill Proficiencies (after all processing in Step 5, from window.character_data.skill_proficiencies):\n";
            if (ccData.skill_proficiencies && ccData.skill_proficiencies.length > 0) {
                 debugTexts += "  [" + ccData.skill_proficiencies.join(", ") + "]\n";
            } else {
                 debugTexts += "  None listed in window.character_data.skill_proficiencies.\n";
            }

            debugOutputEl.textContent = debugTexts;
        } else {
            if (!debugContainer) console.error("Debug container 'skills-proficiencies-debug-container' not found.");
            if (!debugOutputEl) console.error("Debug output element 'skills-proficiencies-debug-output' not found.");
        }
    }
}

function persistInitialProficiencies() {
    const tempProficiencies = new Set(window.character_data.skill_proficiencies);

    (window.character_data.race_data.proficiencies || []).forEach(skill => {
        if (SKILL_DEFINITIONS[skill]) tempProficiencies.add(skill);
    });
    // Direct class skill proficiencies (less common, usually choices)
    (window.character_data.class_data.proficiencies || []).forEach(p => {
         if (SKILL_DEFINITIONS[p]) tempProficiencies.add(p); // Check if it's actually a skill
    });
    (window.character_data.background_data.proficiencies || []).forEach(skill => {
        if (SKILL_DEFINITIONS[skill]) tempProficiencies.add(skill);
    });

    window.character_data.skill_proficiencies = Array.from(tempProficiencies);
    console.log("Initial skill_proficiencies:", window.character_data.skill_proficiencies);
}


function populateSavingThrowsTable(ability_scores, class_saving_throws, proficiency_bonus) {
    const tableBody = document.getElementById('saving-throws-table').getElementsByTagName('tbody')[0];
    if (!tableBody) {
        console.error("Saving throws table body not found!");
        return;
    }
    tableBody.innerHTML = '';

    SAVING_THROW_DEFINITIONS.forEach(ability => {
        const score = ability_scores[ability.toLowerCase()] || ability_scores[ability] || 10; // Handle potential case diffs
        const modifier = getAbilityModifier(score);
        const isProficient = class_saving_throws.map(s => s.toLowerCase()).includes(ability.toLowerCase());
        const proficiencyValue = isProficient ? proficiency_bonus : 0;
        const total = modifier + proficiencyValue;

        const row = tableBody.insertRow();
        row.insertCell().textContent = ability;
        row.insertCell().textContent = modifier >= 0 ? `+${modifier}` : modifier;
        const proficientCell = row.insertCell();
        const proficientCheckbox = document.createElement('input');
        proficientCheckbox.type = 'checkbox';
        proficientCheckbox.checked = isProficient;
        proficientCheckbox.disabled = true;
        proficientCell.appendChild(proficientCheckbox);
        row.insertCell().textContent = total >= 0 ? `+${total}` : total;
        // Store saving throw proficiencies in character_data (if not already there by class)
        // Ensure saving_throw_proficiencies is initialized
        window.character_data.saving_throw_proficiencies = window.character_data.saving_throw_proficiencies || [];
        if (isProficient) {
            if (!window.character_data.saving_throw_proficiencies.map(s => s.toLowerCase()).includes(ability.toLowerCase())) {
                window.character_data.saving_throw_proficiencies.push(ability);
            }
        }
    });
}

function populateSkillsTable(ability_scores, class_data, race_data, background_data, proficiency_bonus) {
    const tableBody = document.getElementById('skills-table').getElementsByTagName('tbody')[0];
    if (!tableBody) {
        console.error("Skills table body not found!");
        return;
    }
    tableBody.innerHTML = '';

    const available_choice_skills = new Set(class_data.skill_choices ? class_data.skill_choices.from.map(s => s.trim()) : []);

    // Pre-load chosen skills if character_data.skill_proficiencies already has choices
    // This helps maintain state if user navigates back and forth
    chosen_skills_for_step5.clear(); // Clear before repopulating from character_data
    (window.character_data.skill_proficiencies || []).forEach(skillName => {
        const isRaceProf = (race_data.proficiencies || []).includes(skillName);
        const isClassFixedProf = (class_data.proficiencies || []).filter(p => SKILL_DEFINITIONS[p]).includes(skillName);
        const isBackgroundProf = (background_data.proficiencies || []).includes(skillName);
        if (available_choice_skills.has(skillName) && !isRaceProf && !isClassFixedProf && !isBackgroundProf) {
            chosen_skills_for_step5.add(skillName);
        }
    });


    for (const [skill, ability] of Object.entries(SKILL_DEFINITIONS)) {
        const score = ability_scores[ability.toLowerCase()] || ability_scores[ability] || 10;
        const modifier = getAbilityModifier(score);

        const proficientByRace = (race_data.proficiencies || []).includes(skill);
        const proficientByClassFixed = (class_data.proficiencies || []).filter(p => SKILL_DEFINITIONS[p]).includes(skill);
        const proficientByBackground = (background_data.proficiencies || []).includes(skill);

        const row = tableBody.insertRow();
        row.dataset.skillName = skill; // Store skill name for easy access

        row.insertCell().textContent = skill;
        row.insertCell().textContent = ability;
        row.insertCell().textContent = modifier >= 0 ? `+${modifier}` : modifier;

        createReadOnlyCheckboxCell(row, proficientByRace);
        createReadOnlyCheckboxCell(row, proficientByClassFixed);
        createReadOnlyCheckboxCell(row, proficientByBackground);

        const choiceCell = row.insertCell();
        const choiceCheckbox = document.createElement('input');
        choiceCheckbox.type = 'checkbox';
        choiceCheckbox.dataset.skillName = skill;
        choiceCheckbox.checked = chosen_skills_for_step5.has(skill);

        const isAlreadyProficient = proficientByRace || proficientByClassFixed || proficientByBackground;
        if (isAlreadyProficient || !available_choice_skills.has(skill)) {
            choiceCheckbox.disabled = true;
            if (choiceCheckbox.checked && isAlreadyProficient) {
                // If it was checked as a choice but is now granted by fixed source, remove from chosen_skills
                chosen_skills_for_step5.delete(skill);
                choiceCheckbox.checked = false; // Ensure it's visually unchecked as a choice
            }
        } else {
            choiceCheckbox.disabled = false; // Will be re-evaluated by validateSkillChoices
            choiceCheckbox.addEventListener('change', handleSkillChoiceChange);
        }
        choiceCell.appendChild(choiceCheckbox);

        const totalCell = row.insertCell(); // Will be cell index 7
        updateSkillRowTotal(row, modifier, proficiency_bonus);
    }
    updateSkillChoiceInfo();
    validateSkillChoices();
    updateCharacterDataSkillProficiencies(); // Ensure character_data is up-to-date after initial population
}

function createReadOnlyCheckboxCell(row, isChecked) {
    const cell = row.insertCell();
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.checked = isChecked;
    checkbox.disabled = true;
    cell.appendChild(checkbox);
}

function handleSkillChoiceChange(event) {
    const checkbox = event.target;
    const skillName = checkbox.dataset.skillName;

    if (checkbox.checked) {
        if (chosen_skills_for_step5.size < number_of_allowed_skill_choices) {
            chosen_skills_for_step5.add(skillName);
        } else {
            checkbox.checked = false;
            alert(`You can only choose ${number_of_allowed_skill_choices} skill(s).`);
        }
    } else {
        chosen_skills_for_step5.delete(skillName);
    }

    updateSkillRowTotal(checkbox.closest('tr'), null, window.character_data.proficiency_bonus);
    updateSkillChoiceInfo();
    validateSkillChoices(); // Re-validate to enable/disable other checkboxes
    updateCharacterDataSkillProficiencies();
}

function validateSkillChoices() {
    const choiceCheckboxes = document.querySelectorAll('#skills-table tbody input[type="checkbox"][data-skill-name]');

    choiceCheckboxes.forEach(cb => {
        const skillName = cb.dataset.skillName;
        const row = cb.closest('tr');
        const isRaceProf = row.cells[3].firstChild.checked;
        const isClassFixedProf = row.cells[4].firstChild.checked;
        const isBgProf = row.cells[5].firstChild.checked;
        const isAlreadyProficient = isRaceProf || isClassFixedProf || isBgProf;
        const available_choice_skills = new Set(window.character_data.class_data.skill_choices ? window.character_data.class_data.skill_choices.from.map(s => s.trim()) : []);


        if (isAlreadyProficient || !available_choice_skills.has(skillName)) {
            cb.disabled = true;
            if (cb.checked) { // If checked but shouldn't be (e.g. now proficient via other means)
                cb.checked = false;
                chosen_skills_for_step5.delete(skillName);
            }
        } else {
            // Enable if not checked AND limit not reached, OR if it IS checked (to allow unchecking)
            if (!cb.checked && chosen_skills_for_step5.size >= number_of_allowed_skill_choices) {
                cb.disabled = true;
            } else {
                cb.disabled = false;
            }
        }
    });
    updateSkillChoiceInfo(); // Refresh info as it depends on chosen_skills_for_step5.size
}


function updateSkillRowTotal(row, modifier, proficiency_bonus) {
    const skillName = row.dataset.skillName;
    if (modifier === null) {
        const ability = SKILL_DEFINITIONS[skillName];
        const abilityKey = ability.toLowerCase();
        const score = window.character_data.ability_scores[abilityKey] || window.character_data.ability_scores[ability] || 10;
        modifier = getAbilityModifier(score);
    }

    const isRaceProf = row.cells[3].firstChild.checked;
    const isClassFixedProf = row.cells[4].firstChild.checked;
    const isBgProf = row.cells[5].firstChild.checked;
    const isChoiceProf = row.cells[6].firstChild.checked; // This is the choice checkbox itself

    const isProficient = isRaceProf || isClassFixedProf || isBgProf || isChoiceProf;
    const proficiencyValue = isProficient ? proficiency_bonus : 0;
    const total = modifier + proficiencyValue;
    row.cells[7].textContent = total >= 0 ? `+${total}` : total;
}

function updateSkillChoiceInfo() {
    const skillChoiceInfoDiv = document.getElementById('skill-choice-info');
    if (skillChoiceInfoDiv) {
        const remainingChoices = Math.max(0, number_of_allowed_skill_choices - chosen_skills_for_step5.size);
        if (number_of_allowed_skill_choices > 0) {
            skillChoiceInfoDiv.innerHTML = `Skill Choices: ${number_of_allowed_skill_choices} total. You have selected ${chosen_skills_for_step5.size}. Remaining: ${remainingChoices}.<br>`;
            if (window.character_data.class_data && window.character_data.class_data.skill_choices && window.character_data.class_data.skill_choices.from.length > 0) {
                 skillChoiceInfoDiv.innerHTML += ` Choose from: ${window.character_data.class_data.skill_choices.from.join(', ')}.`;
            } else {
                 skillChoiceInfoDiv.innerHTML += ` No specific list of skills to choose from was provided by the class data.`;
            }
        } else {
            skillChoiceInfoDiv.textContent = "No additional skill choices available from your class or background.";
        }
    }
}

function updateCharacterDataSkillProficiencies() {
    const finalProficiencies = new Set();
    (window.character_data.race_data.proficiencies || []).forEach(skill => {
        if (SKILL_DEFINITIONS[skill]) finalProficiencies.add(skill);
    });
    (window.character_data.class_data.proficiencies || []).forEach(p => {
         if (SKILL_DEFINITIONS[p]) finalProficiencies.add(p);
    });
    (window.character_data.background_data.proficiencies || []).forEach(skill => {
        if (SKILL_DEFINITIONS[skill]) finalProficiencies.add(skill);
    });
    chosen_skills_for_step5.forEach(skill => finalProficiencies.add(skill));

    window.character_data.skill_proficiencies = Array.from(finalProficiencies);
    // console.log("Updated character_data.skill_proficiencies:", window.character_data.skill_proficiencies);

    // Update the main character_data.proficiencies (general list)
    // This needs to be robust: remove old skills, add current ones, keep non-skill proficiencies.
    let otherProficiencies = (window.character_data.proficiencies || []).filter(p => !SKILL_DEFINITIONS[p] && !SAVING_THROW_DEFINITIONS.map(st => `${st} Saving Throw`).includes(p));

    let allProficiencies = new Set(otherProficiencies);

    (window.character_data.saving_throw_proficiencies || []).forEach(st => allProficiencies.add(`${st} Saving Throw`));
    window.character_data.skill_proficiencies.forEach(skill => allProficiencies.add(skill));

    window.character_data.proficiencies = Array.from(allProficiencies);
    // console.log("Updated character_data.proficiencies (combined):", window.character_data.proficiencies);
}
