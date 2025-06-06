// Test file: tests/test_character_creation_step5.js
console.log("Executing test_character_creation_step5.js");

// --- Minimal Mocks & Stubs for dependencies of loadStep5Logic ---
const SKILL_LIST = {
    'Acrobatics': 'DEX', 'Animal Handling': 'WIS', 'Arcana': 'INT', 'Athletics': 'STR',
    'Deception': 'CHA', 'History': 'INT', 'Insight': 'WIS', 'Intimidation': 'CHA',
    'Investigation': 'INT', 'Medicine': 'WIS', 'Nature': 'INT', 'Perception': 'WIS',
    'Performance': 'CHA', 'Persuasion': 'CHA', 'Religion': 'INT', 'Sleight of Hand': 'DEX',
    'Stealth': 'DEX', 'Survival': 'WIS', 'Culture': 'INT' // Added Culture for Test Case 1
};
const ABILITY_SCORES_ORDER = ['STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA']; // Mocked
const ABILITY_SCORE_FULL_NAMES = { STR: 'Strength', DEX: 'Dexterity', CON: 'Constitution', INT: 'Intelligence', WIS: 'Wisdom', CHA: 'Charisma' }; // Mocked


let step5DebugTextsCollection = []; // Used by addStep5DebugMessage
// const IS_CHARACTER_CREATION_DEBUG_ACTIVE = false; // Default state, runStep5Test will toggle

function addStep5DebugMessage(source, message, details = {}) {
    if (typeof globalThis.IS_CHARACTER_CREATION_DEBUG_ACTIVE !== 'undefined' && globalThis.IS_CHARACTER_CREATION_DEBUG_ACTIVE) {
        step5DebugTextsCollection.push({ source, message, details: JSON.parse(JSON.stringify(details)) }); // Deep copy details
    }
}

function updateSkillChoiceInfoText() { /* console.log("Mock: updateSkillChoiceInfoText called"); */ }
function updateSkillCheckboxStatesBasedOnLimit() { /* console.log("Mock: updateSkillCheckboxStatesBasedOnLimit called"); */ }
function renderStep5DebugInfo() { /* console.log("Mock: renderStep5DebugInfo called"); */ }
function getAbilityModifier(score) { return Math.floor((score - 10) / 2); }
function checkStringForSkillProficiency(text, skillName) { return text.toLowerCase().includes(skillName.toLowerCase());}

let characterCreationData = {};

let testsPassed = 0;
let testsFailed = 0;

function runStep5Test(description, mockData, expectedChoices) {
    console.log(`\n--- Running Test: ${description} ---`);
    step5DebugTextsCollection = [];
    const originalDebugActiveState = typeof globalThis.IS_CHARACTER_CREATION_DEBUG_ACTIVE !== 'undefined' ? globalThis.IS_CHARACTER_CREATION_DEBUG_ACTIVE : false;
    globalThis.IS_CHARACTER_CREATION_DEBUG_ACTIVE = true;

    characterCreationData = JSON.parse(JSON.stringify(mockData));

    if (!characterCreationData.skill_proficiencies) characterCreationData.skill_proficiencies = { base: [], extra: [] };
    if (!characterCreationData.skill_proficiencies.extra) characterCreationData.skill_proficiencies.extra = [];
    if (!characterCreationData.step5_info) characterCreationData.step5_info = {};
    if (!characterCreationData.proficiency_bonus) characterCreationData.proficiency_bonus = 2;

    document.body.innerHTML = `
        <div id="step5-debug-output"></div> <div id="skill-choice-info"></div>
        <table id="saving-throws-table"><tbody></tbody></table> <table id="skills-table"><tbody></tbody></table>`;

    console.log("Initial allowedSkillChoices state (before loadStep5Logic): (Handled internally by loadStep5Logic, starts at 0)");

    loadStep5Logic();

    console.log("--- Detailed Log Trace from loadStep5Logic for this Test ---");
    step5DebugTextsCollection.forEach(log => {
        // Log messages relevant to allowedSkillChoices calculation
        if (log.message.includes("prof_skills") ||
            log.message.includes("proficiency_choices") ||
            log.message.includes("Incrementing allowedSkillChoices") ||
            log.message.includes("Allowed skill choices from class") ||
            log.message.includes("Added ") && log.message.includes("skill choice(s) from background benefit") ||
            log.message.includes("Final total allowed skill choices")) {
            console.log(`  ${log.source}: ${log.message} (Details: ${JSON.stringify(log.details)})`);
        }
    });
    console.log("--- End of Detailed Log Trace ---");

    const actualChoices = characterCreationData.step5_info.allowed_skill_choices;
    if (actualChoices === expectedChoices) {
        console.log(`PASS: Expected ${expectedChoices}, Got ${actualChoices}`);
        testsPassed++;
    } else {
        console.error(`FAIL: Expected ${expectedChoices}, Got ${actualChoices}`);
        testsFailed++;
    }
    globalThis.IS_CHARACTER_CREATION_DEBUG_ACTIVE = originalDebugActiveState;
}

// --- Test Cases ---

// Test Case 1 (Issue Data - Updated for prof_skills)
runStep5Test(
    "Test Case 1: Class from prof_skills ('Choose two'), Background grants 1 choice.",
    {
        step2_selected_base_class: {
            name: "Test Class from Issue",
            prof_skills: "Choose two from Animal Handling, Athletics, Intimidation, Nature, Perception, and Survival",
            proficiency_choices: [] // Explicitly empty to ensure prof_skills is used
        },
        step3_background_selection: {
            name: "Test Background",
            benefits: [
                { desc: "Performance, and either Acrobatics, Culture, or Persuasion.", type: "skill_proficiency" },
                { desc: "Tool Proficiency: Lute", type: "tool_proficiency"}
            ]
        },
        ability_scores: { STR: 10, DEX: 10, CON: 10, INT: 10, WIS: 10, CHA: 10 }
    },
    3 // 2 from class (prof_skills) + 1 from background
);

// Test Case 2 (Class Only - Simple - Updated for prof_skills)
runStep5Test(
    "Test Case 2: Class prof_skills ('Choose one'), no background choices.",
    {
        step2_selected_base_class: {
            name: "Class B",
            prof_skills: "Choose one from Athletics, History",
            proficiency_choices: [] // Ensure prof_skills is primary
        },
        step3_background_selection: { benefits: [] },
        ability_scores: { STR: 10, DEX: 10, CON: 10, INT: 10, WIS: 10, CHA: 10 }
    },
    1
);

// Test Case 3 (Background Only - Simple Choice) - No change needed, class part is empty
runStep5Test(
    "Test Case 3: Background proficiency only (Choose one from three).",
    {
        step2_selected_base_class: { name: "NoClassChoices", prof_skills: "", proficiency_choices: [] },
        step3_background_selection: {
            benefits: [ { desc: "Choose one from Insight, Medicine, or Religion.", type: "skill_proficiency" } ]
        },
        ability_scores: { STR: 10, DEX: 10, CON: 10, INT: 10, WIS: 10, CHA: 10 }
    },
    1
);

// Test Case 4 (Background Only - "Two of your choice") - No change needed
runStep5Test(
    "Test Case 4: Background proficiency 'Two of your choice'.",
    {
        step2_selected_base_class: { name: "NoClassChoicesAgain", prof_skills: null, proficiency_choices: [] },
        step3_background_selection: {
            benefits: [ { desc: "Two of your choice", type: "skill_proficiency" } ]
        },
        ability_scores: { STR: 10, DEX: 10, CON: 10, INT: 10, WIS: 10, CHA: 10 }
    },
    2
);

// Test Case 5 (Class and Background - Updated for prof_skills)
runStep5Test(
    "Test Case 5: Class prof_skills ('Choose two') and background (Choose one).",
    {
        step2_selected_base_class: {
            name: "Class C",
            prof_skills: "Choose two from Acrobatics, Stealth, Perception",
            proficiency_choices: []
        },
        step3_background_selection: {
            benefits: [ { desc: "Choose one from History, Arcana.", type: "skill_proficiency" } ]
        },
        ability_scores: { STR: 10, DEX: 10, CON: 10, INT: 10, WIS: 10, CHA: 10 }
    },
    3 // 2 from class (prof_skills) + 1 from background
);

// Test Case 6 (Complex Background - Fixed and Choice) - No change needed
runStep5Test(
    "Test Case 6: Complex background (Fixed skill and a choice).",
    {
        step2_selected_base_class: { prof_skills: "", proficiency_choices: [] },
        step3_background_selection: {
            benefits: [ { desc: "Stealth, and either Acrobatics or Deception.", type: "skill_proficiency" } ]
        },
        ability_scores: { STR: 10, DEX: 10, CON: 10, INT: 10, WIS: 10, CHA: 10 }
    },
    1
);

// Test Case 7 (No Choices Offered - Updated for prof_skills)
runStep5Test(
    "Test Case 7: No choices from class (prof_skills fixed) or background (fixed).",
    {
        step2_selected_base_class: {
            name: "FixedClass",
            prof_skills: "Athletics, Intimidation", // Fixed skills, no "Choose..."
            proficiency_choices: []
        },
        step3_background_selection: {
            benefits: [
                { desc: "Proficiency in History.", type: "skill_proficiency" },
                { desc: "Proficiency in Investigation.", type: "skill_proficiency" }
            ]
        },
        ability_scores: { STR: 10, DEX: 10, CON: 10, INT: 10, WIS: 10, CHA: 10 }
    },
    0
);

// Test Case 8 (Class Only - Multiple Choice Groups from proficiency_choices - Fallback Test)
runStep5Test(
    "Test Case 8: Class prof_skills empty, fallback to multiple proficiency_choices groups.",
    {
        step2_selected_base_class: {
            name: "FallbackClass",
            prof_skills: "This class offers skills as detailed below.", // Non-choice text
            proficiency_choices: [
                { desc: "Choose one from A, B", choose_from: { count: 1, options: [{ item: { name: "Acrobatics" } }, { item: { name: "Athletics" } }] } },
                { desc: "Choose one from C, D", choose_from: { count: 1, options: [{ item: { name: "History" } }, { item: { name: "Arcana" } }] } }
            ]
        },
        step3_background_selection: { benefits: [] },
        ability_scores: { STR: 10, DEX: 10, CON: 10, INT: 10, WIS: 10, CHA: 10 }
    },
    2 // 1 from first group + 1 from second group in proficiency_choices
);

// Test Case 9 (Background - "Choose two skills") - No change needed
runStep5Test(
    "Test Case 9: Background 'Choose two skills'.",
    {
        step2_selected_base_class: { prof_skills: "", proficiency_choices: [] },
        step3_background_selection: {
            benefits: [ { desc: "Choose two skills", type: "skill_proficiency" } ]
        },
        ability_scores: { STR: 10, DEX: 10, CON: 10, INT: 10, WIS: 10, CHA: 10 }
    },
    2
);

// Test Case 10 (Background - "Choose any one skill") - No change needed
runStep5Test(
    "Test Case 10: Background 'Choose any one skill'.",
    {
        step2_selected_base_class: { prof_skills: "", proficiency_choices: [] },
        step3_background_selection: {
            benefits: [ { desc: "Choose any one skill", type: "skill_proficiency" } ]
        },
        ability_scores: { STR: 10, DEX: 10, CON: 10, INT: 10, WIS: 10, CHA: 10 }
    },
    1
);

// Test Case 11 (New - Fallback Logic Test)
runStep5Test(
    "Test Case 11: Class prof_skills fixed, fallback to proficiency_choices (Choose one).",
    {
        step2_selected_base_class: {
            name: "FallbackTestClass",
            prof_skills: "Some fixed skills like Athletics, Stealth.", // No "Choose..." pattern
            proficiency_choices: [
                { desc: "Choose one from Arcana, History", choose_from: { count: 1, options: [{item: {name: "Arcana"}}, {item: {name: "History"}}] } }
            ]
        },
        step3_background_selection: { benefits: [] },
        ability_scores: { STR: 10, DEX: 10, CON: 10, INT: 10, WIS: 10, CHA: 10 }
    },
    1 // 1 from proficiency_choices after prof_skills provides no choices
);


// --- Summary ---
console.log("\n--- Test Summary ---");
console.log(`Total Tests: ${testsPassed + testsFailed}`);
console.log(`Passed: ${testsPassed}`);
console.log(`Failed: ${testsFailed}`);

if (testsFailed === 0) {
    console.log("All tests passed!");
} else {
    console.warn(`${testsFailed} test(s) failed.`);
}

// To run these tests:
// 1. Ensure `character_creation_step5.js` is loaded in the same HTML page before this script.
// 2. Open the browser's developer console to see the output.
