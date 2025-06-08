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

                // List of descriptive phrases to ignore
                const descriptivePhrases = [
                    "you start with the following equipment",
                    "in addition to the equipment granted by your background",
                    "includes:",
                    // Add more phrases as needed
                ];

                // Helper function to parse quantity from item strings
                function parseQuantityAndName(text) {
                    const quantityWords = {
                        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10
                        // Add more if common, e.g., "a dozen"
                    };
                    const parts = text.trim().split(/\s+/);
                    let quantity = 1;
                    let name = text;

                    if (parts.length > 1) {
                        const firstPart = parts[0].toLowerCase();
                        if (!isNaN(parseInt(firstPart))) { // Check for digit quantity "20 arrows"
                            quantity = parseInt(firstPart);
                            name = parts.slice(1).join(" ");
                        } else if (quantityWords[firstPart]) { // Check for word quantity "four javelins"
                            quantity = quantityWords[firstPart];
                            name = parts.slice(1).join(" ");
                        }
                    }
                    // Return name and quantity. For now, format as "name (xQuantity)" if quantity > 1
                    return quantity > 1 ? `${name} (x${quantity})` : name;
                }


                function cleanAndCategorizeText(text, source, isExplicitEquipment = false, isEquipmentChoice = false) {
                    if (!text || typeof text !== 'string') return;

                    let originalText = text; // Keep original for adding to categorizedItems if needed

                    // Parse quantity and name first
                    let textToCategorize = parseQuantityAndName(originalText);
                    // Use the (potentially) quantity-modified text for subsequent operations
                    // but keep originalText for adding to lists if you want the original formatting.
                    // For now, we'll use textToCategorize for everything.

                    let cleanedTextForApiMatch = textToCategorize.toLowerCase().trim();

                    // Check if the text is a descriptive phrase
                    // Use cleanedTextForApiMatch for this check as it's already lowercased and trimmed.
                    for (const phrase of descriptivePhrases) {
                        if (cleanedTextForApiMatch.startsWith(phrase.toLowerCase())) {
                            console.log(`Skipping descriptive phrase: ${textToCategorize}`);
                            return; // Skip this text
                        }
                    }
                    let categorized = false;

                    // 1. Check against API-fetched weapons (using minimally cleaned text)
                    // We use cleanedTextForApiMatch here which has quantity already processed
                    for (const weapon of lowerAvailableWeapons) {
                        // Ensure the weapon name itself is present, not just as part of " (x4)"
                        if (cleanedTextForApiMatch.includes(weapon) && cleanedTextForApiMatch.split(" (x")[0].includes(weapon)) {
                            if (!categorizedItems.weapons.includes(textToCategorize)) categorizedItems.weapons.push(textToCategorize);
                            categorized = true;
                            break;
                        }
                    }
                    if (categorized) return;

                    // 2. Check against API-fetched armor (using minimally cleaned text)
                    for (const armor of lowerAvailableArmor) {
                        // Similar check for armor
                        if ((cleanedTextForApiMatch.includes(armor) && cleanedTextForApiMatch.split(" (x")[0].includes(armor)) ||
                            (armor === "shield" && cleanedTextForApiMatch.includes("shield"))) { // Shield doesn't usually have quantity
                             if (!categorizedItems.armor.includes(textToCategorize)) categorizedItems.armor.push(textToCategorize);
                            categorized = true;
                            break;
                        }
                    }
                    if (categorized) return;

                    // If not matched with specific API items, then try more aggressive cleaning for proficiencies/keywords
                    // Use the potentially quantity-modified text for proficiency checks as well
                    let cleanedTextForProficiency = cleanedTextForApiMatch;
                    cleanedTextForProficiency = cleanedTextForProficiency.replace(/^proficiency with\s*/, '');
                    // The following replacements are for broad categories like "light armor", "simple weapons"
                    // Be careful if item names could end with "armor" or "weapons"
                    let textForKeywordSearch = cleanedTextForProficiency; // This now includes (xN) if present
                    let tempCleanedForProficiency = cleanedTextForProficiency.replace(/\s*\(x\d+\)$/, ''); // Remove (xN) for proficiency matching
                    tempCleanedForProficiency = tempCleanedForProficiency.replace(/\s*armor$/, '');
                    tempCleanedForProficiency = tempCleanedForProficiency.replace(/\s*weapons$/, '');

                    // Handle specific named proficiencies like "Elf Weapon Training"
                    // We use originalText here if we want to capture the full description.
                    // Or use textToCategorize if it has useful modifications (like quantity, though unlikely for profs).
                    // Let's use originalText for now to get the full description.
                    if (originalText.toLowerCase().includes("elf weapon training")) {
                        if (!categorizedItems.proficiencies.includes(originalText)) {
                            categorizedItems.proficiencies.push(originalText + " (Proficiency)");
                        }
                        categorized = true;
                        // If this is *only* a proficiency and not also equipment, we can return.
                        if (!isExplicitEquipment) return;
                    }
                    // Add similar checks for other specific proficiencies if needed

                    // Specific proficiency checks (e.g. "all simple weapons", "light armor")
                    // If it's an equipment choice, we delay these general proficiency checks.
                    if (!categorized && !isEquipmentChoice) {
                        if (tempCleanedForProficiency.includes("all simple") || tempCleanedForProficiency.includes("simple weapon")) {
                            if (!categorizedItems.proficiencies.includes(textToCategorize)) categorizedItems.proficiencies.push(textToCategorize + " (Proficiency)");
                            categorized = true;
                        }
                        else if (tempCleanedForProficiency.includes("all martial") || tempCleanedForProficiency.includes("martial weapon")) {
                            if (!categorizedItems.proficiencies.includes(textToCategorize)) categorizedItems.proficiencies.push(textToCategorize + " (Proficiency)");
                            categorized = true;
                        }
                        else if (tempCleanedForProficiency.includes("light") || tempCleanedForProficiency.includes("medium") || tempCleanedForProficiency.includes("heavy") || tempCleanedForProficiency.includes("all armor") || tempCleanedForProficiency.includes("shields")) {
                             if (!categorizedItems.proficiencies.includes(textToCategorize)) categorizedItems.proficiencies.push(textToCategorize + " (Proficiency)");
                            categorized = true;
                        }
                    }

                    // If it's identified as a general proficiency and NOT an explicit piece of equipment,
                    // AND it's not an equipment choice (which should try to be categorized as an item first),
                    // then we can often return early.
                    if (categorized && !isExplicitEquipment && !isEquipmentChoice) return;
                    // If it IS an equipment choice and already categorized as weapon/armor, we can also return.
                    if (isEquipmentChoice && categorized && (categorizedItems.weapons.includes(textToCategorize) || categorizedItems.armor.includes(textToCategorize)) ) return;


                    // 3. Check for Tools
                    if (!categorized) {
                        for (const toolKeyword of toolKeywords) {
                            if (textForKeywordSearch.includes(toolKeyword)) {
                                if (!categorizedItems.tools.includes(textToCategorize)) categorizedItems.tools.push(textToCategorize);
                                categorized = true;
                                break;
                            }
                        }
                    }
                    // If an equipment choice is categorized as a tool, we can return.
                    if (isEquipmentChoice && categorized && categorizedItems.tools.includes(textToCategorize)) return;


                    // 4. Check for General Items
                    if (!categorized) {
                        for (const itemKeyword of generalItemKeywords) {
                            if (textForKeywordSearch.includes(itemKeyword)) {
                                if (!categorizedItems.general_items.includes(textToCategorize)) categorizedItems.general_items.push(textToCategorize);
                                categorized = true;
                                break;
                            }
                        }
                    }
                    // If an equipment choice is categorized as a general item, we can return.
                    if (isEquipmentChoice && categorized && categorizedItems.general_items.includes(textToCategorize)) return;

                    // 5. General proficiency checks for equipment choices (if not already categorized as an item)
                    // This is where choices like "(b) any simple weapon" get classified as proficiency if they weren't matched as a specific weapon.
                    if (isEquipmentChoice && !categorized) {
                        if (tempCleanedForProficiency.includes("all simple") || tempCleanedForProficiency.includes("simple weapon")) {
                            if (!categorizedItems.proficiencies.includes(textToCategorize)) categorizedItems.proficiencies.push(textToCategorize + " (Proficiency from Choice)");
                            categorized = true;
                        }
                        else if (tempCleanedForProficiency.includes("all martial") || tempCleanedForProficiency.includes("martial weapon")) {
                            if (!categorizedItems.proficiencies.includes(textToCategorize)) categorizedItems.proficiencies.push(textToCategorize + " (Proficiency from Choice)");
                            categorized = true;
                        }
                        else if (tempCleanedForProficiency.includes("light") || tempCleanedForProficiency.includes("medium") || tempCleanedForProficiency.includes("heavy") || tempCleanedForProficiency.includes("all armor") || tempCleanedForProficiency.includes("shields")) {
                             if (!categorizedItems.proficiencies.includes(textToCategorize)) categorizedItems.proficiencies.push(textToCategorize + " (Proficiency from Choice)");
                            categorized = true;
                        }
                    }
                    if (categorized && isEquipmentChoice) return; // Done with equipment choice if it became a proficiency

                    // 6. Fallback for items that are explicit equipment but not categorized yet
                    // OR if it's an equipment choice and still not categorized (should be rare by now).
                    if (!categorized && (isExplicitEquipment || isEquipmentChoice)) {
                         if (!categorizedItems.general_items.includes(textToCategorize) &&
                             !categorizedItems.weapons.includes(textToCategorize) &&
                             !categorizedItems.armor.includes(textToCategorize) &&
                             !categorizedItems.tools.includes(textToCategorize) &&
                             !categorizedItems.proficiencies.some(p => p.startsWith(textToCategorize))) { // Avoid double adding if already a prof.
                            const suffix = isEquipmentChoice ? " (Uncategorized from Choice)" : " (Uncategorized Equipment)";
                            categorizedItems.general_items.push(textToCategorize + suffix);
                         }
                    }
                }

                function processMultipleItemsText(text, source, isExplicitEquipment = false) {
                    if (!text || typeof text !== 'string') return;
                    // Split by common delimiters like comma, "and", or newline.
                    const items = text.split(/,\s*(?:and\s)?|\s+and\s+|\n/).map(item => item.trim()).filter(item => item);
                    items.forEach(item => {
                        // Basic preposition/article removal - can be expanded
                        // This removal should happen BEFORE quantity parsing, as "a" or "an" can be part of item names after quantity.
                        // However, parseQuantityAndName handles "one", "two" etc.
                        // Let's adjust where this cleaning happens.
                        // For now, parseQuantityAndName is called first in cleanAndCategorizeText.
                        // The "a ", "an " removal in processMultipleItemsText might be redundant or misplaced if parseQuantityAndName is robust.
                        // Let's test current flow.

                        // The primary role of this loop is to split multi-item strings.
                        // The actual cleaning and categorization happens in cleanAndCategorizeText.
                        // No need to call parseQuantityAndName or extensive cleaning here.

                        // Check for item choices before general categorization
                        if (parseItemChoices(item, source, isExplicitEquipment)) { // Pass 'item' directly
                            return; // Item choices handled, no further processing needed for this line
                        }
                        cleanAndCategorizeText(item, source, isExplicitEquipment); // Pass 'item' directly
                    });
                }

                // Helper function to parse item choices like "(a)... or (b)..."
                function parseItemChoices(text, source, isExplicitEquipment = false) {
                    const choicePattern = /\((?:[a-z]|[ivx]+)\)\s*([^()]+?)(?:\s+or\s+\((?:[a-z]|[ivx]+)\)\s*([^()]+))?\.?/gi;
                    let match;
                    let choicesFound = false;
                    while ((match = choicePattern.exec(text)) !== null) {
                        choicesFound = true;
                        // Extract the main part of choice (e.g., "a greataxe", "any martial melee weapon")
                        // Match[1] is the first option, match[2] is the second (if present)
                        const option1 = match[1]?.trim();
                        const option2 = match[2]?.trim();

                        if (option1) {
                            // Prefix with "(Choice)" to indicate its origin, but categorize the item itself
                            // cleanAndCategorizeText will handle the actual categorization
                            // Pass true for isEquipmentChoice, and also inherit isExplicitEquipment
                            cleanAndCategorizeText(option1, source + "_choice1", isExplicitEquipment, true);
                        }
                        if (option2) {
                            cleanAndCategorizeText(option2, source + "_choice2", isExplicitEquipment, true);
                        }
                    }
                    return choicesFound; // Return true if choices were processed
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
