let step6DebugTextsCollection = [];

// Function to add a debug message for Step 6
function addStep6DebugMessage(source, message, details = {}) {
    if (typeof IS_CHARACTER_CREATION_DEBUG_ACTIVE !== 'undefined' && IS_CHARACTER_CREATION_DEBUG_ACTIVE) {
        step6DebugTextsCollection.push({
            timestamp: new Date().toISOString(),
            source: source,
            message: message,
            details: details
        });
    }
}

// Function to render all debug information collected for Step 6
function renderStep6DebugInfo() {
    const debugOutputEl = document.getElementById('step6-debug-output');
    if (debugOutputEl && typeof IS_CHARACTER_CREATION_DEBUG_ACTIVE !== 'undefined' && IS_CHARACTER_CREATION_DEBUG_ACTIVE) {
        let focusedDebugData = {
            selected_race: characterCreationData.step1_race_selection || 'Not Selected',
            selected_class: characterCreationData.step2_selected_base_class || 'Not Selected',
            ability_scores: characterCreationData.ability_scores || {},
            calculated_combat_stats: characterCreationData.step6_combat_stats || {}
        };

        let formattedDebugText = `Focused Character Data for Step 6 Calculations:
${JSON.stringify(focusedDebugData, null, 2)}

Step 6 Processing Log:
`;
        step6DebugTextsCollection.forEach(item => {
            formattedDebugText += `Timestamp: ${item.timestamp}
Source: ${item.source}
Message: ${item.message}
Details: ${JSON.stringify(item.details, null, 2)}
------------------------------------
`;
        });
        debugOutputEl.textContent = formattedDebugText;
    }
}

// Helper function to get ability modifier
function getAbilityModifier(score) {
    if (typeof score !== 'number' || isNaN(score)) {
        addStep6DebugMessage("getAbilityModifier", "Invalid score provided, defaulting to 0 modifier.", { score });
        return 0;
    }
    return Math.floor((score - 10) / 2);
}

// Main function to load logic for Step 6
function loadStep6Logic() {
    console.log("Loading Step 6 Logic...");
    addStep6DebugMessage("loadStep6Logic", "Starting Step 6 processing.");
    step6DebugTextsCollection = []; // Reset debug messages for this step load

    if (!characterCreationData.step6_combat_stats) {
        characterCreationData.step6_combat_stats = {};
        addStep6DebugMessage("loadStep6Logic", "Initialized step6_combat_stats.", characterCreationData.step6_combat_stats);
    }

    // Retrieve data from previous steps
    const raceData = characterCreationData.step1_race_selection;
    addStep6DebugMessage("loadStep6Logic", "Retrieved race data.", { raceData });

    const classData = characterCreationData.step2_selected_base_class;
    addStep6DebugMessage("loadStep6Logic", "Retrieved class data.", { classData });

    const abilityScores = characterCreationData.ability_scores;
    addStep6DebugMessage("loadStep6Logic", "Retrieved ability scores.", { abilityScores });

    // --- HP Calculation ---
    let hitDieValue = 6; // Default hit die
    if (classData && classData.hit_die && typeof classData.hit_die === 'number') {
        hitDieValue = classData.hit_die;
        addStep6DebugMessage("HP Calculation", "Using class hit die.", { hitDieValue });
    } else {
        addStep6DebugMessage("HP Calculation", "Class data or hit_die not found or invalid, defaulting hit die to 6.", { classData });
    }

    let conScore = 10; // Default CON score
    if (abilityScores && typeof abilityScores.CON === 'number') {
        conScore = abilityScores.CON;
        addStep6DebugMessage("HP Calculation", "Using CON score from ability scores.", { conScore });
    } else {
        addStep6DebugMessage("HP Calculation", "CON score not found in ability scores, defaulting to 10.", { abilityScores });
    }
    const conModifier = getAbilityModifier(conScore);
    const calculatedHp = hitDieValue + conModifier;
    characterCreationData.step6_combat_stats.hp = calculatedHp;
    document.getElementById('hp-value').textContent = calculatedHp;
    addStep6DebugMessage("HP Calculation", "HP calculated and stored.", { hitDieValue, conScore, conModifier, calculatedHp });

    // --- Hit Dice Calculation ---
    // hitDieValue is already determined from HP calculation
    const hitDiceType = 'd' + hitDieValue;
    const hitDiceCount = 1; // For level 1
    characterCreationData.step6_combat_stats.hit_dice_type = hitDiceType;
    characterCreationData.step6_combat_stats.hit_dice_count = hitDiceCount;
    document.getElementById('hit-dice-value').textContent = `${hitDiceCount}${hitDiceType}`;
    addStep6DebugMessage("Hit Dice Calculation", "Hit Dice calculated and stored.", { hitDiceCount, hitDiceType });

    // --- AC Calculation ---
    let dexScoreAC = 10; // Default DEX score for AC
    if (abilityScores && typeof abilityScores.DEX === 'number') {
        dexScoreAC = abilityScores.DEX;
        addStep6DebugMessage("AC Calculation", "Using DEX score from ability scores.", { dexScoreAC });
    } else {
        addStep6DebugMessage("AC Calculation", "DEX score not found in ability scores, defaulting to 10 for AC.", { abilityScores });
    }
    const dexModifierAC = getAbilityModifier(dexScoreAC);
    const calculatedAc = 10 + dexModifierAC; // Base AC, no armor
    characterCreationData.step6_combat_stats.ac = calculatedAc;
    document.getElementById('ac-value').textContent = calculatedAc;
    addStep6DebugMessage("AC Calculation", "AC calculated and stored.", { dexScoreAC, dexModifierAC, calculatedAc });

    // --- Speed Calculation ---
    let calculatedSpeed = 30; // Default speed
    if (raceData && raceData.speed) {
        if (typeof raceData.speed === 'number') {
            calculatedSpeed = raceData.speed;
            addStep6DebugMessage("Speed Calculation", "Using race speed (numeric).", { calculatedSpeed });
        } else if (raceData.speed.walk && typeof raceData.speed.walk === 'number') {
            calculatedSpeed = raceData.speed.walk;
            addStep6DebugMessage("Speed Calculation", "Using race walk speed from object.", { calculatedSpeed });
        } else {
            addStep6DebugMessage("Speed Calculation", "Race speed format not recognized, defaulting to 30.", { speedData: raceData.speed });
        }
    } else {
        addStep6DebugMessage("Speed Calculation", "Race data or speed not found, defaulting speed to 30.", { raceData });
    }
    characterCreationData.step6_combat_stats.speed = calculatedSpeed;
    document.getElementById('speed-value').textContent = calculatedSpeed;
    addStep6DebugMessage("Speed Calculation", "Speed calculated and stored.", { calculatedSpeed });

    // --- Initiative Calculation ---
    // dexModifierAC is already calculated for AC
    const calculatedInitiative = dexModifierAC;
    characterCreationData.step6_combat_stats.initiative = calculatedInitiative;
    document.getElementById('initiative-value').textContent = calculatedInitiative >= 0 ? `+${calculatedInitiative}` : calculatedInitiative.toString();
    addStep6DebugMessage("Initiative Calculation", "Initiative calculated and stored.", { dexModifier: dexModifierAC, calculatedInitiative });

    // Save data and render debug info
    if (typeof saveCharacterDataToSession === 'function') {
        saveCharacterDataToSession();
        addStep6DebugMessage("loadStep6Logic", "Character data saved to session.");
    } else {
        addStep6DebugMessage("loadStep6Logic", "Error: saveCharacterDataToSession function not found.", {}, "error");
        console.error("Error: saveCharacterDataToSession function not found.");
    }

    renderStep6DebugInfo();
    console.log("Step 6 Logic Loaded. Final Data:", characterCreationData);
    addStep6DebugMessage("loadStep6Logic", "Step 6 processing finished.", { finalData: characterCreationData.step6_combat_stats });
}

// Ensure loadStep6Logic is called when the script is loaded, assuming DOM is ready
// or it's called by the main character creation script after HTML is loaded.
// For now, it will rely on being called externally.
// Example: if (document.readyState === 'loading') {
// document.addEventListener('DOMContentLoaded', loadStep6Logic);
// } else {
// loadStep6Logic();
// }
// This should be called by the main navigation logic when this step becomes active.
