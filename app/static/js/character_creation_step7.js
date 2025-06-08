// API Endpoints
const WEAPONS_API_URL = '/api/v2/weapons/';
const ARMOR_API_URL = '/api/v2/armor/';

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

// Function to fetch data from Open5e API
async function fetchOpen5eData(apiUrl) {
    let allItems = [];
    let nextUrl = apiUrl;

    while (nextUrl) {
        try {
            const response = await fetch(nextUrl);
            if (!response.ok) {
                throw new Error(`API request failed with status ${response.status}: ${response.statusText}`);
            }
            const data = await response.json();
            if (data.results && Array.isArray(data.results)) {
                data.results.forEach(item => {
                    if (item.name) {
                        allItems.push(item.name);
                    } else if (item.slug) {
                        console.warn(`Item from ${apiUrl} is missing a 'name', falling back to slug: '${item.slug}'. Full item:`, item);
                        allItems.push(item.slug);
                    } else {
                        console.warn(`Item from ${apiUrl} is missing both 'name' and 'slug'. Skipping item. Full item:`, item);
                    }
                });
            }
            nextUrl = data.next; // Get the next page URL
        } catch (error) {
            console.error(`Error fetching data from ${nextUrl}:`, error);
            nextUrl = null; // Stop pagination on error
            // Optionally, re-throw the error if you want Promise.all to fail
            // throw error;
        }
    }
    return allItems;
}

async function loadStep7Logic() {
    console.log("Step 7 JS loaded");

    // Ensure this global variable is set by the template
    // For example: <script>var isDebugModeEnabled = {{ config.CHARACTER_CREATION_DEBUG_MODE | tojson }};</script>
    // Default to false if not defined, though it should be.
    const debugModeEnabled = typeof isDebugModeEnabled !== 'undefined' ? isDebugModeEnabled : false;

    const debugDiv = document.getElementById('character-creation-debug-div');
    const debugDataPre = document.getElementById('character-creation-debug-data');

    let availableWeapons = [];
    let availableArmor = [];

    try {
        console.log("Fetching weapon and armor data from Open5E API...");
        const [weaponNames, armorNames] = await Promise.all([
            fetchOpen5eData(WEAPONS_API_URL),
            fetchOpen5eData(ARMOR_API_URL)
        ]);

        availableWeapons = weaponNames;
        availableArmor = armorNames;

        console.log(`Successfully fetched ${availableWeapons.length} weapons and ${availableArmor.length} armor items.`);
        // console.log("Fetched Weapons:", availableWeapons); // Optional: log fetched items
        // console.log("Fetched Armor:", availableArmor); // Optional: log fetched items

    } catch (error) {
        console.error("Failed to fetch data from Open5E API. Proceeding with empty lists.", error);
        // Allow the script to continue with empty lists, error is already logged by fetchOpen5eData
    }

    if (debugModeEnabled && debugDiv && debugDataPre) {
        try {
            const characterDataString = sessionStorage.getItem('characterCreationData');
            if (characterDataString) {
                const characterDataObject = JSON.parse(characterDataString);

                // --- Categorization Logic ---
                let categorizedItems = {
                    weapons: [],
                    armor: [],
                    tools: [],
                    general_items: [],
                    proficiencies: [] // For broad proficiencies like "all simple weapons"
                };

                const toolKeywords = ["kit", "tools", "artisan's tools", "thieves' tools", "disguise kit", "forgery kit", "herbalism kit", "navigator's tools", "poisoner's kit", "gaming set", "musical instrument"];
                const generalItemKeywords = ["pack", "pouch", "rope", "rations", "waterskin", "tinderbox", "crowbar", "hammer", "piton", "tent", "bedroll", "mess kit", "holy symbol", "spellbook", "component pouch", "scroll", "potion", "ammunition", "arrows", "bolts", "sling bullets"];
                // Old inventoryKeywords for broader check, might be less needed now
                // const inventoryKeywords = ["armor", "weapon", "shield", "tool", "pack", "equipment", "proficiency"];

                const lowerAvailableWeapons = availableWeapons.map(w => w.toLowerCase());
                const lowerAvailableArmor = availableArmor.map(a => a.toLowerCase());

                function cleanAndCategorizeText(text, source, isExplicitEquipment = false) {
                    if (!text || typeof text !== 'string') return;

                    let originalText = text; // Keep original for adding to categorizedItems if needed
                    let cleanedTextForApiMatch = text.toLowerCase().trim();
                    let categorized = false;

                    // 1. Check against API-fetched weapons (using minimally cleaned text)
                    for (const weapon of lowerAvailableWeapons) {
                        if (cleanedTextForApiMatch.includes(weapon)) {
                            if (!categorizedItems.weapons.includes(originalText)) categorizedItems.weapons.push(originalText);
                            categorized = true;
                            break;
                        }
                    }
                    if (categorized) return;

                    // 2. Check against API-fetched armor (using minimally cleaned text)
                    for (const armor of lowerAvailableArmor) {
                        // Special handling for "shield" as it's often listed with armor
                        if (cleanedTextForApiMatch.includes(armor) || (armor === "shield" && cleanedTextForApiMatch.includes("shield"))) {
                             if (!categorizedItems.armor.includes(originalText)) categorizedItems.armor.push(originalText);
                            categorized = true;
                            break;
                        }
                    }
                    if (categorized) return;

                    // If not matched with specific API items, then try more aggressive cleaning for proficiencies/keywords
                    let cleanedTextForProficiency = cleanedTextForApiMatch;
                    cleanedTextForProficiency = cleanedTextForProficiency.replace(/^proficiency with\s*/, '');
                    // The following replacements are for broad categories like "light armor", "simple weapons"
                    // Be careful if item names could end with "armor" or "weapons"
                    let textForKeywordSearch = cleanedTextForProficiency;
                    let tempCleanedForProficiency = cleanedTextForProficiency.replace(/\s*armor$/, '');
                    tempCleanedForProficiency = tempCleanedForProficiency.replace(/\s*weapons$/, '');


                    // Specific proficiency checks (e.g. "all simple weapons", "light armor")
                    if (tempCleanedForProficiency.includes("all simple") || tempCleanedForProficiency.includes("simple weapon")) {
                        if (!categorizedItems.proficiencies.includes(originalText)) categorizedItems.proficiencies.push(originalText + " (Proficiency)");
                        categorized = true;
                    }
                    else if (tempCleanedForProficiency.includes("all martial") || tempCleanedForProficiency.includes("martial weapon")) {
                        if (!categorizedItems.proficiencies.includes(originalText)) categorizedItems.proficiencies.push(originalText + " (Proficiency)");
                        categorized = true;
                    }
                    else if (tempCleanedForProficiency.includes("light") || tempCleanedForProficiency.includes("medium") || tempCleanedForProficiency.includes("heavy") || tempCleanedForProficiency.includes("all armor") || tempCleanedForProficiency.includes("shields")) {
                         if (!categorizedItems.proficiencies.includes(originalText)) categorizedItems.proficiencies.push(originalText + " (Proficiency)");
                        categorized = true;
                    }

                    // If it's identified as a general proficiency and NOT an explicit piece of equipment,
                    // then we can often return early. If it IS explicit equipment, it might also be a general item.
                    if (categorized && !isExplicitEquipment) return;


                    // 3. Check for Tools (using text that had "proficiency with" removed)
                    for (const toolKeyword of toolKeywords) {
                        if (textForKeywordSearch.includes(toolKeyword)) {
                            if (!categorizedItems.tools.includes(originalText)) categorizedItems.tools.push(originalText);
                            categorized = true;
                            break;
                        }
                    }
                    if (categorized) return;

                    // 4. Check for General Items (using text that had "proficiency with" removed)
                    for (const itemKeyword of generalItemKeywords) {
                        if (textForKeywordSearch.includes(itemKeyword)) {
                            if (!categorizedItems.general_items.includes(originalText)) categorizedItems.general_items.push(originalText);
                            categorized = true;
                            break;
                        }
                    }
                    if (categorized) return;

                    // 5. Fallback for items that are explicit equipment but not categorized yet
                    if (isExplicitEquipment && !categorizedItems.general_items.includes(originalText) &&
                        !categorizedItems.weapons.includes(originalText) &&
                        !categorizedItems.armor.includes(originalText) &&
                        !categorizedItems.tools.includes(originalText)) {
                         categorizedItems.general_items.push(originalText + " (Uncategorized Equipment)");
                    }
                    // Note: General proficiencies not matching keywords are not added to a fallback category
                    // to avoid noise, unless they were explicit equipment.
                }

                function processMultipleItemsText(text, source, isExplicitEquipment = false) {
                    if (!text || typeof text !== 'string') return;
                    // Split by common delimiters like comma, "and", or newline.
                    // Handles "item1, item2 and item3"
                    // Also handles lists like "20 arrows" - "20 arrows" will be processed as one item.
                    // Further splitting of quantities from item names (e.g. "20 arrows" -> "arrows") can be a future enhancement.
                    const items = text.split(/,\s*(?:and\s)?|\s+and\s+|\n/).map(item => item.trim()).filter(item => item);
                    items.forEach(item => {
                        // Basic preposition/article removal - can be expanded
                        let cleanedItem = item.replace(/^(a|an|one|two|some)\s+/i, '');
                        cleanAndCategorizeText(cleanedItem, source, isExplicitEquipment);
                    });
                }


                // Access race data
                const raceData = characterDataObject.step1_race_selection;
                if (raceData) {
                    processMultipleItemsText(getTextFromPath(raceData, 'starting_proficiencies.armor'), "race_prof_armor");
                    processMultipleItemsText(getTextFromPath(raceData, 'starting_proficiencies.weapons'), "race_prof_weapons");
                    processMultipleItemsText(getTextFromPath(raceData, 'starting_proficiencies.tools'), "race_prof_tools");

                    const traits = raceData.traits;
                    if (Array.isArray(traits)) {
                        traits.forEach(trait => {
                            const traitDesc = getTextFromPath(trait, 'desc');
                            // Process trait descriptions carefully, don't mark as explicit equipment
                            processMultipleItemsText(traitDesc, "trait_desc");
                        });
                    }
                     // Process general race description for keywords if other fields yielded little
                    // processMultipleItemsText(getTextFromPath(raceData, 'desc'), "race_desc");
                }

                // Access class data
                const classData = characterDataObject.step2_selected_base_class;
                if (classData) {
                    processMultipleItemsText(getTextFromPath(classData, 'equipment'), "class_equipment", true); // Explicit equipment
                    processMultipleItemsText(getTextFromPath(classData, 'prof_armor'), "class_prof_armor");
                    processMultipleItemsText(getTextFromPath(classData, 'prof_weapons'), "class_prof_weapons");
                    processMultipleItemsText(getTextFromPath(classData, 'prof_tools'), "class_prof_tools");
                }

                // Access archetype data
                const archetypeData = characterDataObject.step2_selected_archetype;
                if (archetypeData) {
                    const archetypeDesc = getTextFromPath(archetypeData, 'desc');
                    if (archetypeDesc) {
                        const lines = archetypeDesc.split('\n');
                        lines.forEach(line => {
                             // Process archetype features carefully
                            processMultipleItemsText(line, "archetype_desc");
                        });
                    }
                }

                // Access background data
                const backgroundSelection = characterDataObject.step3_background_selection;
                if (backgroundSelection) {
                    const benefits = backgroundSelection.benefits;
                    if (Array.isArray(benefits)) {
                        benefits.forEach(benefit => {
                            const benefitType = getTextFromPath(benefit, 'type').toLowerCase();
                            const benefitDesc = getTextFromPath(benefit, 'desc');
                            if (benefitType === 'equipment') {
                                processMultipleItemsText(benefitDesc, "background_equipment", true); // Explicit equipment
                            } else {
                                processMultipleItemsText(benefitDesc, "background_benefit");
                            }
                        });
                    }
                }

                // --- Debug Output Update ---
                let debugContent = "";
                if (availableWeapons.length > 0) {
                    debugContent += `--- Fetched Weapons (${availableWeapons.length}) ---\n${availableWeapons.join(', ')}\n\n`;
                }
                if (availableArmor.length > 0) {
                    debugContent += `--- Fetched Armor (${availableArmor.length}) ---\n${availableArmor.join(', ')}\n\n`;
                }

                // Format categorized items for display
                debugContent += "--- CATEGORIZED ITEMS ---\n";
                const categoryOrder = ["weapons", "armor", "tools", "general_items", "proficiencies"];
                const categoryTitles = {
                    weapons: "WEAPONS",
                    armor: "ARMOR",
                    tools: "TOOLS",
                    general_items: "GENERAL ITEMS",
                    proficiencies: "PROFICIENCIES & OTHER"
                };

                for (const category of categoryOrder) {
                    debugContent += `--- ${categoryTitles[category]} ---\n`;
                    if (categorizedItems[category] && categorizedItems[category].length > 0) {
                        categorizedItems[category].forEach(item => {
                            debugContent += `- ${item}\n`;
                        });
                    } else {
                        debugContent += "(None found)\n";
                    }
                    debugContent += "\n"; // Add a blank line after each category
                }

                debugContent += "--- FULL RAW DATA ---\n\n" + JSON.stringify(characterDataObject, null, 2);
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
