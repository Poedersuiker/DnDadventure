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
            } else if (stepNumber === 4) { // This is Ability Scores, which calls loadStep4Logic (formerly loadStep3Logic)
                loadStep3Logic(); // TODO: Rename loadStep3Logic to loadStep4Logic if it's purely for step 4. For now, keeping as is.
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
        // Logic for Step 3: Ensure final ability scores are updated before leaving
        else if (currentStep === 4) {
            updateAndSaveFinalAbilityScores(); // This also calls saveCharacterDataToSession()
            console.log("Proceeding from Step 3. Final ability_scores:", characterCreationData.ability_scores);
            // No specific validation here currently, assuming stats are handled or defaulted.
        }
        // Logic for Step 4: Background Selection
        else if (currentStep === 3) { // This is when user is ON step 3 and clicks "Next"
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

// STEP 3: ABILITY SCORES LOGIC
// =====================================================================================================================

function identifyASIs(descriptionText, sourceName, abilityScoreMap) {
    if (IS_CHARACTER_CREATION_DEBUG_ACTIVE && descriptionText) {
        asiDebugTextsCollection.push({
            source: sourceName,
            text: descriptionText
        });
    }
    const identified = {
        fixed: [], // { abilityName: "STR", bonusValue: 1 }
        choices: [] // { id, source, description, number_of_abilities_to_choose, points_per_ability, total_points_to_allocate, options: ["STR", "DEX", ...] }
    };
    if (typeof descriptionText !== 'string') return identified;

    const uniqueAbilityCodes = Object.values(GLOBAL_ABILITY_SCORE_MAP).filter((v, i, a) => a.indexOf(v) === i && v.length === 3);

    // New: Handle compound pattern like "+1 to Dexterity and one other ability score"
    const compoundPattern = /([+-]\d+)\s+to\s+([\w\s]+)\s+and\s+(?:one|an)\s+(?:other|additional)\s+ability\s+score/i;
    let compoundMatch = descriptionText.match(compoundPattern);

    if (compoundMatch) {
        const bonusValueStr = compoundMatch[1]; // e.g., "+1"
        const abilityNameFull = compoundMatch[2].trim().toLowerCase(); // e.g., "dexterity"
        const bonusValue = parseInt(bonusValueStr.replace('+', ''), 10);

        if (abilityScoreMap[abilityNameFull]) {
            identified.fixed.push({ abilityName: abilityScoreMap[abilityNameFull], bonusValue });
        }

        identified.choices.push({
            id: `choice_${sourceName.replace(/[^a-zA-Z0-9]/g, '_')}_compound_${identified.choices.length}`,
            source: sourceName,
            description: `From "${descriptionText}" - choose one other ability score`, // Using full desc for more context
            number_of_abilities_to_choose: 1,
            points_per_ability: bonusValue, // Inferred from the first part
            total_points_to_allocate: bonusValue,
            options: uniqueAbilityCodes
        });
        return identified; // Successfully parsed as a compound, return to avoid other regexes
    }

    // New: Handle Half-Elf-like compound pattern: "Your Charisma score increases by 2, and two other ability scores of your choice increase by 1."
    const halfElfLikeCompoundRegex = /Your (\w+) score increases by (\d+),\s*and\s*(one|two|three|four|five|six)\s+other\s+ability\s+scores(?:\s+of\s+your\s+choice)?\s+increase\s+by\s+(\d+)/i;
    let halfElfMatch = descriptionText.match(halfElfLikeCompoundRegex);

    if (halfElfMatch) {
        // Fixed Part
        const fixedAbilityNameFull = halfElfMatch[1].toLowerCase();
        const fixedBonusValue = parseInt(halfElfMatch[2], 10);
        if (abilityScoreMap[fixedAbilityNameFull]) {
            identified.fixed.push({ abilityName: abilityScoreMap[fixedAbilityNameFull], bonusValue: fixedBonusValue });
        }

        // Choice Part
        const numScoresToChoose = parseWordToNumber(halfElfMatch[3].toLowerCase());
        const choiceBonusValue = parseInt(halfElfMatch[4], 10);

        if (numScoresToChoose > 0 && choiceBonusValue > 0) {
            identified.choices.push({
                id: `choice_${sourceName.replace(/[^a-zA-Z0-9]/g, '_')}_halfelf_${identified.choices.length}`,
                source: sourceName,
                description: halfElfMatch[0], // Full matched string for description
                number_of_abilities_to_choose: numScoresToChoose,
                points_per_ability: choiceBonusValue,
                total_points_to_allocate: numScoresToChoose * choiceBonusValue,
                options: uniqueAbilityCodes
            });
        }
        return identified; // Successfully parsed, return early
    }

    // New Regex for patterns like "+1 to Dexterity" (if not part of the compound pattern handled above)
    const plusValueToAbilityRegex = /([+-]\d+)\s+to\s+([\w\s]+)/gi;
    let matchPlusValue;
    while ((matchPlusValue = plusValueToAbilityRegex.exec(descriptionText)) !== null) {
        const bonusValueStrPM = matchPlusValue[1]; // e.g., "+1" or "-1"
        const abilityNameFullPM = matchPlusValue[2].trim().toLowerCase(); // e.g., "dexterity"
        const bonusValuePM = parseInt(bonusValueStrPM.replace('+', ''), 10);

        if (abilityScoreMap[abilityNameFullPM]) {
            // Avoid double-adding if a more specific regex like "Your X score increases by Y" also matches.
            // This is a simple safeguard. More complex logic might be needed if descriptions become very tricky.
            const alreadyAddedByFixedRegex = identified.fixed.some(
                f => f.abilityName === abilityScoreMap[abilityNameFullPM] &&
                     f.bonusValue === bonusValuePM &&
                     descriptionText.includes(`Your ${abilityNameFullPM} score increases by ${Math.abs(bonusValuePM)}`) // Math.abs for "increases by"
            );
            if (!alreadyAddedByFixedRegex) {
                identified.fixed.push({ abilityName: abilityScoreMap[abilityNameFullPM], bonusValue: bonusValuePM });
            }
        }
    }

    // Regex for "Your X score increases by Y."
    const fixedRegex = /Your (\w+) score increases by (\d+)/gi;
    let match;
    while ((match = fixedRegex.exec(descriptionText)) !== null) {
        const abilityName = match[1].toLowerCase();
        const bonusValue = parseInt(match[2], 10);
        if (abilityScoreMap[abilityName]) {
            identified.fixed.push({ abilityName: abilityScoreMap[abilityName], bonusValue });
        }
    }

    // Regex for "Choose any ability score to increase by X." or "Increase any one ability score by X."
    // Example: "Choose any one ability score to increase by 2."
    // Example: "Increase one ability score of your choice by 2."
    // Example: "one ability score of your choice increases by 2"
    const chooseAnyRegex = /(?:Choose any|Increase) (one|two|three|an) ability score(?: of your choice)? (?:to increase |increases )?by (\d+)/gi;
    while ((match = chooseAnyRegex.exec(descriptionText)) !== null) {
        const numScoresToChoose = parseWordToNumber(match[1] === 'an' ? 'one' : match[1]);
        const bonusValue = parseInt(match[2], 10);
        if (numScoresToChoose > 0 && bonusValue > 0) {
            identified.choices.push({
                id: `choice_${sourceName.replace(/[^a-zA-Z0-9]/g, '_')}_${identified.choices.length}`,
                source: sourceName,
                description: match[0],
                number_of_abilities_to_choose: numScoresToChoose,
                points_per_ability: bonusValue,
                total_points_to_allocate: numScoresToChoose * bonusValue,
                options: uniqueAbilityCodes // Allows choosing from any ability
            });
        }
    }

    // Regex for "Increase one ability score by X and another ability score by Y."
    // Example: "Increase one ability score by 2 and another ability score by 1."
    const increaseTwoDifferentRegex = /Increase one ability score by (\d+) and another ability score by (\d+)/gi;
    while ((match = increaseTwoDifferentRegex.exec(descriptionText)) !== null) {
        const bonus1 = parseInt(match[1], 10);
        const bonus2 = parseInt(match[2], 10);
        // This creates two separate choices, as they are distinct applications.
        // Or, it could be one choice with two parts, but current model is simpler.
        // For now, let's model as two choices of "pick 1, get X" and "pick 1, get Y, must be different"
        // This specific phrasing implies two distinct choices that must target different abilities.
        // A more complex UI might handle this as one "choice group".
        // For now: two distinct choices, UI later needs to enforce "different".
        identified.choices.push({
            id: `choice_${sourceName.replace(/[^a-zA-Z0-9]/g, '_')}_${identified.choices.length}`,
            source: `${sourceName} (Part 1)`,
            description: `Increase one ability score by ${bonus1} (must be different from other choice part)`,
            number_of_abilities_to_choose: 1,
            points_per_ability: bonus1,
            total_points_to_allocate: bonus1,
            options: uniqueAbilityCodes
        });
        identified.choices.push({
            id: `choice_${sourceName.replace(/[^a-zA-Z0-9]/g, '_')}_${identified.choices.length}`,
            source: `${sourceName} (Part 2)`,
            description: `Increase another ability score by ${bonus2} (must be different from other choice part)`,
            number_of_abilities_to_choose: 1,
            points_per_ability: bonus2,
            total_points_to_allocate: bonus2,
            options: uniqueAbilityCodes
        });
    }

    // Regex for "Your X, Y, and Z scores each increase by N."
    const multipleSpecificScoresRegex = /Your ([\w\s,]+(?:and \w+)?) scores each increase by (\d+)/gi;
    while ((match = multipleSpecificScoresRegex.exec(descriptionText)) !== null) {
        const abilitiesListStr = match[1];
        const bonusValue = parseInt(match[2], 10);
        const abilities = parseAbilityList(abilitiesListStr, abilityScoreMap);
        abilities.forEach(abilityName => {
            if (abilityScoreMap[abilityName.toLowerCase()]) { // Ensure mapping before pushing
                 identified.fixed.push({ abilityName: abilityScoreMap[abilityName.toLowerCase()], bonusValue });
            } else if (Object.values(abilityScoreMap).includes(abilityName)) { // If already an ABBR
                 identified.fixed.push({ abilityName: abilityName, bonusValue });
            }
        });
    }


    // Regex for "Choose N ability scores from [list] to increase by Y"
    // Example: "Choose two ability scores from Strength, Dexterity, or Constitution to increase by 1."
    const chooseNFromListRegex = /Choose (one|two|three|four|five|six) ability scores from ([\w\s,]+(?:or \w+)?) to increase by (\d+)/gi;
    while ((match = chooseNFromListRegex.exec(descriptionText)) !== null) {
        const numToChoose = parseWordToNumber(match[1]);
        const abilityListStr = match[2];
        const bonusValue = parseInt(match[3], 10);
        const options = parseAbilityList(abilityListStr, abilityScoreMap);
        if (numToChoose > 0 && bonusValue > 0 && options.length > 0) {
            identified.choices.push({
                id: `choice_${sourceName.replace(/[^a-zA-Z0-9]/g, '_')}_${identified.choices.length}`,
                source: sourceName,
                description: match[0],
                number_of_abilities_to_choose: numToChoose,
                points_per_ability: bonusValue,
                total_points_to_allocate: numToChoose * bonusValue,
                options // This is already filtered by parseAbilityList
            });
        }
    }

    // Regex for "Two ability scores of your choice increase by 1." (general choice)
    // Example: "Two ability scores of your choice increase by 1."
    const NAbilitiesOfChoiceRegex = /(\w+) ability scores of your choice increase by (\d+)/gi;
    while ((match = NAbilitiesOfChoiceRegex.exec(descriptionText)) !== null) {
        const numToChoose = parseWordToNumber(match[1]);
        const bonusValue = parseInt(match[2], 10);
        if (numToChoose > 0 && bonusValue > 0) {
            identified.choices.push({
                id: `choice_${sourceName.replace(/[^a-zA-Z0-9]/g, '_')}_${identified.choices.length}`,
                source: sourceName,
                description: match[0],
                number_of_abilities_to_choose: numToChoose,
                points_per_ability: bonusValue,
                total_points_to_allocate: numToChoose * bonusValue,
                options: uniqueAbilityCodes // Any ability can be chosen
            });
        }
    }

    // Regex for "All of your ability scores increase by 1."
    const allScoresIncreaseRegex = /All (?:of your |your six )?ability scores increase by (\d+)/gi;
    while ((match = allScoresIncreaseRegex.exec(descriptionText)) !== null) {
        const bonusValue = parseInt(match[1], 10);
        uniqueAbilityCodes.forEach(abilityName => { // Iterate over unique codes
            identified.fixed.push({ abilityName, bonusValue });
        });
    }

    // Regex for "Your Charisma score increases by 2, and your Dexterity score increases by 1."
    const specificScoresMixedBonusesRegex = /Your (\w+) score increases by (\d+), and your (\w+) score increases by (\d+)/gi;
    while ((match = specificScoresMixedBonusesRegex.exec(descriptionText)) !== null) {
        const abilityName1 = match[1].toLowerCase();
        const bonusValue1 = parseInt(match[2], 10);
        const abilityName2 = match[3].toLowerCase();
        const bonusValue2 = parseInt(match[4], 10);

        if (abilityScoreMap[abilityName1]) {
            identified.fixed.push({ abilityName: abilityScoreMap[abilityName1], bonusValue: bonusValue1 });
        }
        if (abilityScoreMap[abilityName2]) {
            identified.fixed.push({ abilityName: abilityScoreMap[abilityName2], bonusValue: bonusValue2 });
        }
    }

    // Regex for simple format like "Strength +1, Dexterity +1"
    const simpleFormatRegex = /(\w+)\s*\+\s*(\d+)/gi;
    // Need to be careful this doesn't overlap too much with previous, or run it on segments.
    // For now, assume it's applied to the whole description.
    // To avoid double counting if "Your Strength score increases by 1" (already caught) and "Strength +1" (this regex) are both present
    // this should ideally be run if other patterns *don't* match, or fixed bonuses are stored in a way that prevents duplicates for same stat.
    // Current logic: add all found, then sum up. So duplicates are fine if they mean "total +2 from two sources".
    // But if it's the same sentence rephrased, it's an issue.
    // For now, let's assume descriptions are not intentionally redundant in this way.
    while ((match = simpleFormatRegex.exec(descriptionText)) !== null) {
        const abilityName = match[1].toLowerCase();
        const bonusValue = parseInt(match[2], 10);
        if (abilityScoreMap[abilityName]) {
            // Check if this exact bonus was already added by a more specific regex like "Your X score increases by Y"
            // This is a simple check; a more robust solution might involve processing text in stages or more complex state.
            const alreadyAdded = identified.fixed.some(f => f.abilityName === abilityScoreMap[abilityName] && f.bonusValue === bonusValue && descriptionText.includes(`Your ${match[1]} score increases by ${bonusValue}`));
            if (!alreadyAdded) {
                 identified.fixed.push({ abilityName: abilityScoreMap[abilityName], bonusValue });
            }
        }
    }


    return identified;
}


function getStatBonuses() {
    // Clear existing choices here as per plan, so it's fresh for this calculation run
    characterCreationData.step4_asi_choices = [];
    const bonuses = {
        STR: { race: 0, class: 0, background: 0 }, DEX: { race: 0, class: 0, background: 0 }, CON: { race: 0, class: 0, background: 0 },
        INT: { race: 0, class: 0, background: 0 }, WIS: { race: 0, class: 0, background: 0 }, CHA: { race: 0, class: 0, background: 0 }
    };
    // const abilityScoreMap = GLOBAL_ABILITY_SCORE_MAP; // Use global map

    function processTraits(traits, type, sourceNamePrefix) { // type is 'race' or 'class'
        if (traits && Array.isArray(traits)) {
            traits.forEach(trait => {
                if (trait.name === "Ability Score Increase" && trait.desc) {
                    console.log(`[DEBUG] getStatBonuses/processTraits: Identifying ASIs for ${type} trait '${trait.name}'. Desc:`, trait.desc);
                    const sourceFullName = `${sourceNamePrefix}: ${trait.name}`;
                    const asiResult = identifyASIs(trait.desc, sourceFullName, GLOBAL_ABILITY_SCORE_MAP);
                    console.log(`[DEBUG] getStatBonuses/processTraits: Identified ASIs for ${type} trait '${trait.name}': Fixed:`, JSON.parse(JSON.stringify(asiResult.fixed)), "Choices:", JSON.parse(JSON.stringify(asiResult.choices)));

                    asiResult.fixed.forEach(fixedBonus => {
                        if (bonuses[fixedBonus.abilityName]) {
                            if (type === 'race') bonuses[fixedBonus.abilityName].race += fixedBonus.bonusValue;
                            else if (type === 'class') bonuses[fixedBonus.abilityName].class += fixedBonus.bonusValue;
                        }
                    });
                    characterCreationData.step4_asi_choices.push(...asiResult.choices);
                }
            });
        }
    }

    // Process Race Bonuses from traits
    if (characterCreationData.step1_race_selection) {
        const raceName = characterCreationData.step1_race_selection.name || characterCreationData.step1_race_selection.slug;
        if (characterCreationData.step1_race_selection.traits) {
            processTraits(characterCreationData.step1_race_selection.traits, 'race', `Race (${raceName})`);
        }
    }
    if (characterCreationData.step1_parent_race_selection) {
        const parentRaceName = characterCreationData.step1_parent_race_selection.name || characterCreationData.step1_parent_race_selection.slug;
        if (characterCreationData.step1_parent_race_selection.traits) {
             processTraits(characterCreationData.step1_parent_race_selection.traits, 'race', `Parent Race (${parentRaceName})`);
        }
    }


    // Process Class Bonuses from traits
    if (characterCreationData.step2_selected_base_class) {
        const className = characterCreationData.step2_selected_base_class.name || characterCreationData.step2_selected_base_class.slug;
        if (characterCreationData.step2_selected_base_class.traits) {
            processTraits(characterCreationData.step2_selected_base_class.traits, 'class', `Class (${className})`);
        }
    }
    if (characterCreationData.step2_selected_archetype) {
        const archetypeName = characterCreationData.step2_selected_archetype.name || characterCreationData.step2_selected_archetype.slug;
        if (characterCreationData.step2_selected_archetype.traits) {
            processTraits(characterCreationData.step2_selected_archetype.traits, 'class', `Archetype (${archetypeName})`);
        }
    }


    // Process Background Bonuses
    const backgroundData = characterCreationData.step3_background_selection;
    if (backgroundData) {
        const backgroundName = backgroundData.name || backgroundData.slug || "Unknown Background";

        // Attempt 1: Structured bonuses from backgroundData.data.ability_score_bonuses (if applicable)
        // This existing logic can remain if backgroundData.data is a valid path and distinct source
        if (backgroundData.data && backgroundData.data.ability_score_bonuses && Array.isArray(backgroundData.data.ability_score_bonuses)) {
            console.log(`[DEBUG] getStatBonuses: Processing structured ASIs from backgroundData.data.ability_score_bonuses for ${backgroundName}`);
            backgroundData.data.ability_score_bonuses.forEach(bonus_info => {
                if (bonus_info.ability_score && bonus_info.ability_score.name && bonus_info.bonus) {
                    const abilityName = bonus_info.ability_score.name.toLowerCase();
                    const statAbbr = GLOBAL_ABILITY_SCORE_MAP[abilityName];
                    if (statAbbr && bonuses[statAbbr] && bonuses[statAbbr].background !== undefined) {
                        bonuses[statAbbr].background += parseInt(bonus_info.bonus, 10);
                    } else {
                        console.warn(`Unknown ability name or structure in background structured ASI: ${bonus_info.ability_score.name}`);
                    }
                }
            });
        }

        // NEW: Process ASIs from the benefits array
        let processedBenefitDescs = []; // To track descriptions processed from benefits
        if (backgroundData.benefits && Array.isArray(backgroundData.benefits)) {
            console.log(`[DEBUG] getStatBonuses: Processing ASIs from backgroundData.benefits for ${backgroundName}`);
            backgroundData.benefits.forEach(benefit => {
                if (benefit.type === "ability_score" && benefit.desc) {
                    processedBenefitDescs.push(benefit.desc.trim()); // Track for de-duplication with general text
                    const sourceFullName = `Background Benefit (${backgroundName}): ${benefit.name || 'ASI'}`;
                    console.log(`[DEBUG] getStatBonuses/backgroundBenefits: Identifying ASIs for '${sourceFullName}'. Desc:`, benefit.desc);
                    const benefitAsiResult = identifyASIs(benefit.desc, sourceFullName, GLOBAL_ABILITY_SCORE_MAP);
                    console.log(`[DEBUG] getStatBonuses/backgroundBenefits: Identified ASIs: Fixed:`, JSON.parse(JSON.stringify(benefitAsiResult.fixed)), "Choices:", JSON.parse(JSON.stringify(benefitAsiResult.choices)));

                    benefitAsiResult.fixed.forEach(fixedBonus => {
                        if (bonuses[fixedBonus.abilityName] && bonuses[fixedBonus.abilityName].background !== undefined) {
                            bonuses[fixedBonus.abilityName].background += fixedBonus.bonusValue;
                        } else {
                             console.warn(`[DEBUG] getStatBonuses/backgroundBenefits: bonuses[${fixedBonus.abilityName}] or .background is undefined for fixed bonus. Stat exists: ${!!bonuses[fixedBonus.abilityName]}`);
                        }
                    });
                    benefitAsiResult.choices.forEach(choice => {
                        if (!characterCreationData.step4_asi_choices.find(existingChoice => existingChoice.description === choice.description && existingChoice.source.startsWith(`Background Benefit (${backgroundName})`))) {
                            characterCreationData.step4_asi_choices.push(choice);
                        } else {
                            console.log(`[DEBUG] getStatBonuses/backgroundBenefits: Duplicate choice (from benefit) detected and skipped: ${choice.description}`);
                        }
                    });
                }
            });
        }

        // Attempt 2: Parse from text descriptions (desc and feature_desc from backgroundData.data or backgroundData directly)
        let combinedBackgroundText = "";
        const dataContext = backgroundData.data || backgroundData; // Prefer .data if it exists, else use backgroundData directly

        if (typeof dataContext.desc === 'string') {
            combinedBackgroundText += dataContext.desc + " ";
        }
        // Only add feature_desc if it's different from general desc and not already covered by benefits
        if (typeof dataContext.feature_desc === 'string' && dataContext.feature_desc !== dataContext.desc) {
            // combinedBackgroundText += dataContext.feature_desc + " "; // This line was commented out in thought, let's keep it for broader check unless it causes issues.
        }

        const trimmedCombinedText = combinedBackgroundText.trim();

        if (trimmedCombinedText && !processedBenefitDescs.includes(trimmedCombinedText)) {
            console.log(`[DEBUG] getStatBonuses: Identifying ASIs from background general text for '${backgroundName}'. Combined Text:`, trimmedCombinedText);
            const sourceFullName = `Background Text (${backgroundName})`; // Differentiate source
            const bgTextAsiResult = identifyASIs(trimmedCombinedText, sourceFullName, GLOBAL_ABILITY_SCORE_MAP);
            console.log(`[DEBUG] getStatBonuses/backgroundText: Identified ASIs: Fixed:`, JSON.parse(JSON.stringify(bgTextAsiResult.fixed)), "Choices:", JSON.parse(JSON.stringify(bgTextAsiResult.choices)));

            bgTextAsiResult.fixed.forEach(fixedBonus => {
                if (bonuses[fixedBonus.abilityName] && bonuses[fixedBonus.abilityName].background !== undefined) {
                    bonuses[fixedBonus.abilityName].background += fixedBonus.bonusValue;
                } else {
                     console.warn(`[DEBUG] getStatBonuses/backgroundText: bonuses[${fixedBonus.abilityName}] or .background is undefined for fixed bonus. Stat exists: ${!!bonuses[fixedBonus.abilityName]}`);
                }
            });
            bgTextAsiResult.choices.forEach(choice => {
                // Check against choices from benefits AND from other general text parsing
                if (!characterCreationData.step4_asi_choices.find(existingChoice => existingChoice.description === choice.description && (existingChoice.source.startsWith(`Background Benefit (${backgroundName})`) || existingChoice.source.startsWith(`Background Text (${backgroundName})`)) )) {
                    characterCreationData.step4_asi_choices.push(choice);
                } else {
                    console.log(`[DEBUG] getStatBonuses/backgroundText: Duplicate choice (from text) detected and skipped: ${choice.description}`);
                }
            });
        } else if (trimmedCombinedText && processedBenefitDescs.includes(trimmedCombinedText)) {
            console.log(`[DEBUG] getStatBonuses: General background text for '${backgroundName}' is identical to an already processed ASI benefit. Skipping general text parsing for ASIs.`);
        }
    } else {
        console.log("[DEBUG] getStatBonuses: No backgroundData found for ASI processing.");
    }

    // The old logic for raceData.ability_score_bonuses is now replaced.
    // If the API also provides structured bonuses in `ability_score_bonuses` AND these are meant to be
    // *additional* to what's in traits, then that logic would need to be reinstated or merged carefully.
    // Based on the task, parsing traits is the primary source now.

    console.log("[DEBUG] getStatBonuses: Final bonuses object:", JSON.parse(JSON.stringify(bonuses)));
    console.log("[DEBUG] getStatBonuses: Final step4_asi_choices:", JSON.parse(JSON.stringify(characterCreationData.step4_asi_choices)));
    console.log("[DEBUG] Exiting getStatBonuses.");
    return bonuses;
}

function prepareASIChoiceDataForUI() {
    console.log("[DEBUG] Entering prepareASIChoiceDataForUI. Current step4_asi_choices:", JSON.parse(JSON.stringify(characterCreationData.step4_asi_choices)));
    characterCreationData.step4_unallocated_asi_points = 0;
    characterCreationData.step4_asi_choice_details_for_ui = [];

    if (characterCreationData.step4_asi_choices && characterCreationData.step4_asi_choices.length > 0) {
        characterCreationData.step4_asi_choices.forEach(choice => {
            characterCreationData.step4_unallocated_asi_points += choice.total_points_to_allocate;
            characterCreationData.step4_asi_choice_details_for_ui.push({
                ...choice, // Spread existing choice properties
                allocated_points_for_this_choice: 0 // Initialize points used for this specific choice
            });
        });
    }
    console.log("[DEBUG] prepareASIChoiceDataForUI: Resulting step4_unallocated_asi_points:", characterCreationData.step4_unallocated_asi_points);
    console.log("[DEBUG] prepareASIChoiceDataForUI: Resulting step4_asi_choice_details_for_ui:", JSON.parse(JSON.stringify(characterCreationData.step4_asi_choice_details_for_ui)));
}

function renderASIChoicesUI() {
    console.log("[DEBUG] Entering renderASIChoicesUI.");
    console.log("[DEBUG] renderASIChoicesUI data: step4_asi_choice_details_for_ui:", JSON.parse(JSON.stringify(characterCreationData.step4_asi_choice_details_for_ui)),
                "step4_unallocated_asi_points:", characterCreationData.step4_unallocated_asi_points,
                "step4_allocated_choice_bonuses:", JSON.parse(JSON.stringify(characterCreationData.step4_allocated_choice_bonuses)));
    const asiChoiceListEl = document.getElementById('asi-choice-list');
    const totalRemainingPointsEl = document.getElementById('total-remaining-choice-points');
    console.log("[DEBUG] renderASIChoicesUI: Found #asi-choice-list:", asiChoiceListEl ? 'Yes' : 'No');
    console.log("[DEBUG] renderASIChoicesUI: Found #total-remaining-choice-points:", totalRemainingPointsEl ? 'Yes' : 'No');


    if (!asiChoiceListEl || !totalRemainingPointsEl) {
        console.error("ASI Choice UI elements not found!");
        return;
    }

    asiChoiceListEl.innerHTML = ''; // Clear previous list

    characterCreationData.step4_asi_choice_details_for_ui.forEach(choice => {
        const li = document.createElement('li');
        const pointsRemainingForThis = choice.total_points_to_allocate - choice.allocated_points_for_this_choice;
        li.textContent = `${choice.source}: ${choice.description} (Points remaining for this choice: ${pointsRemainingForThis})`;
        if (pointsRemainingForThis <= 0) {
            li.classList.add('choice-completed');
        }
        asiChoiceListEl.appendChild(li);
    });

    totalRemainingPointsEl.textContent = characterCreationData.step4_unallocated_asi_points;

    // Update displayed choice bonuses on stats
    characterCreationData.step4_ability_scores.forEach(stat => {
        const choiceBonusEl = document.querySelector(`.stat-bonus.choice-bonus[data-stat='${stat}']`);
        if (choiceBonusEl) {
            const bonusValue = characterCreationData.step4_allocated_choice_bonuses[stat] || 0;
            choiceBonusEl.textContent = `+${bonusValue}`;
            choiceBonusEl.style.display = bonusValue > 0 ? 'inline-block' : 'none';
        }
    });
}


function handleAsiAllocateClick(event) {
    const targetStat = event.target.dataset.stat;
    const asiAllocationMessageEl = document.getElementById('asi-allocation-message');

    if (characterCreationData.step4_unallocated_asi_points <= 0) {
        asiAllocationMessageEl.textContent = "No more ASI points to allocate.";
        asiAllocationMessageEl.style.display = 'block';
        return;
    }

    // Find the first available ASI choice to allocate from
    let currentChoiceToAllocateFrom = null;
    for (let i = 0; i < characterCreationData.step4_asi_choice_details_for_ui.length; i++) {
        if (characterCreationData.step4_asi_choice_details_for_ui[i].allocated_points_for_this_choice < characterCreationData.step4_asi_choice_details_for_ui[i].total_points_to_allocate) {
            currentChoiceToAllocateFrom = characterCreationData.step4_asi_choice_details_for_ui[i];
            break;
        }
    }

    if (!currentChoiceToAllocateFrom) {
        asiAllocationMessageEl.textContent = "Error: Unallocated points exist, but no available choice found.";
        asiAllocationMessageEl.style.display = 'block';
        console.error("Mismatch between unallocated_asi_points and available choices.");
        return;
    }

    // Simplified logic: each click allocates +1.
    // More complex logic would be needed to enforce "points_per_ability > 1" for a single click
    // or "number_of_abilities_to_choose" if a choice requires picking multiple distinct abilities.
    // For now, this is a pool of +1s. The description on the choice list item provides context.

    characterCreationData.step4_unallocated_asi_points -= 1;
    currentChoiceToAllocateFrom.allocated_points_for_this_choice += 1;
    characterCreationData.step4_allocated_choice_bonuses[targetStat] = (characterCreationData.step4_allocated_choice_bonuses[targetStat] || 0) + 1;

    asiAllocationMessageEl.textContent = `+1 allocated to ${targetStat} from choice: ${currentChoiceToAllocateFrom.source}.`;
    asiAllocationMessageEl.style.display = 'block';

    renderASIChoicesUI();
    renderMainStatDisplay(); // Update totals which now include choice bonuses
    saveCharacterDataToSession();
    updateAndSaveFinalAbilityScores(); // Recalculate final scores
}


function getVitalStats() {
    let vital = [];
    const raceData = characterCreationData.step1_race_selection;
    const classData = characterCreationData.step2_selected_base_class;
    // const abilityScoreMap = GLOBAL_ABILITY_SCORE_MAP; // Use global map

    // Always suggest Constitution
    if (!vital.includes("CON")) vital.push("CON");

    // From Class
    if (classData) {
        // Primary ability for spellcasters
        if (classData.spellcasting && classData.spellcasting.spellcasting_ability) {
            const primaryCastingStat = GLOBAL_ABILITY_SCORE_MAP[classData.spellcasting.spellcasting_ability.name.toLowerCase()];
            if (primaryCastingStat && !vital.includes(primaryCastingStat)) {
                vital.push(primaryCastingStat);
            }
        }
        // Common key stats for certain class archetypes (heuristic)
        const className = classData.name.toLowerCase();
        if (className.includes("fighter") || className.includes("paladin") || className.includes("barbarian")) {
            if (!vital.includes("STR")) vital.push("STR");
        }
        if (className.includes("ranger") || className.includes("rogue") || className.includes("monk")) {
            if (!vital.includes("DEX")) vital.push("DEX");
        }
        if (className.includes("cleric") || className.includes("druid")) {
            if (!vital.includes("WIS")) vital.push("WIS");
        }
        if (className.includes("wizard")) {
            if (!vital.includes("INT")) vital.push("INT");
        }
        if (className.includes("sorcerer") || className.includes("bard") || className.includes("warlock")) {
            if (!vital.includes("CHA")) vital.push("CHA");
        }
    }

    // From Race (stats that get bonuses)
    if (raceData && raceData.ability_score_bonuses && Array.isArray(raceData.ability_score_bonuses)) {
        raceData.ability_score_bonuses.forEach(bonus => {
            if (bonus.bonus > 0) {
                const statAbbr = GLOBAL_ABILITY_SCORE_MAP[bonus.ability_score.name.toLowerCase()];
                if (statAbbr && !vital.includes(statAbbr)) {
                    vital.push(statAbbr);
                }
            }
        });
    }

    let uniqueVital = [...new Set(vital)]; // Should be redundant if checks are done before pushing

    // Simple prioritization if list is too long (e.g., > 3 prominent stats)
    // This aims to provide the most impactful suggestions.
    if (uniqueVital.length > 3) {
        let prioritizedVital = [];
        // 1. Primary casting stat (if any)
        if (classData && classData.spellcasting && classData.spellcasting.spellcasting_ability) {
            const primaryCastingStat = GLOBAL_ABILITY_SCORE_MAP[classData.spellcasting.spellcasting_ability.name.toLowerCase()];
            if (primaryCastingStat && uniqueVital.includes(primaryCastingStat)) {
                prioritizedVital.push(primaryCastingStat);
            }
        }
        // 2. Constitution
        if (uniqueVital.includes("CON") && !prioritizedVital.includes("CON")) {
            prioritizedVital.push("CON");
        }
        // 3. Other class-suggested stats or major racial bonus stats
        const classSpecificSuggestions = [];
        if (classData) {
            const className = classData.name.toLowerCase();
            if (className.includes("fighter") || className.includes("paladin") || className.includes("barbarian")) classSpecificSuggestions.push("STR");
            if (className.includes("ranger") || className.includes("rogue") || className.includes("monk")) classSpecificSuggestions.push("DEX");
            // Add more as needed
        }
        for (const stat of classSpecificSuggestions) {
            if (prioritizedVital.length < 3 && uniqueVital.includes(stat) && !prioritizedVital.includes(stat)) {
                prioritizedVital.push(stat);
            }
        }
        // Fill with any stat that received a racial bonus > 0
        if (raceData && raceData.ability_score_bonuses) {
            for (const bonus of raceData.ability_score_bonuses) {
                if (prioritizedVital.length < 3 && bonus.bonus > 0) {
                    const statAbbr = GLOBAL_ABILITY_SCORE_MAP[bonus.ability_score.name.toLowerCase()];
                    if (statAbbr && uniqueVital.includes(statAbbr) && !prioritizedVital.includes(statAbbr)) {
                        prioritizedVital.push(statAbbr);
                    }
                }
            }
        }
        // If still not full, take from the remaining uniqueVital
        for (const stat of uniqueVital) {
            if (prioritizedVital.length < 3 && !prioritizedVital.includes(stat)) {
                prioritizedVital.push(stat);
            }
        }
        uniqueVital = prioritizedVital.slice(0, 3); // Ensure it's max 3
    }

    console.log("Determined Vital Stats:", uniqueVital);
    return uniqueVital;
}

function updateDisplayedBonuses() {
    console.log("[DEBUG] Entering updateDisplayedBonuses. Current step4_stat_bonuses:", JSON.parse(JSON.stringify(characterCreationData.step4_stat_bonuses)));
    characterCreationData.step4_ability_scores.forEach(stat => {
        const raceBonusEl = document.querySelector(`.stat-bonus.race-bonus[data-stat='${stat}']`);
        const classBonusEl = document.querySelector(`.stat-bonus.class-bonus[data-stat='${stat}']`);
        const backgroundBonusEl = document.querySelector(`.stat-bonus.background-bonus[data-stat='${stat}']`); // New element

        if (raceBonusEl) {
            raceBonusEl.textContent = `+${(characterCreationData.step4_stat_bonuses[stat] && characterCreationData.step4_stat_bonuses[stat].race) || 0}`;
        }
        if (classBonusEl) {
            classBonusEl.textContent = `+${(characterCreationData.step4_stat_bonuses[stat] && characterCreationData.step4_stat_bonuses[stat].class) || 0}`;
        }
        if (backgroundBonusEl) { // Update background bonus display
            backgroundBonusEl.textContent = `+${(characterCreationData.step4_stat_bonuses[stat] && characterCreationData.step4_stat_bonuses[stat].background) || 0}`;
        }
    });
}

function renderMainStatDisplay() {
    console.log("[DEBUG] Entering renderMainStatDisplay.");
    console.log("[DEBUG] renderMainStatDisplay data: step4_assigned_stats:", JSON.parse(JSON.stringify(characterCreationData.step4_assigned_stats)),
                "step4_stat_bonuses:", JSON.parse(JSON.stringify(characterCreationData.step4_stat_bonuses)),
                "step4_allocated_choice_bonuses:", JSON.parse(JSON.stringify(characterCreationData.step4_allocated_choice_bonuses)));
    characterCreationData.step4_ability_scores.forEach(stat => {
        const assignedValueEl = document.querySelector(`.stat-assigned-value[data-stat='${stat}']`);
        const totalEl = document.querySelector(`.stat-total[data-stat='${stat}']`);

        const assignedValue = characterCreationData.step4_assigned_stats[stat] || '-';
        assignedValueEl.textContent = assignedValue;

        if (assignedValue !== '-') {
            const raceBonus = (characterCreationData.step4_stat_bonuses[stat] && characterCreationData.step4_stat_bonuses[stat].race) || 0;
            const classBonus = (characterCreationData.step4_stat_bonuses[stat] && characterCreationData.step4_stat_bonuses[stat].class) || 0;
            const backgroundBonus = (characterCreationData.step4_stat_bonuses[stat] && characterCreationData.step4_stat_bonuses[stat].background) || 0;
            const choiceBonusTotal = (characterCreationData.step4_allocated_choice_bonuses && characterCreationData.step4_allocated_choice_bonuses[stat]) ?
                parseInt(characterCreationData.step4_allocated_choice_bonuses[stat]) : 0;
            totalEl.textContent = parseInt(assignedValue) + raceBonus + classBonus + backgroundBonus + choiceBonusTotal;
        } else {
            totalEl.textContent = '-';
        }
    });
    updateDisplayedBonuses(); // Ensure bonuses are also up-to-date
    console.log("Main stat display rendered.");
}

function renderAssignableDicePool(diceValues) {
    const assignableDicePool = document.getElementById('assignable-dice-pool');
    assignableDicePool.innerHTML = ''; // Clear existing dice

    // Create a frequency map of assigned dice values
    const assignedValues = Object.values(characterCreationData.step4_assigned_stats);
    const assignedCounts = {};
    assignedValues.forEach(val => {
        if (val !== null) { // only count actual assigned values
            assignedCounts[val] = (assignedCounts[val] || 0) + 1;
        }
    });

    // Create a frequency map of available dice values
    const availableCounts = {};
    diceValues.forEach(val => {
        availableCounts[val] = (availableCounts[val] || 0) + 1;
    });

    // Display each unique dice value, considering how many are used
    const uniqueDiceValues = [...new Set(diceValues)].sort((a, b) => b - a); // Display in descending order

    uniqueDiceValues.forEach(value => {
        const totalAvailable = availableCounts[value] || 0;
        const totalAssignedToThisValue = assignedCounts[value] || 0;
        const numberToDisplay = totalAvailable - totalAssignedToThisValue;

        for (let i = 0; i < numberToDisplay; i++) {
            const diceDiv = document.createElement('div');
            diceDiv.classList.add('dice-value');
            diceDiv.textContent = value;
            if (characterCreationData.step4_selected_dice_value === value && i === 0 && numberToDisplay > 0) { // Highlight only one instance if multiple are same value
                // This simple selection highlight might need refinement if multiple identical values are present
                // and one is selected. For now, highlights the first available one that matches.
                diceDiv.classList.add('selected');
            }
            diceDiv.addEventListener('click', handleDicePoolClick);
            assignableDicePool.appendChild(diceDiv);
        }
    });
    // Add placeholders for any dice that were assigned but now the source (standard/rolled) has changed
    // or if a value was assigned that's not in the current diceValues (should ideally not happen with proper logic)
    Object.entries(characterCreationData.step4_assigned_stats).forEach(([stat, value]) => {
        if (value !== null && !diceValues.includes(value)) {
            // This indicates a mismatch, possibly log an error or handle gracefully
            // For now, we assume assigned_stats are cleared if dice source changes.
        }
    });
}

function handleDicePoolClick(event) {
    const clickedValue = parseInt(event.target.textContent);
    characterCreationData.step4_selected_dice_value = clickedValue;

    // Update visual selection in the pool
    document.querySelectorAll('#assignable-dice-pool .dice-value').forEach(el => el.classList.remove('selected'));
    event.target.classList.add('selected');

    console.log("Selected dice value from pool:", clickedValue);
    saveCharacterDataToSession();
}

function handleRollDiceClick() {
    const rollDiceWarning = document.getElementById('roll-dice-warning'); // Get warning element again
    if (characterCreationData.step4_dice_rolled_once) {
        alert("You have already rolled the dice. You cannot roll again.");
        return;
    }

    if (confirm("Warning: Rolling dice will override the standard array values and can only be done once. Are you sure you want to proceed?")) {
        characterCreationData.step4_rolled_stats = generate4d6DropLowest();
        characterCreationData.step4_dice_rolled_once = true;
        characterCreationData.step4_assigned_stats = {}; // Clear assignments
        characterCreationData.step4_selected_dice_value = null; // Clear selected dice from pool

        document.getElementById('roll-dice-button').disabled = true;
        rollDiceWarning.style.display = 'block'; // Show warning text permanently after roll

        console.log("Dice rolled:", characterCreationData.step4_rolled_stats);
        loadStep3Logic(); // Reload/re-render Step 3 UI with new dice
        // saveCharacterDataToSession(); // loadStep3Logic calls save and also calls updateAndSaveFinalAbilityScores
        updateAndSaveFinalAbilityScores(); // Explicitly call here to ensure scores are reset based on new empty assignments
    }
}

function handleStatAssignmentClick(event) {
    const targetStat = event.target.dataset.stat;
    if (!targetStat) return; // Clicked somewhere else in the block

    const selectedDiceValue = characterCreationData.step4_selected_dice_value;

    if (selectedDiceValue === null) {
        // If a stat is clicked without a dice value selected, and that stat currently has a value,
        // make that value available again in the pool.
        if (characterCreationData.step4_assigned_stats[targetStat] !== null && characterCreationData.step4_assigned_stats[targetStat] !== undefined) {
            console.log(`Unassigning ${characterCreationData.step4_assigned_stats[targetStat]} from ${targetStat}`);
            characterCreationData.step4_assigned_stats[targetStat] = null;
        } else {
            alert("Please select a dice roll from the 'Available Rolls' pool first.");
        }
    } else {
        // If there was a value previously assigned to this stat, make it available again ( conceptually)
        // The renderAssignableDicePool will handle making it visible if it's part of the current source array.
        const oldValue = characterCreationData.step4_assigned_stats[targetStat];
        if (oldValue !== null && oldValue !== undefined) {
        }

        // Check if the selected dice value is already assigned to another stat
        // This simple check prevents direct assignment if already used.
        // More complex logic could allow swapping. For now, user must unassign first.
        let valueAlreadyAssignedElsewhere = false;
        for (const stat in characterCreationData.step4_assigned_stats) {
            if (characterCreationData.step4_assigned_stats[stat] === selectedDiceValue && stat !== targetStat) {
                // A simple count check for available vs assigned of this value
                const sourceStats = characterCreationData.step4_rolled_stats || characterCreationData.step4_standard_stats;
                const countInSource = sourceStats.filter(s => s === selectedDiceValue).length;
                const countAssigned = Object.values(characterCreationData.step4_assigned_stats).filter(s => s === selectedDiceValue).length;

                if (countAssigned >= countInSource) {
                    valueAlreadyAssignedElsewhere = true;
                    break;
                }
            }
        }

        if (valueAlreadyAssignedElsewhere) {
            alert(`The value ${selectedDiceValue} is already assigned as many times as it appears in your rolls/standard array. Please unassign it first if you want to move it.`);
            return;
        }

        characterCreationData.step4_assigned_stats[targetStat] = selectedDiceValue;
        console.log(`Assigned ${selectedDiceValue} to ${targetStat}`);

        // Optional: Clear selected dice from pool after assignment, requiring re-selection for next assignment
        // characterCreationData.step4_selected_dice_value = null;
        // document.querySelectorAll('#assignable-dice-pool .dice-value.selected').forEach(el => el.classList.remove('selected'));
    }

    // Re-render displays
    let currentStatsToUse = characterCreationData.step4_rolled_stats || characterCreationData.step4_standard_stats;
    renderAssignableDicePool(currentStatsToUse);
    renderMainStatDisplay();
    saveCharacterDataToSession();
    updateAndSaveFinalAbilityScores(); // Update final scores after stat assignment changes
}

function loadStep3Logic() {
    console.log("[DEBUG] Entering loadStep3Logic. Current characterCreationData:", JSON.parse(JSON.stringify(characterCreationData)));
    console.log("[DEBUG] loadStep3Logic: Race Selection:", JSON.parse(JSON.stringify(characterCreationData.step1_race_selection)));
    console.log("[DEBUG] loadStep3Logic: Class Selection:", JSON.parse(JSON.stringify(characterCreationData.step2_selected_base_class)));
    console.log("[DEBUG] loadStep3Logic: Background Selection:", JSON.parse(JSON.stringify(characterCreationData.step3_background_selection)));
    console.log("Loading Step 3 logic (Ability Scores)...");
    characterCreationData.step4_allocated_choice_bonuses = { STR: 0, DEX: 0, CON: 0, INT: 0, WIS: 0, CHA: 0 };
    characterCreationData.step4_unallocated_asi_points = 0;
    // characterCreationData.step4_asi_choices is cleared in getStatBonuses

    // Initialize/retrieve DOM elements for step 3
    // const vitalStatsDisplay = document.getElementById('vital-stats-display'); // Moved down
    const standardArrayDisplay = document.getElementById('standard-array-display');
    const rolledDiceDisplay = document.getElementById('rolled-dice-display');
    const rolledDiceValues = document.getElementById('rolled-dice-values');
    const rollDiceButton = document.getElementById('roll-dice-button');
    const rollDiceWarning = document.getElementById('roll-dice-warning'); // Added for the warning message
    const assignableDicePool = document.getElementById('assignable-dice-pool');

    // Initialize stat blocks for assignment listeners
    const statBlocks = document.querySelectorAll('.stat-block .stat-assigned-value');
    const asiAllocateButtons = document.querySelectorAll('.asi-allocate-button');


    // Get the vitalStatsDisplay element
    const vitalStatsDisplay = document.getElementById('vital-stats-display');

    // Calculate and store/update bonuses and vital stats (including ASI choices)
    // Ensure raceData and classData are available in characterCreationData as expected by helper functions
    if (characterCreationData.step1_race_selection && characterCreationData.step2_selected_base_class) {
        characterCreationData.step4_stat_bonuses = getStatBonuses(); // Uses data from characterCreationData
        characterCreationData.step4_vital_stats = getVitalStats();   // Uses data from characterCreationData
    } else {
        // Fallback if race/class data not yet fully loaded or selected
        console.warn("Race or Class data not fully available for Step 4 calculations. Using defaults for bonuses.");
        // Ensure the default structure includes background
        characterCreationData.step4_stat_bonuses = {
            STR: { race: 0, class: 0, background: 0 }, DEX: { race: 0, class: 0, background: 0 }, CON: { race: 0, class: 0, background: 0 },
            INT: { race: 0, class: 0, background: 0 }, WIS: { race: 0, class: 0, background: 0 }, CHA: { race: 0, class: 0, background: 0 }
        };
        characterCreationData.step4_vital_stats = ["CON"]; // Default vital stat
    }
    saveCharacterDataToSession(); // Save after calculating these

    // Display vital stats
    if (vitalStatsDisplay) {
        if (characterCreationData.step4_vital_stats && characterCreationData.step4_vital_stats.length > 0) {
            vitalStatsDisplay.textContent = characterCreationData.step4_vital_stats.join(', ');
        } else {
            vitalStatsDisplay.textContent = "None specific (General: CON)";
        }
    }

    // Display stat bonuses (now using the calculated ones)
    updateDisplayedBonuses(); // This function should read from characterCreationData.step4_stat_bonuses

    // Prepare and Render ASI Choice UI
    prepareASIChoiceDataForUI();
    renderASIChoicesUI();

    // The rest of loadStep3Logic (rendering dice pool, main stat display, button states) follows...
    // Determine which set of stats to use (standard or rolled)
    let currentStatsToDisplay = characterCreationData.step4_rolled_stats || characterCreationData.step4_standard_stats;

    if (characterCreationData.step4_rolled_stats) {
        standardArrayDisplay.style.display = 'none';
        rolledDiceValues.textContent = characterCreationData.step4_rolled_stats.join(', ');
        rolledDiceDisplay.style.display = 'block';
    } else {
        standardArrayDisplay.style.display = 'block';
        rolledDiceDisplay.style.display = 'none';
    }

    // Populate assignable dice pool
    renderAssignableDicePool(currentStatsToDisplay);

    // Update main stat display (assigned values and totals)
    renderMainStatDisplay();

    // Roll Dice Button state and event listener
    if (characterCreationData.step4_dice_rolled_once) {
        rollDiceButton.disabled = true;
        rollDiceWarning.style.display = 'block'; // Show warning if dice already rolled
    } else {
        rollDiceButton.disabled = false;
        rollDiceWarning.style.display = 'none'; // Hide warning if not yet rolled
    }

    // Display ASI Debug Texts if active
    if (IS_CHARACTER_CREATION_DEBUG_ACTIVE) {
        const debugOutputEl = document.getElementById('asi-debug-output');
        if (debugOutputEl) {
            if (asiDebugTextsCollection.length > 0) {
                let formattedDebugText = "";
                asiDebugTextsCollection.forEach(item => {
                    formattedDebugText += `Source: ${item.source}\n`;
                    formattedDebugText += `Text Processed:\n${item.text}\n\n`;
                    formattedDebugText += "------------------------------------\n";
                });
                debugOutputEl.textContent = formattedDebugText;
            } else {
                debugOutputEl.textContent = "No specific ASI-related texts were processed (or debug collection failed).";
            }
        }
    }

    // Remove existing listener to prevent multiple attachments if loadStep3Logic is called again
    const newRollDiceButton = rollDiceButton.cloneNode(true);
    rollDiceButton.parentNode.replaceChild(newRollDiceButton, rollDiceButton);
    newRollDiceButton.addEventListener('click', handleRollDiceClick);

    // Event listeners for stat assignment (on the stat boxes themselves)
    statBlocks.forEach(block => {
        const newBlock = block.cloneNode(true); // Clone to remove old listeners
        block.parentNode.replaceChild(newBlock, block);
        newBlock.addEventListener('click', handleStatAssignmentClick);
    });

    asiAllocateButtons.forEach(button => {
        const newButton = button.cloneNode(true);
        button.parentNode.replaceChild(newButton, button);
        newButton.addEventListener('click', handleAsiAllocateClick);
    });

    console.log("Step 3 characterCreationData:", JSON.parse(JSON.stringify(characterCreationData)));
    saveCharacterDataToSession();
    updateAndSaveFinalAbilityScores(); // Update final scores after Step 3 logic is loaded
}

// END STEP 3 LOGIC
// =====================================================================================================================

function updateAndSaveFinalAbilityScores() {
    console.log("Updating and saving final ability scores...");
    const abilities = characterCreationData.step4_ability_scores; // ["STR", "DEX", ...]
    if (!characterCreationData.ability_scores) {
        characterCreationData.ability_scores = {};
    }

    abilities.forEach(stat => {
        let baseValue = characterCreationData.step4_assigned_stats[stat];
        if (baseValue === null || baseValue === undefined || isNaN(parseInt(baseValue))) {
            baseValue = 10; // Default to 10 if not assigned or not a number
        } else {
            baseValue = parseInt(baseValue);
        }

        const raceBonus = (characterCreationData.step4_stat_bonuses[stat] && characterCreationData.step4_stat_bonuses[stat].race) ?
            parseInt(characterCreationData.step4_stat_bonuses[stat].race) : 0;

        const classBonus = (characterCreationData.step4_stat_bonuses[stat] && characterCreationData.step4_stat_bonuses[stat].class) ?
            parseInt(characterCreationData.step4_stat_bonuses[stat].class) : 0;

        const backgroundBonus = (characterCreationData.step4_stat_bonuses[stat] && characterCreationData.step4_stat_bonuses[stat].background) ?
            parseInt(characterCreationData.step4_stat_bonuses[stat].background) : 0;

        const choiceBonus = (characterCreationData.step4_allocated_choice_bonuses && characterCreationData.step4_allocated_choice_bonuses[stat]) ?
            parseInt(characterCreationData.step4_allocated_choice_bonuses[stat]) : 0;

        characterCreationData.ability_scores[stat] = baseValue + raceBonus + classBonus + backgroundBonus + choiceBonus;
    });

    console.log("Final ability_scores calculated (incl choice):", characterCreationData.ability_scores);
    saveCharacterDataToSession();
}


// Initialize first step
showStep(currentStep);
