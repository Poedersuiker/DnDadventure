// Helper function to safely extract text from nested properties
function getTextFromPath(obj, path, defaultValue = '') {
    const keys = path.split('.');
    let current = obj;
    for (const key of keys) {
        if (current && typeof current === 'object' && key in current) {
            current = current[key];
        } else {
            return defaultValue;
        }
    }
    return typeof current === 'string' ? current : defaultValue;
}

function loadStep7Logic() {
    console.log("Step 7 JS loaded");

    // Ensure this global variable is set by the template
    // For example: <script>var isDebugModeEnabled = {{ config.CHARACTER_CREATION_DEBUG_MODE | tojson }};</script>
    // Default to false if not defined, though it should be.
    const debugModeEnabled = typeof isDebugModeEnabled !== 'undefined' ? isDebugModeEnabled : false;

    const debugDiv = document.getElementById('character-creation-debug-div');
    const debugDataPre = document.getElementById('character-creation-debug-data');

    if (debugModeEnabled && debugDiv && debugDataPre) {
        try {
            const characterDataString = sessionStorage.getItem('characterCreationData');
            if (characterDataString) {
                const characterDataObject = JSON.parse(characterDataString);
                // debugDataPre.textContent = JSON.stringify(characterDataObject, null, 2); // Will be set later
                // debugDiv.style.display = 'block'; // Will be set after content is ready

                // --- Inventory Text Extraction Logic ---
                const inventoryTexts = [];

                // Access race data
                const raceData = characterDataObject.step1_race_selection;
                if (raceData) {
                    let raceTextFound = false;
                    let text = getTextFromPath(raceData, 'starting_proficiencies.armor');
                    if (text) { inventoryTexts.push(`Race: ${text}`); raceTextFound = true; }

                    text = getTextFromPath(raceData, 'starting_proficiencies.weapons');
                    if (text) { inventoryTexts.push(`Race: ${text}`); raceTextFound = true; }

                    text = getTextFromPath(raceData, 'starting_proficiencies.tools');
                    if (text) { inventoryTexts.push(`Race: ${text}`); raceTextFound = true; }

                    text = getTextFromPath(raceData, 'asi_description');
                    if (text && !raceTextFound) { inventoryTexts.push(`Race: ${text}`); raceTextFound = true; }

                    text = getTextFromPath(raceData, 'desc');
                    if (text && !raceTextFound) { inventoryTexts.push(`Race: ${text}`);}
                }

                // Access class data
                const classData = characterDataObject.step2_selected_base_class;
                if (classData) {
                    let classTextFound = false;
                    let text = getTextFromPath(classData, 'starting_equipment.full_text');
                    if (text) { inventoryTexts.push(`Class: ${text}`); classTextFound = true; }

                    text = getTextFromPath(classData, 'starting_equipment.options_text');
                    if (text) { inventoryTexts.push(`Class: ${text}`); classTextFound = true; }

                    text = getTextFromPath(classData, 'proficiencies_text');
                    if (text) { inventoryTexts.push(`Class: ${text}`); classTextFound = true; }

                    text = getTextFromPath(classData, 'desc');
                    if (text && !classTextFound) { inventoryTexts.push(`Class: ${text}`); }
                }

                // Access archetype data
                const archetypeData = characterDataObject.step2_selected_archetype;
                if (archetypeData) {
                    let archetypeTextFound = false;
                    // Assuming similar properties for archetypes, adjust as needed
                    let text = getTextFromPath(archetypeData, 'starting_equipment.full_text');
                    if (text) { inventoryTexts.push(`Archetype: ${text}`); archetypeTextFound = true; }

                    text = getTextFromPath(archetypeData, 'proficiencies_text'); // e.g. Artificer Specialist tool proficiency
                    if (text) { inventoryTexts.push(`Archetype: ${text}`); archetypeTextFound = true; }

                    text = getTextFromPath(archetypeData, 'feature_description'); // Generic feature text
                    if (text) { inventoryTexts.push(`Archetype: ${text}`); archetypeTextFound = true; }

                    text = getTextFromPath(archetypeData, 'desc');
                    if (text && !archetypeTextFound) { inventoryTexts.push(`Archetype: ${text}`); }
                }

                // Access background data
                const backgroundData = characterDataObject.step3_background_selection;
                if (backgroundData) {
                    let backgroundTextFound = false;
                    let text = getTextFromPath(backgroundData, 'equipment_text');
                    if (text) { inventoryTexts.push(`Background: ${text}`); backgroundTextFound = true; }

                    text = getTextFromPath(backgroundData, 'tool_proficiencies_text');
                    if (text) { inventoryTexts.push(`Background: ${text}`); backgroundTextFound = true; }

                    text = getTextFromPath(backgroundData, 'tools_text');
                    if (text) { inventoryTexts.push(`Background: ${text}`); backgroundTextFound = true; }

                    text = getTextFromPath(backgroundData, 'feature_description');
                    if (text) { inventoryTexts.push(`Background: ${text}`); backgroundTextFound = true; }

                    text = getTextFromPath(backgroundData, 'desc');
                    if (text && !backgroundTextFound) { inventoryTexts.push(`Background: ${text}`); }
                }

                const extractedInventoryInfo = inventoryTexts.join('\n');
                console.log("--- Extracted Inventory Info ---");
                console.log(extractedInventoryInfo);

                // Update debug div content
                let debugContent = "";
                if (extractedInventoryInfo) {
                    debugContent += "--- Extracted Inventory Info ---\n" + extractedInventoryInfo + "\n\n";
                } else {
                    debugContent += "--- No Inventory Info Extracted ---\n\n";
                }
                debugContent += "--- Full Data ---\n\n" + JSON.stringify(characterDataObject, null, 2);
                debugDataPre.textContent = debugContent;
                debugDiv.style.display = 'block';

            } else {
                debugDataPre.textContent = 'characterCreationData not found in session storage.';
                debugDiv.style.display = 'block'; // Show div to indicate missing data
            }
        } catch (error) {
            console.error('Error processing character creation debug data:', error);
            debugDataPre.textContent = 'Error loading debug data. Check console for details.';
            debugDiv.style.display = 'block'; // Show div to indicate error
        }
    } else if (debugDiv) {
        debugDiv.style.display = 'none';
    }
}

// Since the character creation steps are loaded dynamically,
// ensure loadStep7Logic is called when the step becomes active.
// This might be handled by a central navigation script.
// If this script is loaded specifically for step 7 (e.g. via a script tag in step7_equipment.html),
// then calling it directly might be appropriate.
// For now, assuming it's called correctly by the existing infrastructure.
// If characterCreationData might not be immediately available, consider using DOMContentLoaded or similar.
// However, sessionStorage should be available immediately.

// If this script is loaded *after* the DOM is ready (e.g. end of body in step7_equipment.html)
// then it can be called directly.
// Otherwise, wrap it in an event listener:
// document.addEventListener('DOMContentLoaded', loadStep7Logic);
// For now, let's assume it's called by the existing character creation script runner.
