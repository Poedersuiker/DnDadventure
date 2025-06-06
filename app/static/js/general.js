function saveCharacterDataToSession() {
    try {
        sessionStorage.setItem('characterCreationData', JSON.stringify(characterCreationData));
        console.log("Character data saved to session storage.");
    } catch (e) {
        console.error("Error saving character data to session storage:", e);
    }
}

function getSlugFromUrl(url) {
    if (!url || typeof url !== 'string') return null;
    // Example: "/api/v2/races/human/" -> "human"
    // Handles potential trailing slashes as well
    const parts = url.split('/').filter(part => part.length > 0);
    return parts.pop() || null; // Returns the last significant part
}

function parseWordToNumber(word) {
    const map = { "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6 };
    if (typeof word === 'string') {
        const lowerWord = word.toLowerCase();
        if (map[lowerWord] !== undefined) return map[lowerWord];
    }
    const num = parseInt(word);
    return isNaN(num) ? 0 : num;
}

function parseAbilityList(str, abilityScoreMap) {
    const abilities = [];
    if (typeof str !== 'string') return abilities;
    // Split by comma, "or", "and", and trim parts
    const parts = str.split(/,\s*|\s+or\s+|\s+and\s+/i);
    parts.forEach(part => {
        const cleanPart = part.trim().toLowerCase();
        if (abilityScoreMap[cleanPart]) {
            abilities.push(abilityScoreMap[cleanPart]);
        }
    });
    return [...new Set(abilities)]; // Return unique abilities
}

function generate4d6DropLowest() {
    let abilityScores = [];
    for (let i = 0; i < 6; i++) {
        let rolls = [];
        for (let j = 0; j < 4; j++) {
            rolls.push(Math.floor(Math.random() * 6) + 1);
        }
        rolls.sort((a, b) => a - b); // Sort in ascending order
        rolls.shift(); // Remove the lowest die
        abilityScores.push(rolls.reduce((sum, val) => sum + val, 0));
    }
    console.log("Generated 4d6 drop lowest scores:", abilityScores);
    return abilityScores;
}

const GLOBAL_ABILITY_SCORE_MAP = {
    "strength": "STR", "dexterity": "DEX", "constitution": "CON",
    "intelligence": "INT", "wisdom": "WIS", "charisma": "CHA",
    "str": "STR", "dex": "DEX", "con": "CON",
    "int": "INT", "wis": "WIS", "cha": "CHA"
};
