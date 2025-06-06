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
