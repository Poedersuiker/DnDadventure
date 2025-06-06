let currentStep = 0; // Start at Step 0 (Introduction)
    const totalSteps = 9; // Last actual step number for choices

    // Global variables for character creation
    let allClassesData = null; // Added for Step 2
    // let allBackgroundsData = null; // Moved to character_creation_step3.js
    let characterCreationData;
    try {
        const storedData = sessionStorage.getItem('characterCreationData');
        if (storedData) {
            characterCreationData = JSON.parse(storedData);
            console.log("Loaded characterCreationData from session storage:", characterCreationData);
        } else {
            characterCreationData = {}; // Initialize as empty object
            console.log("Initialized new characterCreationData.");
        }
    } catch (e) {
        console.error("Error loading character creation data from session storage:", e);
        characterCreationData = {}; // Initialize as empty object on error
    }
    // Ensure all expected keys exist
    characterCreationData.step1_race_selection = characterCreationData.step1_race_selection || null;
    characterCreationData.step1_parent_race_selection = characterCreationData.step1_parent_race_selection || null;
    characterCreationData.step1_race_traits_text = characterCreationData.step1_race_traits_text || '';
    // New Step 2 keys
    characterCreationData.step2_selected_base_class = characterCreationData.step2_selected_base_class || null;
    characterCreationData.step2_selected_archetype = characterCreationData.step2_selected_archetype || null;
    characterCreationData.step2_selection_details_text = characterCreationData.step2_selection_details_text || '';
    // ... any other steps ...
    characterCreationData.step4_standard_stats = characterCreationData.step4_standard_stats || [15, 14, 13, 12, 10, 8];
    characterCreationData.step4_rolled_stats = characterCreationData.step4_rolled_stats || null;
    characterCreationData.step4_assigned_stats = characterCreationData.step4_assigned_stats || {}; // e.g., { STR: null, DEX: null, ... }
    characterCreationData.step4_stat_bonuses = characterCreationData.step4_stat_bonuses || {
        STR: { race: 0, class: 0 }, DEX: { race: 0, class: 0 }, CON: { race: 0, class: 0 },
        INT: { race: 0, class: 0 }, WIS: { race: 0, class: 0 }, CHA: { race: 0, class: 0 }
    };
    characterCreationData.step4_vital_stats = characterCreationData.step4_vital_stats || []; // e.g., ["STR", "CON"]
    characterCreationData.step4_dice_rolled_once = characterCreationData.step4_dice_rolled_once || false;
    characterCreationData.step4_selected_dice_value = characterCreationData.step4_selected_dice_value || null; // To store the currently clicked dice from the pool
    characterCreationData.step4_ability_scores = characterCreationData.step4_ability_scores || ["STR", "DEX", "CON", "INT", "WIS", "CHA"];
    characterCreationData.ability_scores = characterCreationData.ability_scores || {}; // For final calculated scores
    characterCreationData.step4_asi_choices = characterCreationData.step4_asi_choices || []; // For storing ASI choices
    characterCreationData.step4_allocated_choice_bonuses = characterCreationData.step4_allocated_choice_bonuses || { STR: 0, DEX: 0, CON: 0, INT: 0, WIS: 0, CHA: 0 };
    characterCreationData.step4_unallocated_asi_points = characterCreationData.step4_unallocated_asi_points || 0;
    characterCreationData.step4_asi_choice_details_for_ui = characterCreationData.step4_asi_choice_details_for_ui || [];
    // Step 3 (Background) data state
    characterCreationData.step3_selected_background_slug = characterCreationData.step3_selected_background_slug || null;
    characterCreationData.step3_background_selection = characterCreationData.step3_background_selection || null;
    characterCreationData.step3_background_details_text = characterCreationData.step3_background_details_text || '';
    characterCreationData.step3_background_data_loaded = characterCreationData.step3_background_data_loaded || false;

    // Step 5 data
    characterCreationData.skill_proficiencies = characterCreationData.skill_proficiencies || []; // Stores chosen/granted skill proficiencies
    characterCreationData.saving_throw_proficiencies = characterCreationData.saving_throw_proficiencies || []; // Stores saving throw proficiencies (usually from class)
    characterCreationData.proficiency_bonus = characterCreationData.proficiency_bonus || 2; // Default for level 1, might be set elsewhere too


    let selectedClassOrArchetypeSlug = null; // Renamed from selectedClassSlug

let asiDebugTextsCollection = []; // To store texts for debug display

    const prevButton = document.getElementById('prev-button'); // This ID is now in wizard-top-controls
    const nextButton = document.getElementById('next-button'); // This ID is now in wizard-top-controls
    const cancelButton = document.getElementById('cancel-button'); // This ID is now in wizard-top-controls
    // Ensure stepIndicators query selector targets the one inside wizard-top-controls for active class updates
    const stepIndicators = document.querySelectorAll('.wizard-top-controls .step-indicator');


    const phbPlaceholders = {
        1: `<h3>1. Choose a Race</h3>
            <p>Your choice of race affects many different aspects of your character. It establishes fundamental qualities that exist throughout your character’s adventuring career.</p>
            <p><strong>Racial Traits:</strong> The description of each race includes racial traits that are common to members of that race. These can include: Ability Score Increase, Age, Alignment tendencies, Size, Speed, Languages, and Subraces.</p>`,
        2: `<h3>2. Choose a Class</h3>
            <p>Your class gives you a variety of special features, such as a fighter’s mastery of weapons and armor, or a wizard’s spells. At low levels, your class gives you only two or three features, but as you advance in level you gain more, and your existing features often improve.</p>
            <p>Your class is the primary definition of what your character can do in the extraordinary world of Dungeons & Dragons. It's more than a profession; it’s your character’s calling. Class determines your character's combat capabilities, skills, and access to magic.</p>
<p>Key aspects of your chosen class include:</p>
<ul>
    <li><strong>Hit Dice:</strong> Determines your character's hit points and ability to recover from damage.</li>
    <li><strong>Proficiencies:</strong> Includes armor, weapons, tools, saving throws, and skills. These are things your character is particularly good at.</li>
    <li><strong>Starting Equipment:</strong> The gear your character begins their adventuring career with.</li>
    <li><strong>Class Features:</strong> Special abilities, such as a fighter’s Action Surge or a wizard’s Spellcasting, that define your class. Many classes gain more features as they level up.</li>
</ul>
<p>Consider how your choice of class will complement your chosen race and your desired play style. The information presented here is typically from the Player's Handbook (PHB) or other official sources available through the API.</p>`,
        3: `<h3>3. Choose a Background</h3>
            <p>Your character's background describes where you came from, your original occupation, and your place in the D&D world. Your DM might offer additional backgrounds beyond those in the PHB.</p>
            <p>A background usually provides:
            <br> - Skill Proficiencies
            <br> - Tool Proficiencies
            <br> - Languages
            <br> - Starting Equipment
            <br> - A special background feature</p>
            <p>It also offers suggestions for personality traits, ideals, bonds, and flaws. These are roleplaying cues that help you bring your character to life.</p>
            <p>When you choose a background, it will grant you certain benefits and provide roleplaying hooks. Select a background from the list to see its details and what it offers your character.</p>`,
        4: `<h3>4. Determine Ability Scores</h3>
            <p>Six abilities provide a quick description of every creature’s physical and mental characteristics:
            <br> - <strong>Strength (STR):</strong> Natural athleticism, bodily power.
            <br> - <strong>Dexterity (DEX):</strong> Physical agility, reflexes, balance, poise.
            <br> - <strong>Constitution (CON):</strong> Health, stamina, vital force.
            <br> - <strong>Intelligence (INT):</strong> Mental acuity, information recall, analytical skill.
            <br> - <strong>Wisdom (WIS):</strong> Awareness, intuition, insight.
            <br> - <strong>Charisma (CHA):</strong> Confidence, eloquence, leadership.</p>
            <p>Each ability has a score. Common methods for generating these scores are:
            <br> - <strong>Standard Array:</strong> Use the scores 15, 14, 13, 12, 10, 8, and assign them as you wish.
            <br> - <strong>Rolling (4d6 drop lowest):</strong> For each of the six abilities, roll four 6-sided dice and record the total of the highest three dice. Assign these totals to your abilities.
            <br> - <strong>Point Buy:</strong> You have a number of points to spend on increasing base ability scores. (Details in PHB/DMG).</p>
            <p><strong>Ability Modifiers:</strong> Each ability score has a modifier, derived from the score and ranging from -5 (for an ability score of 1) to +10 (for a score of 30). The formula is (Score - 10) / 2, rounded down.
            <br>Example Modifiers: Score 1 (-5), 2-3 (-4), 4-5 (-3), 6-7 (-2), 8-9 (-1), 10-11 (+0), 12-13 (+1), 14-15 (+2), 16-17 (+3), 18-19 (+4), 20-21 (+5).</p>
            <p>After assigning scores, apply any racial ability score increases.</p>`,
        5: `<h3>5. Skills and Proficiencies</h3>
            <p><strong>Skills:</strong> Each ability covers a broad range of capabilities, including skills that a character or a monster can be proficient in. A skill represents a specific aspect of an ability score, and a character's proficiency in a skill demonstrates a focus on that aspect. Your character gains skill proficiencies from their class, background, and sometimes race.</p>
            <p>The information out of the open5e API gives multiple options for how these are gained:</p>
            <ul>
                <li><strong>Race - Skill Proficiencies (Racial):</strong> Example: Intimidation. This results in one skill with +proficiency. These are automatically granted if your race provides them.</li>
                <li><strong>Class - Skill Proficiencies:</strong> Example: Choose two from Animal Handling, Athletics, Intimidation, Nature, Perception, and Survival. This requires you to select the specified number of skills from the list provided by your class.</li>
                <li><strong>Background - Skill Proficiencies:</strong> Example: Religion, and either Insight or Persuasion. This gives Religion a +proficiency automatically and requires you to choose between Insight or Persuasion.</li>
            </ul>
            <p><strong>Proficiency Bonus:</strong> Characters have a proficiency bonus determined by level. This bonus is used for:
            <br> - Attack rolls using weapons you’re proficient with
            <br> - Attack rolls with spells you cast
            <br> - Ability checks using skills you’re proficient in
            <br> - Ability checks using tools you’re proficient with
            <br> - Saving throws you’re proficient in
            <br> - The saving throw DCs for spells you cast (if applicable)</p>
            <p>Your selected skills will grant you this proficiency bonus when making relevant ability checks.</p>`,
        6: `<h3>6. Hit Points and Combat Stats</h3>
            <p><strong>Hit Points (HP):</strong> Your character’s hit points define how tough your character is in combat and other dangerous situations. Your hit points are determined by your Hit Dice (from your class).
            <br> - <strong>At 1st Level:</strong> You start with hit points equal to the highest roll of your Hit Die, plus your Constitution modifier.
            <br> - <strong>Hit Dice:</strong> Represent your character's general toughness and ability to recover from wounds. You have a number of Hit Dice equal to your level. You can spend Hit Dice during a short rest to regain hit points.</p>
            <p><strong>Armor Class (AC):</strong> Your Armor Class represents how well your character avoids being wounded in battle. It's typically 10 + your Dexterity modifier, plus any bonuses from armor, shields, or other magical effects.</p>
            <p><strong>Speed:</strong> Your race determines your base walking speed.</p>
            <p><strong>Initiative:</strong> At the beginning of every combat, you roll for initiative (a Dexterity check) to determine the order of turns.</p>`,
        7: `<h3>7. Choose Equipment</h3>
            <p>Your class and background determine your character’s starting equipment. The PHB provides packages of starting equipment for each class. Alternatively, you can choose to start with a number of gold pieces (gp) based on your class and spend it on items from the equipment lists.</p>
            <p>Consider:
            <br> - Weapons and Armor
            <br> - Adventuring Gear (backpack, bedroll, rope, torches, rations, etc.)
            <br> - Tools (thieves' tools, artisan's tools, musical instruments)
            <br> - Holy Symbols or Spellcasting Focuses
            <br> - Coins and Wealth</p>`,
        8: `<h3>8. Spellcasting</h3>
            <p>For many classes, magic is a key part of their power. If your class grants spellcasting, you'll need to understand:
            <br> - <strong>Cantrips:</strong> Simple spells you can cast at will without using a spell slot.
            <br> - <strong>Spell Slots:</strong> Casting a spell requires using a slot of the spell's level or higher. You regain spent spell slots after finishing a long rest (or sometimes short rest for Warlocks).
            <br> - <strong>Spells Known and Prepared:</strong> Some classes (like Sorcerers and Bards) know a limited number of spells and can cast any of them using available slots. Others (like Clerics, Druids, and Wizards) have access to a larger list but must prepare a selection of spells each day.
            <br> - <strong>Spellcasting Ability:</strong> Each spellcasting class has a specific ability score that powers their magic (e.g., Intelligence for Wizards, Wisdom for Clerics, Charisma for Sorcerers). This affects your spell attack bonus and spell save DC.
            <br> - <strong>Components:</strong> Spells can have Verbal (V), Somatic (S), and Material (M) components. Material components might be consumed or might be a reusable focus.</p>
            <p>If your class does not grant spells at 1st level, this step may provide general information or be skipped for your current choices.</p>`,
        9: `<h3>9. Review & Finalize</h3>
            <p>At this stage, you bring all the pieces of your character together and add the finishing touches.</p>
            <p>Consider the following:
            <br> - <strong>Character Name:</strong> What is your adventurer called?
            <br> - <strong>Alignment:</strong> Describes your character's moral and personal attitudes (e.g., Lawful Good, Chaotic Neutral, True Neutral).
            <br> - <strong>Personality Traits:</strong> Distinctive aspects of your character's behavior.
            <br> - <strong>Ideals:</strong> The things your character believes in most strongly.
            <br> - <strong>Bonds:</strong> Connections to people, places, or events in the world.
            <br> - <strong>Flaws:</strong> A vice, compulsion, fear, or weakness.
            <br> - <strong>Appearance:</strong> What does your character look like? Hair color, eye color, height, distinguishing marks.
            <br> - <strong>Backstory Snippets:</strong> Brief notes about your character's history that might come up in play.</p>
            <p>This is your chance to ensure all mechanical choices are recorded and your character concept is clear, ready for adventure!</p>`
    };

    function showStep(stepNumber) {
        if (stepNumber === 0) {
            characterCreationData.step4_assigned_stats = {};
            characterCreationData.step4_dice_rolled_once = false;
            characterCreationData.step4_rolled_stats = null;
            characterCreationData.step4_asi_choices = []; // Reset ASI choices
            characterCreationData.step4_allocated_choice_bonuses = { STR: 0, DEX: 0, CON: 0, INT: 0, WIS: 0, CHA: 0 };
            characterCreationData.step4_unallocated_asi_points = 0;
            characterCreationData.step4_asi_choice_details_for_ui = [];
            characterCreationData.step3_background_data_loaded = false; // Reset on intro step
            saveCharacterDataToSession();
        }

        // Handle ASI Debug Texts visibility and initialization
        if (stepNumber === 4) { // This is the ASI step (currently handled by loadStep3Logic)
            asiDebugTextsCollection = []; // Clear previous texts when entering the step
            if (IS_CHARACTER_CREATION_DEBUG_ACTIVE) {
                const debugContainer = document.getElementById('asi-debug-texts-container');
                if (debugContainer) {
                    debugContainer.style.display = 'block'; // Ensure it's visible
                }
                const debugOutputEl = document.getElementById('asi-debug-output');
                if (debugOutputEl) {
                    debugOutputEl.textContent = 'Collecting ASI processing texts...'; // Initial message
                }
            }
            // loadStep3Logic(); // This function will now populate the debug texts - called later in showStep
        } else if (IS_CHARACTER_CREATION_DEBUG_ACTIVE) { // Hide debug container if not on step 4
            const debugContainer = document.getElementById('asi-debug-texts-container');
            if (debugContainer) {
                // debugContainer.style.display = 'none'; // Jinja handles initial rendering, JS might not need to explicitly hide.
                                                       // If JS *did* show it for step 4, then it should hide it here.
                                                       // For now, let's assume Jinja handles initial state and JS only shows for step 4.
            }
        }

        // Clear race-specific content when leaving step 1
        if (stepNumber !== 1) {
            const raceListContainer = document.getElementById('race-list-container');
            const raceDescriptionContainer = document.getElementById('race-description-container');
            // const traitsDisplayContainer = document.getElementById('race-traits-display'); // Removed
            if (raceListContainer) raceListContainer.innerHTML = '';
            if (raceDescriptionContainer) raceDescriptionContainer.innerHTML = ''; // This now also clears traits if they were in race-description-container
            // if (traitsDisplayContainer) traitsDisplayContainer.innerHTML = ''; // Removed
        }
       if (stepNumber !== 2) {
           const classListContainer = document.getElementById('class-list-container');
           const classDescriptionContainer = document.getElementById('class-description-container');
           if (classListContainer) classListContainer.innerHTML = '';
           if (classDescriptionContainer) classDescriptionContainer.innerHTML = '';
       }
        if (stepNumber !== 3) {
            const backgroundListContainer = document.getElementById('background-list-container');
            const backgroundDescriptionContainer = document.getElementById('background-description-container');
            if (backgroundListContainer) backgroundListContainer.innerHTML = '';
            if (backgroundDescriptionContainer) backgroundDescriptionContainer.innerHTML = '';
            characterCreationData.step3_background_data_loaded = false; // Reset if not on background step
        }

        // Hide all main content wizard steps first
        document.querySelectorAll('.wizard-step').forEach(step => {
            step.style.display = 'none';
        });

        // Show current step's main content
        if (stepNumber > 0) {
            const currentStepContent = document.getElementById(`step-${stepNumber}`);
            if (currentStepContent) {
                currentStepContent.style.display = 'block';
            }
            // Special handling for Step 1 (Race Selection)
            if (stepNumber === 1) {
                const step1ContentDiv = document.getElementById('step-1');
                // Check if content is already loaded by looking for specific elements expected from the HTML, e.g., a known ID from the loaded content
                if (step1ContentDiv && !step1ContentDiv.querySelector('#race-list-container')) {
                    fetch('/static/character_creation/step1_race_selection.html')
                        .then(response => {
                            if (!response.ok) {
                                throw new Error('Network response was not ok for step1_race_selection.html');
                            }
                            return response.text();
                        })
                        .then(html => {
                            step1ContentDiv.innerHTML = html;
                            // Now that the HTML structure is loaded, call the function to populate race data
                            if (typeof loadRaceStepData === 'function') {
                                loadRaceStepData(); // This function is in character_creation_step1.js
                            } else {
                                console.error('loadRaceStepData function not found. Ensure character_creation_step1.js is loaded.');
                            }
                        })
                        .catch(error => {
                            console.error('Error fetching or loading Step 1 HTML:', error);
                            if (step1ContentDiv) {
                                step1ContentDiv.innerHTML = '<p class="error-message">Error loading race selection content. Please try refreshing or contact support.</p>';
                            }
                        });
                } else if (step1ContentDiv && step1ContentDiv.querySelector('#race-list-container')) {
                    // Content is already loaded, just ensure data is populated/refreshed.
                    // loadRaceStepData itself handles the logic of fetching vs using existing data.
                    if (typeof loadRaceStepData === 'function') {
                        loadRaceStepData();
                        // Optional: If a race was previously selected (e.g. characterCreationData.step1_race_selection exists),
                        // and you want to re-highlight it or re-display its details, you might need to call
                        // a function from character_creation_step1.js here that handles that.
                        // For example, if selectedRaceSlug is maintained in character_creation_step1.js,
                        // that script could have a function to re-apply selection based on characterCreationData.
                    } else {
                        console.error('loadRaceStepData function not found on subsequent load. Ensure character_creation_step1.js is loaded.');
                    }
                } else if (!step1ContentDiv) {
                    console.error("Step 1 content div ('step-1') not found in the DOM.");
                }
            } else if (stepNumber === 2) {
                const step2ContentDiv = document.getElementById('step-2');
                // Check if content is already loaded or needs to be fetched
                if (step2ContentDiv && !step2ContentDiv.querySelector('#class-list-container')) { // Or some other unique element from step2_class_selection.html
                    fetch('/static/character_creation/step2_class_selection.html')
                        .then(response => {
                            if (!response.ok) {
                                throw new Error('Network response was not ok for step2_class_selection.html');
                            }
                            return response.text();
                        })
                        .then(html => {
                            if (step2ContentDiv) {
                                step2ContentDiv.innerHTML = html;
                            }
                            // Now that the HTML structure is loaded, call the function to populate class data
                            if (typeof loadClassStepData === 'function') {
                                loadClassStepData(); // This function is now in character_creation_step2.js
                            } else {
                                console.error('loadClassStepData function not found. Ensure character_creation_step2.js is loaded.');
                            }
                        })
                        .catch(error => {
                            console.error('Error fetching or loading Step 2 HTML:', error);
                            if (step2ContentDiv) {
                                step2ContentDiv.innerHTML = '<p class="error-message">Error loading class selection content. Please try refreshing or contact support.</p>';
                            }
                        });
                } else if (step2ContentDiv && step2ContentDiv.querySelector('#class-list-container')) {
                    // Content is already loaded, just ensure data is populated/refreshed.
                    if (typeof loadClassStepData === 'function') {
                        loadClassStepData(); // Handles fetching vs using existing data internally
                        // Optional: If a class was previously selected and needs re-highlighting, add logic here or ensure loadClassStepData handles it.
                    } else {
                        console.error('loadClassStepData function not found on subsequent load for step 2. Ensure character_creation_step2.js is loaded.');
                    }
                } else if (!step2ContentDiv) {
                    console.error("Step 2 content div ('step-2') not found in the DOM.");
                }
            } else if (stepNumber === 3) { // This is Backgrounds (Step 3)
                const step3ContentDiv = document.getElementById('step-3');

                // Ensure the main step div is visible. This should typically be handled by the generic
                // currentStepContent.style.display = 'block' earlier, but this is a safeguard.
                if (step3ContentDiv) {
                    step3ContentDiv.style.display = 'block';
                }

                // Check if content needs to be loaded
                if (step3ContentDiv && !step3ContentDiv.querySelector('#background-list-container')) {
                    fetch('/static/character_creation/step3_background_selection.html')
                        .then(response => {
                            if (!response.ok) {
                                throw new Error('Network response was not ok for step3_background_selection.html');
                            }
                            return response.text();
                        })
                        .then(html => {
                            step3ContentDiv.innerHTML = html;
                            // Ensure visibility AFTER innerHTML update
                            step3ContentDiv.style.display = 'block';

                            // Now that the HTML structure is loaded, call the function to populate background data
                            if (typeof loadBackgroundStepData === 'function') {
                                loadBackgroundStepData(); // This function is in character_creation_step3.js
                                // If a background was previously selected, re-display its details
                                if (characterCreationData.step3_selected_background_slug && typeof displayBackgroundDetails === 'function') {
                                    displayBackgroundDetails(characterCreationData.step3_selected_background_slug);
                                }
                            } else {
                                console.error('loadBackgroundStepData function not found. Ensure character_creation_step3.js is loaded.');
                            }
                        })
                        .catch(error => {
                            console.error('Error fetching or loading Step 3 HTML:', error);
                            if (step3ContentDiv) {
                                step3ContentDiv.innerHTML = '<p class="error-message">Error loading background selection content. Please try refreshing or contact support.</p>';
                            }
                        });
                } else if (step3ContentDiv && step3ContentDiv.querySelector('#background-list-container')) {
                    // Content is already loaded
                    // Ensure visibility again, just in case.
                    step3ContentDiv.style.display = 'block';

                    // Ensure data is populated/refreshed.
                    if (typeof loadBackgroundStepData === 'function') {
                        loadBackgroundStepData(); // From character_creation_step3.js
                        // If a background was previously selected, re-display its details
                        if (characterCreationData.step3_selected_background_slug && typeof displayBackgroundDetails === 'function') {
                            displayBackgroundDetails(characterCreationData.step3_selected_background_slug);
                        }
                    } else {
                        console.error('loadBackgroundStepData function not found on subsequent load for step 3. Ensure character_creation_step3.js is loaded.');
                    }
                } else if (!step3ContentDiv) {
                    console.error("Step 3 content div ('step-3') not found in the DOM.");
                }
            } else if (stepNumber === 4) { // This is Ability Scores (Step 4)
                const step4ContentDiv = document.getElementById('step-4');
                if (step4ContentDiv && !step4ContentDiv.querySelector('#vital-stats-container')) { // Check for a unique element from step4 HTML
                    fetch('/static/character_creation/step4_ability_scores.html')
                        .then(response => {
                            if (!response.ok) {
                                throw new Error('Network response was not ok for step4_ability_scores.html');
                            }
                            return response.text();
                        })
                        .then(html => {
                            step4ContentDiv.innerHTML = html;
                            if (typeof loadStep4Logic === 'function') {
                                loadStep4Logic(); // This function is in character_creation_step4.js
                            } else {
                                console.error('loadStep4Logic function not found. Ensure character_creation_step4.js is loaded.');
                            }
                        })
                        .catch(error => {
                            console.error('Error fetching or loading Step 4 HTML:', error);
                            if (step4ContentDiv) {
                                step4ContentDiv.innerHTML = '<p class="error-message">Error loading ability scores content. Please try refreshing or contact support.</p>';
                            }
                        });
                } else if (step4ContentDiv && step4ContentDiv.querySelector('#vital-stats-container')) {
                    // Content is already loaded, just call the logic function
                    if (typeof loadStep4Logic === 'function') {
                        loadStep4Logic();
                    } else {
                        console.error('loadStep4Logic function not found on subsequent load for step 4. Ensure character_creation_step4.js is loaded.');
                    }
                } else if (!step4ContentDiv) {
                    console.error("Step 4 content div ('step-4') not found in the DOM.");
                }
            } else if (stepNumber === 5) { // Skills and Proficiencies
                const step5ContentDiv = document.getElementById('step-5');
                // Using innerHTML.trim() === '' as a simple check for emptiness.
                // A more robust check might be for a specific element ID from step5's HTML if one exists.
                if (step5ContentDiv && step5ContentDiv.innerHTML.trim() === '') {
                    fetch('/static/character_creation/step5_skills_proficiencies.html')
                        .then(response => {
                            if (!response.ok) {
                                throw new Error('Network response was not ok for step5_skills_proficiencies.html');
                            }
                            return response.text();
                        })
                        .then(html => {
                            if (step5ContentDiv) {
                                step5ContentDiv.innerHTML = html;
                            }
                            // Now that the HTML structure is loaded, call the function to populate data
                            if (typeof loadStep5Logic === 'function') {
                                loadStep5Logic(); // This function is in character_creation_step5.js
                            } else {
                                console.error('loadStep5Logic function not found. Ensure character_creation_step5.js is loaded.');
                            }
                        })
                        .catch(error => {
                            console.error('Error fetching or loading Step 5 HTML:', error);
                            if (step5ContentDiv) {
                                step5ContentDiv.innerHTML = '<p class="error-message">Error loading skills & proficiencies content. Please try refreshing or contact support.</p>';
                            }
                        });
                } else if (step5ContentDiv && step5ContentDiv.innerHTML.trim() !== '') {
                    // Content is already loaded, just call the logic function to refresh/repopulate
                    if (typeof loadStep5Logic === 'function') {
                        loadStep5Logic();
                    } else {
                        console.error('loadStep5Logic function not found on subsequent load for step 5. Ensure character_creation_step5.js is loaded.');
                    }
                } else if (!step5ContentDiv) {
                    console.error("Step 5 content div ('step-5') not found in the DOM.");
                }
            } else if (stepNumber === 6) { // HP and Combat Stats
                const step6ContentDiv = document.getElementById('step-6');
                if (step6ContentDiv && step6ContentDiv.innerHTML.trim() === '') {
                    fetch('/static/character_creation/step6_hp_combat_stats.html')
                        .then(response => {
                            if (!response.ok) {
                                throw new Error('Network response was not ok for step6_hp_combat_stats.html');
                            }
                            return response.text();
                        })
                        .then(html => {
                            if (step6ContentDiv) {
                                step6ContentDiv.innerHTML = html;
                            }
                            if (typeof loadStep6Logic === 'function') {
                                loadStep6Logic();
                            } else {
                                console.error('loadStep6Logic function not found. Ensure character_creation_step6.js is loaded.');
                            }
                        })
                        .catch(error => {
                            console.error('Error fetching or loading Step 6 HTML:', error);
                            if (step6ContentDiv) {
                                step6ContentDiv.innerHTML = '<p class="error-message">Error loading HP & combat stats content. Please try refreshing or contact support.</p>';
                            }
                        });
                } else if (step6ContentDiv && step6ContentDiv.innerHTML.trim() !== '') {
                    if (typeof loadStep6Logic === 'function') {
                        loadStep6Logic();
                    } else {
                        console.error('loadStep6Logic function not found on subsequent load for step 6. Ensure character_creation_step6.js is loaded.');
                    }
                } else if (!step6ContentDiv) {
                    console.error("Step 6 content div ('step-6') not found in the DOM.");
                }
            } else if (stepNumber === 7) {
                const step7ContentDiv = document.getElementById('step-7');
                if (step7ContentDiv && step7ContentDiv.innerHTML.trim() === '') {
                    fetch('/static/character_creation/step7_equipment.html')
                        .then(response => {
                            if (!response.ok) {
                                throw new Error('Network response was not ok for step7_equipment.html');
                            }
                            return response.text();
                        })
                        .then(html => {
                            if (step7ContentDiv) {
                                step7ContentDiv.innerHTML = html;
                            }
                            if (typeof loadStep7Logic === 'function') {
                                loadStep7Logic();
                            } else {
                                console.error('loadStep7Logic function not found. Ensure character_creation_step7.js is loaded.');
                            }
                        })
                        .catch(error => {
                            console.error('Error fetching or loading Step 7 HTML:', error);
                            if (step7ContentDiv) {
                                step7ContentDiv.innerHTML = '<p class="error-message">Error loading equipment content. Please try refreshing or contact support.</p>';
                            }
                        });
                } else if (step7ContentDiv && step7ContentDiv.innerHTML.trim() !== '') {
                    if (typeof loadStep7Logic === 'function') {
                        loadStep7Logic();
                    } else {
                        console.error('loadStep7Logic function not found on subsequent load for step 7. Ensure character_creation_step7.js is loaded.');
                    }
                } else if (!step7ContentDiv) {
                    console.error("Step 7 content div ('step-7') not found in the DOM.");
                }
            } else if (stepNumber === 8) {
                const step8ContentDiv = document.getElementById('step-8');
                if (step8ContentDiv && step8ContentDiv.innerHTML.trim() === '') {
                    fetch('/static/character_creation/step8_spells.html')
                        .then(response => {
                            if (!response.ok) {
                                throw new Error('Network response was not ok for step8_spells.html');
                            }
                            return response.text();
                        })
                        .then(html => {
                            if (step8ContentDiv) {
                                step8ContentDiv.innerHTML = html;
                            }
                            if (typeof loadStep8Logic === 'function') {
                                loadStep8Logic();
                            } else {
                                console.error('loadStep8Logic function not found. Ensure character_creation_step8.js is loaded.');
                            }
                        })
                        .catch(error => {
                            console.error('Error fetching or loading Step 8 HTML:', error);
                            if (step8ContentDiv) {
                                step8ContentDiv.innerHTML = '<p class="error-message">Error loading spells content. Please try refreshing or contact support.</p>';
                            }
                        });
                } else if (step8ContentDiv && step8ContentDiv.innerHTML.trim() !== '') {
                    if (typeof loadStep8Logic === 'function') {
                        loadStep8Logic();
                    } else {
                        console.error('loadStep8Logic function not found on subsequent load for step 8. Ensure character_creation_step8.js is loaded.');
                    }
                } else if (!step8ContentDiv) {
                    console.error("Step 8 content div ('step-8') not found in the DOM.");
                }
            } else if (stepNumber === 9) {
                const step9ContentDiv = document.getElementById('step-9');
                if (step9ContentDiv && step9ContentDiv.innerHTML.trim() === '') {
                    fetch('/static/character_creation/step9_review_finalize.html')
                        .then(response => {
                            if (!response.ok) {
                                throw new Error('Network response was not ok for step9_review_finalize.html');
                            }
                            return response.text();
                        })
                        .then(html => {
                            if (step9ContentDiv) {
                                step9ContentDiv.innerHTML = html;
                            }
                            if (typeof loadStep9Logic === 'function') {
                                loadStep9Logic();
                            } else {
                                console.error('loadStep9Logic function not found. Ensure character_creation_step9.js is loaded.');
                            }
                        })
                        .catch(error => {
                            console.error('Error fetching or loading Step 9 HTML:', error);
                            if (step9ContentDiv) {
                                step9ContentDiv.innerHTML = '<p class="error-message">Error loading review & finalize content. Please try refreshing or contact support.</p>';
                            }
                        });
                } else if (step9ContentDiv && step9ContentDiv.innerHTML.trim() !== '') {
                    if (typeof loadStep9Logic === 'function') {
                        loadStep9Logic();
                    } else {
                        console.error('loadStep9Logic function not found on subsequent load for step 9. Ensure character_creation_step9.js is loaded.');
                    }
                } else if (!step9ContentDiv) {
                    console.error("Step 9 content div ('step-9') not found in the DOM.");
                }
            }
            // Update PHB description placeholder for steps > 0
            const phbDescContainer = document.getElementById('phb-description');
            if (phbPlaceholders[stepNumber] !== undefined) {
                phbDescContainer.innerHTML = phbPlaceholders[stepNumber];
            } else {
                phbDescContainer.innerHTML = `<p>Description for step ${stepNumber} will go here.</p>`; // Fallback
            }
        } else { // Step 0 (Introduction)
            const stepZeroContent = document.getElementById('step-0');
            if (stepZeroContent) {
                stepZeroContent.innerHTML = '<p>Loading introduction...</p>'; // Temporary loading message
                stepZeroContent.style.display = 'block';

                // Fetch content for Step 0
                fetch('/static/character_creation/step0_intro.html')
                    .then(response => {
                        if (!response.ok) {
                            throw new Error('Network response was not ok for step0_intro.html');
                        }
                        return response.text();
                    })
                    .then(html => {
                        stepZeroContent.innerHTML = html;
                    })
                    .catch(error => {
                        console.error('Error fetching step 0 content:', error);
                        stepZeroContent.innerHTML = '<p>Error loading introduction. Please try refreshing.</p>';
                    });
            }
            // Clear PHB description for step 0 as content is in stepZeroContent
            const phbDescContainer = document.getElementById('phb-description');
            if (phbDescContainer) {
                phbDescContainer.innerHTML = '';
            }
        }

        // Update button visibility and text
        if (stepNumber === 0) {
            prevButton.style.display = 'none';
            nextButton.textContent = 'Start Character Creation';
        } else {
            prevButton.style.display = 'inline-block';
            if (stepNumber === totalSteps) { // totalSteps is 9 (0-9 means 10 steps)
                nextButton.textContent = 'Finish';
            } else {
                nextButton.textContent = 'Next';
            }
        }

        // Update step indicators
        stepIndicators.forEach(indicator => {
            const indicatorStep = parseInt(indicator.dataset.step);
            if (indicatorStep === stepNumber) {
                indicator.classList.add('active');
            } else {
                indicator.classList.remove('active');
            }
        });
    }

    prevButton.addEventListener('click', () => {
        if (currentStep > 0) { // Allow going back to step 0
            currentStep--;
            showStep(currentStep);
        }
    });

    nextButton.addEventListener('click', async () => {
        // Store data if moving from Step 1
        // selectedRaceSlug is now managed in character_creation_step1.js
        // We rely on characterCreationData.step1_race_selection being populated by step 1's logic.
        if (currentStep === 1) {
            if (!characterCreationData.step1_race_selection) {
                alert("Please select a race before proceeding.");
                return;
            }
            // Data fetching for race/parent race is now primarily handled in character_creation_step1.js.
            // This section will now mostly ensure data is saved or perform final validation if needed.
            // The detailed fetch logic previously here has been removed.

            // Fallback example: if parent race data wasn't loaded in step1.js, try here.
            // This is more of a safeguard; ideally, step1.js handles all its data population.
            const raceData = characterCreationData.step1_race_selection;
            if (raceData && raceData.subrace_of && !characterCreationData.step1_parent_race_selection) {
                console.warn("Parent race slug present but parent race data not loaded by Step 1 logic. Attempting fallback fetch.");
                try {
                    const parentRaceUrlParts = raceData.subrace_of.split('/').filter(part => part);
                    const parentRaceSlugFromData = parentRaceUrlParts.pop();

                    if (parentRaceSlugFromData) {
                        const parentRaceResponse = await fetch(`/api/v2/races/${parentRaceSlugFromData}/`);
                        if (!parentRaceResponse.ok) {
                            throw new Error(`Failed to fetch parent race data for ${parentRaceSlugFromData}: ${parentRaceResponse.status}`);
                        }
                        const parentRaceData = await parentRaceResponse.json();
                        characterCreationData.step1_parent_race_selection = parentRaceData;
                        console.log("Fallback: Parent race data fetched and stored on Next button click.");
                    }
                } catch (error) {
                     console.error("Error during fallback parent race fetch:", error);
                     // Decide if this error is critical enough to halt progression
                }
            }
            // End of fallback example.

            console.log("Step 1 data (race selection) seems okay. Proceeding to save.", characterCreationData);
            saveCharacterDataToSession(); // Save the state which should include race data from step1.js

        }
        // Logic for Step 2: Class/Archetype Selection
        else if (currentStep === 2) {
            if (!selectedClassOrArchetypeSlug) {
                alert("Please select a class or archetype before proceeding.");
                return;
            }

            const selectedLi = document.querySelector(`#class-selection-list li[data-slug='${selectedClassOrArchetypeSlug}']`);
            if (!selectedLi) {
                console.error("Selected LI element not found for slug:", selectedClassOrArchetypeSlug);
                alert("An error occurred with your selection. Please try selecting again.");
                return;
            }

            let isArchetypeSelected = false;
            let parentClassSlugForArchetype = null;

            if (selectedLi.dataset.parentClassSlug) {
                isArchetypeSelected = true;
                parentClassSlugForArchetype = selectedLi.dataset.parentClassSlug;
            }

            try {
                if (isArchetypeSelected) {
                    const baseClassResponse = await fetch(`/api/v1/classes/${parentClassSlugForArchetype}/`);
                    if (!baseClassResponse.ok) {
                        throw new Error(`Failed to fetch base class data for ${parentClassSlugForArchetype}: ${baseClassResponse.status}`);
                    }
                    const baseClassData = await baseClassResponse.json();
                    characterCreationData.step2_selected_base_class = baseClassData;

                    let foundArchetype = null;
                    if (baseClassData.archetypes && Array.isArray(baseClassData.archetypes)) {
                        foundArchetype = baseClassData.archetypes.find(arch => arch.slug === selectedClassOrArchetypeSlug);
                    }

                    if (foundArchetype) {
                        characterCreationData.step2_selected_archetype = foundArchetype;
                    } else {
                        throw new Error(`Selected archetype '${selectedClassOrArchetypeSlug}' details not found within the base class '${parentClassSlugForArchetype}'.`);
                    }
                } else { // Base class was selected
                    const baseClassResponse = await fetch(`/api/v1/classes/${selectedClassOrArchetypeSlug}/`);
                    if (!baseClassResponse.ok) {
                        throw new Error(`Failed to fetch class data for ${selectedClassOrArchetypeSlug}: ${baseClassResponse.status}`);
                    }
                    const baseClassData = await baseClassResponse.json();
                    characterCreationData.step2_selected_base_class = baseClassData;
                    characterCreationData.step2_selected_archetype = null; // Ensure archetype is cleared
                }

                // step2_selection_details_text is already saved by displayClassDetails
                console.log("Updated characterCreationData after step 2:", characterCreationData);
                saveCharacterDataToSession();
                // Fall through to proceed to next step
            } catch (error) {
                console.error("Error processing class/archetype selection on next:", error);
                alert(`Error saving selection: ${error.message}. Please try again.`);
                return; // Prevent moving to next step
            }
        }
        // Logic for Step 3 (now Step 4 in terms of data model, Ability Scores): Ensure final ability scores are updated before leaving
        else if (currentStep === 4) { // User is ON Ability Scores (Step 4) and clicks "Next"
            // updateAndSaveFinalAbilityScores() is defined in character_creation_step4.js and called by loadStep4Logic and other handlers within that file.
            // We need to ensure that characterCreationData.ability_scores is correctly populated before proceeding.
            // A direct call here might be redundant if loadStep4Logic and its internal functions handle it thoroughly.
            // However, as a safeguard, or if specific "on next" validation/saving for step 4 is needed, it could be here.
            // For now, relying on step4.js to manage its own data saving via its event handlers.
            // If characterCreationData.ability_scores is not populated by this point, it means something is wrong in step4.js logic
            if (Object.keys(characterCreationData.ability_scores || {}).length === 0) {
                 console.warn("Proceeding from Step 4 (Ability Scores), but characterCreationData.ability_scores is empty. This might indicate an issue if scores were expected to be finalized.");
                 // alert("Ability scores have not been finalized. Please complete score assignment."); // Optional: User-facing alert
                 // return; // Optional: Prevent proceeding
            }
            console.log("Proceeding from Step 4 (Ability Scores). Current ability_scores in main:", JSON.parse(JSON.stringify(characterCreationData.ability_scores)));
            saveCharacterDataToSession(); // Ensure the latest state, including potentially updated ability_scores from step4.js, is saved.
        }
        // Logic for Background Selection (Step 3)
        else if (currentStep === 3) { // This is when user is ON Backgrounds (Step 3) and clicks "Next"
            if (!characterCreationData.step3_selected_background_slug) {
                alert("Please select a background before proceeding.");
                return;
            }
            // New check for data loaded flag
            if (!characterCreationData.step3_background_data_loaded) {
                alert("Background details are still loading or failed to load. Please wait a moment or reselect the background.");
                console.log("[DEBUG] NextButton Step 3: Prevented proceeding, step3_background_data_loaded is false. Slug:", characterCreationData.step3_selected_background_slug);
                return;
            }
            // Log corrected to refer to Step 3
            console.log("[DEBUG] Proceeding from Step 3 (Background). Background selection object:", JSON.parse(JSON.stringify(characterCreationData.step3_background_selection)));
            saveCharacterDataToSession(); // Ensure latest state, though likely redundant if flag is true
        }


        if (currentStep < totalSteps) {
            currentStep++;
            showStep(currentStep);
        } else {
            // Handle Finish action
            alert('Character creation finished! (Review/Finalize placeholder)');
            console.log("Final Character Data:", characterCreationData);
            saveCharacterDataToSession(); // Save on finish
            // finalizeCharacter();
        }
    });

// Placeholder for any remaining top-level logic or helper functions from character_creation.js
// that might be needed by the functions above, or by other steps.
// For now, this section will be empty if all specific step logic is moved.

// Initialize first step
showStep(currentStep);
