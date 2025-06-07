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

                // --- Inventory Text Extraction Logic ---
                const inventoryTexts = [];
                const inventoryKeywords = ["armor", "weapon", "shield", "tool", "pack", "equipment", "proficiency"];

                // Access race data
                const raceData = characterDataObject.step1_race_selection;
                if (raceData) {
                    let raceTextFound = false;
                    let text = getTextFromPath(raceData, 'starting_proficiencies.armor');
                    if (text) { inventoryTexts.push(`Race Starting Proficiency: ${text}`); raceTextFound = true; }

                    text = getTextFromPath(raceData, 'starting_proficiencies.weapons');
                    if (text) { inventoryTexts.push(`Race Starting Proficiency: ${text}`); raceTextFound = true; }

                    text = getTextFromPath(raceData, 'starting_proficiencies.tools');
                    if (text) { inventoryTexts.push(`Race Starting Proficiency: ${text}`); raceTextFound = true; }

                    const traits = raceData.traits;
                    if (Array.isArray(traits)) {
                        traits.forEach(trait => {
                            const traitName = getTextFromPath(trait, 'name').toLowerCase();
                            const traitDesc = getTextFromPath(trait, 'desc').toLowerCase();
                            let traitHasKeyword = false;

                            if (traitDesc) {
                                for (const keyword of inventoryKeywords) {
                                    if (traitName.includes(keyword) || traitDesc.includes(keyword)) {
                                        traitHasKeyword = true;
                                        break;
                                    }
                                }
                                if (traitHasKeyword) {
                                    inventoryTexts.push(`Race Trait (${getTextFromPath(trait, 'name', 'N/A')}): ${getTextFromPath(trait, 'desc')}`);
                                }
                            }
                        });
                    }

                    if (!raceTextFound && inventoryTexts.filter(t => t.startsWith("Race Trait")).length === 0) {
                        text = getTextFromPath(raceData, 'asi_description');
                        if (text) { inventoryTexts.push(`Race Info: ${text}`); raceTextFound = true; }

                        text = getTextFromPath(raceData, 'desc');
                        if (text && !raceTextFound) { inventoryTexts.push(`Race Info: ${text}`);}
                    }
                }

                // Access class data
                const classData = characterDataObject.step2_selected_base_class;
                if (classData) {
                    let text = getTextFromPath(classData, 'equipment');
                    if (text) { inventoryTexts.push(`Class Equipment: ${text}`); }

                    text = getTextFromPath(classData, 'prof_armor');
                    if (text) { inventoryTexts.push(`Class Armor Proficiencies: ${text}`); }

                    text = getTextFromPath(classData, 'prof_weapons');
                    if (text) { inventoryTexts.push(`Class Weapon Proficiencies: ${text}`); }

                    text = getTextFromPath(classData, 'prof_tools');
                    if (text) { inventoryTexts.push(`Class Tool Proficiencies: ${text}`); }
                }

                // Access archetype data
                const archetypeData = characterDataObject.step2_selected_archetype;
                if (archetypeData) {
                    const archetypeDesc = getTextFromPath(archetypeData, 'desc');
                    if (archetypeDesc) {
                        const lines = archetypeDesc.split('\n');
                        let currentFeatureName = null;

                        for (const line of lines) {
                            const trimmedLine = line.trim();
                            if (!trimmedLine) {
                                continue;
                            }

                            const featureMatch = trimmedLine.match(/^(?:#+\s*)(.+)/);
                            if (featureMatch && featureMatch[1]) {
                                currentFeatureName = featureMatch[1].trim();
                            }

                            const lowerLine = trimmedLine.toLowerCase();
                            let keywordFoundInLine = false;
                            for (const keyword of inventoryKeywords) {
                                if (lowerLine.includes(keyword)) {
                                    keywordFoundInLine = true;
                                    break;
                                }
                            }

                            if (keywordFoundInLine) {
                                if (currentFeatureName) {
                                    if (trimmedLine !== currentFeatureName && !trimmedLine.startsWith("#")) {
                                       inventoryTexts.push(`Archetype Feature (${currentFeatureName}): ${trimmedLine}`);
                                    } else if (trimmedLine === currentFeatureName) {
                                       inventoryTexts.push(`Archetype Feature (${currentFeatureName}): ${trimmedLine}`);
                                    } else if (!trimmedLine.startsWith("#")) {
                                       inventoryTexts.push(`Archetype Feature: ${trimmedLine}`);
                                    }
                                } else {
                                    inventoryTexts.push(`Archetype Feature: ${trimmedLine}`);
                                }
                            }
                        }
                    }
                }

                // Access background data
                const backgroundSelection = characterDataObject.step3_background_selection;
                if (backgroundSelection) {
                    const benefits = backgroundSelection.benefits;
                    if (Array.isArray(benefits)) {
                        benefits.forEach(benefit => {
                            const benefitType = getTextFromPath(benefit, 'type').toLowerCase();
                            const benefitName = getTextFromPath(benefit, 'name', 'Details');
                            const benefitDesc = getTextFromPath(benefit, 'desc');

                            if (benefitDesc) {
                                if (benefitType === 'equipment') {
                                    inventoryTexts.push(`Background Equipment (${benefitName}): ${benefitDesc}`);
                                } else {
                                    const lowerDesc = benefitDesc.toLowerCase();
                                    let keywordFound = false;
                                    for (const keyword of inventoryKeywords) {
                                        if (lowerDesc.includes(keyword)) {
                                            keywordFound = true;
                                            break;
                                        }
                                    }
                                    if (keywordFound) {
                                        inventoryTexts.push(`Background Benefit (${benefitName}): ${benefitDesc}`);
                                    }
                                }
                            }
                        });
                    }
                }

                // Finalize extracted inventory information for display
                let extractedInventoryInfo;
                if (inventoryTexts.length === 0) {
                    extractedInventoryInfo = "--- No specific inventory info extracted from Race, Class, Archetype, or Background ---";
                } else {
                    extractedInventoryInfo = inventoryTexts.join('\n');
                }

                console.log("--- Extracted Inventory Info For Debug Display ---");
                console.log(extractedInventoryInfo);

                // Update debug div content
                let debugContent = "--- Extracted Inventory Info ---\n" + extractedInventoryInfo + "\n\n";
                debugContent += "--- Full Data ---\n\n" + JSON.stringify(characterDataObject, null, 2);
                debugDataPre.textContent = debugContent;
                debugDiv.style.display = 'block';

            } else {
                debugDataPre.textContent = 'characterCreationData not found in session storage.';
                debugDiv.style.display = 'block';
            }
        } catch (error) {
            console.error('Error processing character creation debug data:', error);
            debugDataPre.textContent = 'Error loading debug data. Check console for details.';
            debugDiv.style.display = 'block';
        }
    } else if (debugDiv) {
        debugDiv.style.display = 'none';
    }
}

// ... (rest of the script remains the same)
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
