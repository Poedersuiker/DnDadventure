let currentStep = 0; // Start at Step 0 (Introduction)
    const totalSteps = 9; // Last actual step number for choices

    // Global variables for character creation
    let allRacesData = null;
    let allClassesData = null; // Added for Step 2
    let allBackgroundsData = null;
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
    characterCreationData.step3_standard_stats = characterCreationData.step3_standard_stats || [15, 14, 13, 12, 10, 8];
    characterCreationData.step3_rolled_stats = characterCreationData.step3_rolled_stats || null;
    characterCreationData.step3_assigned_stats = characterCreationData.step3_assigned_stats || {}; // e.g., { STR: null, DEX: null, ... }
    characterCreationData.step3_stat_bonuses = characterCreationData.step3_stat_bonuses || {
        STR: { race: 0, class: 0 }, DEX: { race: 0, class: 0 }, CON: { race: 0, class: 0 },
        INT: { race: 0, class: 0 }, WIS: { race: 0, class: 0 }, CHA: { race: 0, class: 0 }
    };
    characterCreationData.step3_vital_stats = characterCreationData.step3_vital_stats || []; // e.g., ["STR", "CON"]
    characterCreationData.step3_dice_rolled_once = characterCreationData.step3_dice_rolled_once || false;
    characterCreationData.step3_selected_dice_value = characterCreationData.step3_selected_dice_value || null; // To store the currently clicked dice from the pool
    characterCreationData.step3_ability_scores = characterCreationData.step3_ability_scores || ["STR", "DEX", "CON", "INT", "WIS", "CHA"];
    // Step 4 keys
    characterCreationData.step4_selected_background_slug = characterCreationData.step4_selected_background_slug || null;
    characterCreationData.step4_background_selection = characterCreationData.step4_background_selection || null;
    characterCreationData.step4_background_details_text = characterCreationData.step4_background_details_text || '';

    let selectedRaceSlug = null;
    let selectedClassOrArchetypeSlug = null; // Renamed from selectedClassSlug

    const prevButton = document.getElementById('prev-button'); // This ID is now in wizard-top-controls
    const nextButton = document.getElementById('next-button'); // This ID is now in wizard-top-controls
    const cancelButton = document.getElementById('cancel-button'); // This ID is now in wizard-top-controls
    // Ensure stepIndicators query selector targets the one inside wizard-top-controls for active class updates
    const stepIndicators = document.querySelectorAll('.wizard-top-controls .step-indicator');


    const phbPlaceholders = {
        0: `<h3>Character Creation Steps</h3>
            <p>Your first step in playing an adventurer in the Dungeons & Dragons game is to imagine and create a character of your own. Your character is a combination of game statistics, roleplaying hooks, and your imagination. You choose a race (such as human or halfling) and a class (such as fighter or wizard). You also invent the personality, appearance, and backstory of your character.</p>
            <p>The process involves these main steps:<br><br>
            <strong>1. Choose a Race:</strong> Every character belongs to a race, one of the many intelligent humanoid species in the D&D world. The most common player character races are dwarves, elves, halflings, and humans. Your character’s race grants particular racial traits, such as special senses, or proficiency with certain weapons or tools.<br><br>
            <strong>2. Choose a Class:</strong> Every adventurer is a member of a character class. Class broadly describes a character’s vocation, special talents, and the tactics the character is most likely to employ when exploring a dungeon, fighting monsters, or engaging in a tense negotiation. <br><br>
            <strong>3. Determine Ability Scores:</strong> Much of what your character does in the game depends on his or her six abilities: Strength, Dexterity, Constitution, Intelligence, Wisdom, and Charisma. Each ability has a score, which is a number you record on your character sheet. The three main ways to generate ability scores are rolling dice (typically 4d6, dropping the lowest die, for each score), using a standard set of scores (15, 14, 13, 12, 10, 8), or point buy.<br><br>
            <strong>4. Describe Your Character:</strong> Once you know the basic game aspects of your character, it’s time to flesh out his or her history and personality. This includes your character's name, alignment, ideals, bonds, flaws, and background. A background describes your original occupation and provides benefits such as skill/tool proficiencies and starting equipment.<br><br>
            <strong>5. Choose Equipment:</strong> Your class and background determine your character’s starting equipment, including weapons, armor, and other adventuring gear. Alternatively, you can start with a number of gold pieces based on your class and spend them on items from the lists in the Player's Handbook.<br><br>
            <strong>Beyond 1st Level:</strong> As your character goes on adventures and overcomes challenges, he or she gains experience, represented by experience points. A character who reaches a specified experience point total advances in capability. This advancement is called gaining a level.</p>`,
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
        3: `<h3>3. Determine Ability Scores</h3>
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
        4: `<h3>4. Choose a Background</h3>
            <p>Your character's background describes where you came from, your original occupation, and your place in the D&D world. Your DM might offer additional backgrounds beyond those in the PHB.</p>
            <p>A background usually provides:
            <br> - Skill Proficiencies
            <br> - Tool Proficiencies
            <br> - Languages
            <br> - Starting Equipment
            <br> - A special background feature</p>
            <p>It also offers suggestions for personality traits, ideals, bonds, and flaws. These are roleplaying cues that help you bring your character to life.</p>
            <p>When you choose a background, it will grant you certain benefits and provide roleplaying hooks. Select a background from the list to see its details and what it offers your character.</p>`,
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

    function saveCharacterDataToSession() {
        try {
            sessionStorage.setItem('characterCreationData', JSON.stringify(characterCreationData));
            console.log("Character data saved to session storage.");
        } catch (e) {
            console.error("Error saving character data to session storage:", e);
        }
    }

    function showStep(stepNumber) {
        if (stepNumber === 0) {
            characterCreationData.step3_assigned_stats = {};
            characterCreationData.step3_dice_rolled_once = false;
            characterCreationData.step3_rolled_stats = null;
            saveCharacterDataToSession();
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
        if (stepNumber !== 4) {
            const backgroundListContainer = document.getElementById('background-list-container');
            const backgroundDescriptionContainer = document.getElementById('background-description-container');
            if (backgroundListContainer) backgroundListContainer.innerHTML = '';
            if (backgroundDescriptionContainer) backgroundDescriptionContainer.innerHTML = '';
        }

        // Hide all main content wizard steps first
        document.querySelectorAll('.wizard-step').forEach(step => {
            step.style.display = 'none';
        });

        // Show current step's main content (if it's not step 0)
        if (stepNumber > 0) {
            const currentStepContent = document.getElementById(`step-${stepNumber}`);
            if (currentStepContent) {
                currentStepContent.style.display = 'block';
            }
            // Special handling for Step 1 (Race Selection)
            if (stepNumber === 1) {
                if (!allRacesData) {
                    loadRaceStepData(); // Fetch data if not already fetched
                } else {
                    populateRaceList(allRacesData); // Repopulate if data exists
                }
                // Removed logic for displaying traits in a separate #race-traits-display.
                // handleRaceOrSubraceClick is now responsible for updating #race-description-container.
                // If no race is selected when step 1 loads, #race-description-container will be empty
                // or show a default message set by populateRaceList/handleRaceOrSubraceClick if applicable.
                // Ensure correct re-display if race was already selected
               if (selectedRaceSlug) {
                   const selectedLi = document.querySelector(`#race-selection-list li[data-slug="${selectedRaceSlug}"]`);
                   const raceDescContainer = document.getElementById('race-description-container');
                   if (selectedLi && raceDescContainer && (raceDescContainer.innerHTML === '' || raceDescContainer.innerHTML.includes('Loading details for'))) {
                       handleRaceOrSubraceClick({ target: selectedLi });
                   }
               }
            } else if (stepNumber === 2) {
               if (!allClassesData) {
                   loadClassStepData();
               } else {
                   populateClassList(allClassesData);
                   if (selectedClassOrArchetypeSlug) { // Renamed
                       // Ensure details are displayed if a class/archetype was already selected
                       const classDescContainer = document.getElementById('class-description-container');
                       if (classDescContainer && (classDescContainer.innerHTML === '' || classDescContainer.innerHTML.includes('Loading details for'))) {
                            displayClassDetails(selectedClassOrArchetypeSlug); // Renamed
                       } else if (classDescContainer && selectedClassOrArchetypeSlug && !classDescContainer.innerHTML.includes(selectedClassOrArchetypeSlug)) { // Renamed
                           // If a different class's details are showing, or it's empty but a slug is selected
                           displayClassDetails(selectedClassOrArchetypeSlug); // Renamed
                       }
                   }
               }
            } else if (stepNumber === 3) {
                loadStep3Logic(); // Call a new function to handle Step 3's specific logic
            } else if (stepNumber === 4) {
                if (!allBackgroundsData) {
                    loadBackgroundStepData();
                } else {
                    populateBackgroundList(allBackgroundsData);
                }
                if (characterCreationData.step4_selected_background_slug) {
                    displayBackgroundDetails(characterCreationData.step4_selected_background_slug);
                }
           }
        } else {
            // For step 0 (Introduction)
            const stepZeroContent = document.getElementById('step-0');
            if (stepZeroContent) {
                stepZeroContent.style.display = 'block';
            }
        }

        // Update PHB description placeholder
        const phbDescContainer = document.getElementById('phb-description');
        if (phbPlaceholders[stepNumber] !== undefined) { // Check if key exists, including 0
            phbDescContainer.innerHTML = phbPlaceholders[stepNumber];
        } else {
            phbDescContainer.innerHTML = `<p>Description for step ${stepNumber} will go here.</p>`; // Fallback
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
        if (currentStep === 1 && selectedRaceSlug) {
            try {
                // 1. Fetch the complete data for the selectedRaceSlug
                const raceResponse = await fetch(`/api/v2/races/${selectedRaceSlug}/`);
                if (!raceResponse.ok) {
                    throw new Error(`Failed to fetch race data for ${selectedRaceSlug}: ${raceResponse.status}`);
                }
                const raceData = await raceResponse.json();

                // 2. Store this fetched data in characterCreationData.step1_race_selection
                characterCreationData.step1_race_selection = raceData;

                // 3. Check if the fetched data has a subrace_of field
                if (raceData.subrace_of) {
                    // 4.a Extract the parent race slug
                    const parentRaceUrlParts = raceData.subrace_of.split('/').filter(part => part);
                    const parentRaceSlug = parentRaceUrlParts.pop();

                    if (parentRaceSlug) {
                        // 4.b Fetch the complete data for the parent race
                        const parentRaceResponse = await fetch(`/api/v2/races/${parentRaceSlug}/`);
                        if (!parentRaceResponse.ok) {
                            throw new Error(`Failed to fetch parent race data for ${parentRaceSlug}: ${parentRaceResponse.status}`);
                        }
                        const parentRaceData = await parentRaceResponse.json();
                        // 4.c Store this parent race data
                        characterCreationData.step1_parent_race_selection = parentRaceData;
                    } else {
                        console.warn("Could not extract parent race slug from:", raceData.subrace_of);
                        characterCreationData.step1_parent_race_selection = null;
                    }
                } else {
                    // 4.d If it's not a subrace, ensure step1_parent_race_selection is cleared
                    characterCreationData.step1_parent_race_selection = null;
                }

                // 5. Log the characterCreationData object
                console.log("Updated characterCreationData:", characterCreationData);
                saveCharacterDataToSession(); // Save after Step 1 data processing

            } catch (error) {
                console.error("Error processing race selection:", error);
                // Optionally, display an error to the user and/or prevent moving to the next step
                // alert(`Error: ${error.message}. Please try again.`);
                // return; // Prevent moving to next step
            }
        } else if (currentStep === 1 && !selectedRaceSlug) {
            alert("Please select a race before proceeding.");
            return;
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
        // Logic for Step 4: Background Selection
        else if (currentStep === 4) {
            if (!characterCreationData.step4_selected_background_slug) {
                alert("Please select a background before proceeding.");
                return;
            }
            // Data (step4_background_selection and step4_background_details_text)
            // should already be saved by displayBackgroundDetails when a background is selected.
            // Log to confirm.
            console.log("Proceeding from Step 4. Background data:", characterCreationData.step4_background_selection);
            saveCharacterDataToSession(); // Ensure latest state is saved, though likely redundant
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

    // --- New Functions for Step 1: Race Selection ---

    async function loadRaceStepData() {
        const raceListContainer = document.getElementById('race-list-container');
        try {
            const response = await fetch('/api/v2/races/');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json(); // data is now the array itself
            allRacesData = data; // Assign the array directly

            if (!Array.isArray(allRacesData)) {
                console.warn('Race data is not an array after fetch:', allRacesData);
                // Display error in UI as this is an unexpected format from the API
                if(raceListContainer) raceListContainer.innerHTML = '<p>Error: Race data is not in the expected format.</p>';
                allRacesData = []; // Initialize to empty array if the response is not as expected
            }

            populateRaceList(allRacesData); // Pass the array to the population function
        } catch (error) {
            console.error("Could not load race data:", error);
            if(raceListContainer) raceListContainer.innerHTML = '<p>Error loading races. Please try again later.</p>';
            allRacesData = []; // Ensure it's an empty array on error to prevent further issues
        }
    }

    function getSlugFromUrl(url) {
        if (!url || typeof url !== 'string') return null;
        // Example: "/api/v2/races/human/" -> "human"
        // Handles potential trailing slashes as well
        const parts = url.split('/').filter(part => part.length > 0);
        return parts.pop() || null; // Returns the last significant part
    }

    function populateRaceList(racesData) { // racesData is allRacesData
        const raceListContainer = document.getElementById('race-list-container');
        if (!raceListContainer) {
            console.error("Race list container not found!");
            return;
        }
        raceListContainer.innerHTML = ''; // Clear previous content

        const parentRaces = [];
        const subracesByParentSlug = {};

        // Segregate races and subraces
        racesData.forEach(raceItem => {
            if (raceItem.data && raceItem.data.subrace_of && typeof raceItem.data.subrace_of === 'string' && raceItem.data.subrace_of.trim() !== '') {
                const parentSlug = getSlugFromUrl(raceItem.data.subrace_of);
                if (parentSlug) {
                    if (!subracesByParentSlug[parentSlug]) {
                        subracesByParentSlug[parentSlug] = [];
                    }
                    subracesByParentSlug[parentSlug].push(raceItem);
                } else {
                    // Could be a parent race if subrace_of is present but invalid, or log warning
                    console.warn(`Could not extract parent slug from subrace_of URL: ${raceItem.data.subrace_of} for item ${raceItem.slug}`);
                    parentRaces.push(raceItem); // Treat as parent if slug extraction fails but field exists
                }
            } else {
                parentRaces.push(raceItem);
            }
        });

        const raceSelectionList = document.createElement('ul');
        raceSelectionList.id = 'race-selection-list';

        // Populate parent races and their subraces
        parentRaces.forEach(parentRaceItem => {
            const raceLi = document.createElement('li');
            raceLi.textContent = (parentRaceItem.data && parentRaceItem.data.name) ? parentRaceItem.data.name : parentRaceItem.slug;
            raceLi.dataset.slug = parentRaceItem.slug;
            raceSelectionList.appendChild(raceLi);

            const currentSubraces = subracesByParentSlug[parentRaceItem.slug];
            if (currentSubraces && currentSubraces.length > 0) {
                const subraceUl = document.createElement('ul');
                subraceUl.className = 'subrace-list'; // For styling indentation

                currentSubraces.forEach(subraceItem => {
                    const subLi = document.createElement('li');
                    subLi.textContent = (subraceItem.data && subraceItem.data.name) ? subraceItem.data.name : subraceItem.slug;
                    subLi.dataset.slug = subraceItem.slug;
                    subLi.dataset.parentRaceSlug = parentRaceItem.slug; // Set parent slug
                    subLi.classList.add('subrace-item'); // For styling
                    subraceUl.appendChild(subLi);
                });
                raceLi.appendChild(subraceUl); // Append subrace list to parent race's li
            }
        });

        raceListContainer.appendChild(raceSelectionList);
        // Re-attach event listener to the new list
        raceSelectionList.addEventListener('click', handleRaceOrSubraceClick);
    }

    async function handleRaceOrSubraceClick(event) { // Made async
        const clickedLi = event.target.closest('li'); // Get the actual LI that was clicked or contains the click target

        if (!clickedLi || !clickedLi.dataset || !clickedLi.dataset.slug) {
            // Click was not on a valid race/subrace list item or its child
            return;
        }

        const slug = clickedLi.dataset.slug;
        selectedRaceSlug = slug; // Update the global selected slug

        // Find the item (race or subrace) in the flat allRacesData list
        // allRacesData stores objects like { slug: "...", data: { actual race/subrace properties } }
        const selectedItem = allRacesData.find(item => item.slug === slug);

        const descriptionContainer = document.getElementById('race-description-container');
        if (!descriptionContainer) {
            console.error('Race description container not found!');
            return;
        }
        descriptionContainer.innerHTML = ''; // Clear previous content

        if (selectedItem && selectedItem.data) {
            const mainDesc = selectedItem.data.desc;
            let newHtmlContent = '';

            if (mainDesc) {
                newHtmlContent += `<h5>Description</h5><p>${mainDesc}</p>`;
            }

            newHtmlContent += '<h5>Traits</h5>';
            let traitsText = '';
            if (mainDesc) {
                traitsText += `Description:\n${mainDesc}\n\n`;
            }
            traitsText += 'Traits:\n'; // This will be for the selected race/subrace

            if (selectedItem.data.traits && Array.isArray(selectedItem.data.traits)) {
                selectedItem.data.traits.forEach(trait => {
                    newHtmlContent += `<h6>${trait.name}</h6><p>${trait.desc}</p>`;
                    traitsText += `${trait.name}\n${trait.desc}\n\n`;
                });
            }

            // --- Parent Race Trait Handling ---
            const parentRaceSlug = clickedLi.dataset.parentRaceSlug;
            if (parentRaceSlug) {
                try {
                    const response = await fetch(`/api/v2/races/${parentRaceSlug}/`);
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status} for parent race ${parentRaceSlug}`);
                    }
                    const parentRaceFullData = await response.json();
                    console.log("Fetched parentRaceFullData:", parentRaceFullData); // Log 1
                    // const parentRaceData = parentRaceFullData.data; // Original
                    const parentRaceData = parentRaceFullData; // Attempted Fix
                    console.log("Using parentRaceData:", parentRaceData); // Log 3

                    if (parentRaceData && parentRaceData.traits && Array.isArray(parentRaceData.traits)) {
                        console.log("Parent race traits found:", parentRaceData.traits); // Log 4a
                        newHtmlContent += `<h5>Parent race traits (${parentRaceData.name || parentRaceSlug})</h5>`;
                        traitsText += `Parent Race Traits (${parentRaceData.name || parentRaceSlug}):\n`;
                        parentRaceData.traits.forEach(trait => {
                            console.log("Processing parent trait - Name:", trait.name, "Desc:", trait.desc); // Log 4b
                            newHtmlContent += `<h6>${trait.name}</h6><p>${trait.desc}</p>`;
                            traitsText += `${trait.name}\n${trait.desc}\n\n`;
                        });
                    }
                } catch (error) {
                    console.error("Could not load parent race data:", error);
                    newHtmlContent += `<p class="error">Error loading parent race traits: ${error.message}</p>`;
                    traitsText += `Error loading parent race traits: ${error.message}\n\n`;
                }
                console.log("newHtmlContent after parent traits:", newHtmlContent); // Log 5a
                console.log("traitsText after parent traits:", traitsText); // Log 5b
            }
            // --- End Parent Race Trait Handling ---

            console.log("Final newHtmlContent before DOM update:", newHtmlContent); // Log 6
            descriptionContainer.innerHTML = newHtmlContent;
            console.log("Final traitsText before storing:", traitsText); // Log 7
            characterCreationData.step1_race_traits_text = traitsText.trim();
            saveCharacterDataToSession(); // Save after updating traits text

            // Update .selected-item class
            // First, remove from any previously selected item
            const currentlySelected = document.querySelector('#race-selection-list .selected-item');
            if (currentlySelected) {
                currentlySelected.classList.remove('selected-item');
            }
            // Then, add to the newly clicked item
            clickedLi.classList.add('selected-item');
            console.log("Selected item displayed:", selectedRaceSlug, selectedItem.data); // For debugging
            console.log("Formatted traits plain text stored:", characterCreationData.step1_race_traits_text); // Log plain text version
        } else {
            console.error(`Data for slug '${slug}' not found or item.data is missing in allRacesData.`);
            descriptionContainer.textContent = 'Details not found for the selected item.';
            // Clear selection if item not found or data is missing
             const currentlySelected = document.querySelector('#race-selection-list .selected-item');
            if (currentlySelected) {
                currentlySelected.classList.remove('selected-item');
            }
        }
    }

    // --- New Functions for Step 2: Class Selection ---

    async function loadClassStepData() {
       const classListContainer = document.getElementById('class-list-container');
       if (!classListContainer) {
           console.error("Class list container not found for step 2!");
           return;
       }
       classListContainer.innerHTML = '<p>Loading classes...</p>';
       try {
           const response = await fetch('/api/v1/classes/');
           if (!response.ok) {
               throw new Error(`HTTP error! status: ${response.status}`);
           }
           const data = await response.json();
           allClassesData = Array.isArray(data) ? data : (data.results || []); // Handle if data is {results: [...]}

           if (!Array.isArray(allClassesData)) {
               console.warn('Class data is not an array after fetch:', allClassesData);
               if(classListContainer) classListContainer.innerHTML = '<p>Error: Class data is not in the expected format.</p>';
               allClassesData = [];
           }
           populateClassList(allClassesData);
       } catch (error) {
           console.error("Could not load class data:", error);
           if(classListContainer) classListContainer.innerHTML = '<p>Error loading classes. Please try again later.</p>';
           allClassesData = [];
       }
    }

// STEP 3: ABILITY SCORES LOGIC
// =====================================================================================================================

function getStatBonuses() {
    const bonuses = {
        STR: { race: 0, class: 0 }, DEX: { race: 0, class: 0 }, CON: { race: 0, class: 0 },
        INT: { race: 0, class: 0 }, WIS: { race: 0, class: 0 }, CHA: { race: 0, class: 0 }
    };
    const abilityScoreMap = {
        "strength": "STR", "dexterity": "DEX", "constitution": "CON",
        "intelligence": "INT", "wisdom": "WIS", "charisma": "CHA"
    };

    function parseAbilityScoreIncrease(description) {
        if (typeof description !== 'string') return []; // Return empty array for non-string input
        const matches = [];
        const regex = /Your (\w+) score increases by (\d+)/gi; // Added global flag
        let match;
        while ((match = regex.exec(description)) !== null) {
            matches.push({
                abilityName: match[1].toLowerCase(),
                bonusValue: parseInt(match[2], 10)
            });
        }
        // Handle cases like "Choose any +2; choose any other +1" or "All of your ability scores increase by 1."
        // For now, this parser only handles "Your X score increases by Y".
        // More complex parsing can be added here if needed for other formats.
        return matches; // Return array of matches
    }

    function processTraits(traits, type) { // type is 'race' or 'class'
        if (traits && Array.isArray(traits)) {
            traits.forEach(trait => {
                if (trait.name === "Ability Score Increase" && trait.desc) {
                    const parsedBonusesArray = parseAbilityScoreIncrease(trait.desc); // Returns an array
                    if (parsedBonusesArray.length > 0) {
                        parsedBonusesArray.forEach(parsedBonus => { // Iterate over each found bonus
                            const statAbbr = abilityScoreMap[parsedBonus.abilityName];
                            if (statAbbr) {
                                if (type === 'race') {
                                    bonuses[statAbbr].race += parsedBonus.bonusValue;
                                } else if (type === 'class') {
                                    bonuses[statAbbr].class += parsedBonus.bonusValue;
                                }
                            } else {
                                console.warn(`Unknown ability name: ${parsedBonus.abilityName} from trait: ${trait.name} in description: "${trait.desc}"`);
                            }
                        });
                    } else {
                        // This console log can be noisy if many traits don't match the simple pattern.
                        // console.log(`Could not parse any ASI from description: "${trait.desc}" in trait: ${trait.name}`);
                    }
                }
            });
        }
    }

    // Process Race Bonuses from traits
    if (characterCreationData.step1_race_selection && characterCreationData.step1_race_selection.traits) {
        processTraits(characterCreationData.step1_race_selection.traits, 'race');
    }
    if (characterCreationData.step1_parent_race_selection && characterCreationData.step1_parent_race_selection.traits) {
        processTraits(characterCreationData.step1_parent_race_selection.traits, 'race');
    }

    // Process Class Bonuses from traits
    if (characterCreationData.step2_selected_base_class && characterCreationData.step2_selected_base_class.traits) {
        processTraits(characterCreationData.step2_selected_base_class.traits, 'class');
    }
    if (characterCreationData.step2_selected_archetype && characterCreationData.step2_selected_archetype.traits) {
        processTraits(characterCreationData.step2_selected_archetype.traits, 'class');
    }

    // The old logic for raceData.ability_score_bonuses is now replaced by parsing traits.
    // If the API also provides structured bonuses in `ability_score_bonuses` AND these are meant to be
    // *additional* to what's in traits, then that logic would need to be reinstated or merged carefully.
    // Based on the task, parsing traits is the primary source now.

    console.log("Calculated Stat Bonuses from traits:", JSON.parse(JSON.stringify(bonuses)));
    return bonuses;
}

function getVitalStats() {
    let vital = [];
    const raceData = characterCreationData.step1_race_selection;
    const classData = characterCreationData.step2_selected_base_class;
    const abilityScoreMap = {
        "strength": "STR", "dexterity": "DEX", "constitution": "CON",
        "intelligence": "INT", "wisdom": "WIS", "charisma": "CHA"
    };

    // Always suggest Constitution
    if (!vital.includes("CON")) vital.push("CON");

    // From Class
    if (classData) {
        // Primary ability for spellcasters
        if (classData.spellcasting && classData.spellcasting.spellcasting_ability) {
            const primaryCastingStat = abilityScoreMap[classData.spellcasting.spellcasting_ability.name.toLowerCase()];
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
                const statAbbr = abilityScoreMap[bonus.ability_score.name.toLowerCase()];
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
            const primaryCastingStat = abilityScoreMap[classData.spellcasting.spellcasting_ability.name.toLowerCase()];
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
                    const statAbbr = abilityScoreMap[bonus.ability_score.name.toLowerCase()];
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

function updateDisplayedBonuses() {
    characterCreationData.step3_ability_scores.forEach(stat => {
        const raceBonusEl = document.querySelector(`.stat-bonus.race-bonus[data-stat='${stat}']`);
        const classBonusEl = document.querySelector(`.stat-bonus.class-bonus[data-stat='${stat}']`);

        if (raceBonusEl) {
            raceBonusEl.textContent = `+${characterCreationData.step3_stat_bonuses[stat].race || 0}`;
        }
        if (classBonusEl) {
            classBonusEl.textContent = `+${characterCreationData.step3_stat_bonuses[stat].class || 0}`;
        }
    });
}

function renderMainStatDisplay() {
    characterCreationData.step3_ability_scores.forEach(stat => {
        const assignedValueEl = document.querySelector(`.stat-assigned-value[data-stat='${stat}']`);
        const totalEl = document.querySelector(`.stat-total[data-stat='${stat}']`);

        const assignedValue = characterCreationData.step3_assigned_stats[stat] || '-';
        assignedValueEl.textContent = assignedValue;

        if (assignedValue !== '-') {
            const raceBonus = characterCreationData.step3_stat_bonuses[stat].race || 0;
            const classBonus = characterCreationData.step3_stat_bonuses[stat].class || 0;
            totalEl.textContent = parseInt(assignedValue) + raceBonus + classBonus;
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
    const assignedValues = Object.values(characterCreationData.step3_assigned_stats);
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
            if (characterCreationData.step3_selected_dice_value === value && i === 0 && numberToDisplay > 0) { // Highlight only one instance if multiple are same value
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
    Object.entries(characterCreationData.step3_assigned_stats).forEach(([stat, value]) => {
        if (value !== null && !diceValues.includes(value)) {
            // This indicates a mismatch, possibly log an error or handle gracefully
            // For now, we assume assigned_stats are cleared if dice source changes.
        }
    });
}

function handleDicePoolClick(event) {
    const clickedValue = parseInt(event.target.textContent);
    characterCreationData.step3_selected_dice_value = clickedValue;

    // Update visual selection in the pool
    document.querySelectorAll('#assignable-dice-pool .dice-value').forEach(el => el.classList.remove('selected'));
    event.target.classList.add('selected');

    console.log("Selected dice value from pool:", clickedValue);
    saveCharacterDataToSession();
}

function handleRollDiceClick() {
    const rollDiceWarning = document.getElementById('roll-dice-warning'); // Get warning element again
    if (characterCreationData.step3_dice_rolled_once) {
        alert("You have already rolled the dice. You cannot roll again.");
        return;
    }

    if (confirm("Warning: Rolling dice will override the standard array values and can only be done once. Are you sure you want to proceed?")) {
        characterCreationData.step3_rolled_stats = generate4d6DropLowest();
        characterCreationData.step3_dice_rolled_once = true;
        characterCreationData.step3_assigned_stats = {}; // Clear assignments
        characterCreationData.step3_selected_dice_value = null; // Clear selected dice from pool

        document.getElementById('roll-dice-button').disabled = true;
        rollDiceWarning.style.display = 'block'; // Show warning text permanently after roll

        console.log("Dice rolled:", characterCreationData.step3_rolled_stats);
        loadStep3Logic(); // Reload/re-render Step 3 UI with new dice
        saveCharacterDataToSession();
    }
}

function handleStatAssignmentClick(event) {
    const targetStat = event.target.dataset.stat;
    if (!targetStat) return; // Clicked somewhere else in the block

    const selectedDiceValue = characterCreationData.step3_selected_dice_value;

    if (selectedDiceValue === null) {
        // If a stat is clicked without a dice value selected, and that stat currently has a value,
        // make that value available again in the pool.
        if (characterCreationData.step3_assigned_stats[targetStat] !== null && characterCreationData.step3_assigned_stats[targetStat] !== undefined) {
            console.log(`Unassigning ${characterCreationData.step3_assigned_stats[targetStat]} from ${targetStat}`);
            characterCreationData.step3_assigned_stats[targetStat] = null;
        } else {
            alert("Please select a dice roll from the 'Available Rolls' pool first.");
        }
    } else {
        // If there was a value previously assigned to this stat, make it available again ( conceptually)
        // The renderAssignableDicePool will handle making it visible if it's part of the current source array.
        const oldValue = characterCreationData.step3_assigned_stats[targetStat];
        if (oldValue !== null && oldValue !== undefined) {
            console.log(`Stat ${targetStat} had value ${oldValue}, which is now available again.`);
        }

        // Check if the selected dice value is already assigned to another stat
        // This simple check prevents direct assignment if already used.
        // More complex logic could allow swapping. For now, user must unassign first.
        let valueAlreadyAssignedElsewhere = false;
        for (const stat in characterCreationData.step3_assigned_stats) {
            if (characterCreationData.step3_assigned_stats[stat] === selectedDiceValue && stat !== targetStat) {
                // A simple count check for available vs assigned of this value
                const sourceStats = characterCreationData.step3_rolled_stats || characterCreationData.step3_standard_stats;
                const countInSource = sourceStats.filter(s => s === selectedDiceValue).length;
                const countAssigned = Object.values(characterCreationData.step3_assigned_stats).filter(s => s === selectedDiceValue).length;

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

        characterCreationData.step3_assigned_stats[targetStat] = selectedDiceValue;
        console.log(`Assigned ${selectedDiceValue} to ${targetStat}`);

        // Optional: Clear selected dice from pool after assignment, requiring re-selection for next assignment
        // characterCreationData.step3_selected_dice_value = null;
        // document.querySelectorAll('#assignable-dice-pool .dice-value.selected').forEach(el => el.classList.remove('selected'));
    }

    // Re-render displays
    let currentStatsToUse = characterCreationData.step3_rolled_stats || characterCreationData.step3_standard_stats;
    renderAssignableDicePool(currentStatsToUse);
    renderMainStatDisplay();
    saveCharacterDataToSession();
}

function loadStep3Logic() {
    console.log("Loading Step 3 logic...");
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

    // Get the vitalStatsDisplay element
    const vitalStatsDisplay = document.getElementById('vital-stats-display');

    // Calculate and store/update bonuses and vital stats
    // Ensure raceData and classData are available in characterCreationData as expected by helper functions
    if (characterCreationData.step1_race_selection && characterCreationData.step2_selected_base_class) {
        characterCreationData.step3_stat_bonuses = getStatBonuses(); // Uses data from characterCreationData
        characterCreationData.step3_vital_stats = getVitalStats();   // Uses data from characterCreationData
    } else {
        // Fallback if race/class data not yet fully loaded or selected
        console.warn("Race or Class data not fully available for Step 3 calculations. Using defaults.");
        characterCreationData.step3_stat_bonuses = { STR: { race: 0, class: 0 }, DEX: { race: 0, class: 0 }, CON: { race: 0, class: 0 }, INT: { race: 0, class: 0 }, WIS: { race: 0, class: 0 }, CHA: { race: 0, class: 0 } };
        characterCreationData.step3_vital_stats = ["CON"]; // Default vital stat
    }
    saveCharacterDataToSession(); // Save after calculating these

    // Display vital stats
    if (vitalStatsDisplay) {
        if (characterCreationData.step3_vital_stats && characterCreationData.step3_vital_stats.length > 0) {
            vitalStatsDisplay.textContent = characterCreationData.step3_vital_stats.join(', ');
        } else {
            vitalStatsDisplay.textContent = "None specific (General: CON)";
        }
    }

    // Display stat bonuses (now using the calculated ones)
    updateDisplayedBonuses(); // This function should read from characterCreationData.step3_stat_bonuses

    // The rest of loadStep3Logic (rendering dice pool, main stat display, button states) follows...
    // Determine which set of stats to use (standard or rolled)
    let currentStatsToDisplay = characterCreationData.step3_rolled_stats || characterCreationData.step3_standard_stats;

    if (characterCreationData.step3_rolled_stats) {
        standardArrayDisplay.style.display = 'none';
        rolledDiceValues.textContent = characterCreationData.step3_rolled_stats.join(', ');
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
    if (characterCreationData.step3_dice_rolled_once) {
        rollDiceButton.disabled = true;
        rollDiceWarning.style.display = 'block'; // Show warning if dice already rolled
    } else {
        rollDiceButton.disabled = false;
        rollDiceWarning.style.display = 'none'; // Hide warning if not yet rolled
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

    console.log("Step 3 characterCreationData:", JSON.parse(JSON.stringify(characterCreationData)));
    saveCharacterDataToSession();
}

// END STEP 3 LOGIC
// =====================================================================================================================

// --- New Functions for Step 4: Background Selection ---
async function loadBackgroundStepData() {
    const backgroundListContainer = document.getElementById('background-list-container');
    if (!backgroundListContainer) {
        console.error("Background list container not found for step 4!");
        return;
    }
    backgroundListContainer.innerHTML = '<p>Loading backgrounds...</p>';
    allBackgroundsData = []; // Initialize or clear previous data

    let nextUrl = '/api/v2/backgrounds/?limit=50'; // Using a reasonable limit

    try {
        while (nextUrl) {
            const response = await fetch(nextUrl);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status} while fetching ${nextUrl}`);
            }
            const pageData = await response.json();
            if (pageData && pageData.results && Array.isArray(pageData.results)) {
                allBackgroundsData = allBackgroundsData.concat(pageData.results);
            } else {
                console.warn("No results found in page data or results is not an array:", pageData);
            }
            nextUrl = pageData.next; // Update nextUrl, will be null/undefined if no more pages
        }
        console.log("All backgrounds loaded:", allBackgroundsData);
        populateBackgroundList(allBackgroundsData);
    } catch (error) {
        console.error("Could not load background data:", error);
        if (backgroundListContainer) {
            backgroundListContainer.innerHTML = `<p class="error">Error loading backgrounds: ${error.message}. Please try refreshing or try again later.</p>`;
        }
        allBackgroundsData = []; // Ensure it's an empty array on error
    }
}

function populateBackgroundList(backgroundsData) {
    const backgroundListContainer = document.getElementById('background-list-container');
    if (!backgroundListContainer) {
        console.error("Background list container #background-list-container not found in populateBackgroundList!");
        return;
    }
    backgroundListContainer.innerHTML = ''; // Clear previous content

    if (!backgroundsData || backgroundsData.length === 0) {
        backgroundListContainer.innerHTML = '<p>No backgrounds available or error in loading.</p>';
        return;
    }

    const backgroundSelectionList = document.createElement('ul');
    backgroundSelectionList.id = 'background-selection-list';

    backgroundsData.forEach(item => {
        // Assuming item structure is { slug: "...", data: { name: "..." } }
        // or just { slug: "...", name: "..." } directly from some APIs.
        // The API /api/v2/backgrounds/ provides { slug: "...", name: "...", desc: "..." }
        // The list from /api/v2/backgrounds/?limit=50 gives { slug: "slug", document__slug: "slug", document__name: "Name", ... }
        // Let's adjust to the paginated list structure.
        const name = item.document__name || item.name || item.slug;
        const slug = item.slug || item.document__slug;

        if (!slug) {
            console.warn("Background item missing slug:", item);
            return; // Skip item if it doesn't have a slug
        }

        const li = document.createElement('li');
        li.textContent = name;
        li.dataset.slug = slug;

        if (slug === characterCreationData.step4_selected_background_slug) {
            li.classList.add('selected-item');
        }
        backgroundSelectionList.appendChild(li);
    });

    backgroundListContainer.appendChild(backgroundSelectionList);
    // Add event listener to the new list
    backgroundSelectionList.addEventListener('click', handleBackgroundClick);
}

async function handleBackgroundClick(event) {
    const clickedLi = event.target.closest('li');
    if (!clickedLi || !clickedLi.dataset || !clickedLi.dataset.slug) {
        console.log("Clicked element is not a valid background LI or has no slug.");
        return; // Click was not on a valid list item
    }

    const slug = clickedLi.dataset.slug;
    characterCreationData.step4_selected_background_slug = slug;

    // Update selection styling
    const backgroundSelectionList = document.getElementById('background-selection-list');
    if (backgroundSelectionList) {
        const currentlySelected = backgroundSelectionList.querySelector('.selected-item');
        if (currentlySelected) {
            currentlySelected.classList.remove('selected-item');
        }
    }
    clickedLi.classList.add('selected-item');

    // Display details for the selected background
    await displayBackgroundDetails(slug); // This function will also save to session storage
    // saveCharacterDataToSession(); // Called within displayBackgroundDetails
    console.log("Background selected:", slug);
}

async function displayBackgroundDetails(slug) {
    const descriptionContainer = document.getElementById('background-description-container');
    if (!descriptionContainer) {
        console.error('Background description container #background-description-container not found!');
        return;
    }
    descriptionContainer.innerHTML = `<p>Loading details for ${slug}...</p>`;

    try {
        const response = await fetch(`/api/v2/backgrounds/${slug}/`);
        if (!response.ok) {
            throw new Error(`Failed to fetch background details for ${slug}: ${response.status}`);
        }
        const backgroundDetails = await response.json();

        if (!backgroundDetails || !backgroundDetails.name) { // Basic check for valid data
            throw new Error(`Incomplete data received for background ${slug}.`);
        }

        // Store the full background object
        characterCreationData.step4_background_selection = backgroundDetails;

        let htmlContent = `<h4>${backgroundDetails.name}</h4>`;
        let textSummary = `Background: ${backgroundDetails.name}\n`;

        if (backgroundDetails.desc) {
            htmlContent += `<h5>Description</h5><p>${backgroundDetails.desc.replace(/\n/g, '<br>')}</p>`;
            textSummary += `Description: ${backgroundDetails.desc}\n\n`;
        }

        htmlContent += '<h5>Provided Benefits:</h5><ul>';

        // Skill Proficiencies
        // The API provides skill_proficiencies as a string like "Persuasion, Deception"
        if (backgroundDetails.data && backgroundDetails.data.skill_proficiencies) {
            htmlContent += `<li><strong>Skill Proficiencies:</strong> ${backgroundDetails.data.skill_proficiencies}</li>`;
            textSummary += `Skill Proficiencies: ${backgroundDetails.data.skill_proficiencies}\n`;
        } else if (backgroundDetails.skill_proficiencies) { // Some backgrounds might have it at top level
             htmlContent += `<li><strong>Skill Proficiencies:</strong> ${backgroundDetails.skill_proficiencies}</li>`;
            textSummary += `Skill Proficiencies: ${backgroundDetails.skill_proficiencies}\n`;
        }


        // Tool Proficiencies
        // API provides tool_proficiencies as a string like "Thieves' tools, one type of gaming set"
        if (backgroundDetails.data && backgroundDetails.data.tool_proficiencies) {
            htmlContent += `<li><strong>Tool Proficiencies:</strong> ${backgroundDetails.data.tool_proficiencies}</li>`;
            textSummary += `Tool Proficiencies: ${backgroundDetails.data.tool_proficiencies}\n`;
        } else if (backgroundDetails.tool_proficiencies) {
            htmlContent += `<li><strong>Tool Proficiencies:</strong> ${backgroundDetails.tool_proficiencies}</li>`;
            textSummary += `Tool Proficiencies: ${backgroundDetails.tool_proficiencies}\n`;
        }

        // Languages
        // API provides languages as a string like "Two of your choice"
        if (backgroundDetails.data && backgroundDetails.data.languages) {
            htmlContent += `<li><strong>Languages:</strong> ${backgroundDetails.data.languages}</li>`;
            textSummary += `Languages: ${backgroundDetails.data.languages}\n`;
        } else if (backgroundDetails.languages) {
             htmlContent += `<li><strong>Languages:</strong> ${backgroundDetails.languages}</li>`;
            textSummary += `Languages: ${backgroundDetails.languages}\n`;
        }


        // Equipment
        // API provides equipment as a block string
        if (backgroundDetails.data && backgroundDetails.data.equipment) {
            htmlContent += `<li><strong>Starting Equipment:</strong><br>${backgroundDetails.data.equipment.replace(/\n/g, '<br>')}</li>`;
            textSummary += `Starting Equipment:\n${backgroundDetails.data.equipment}\n`;
        } else if (backgroundDetails.equipment) { // check top level as well
            htmlContent += `<li><strong>Starting Equipment:</strong><br>${backgroundDetails.equipment.replace(/\n/g, '<br>')}</li>`;
            textSummary += `Starting Equipment:\n${backgroundDetails.equipment}\n`;
        }


        // Feature
        if (backgroundDetails.data && backgroundDetails.data.feature_name && backgroundDetails.data.feature_desc) {
            htmlContent += `<li><strong>Feature: ${backgroundDetails.data.feature_name}</strong><br>${backgroundDetails.data.feature_desc.replace(/\n/g, '<br>')}</li>`;
            textSummary += `Feature: ${backgroundDetails.data.feature_name}\n${backgroundDetails.data.feature_desc}\n`;
        } else if (backgroundDetails.feature_name && backgroundDetails.feature_desc) { // check top level
            htmlContent += `<li><strong>Feature: ${backgroundDetails.feature_name}</strong><br>${backgroundDetails.feature_desc.replace(/\n/g, '<br>')}</li>`;
            textSummary += `Feature: ${backgroundDetails.feature_name}\n${backgroundDetails.feature_desc}\n`;
        }


        htmlContent += '</ul>';

        // Suggested Characteristics (often a large block of text or structured)
        // For simplicity, just show if present as a string. Could be parsed further if needed.
        if (backgroundDetails.data && backgroundDetails.data.suggested_characteristics) {
            htmlContent += `<h5>Suggested Characteristics</h5><div>${backgroundDetails.data.suggested_characteristics.replace(/\n/g, '<br>')}</div>`;
            textSummary += `\nSuggested Characteristics:\n${backgroundDetails.data.suggested_characteristics}\n`;
        } else if (backgroundDetails.suggested_characteristics) {
             htmlContent += `<h5>Suggested Characteristics</h5><div>${backgroundDetails.suggested_characteristics.replace(/\n/g, '<br>')}</div>`;
            textSummary += `\nSuggested Characteristics:\n${backgroundDetails.suggested_characteristics}\n`;
        }


        descriptionContainer.innerHTML = htmlContent;
        characterCreationData.step4_background_details_text = textSummary.trim();
        saveCharacterDataToSession();
        console.log("Background details displayed and stored for:", slug);

    } catch (error) {
        console.error(`Error displaying background details for ${slug}:`, error);
        descriptionContainer.innerHTML = `<p class="error">Could not load details for ${slug}. ${error.message}</p>`;
        // Clear stored data if loading fails
        characterCreationData.step4_selected_background_slug = null;
        characterCreationData.step4_background_selection = null;
        characterCreationData.step4_background_details_text = '';
        saveCharacterDataToSession();
    }
}

// Initialize first step
showStep(currentStep);

    function populateClassList(classesData) {
       const classListContainer = document.getElementById('class-list-container');
       if (!classListContainer) {
           console.error("Class list container not found in populateClassList!");
           return;
       }
       classListContainer.innerHTML = ''; // Clear previous content

       if (!classesData || classesData.length === 0) {
           classListContainer.innerHTML = '<p>No classes available or error in loading.</p>';
           return;
       }

       const classSelectionList = document.createElement('ul');
       classSelectionList.id = 'class-selection-list';

       classesData.forEach(classItem => {
           // Assuming classItem.slug and classItem.data are present
           // and classItem.data.name and classItem.data.archetypes might be present
           const baseClassName = (classItem.data && classItem.data.name) ? classItem.data.name : classItem.slug;
           const baseClassSlug = classItem.slug;

           if (!baseClassSlug) {
               console.warn("Base class item missing slug:", classItem);
               return;
           }

           const parentLi = document.createElement('li');
           parentLi.textContent = baseClassName;
           parentLi.dataset.slug = baseClassSlug;
           if (baseClassSlug === selectedClassOrArchetypeSlug) {
               parentLi.classList.add('selected-item');
           }
           classSelectionList.appendChild(parentLi);

           // Check for and display archetypes
           if (classItem.data && classItem.data.archetypes && Array.isArray(classItem.data.archetypes) && classItem.data.archetypes.length > 0) {
               const archetypeUl = document.createElement('ul');
               archetypeUl.className = 'archetype-list'; // For styling (e.g., indentation)

               classItem.data.archetypes.forEach(archetype => {
                   const archetypeSlug = archetype.slug; // Assuming archetype has a slug
                   const archetypeName = archetype.name || archetypeSlug; // Assuming archetype has a name

                   if (!archetypeSlug) {
                       console.warn("Archetype item missing slug:", archetype);
                       return;
                   }

                   const childLi = document.createElement('li');
                   childLi.textContent = archetypeName;
                   childLi.dataset.slug = archetypeSlug;
                   childLi.dataset.parentClassSlug = baseClassSlug; // Store parent class slug
                   childLi.classList.add('archetype-item'); // For styling & event handling differentiation

                   if (archetypeSlug === selectedClassOrArchetypeSlug) {
                       childLi.classList.add('selected-item');
                       // Also ensure parent is visually distinct if a child is selected, if desired by CSS.
                       // For now, only the actual selected item gets 'selected-item'.
                   }
                   archetypeUl.appendChild(childLi);
               });
               parentLi.appendChild(archetypeUl);
           }
       });

       classListContainer.appendChild(classSelectionList);
       classSelectionList.addEventListener('click', handleClassOrArchetypeClick); // Renamed listener call
    }

    async function handleClassOrArchetypeClick(event) { // Renamed function
       const clickedLi = event.target.closest('li');
       if (!clickedLi || !clickedLi.dataset || !clickedLi.dataset.slug) {
           return;
       }

       const slug = clickedLi.dataset.slug;
       const parentClassSlug = clickedLi.dataset.parentClassSlug; // Will be undefined for base classes
       selectedClassOrArchetypeSlug = slug;

       // Update selection styling
       const classSelectionList = document.getElementById('class-selection-list');
       if (classSelectionList) {
           const currentlySelected = classSelectionList.querySelector('.selected-item');
           if (currentlySelected) {
               currentlySelected.classList.remove('selected-item');
           }
       }
       clickedLi.classList.add('selected-item');

       // Temporary storage of actual clicked slug, parent will be used by displayClassDetails to fetch base class
       characterCreationData.step2_selected_slug_temp = slug;
       saveCharacterDataToSession();

       await displayClassDetails(slug, parentClassSlug); // Pass both slugs
    }

    async function displayClassDetails(selectionSlug, parentClassSlug) { // Modified signature
       const descriptionContainer = document.getElementById('class-description-container');
       if (!descriptionContainer) {
           console.error('Class description container not found!');
           return;
       }
       descriptionContainer.innerHTML = `<p>Loading details for ${selectionSlug}...</p>`;

       let htmlContent = '';
       let textSummary = '';
       let fetchUrl;

       if (parentClassSlug) { // An archetype was selected
           fetchUrl = `/api/v1/classes/${parentClassSlug}/`;
       } else { // A base class was selected
           fetchUrl = `/api/v1/classes/${selectionSlug}/`;
       }

       try {
           const response = await fetch(fetchUrl);
           if (!response.ok) {
               throw new Error(`Failed to fetch details from ${fetchUrl}: ${response.status}`);
           }
           const baseClassData = await response.json(); // This is always the base class data

           let selectedArchetypeData = null;
           if (parentClassSlug) { // Archetype was selected, find it in the baseClassData
               if (baseClassData.archetypes && Array.isArray(baseClassData.archetypes)) {
                   selectedArchetypeData = baseClassData.archetypes.find(arch => arch.slug === selectionSlug);
               }

               if (selectedArchetypeData) {
                   htmlContent += `<h4>${selectedArchetypeData.name} <span class="archetype-parent-class">(${baseClassData.name} Archetype)</span></h4>`;
                   textSummary += `Archetype: ${selectedArchetypeData.name} (${baseClassData.name})\n`;
                   if (selectedArchetypeData.desc) {
                       htmlContent += `<h5>Archetype Description & Features</h5><div class="archetype-description">${selectedArchetypeData.desc.replace(/\n/g, '<br>')}</div>`;
                       textSummary += `Archetype Description: ${selectedArchetypeData.desc}\n\n`;
                   }
                    // Placeholder for more structured archetype features if available later
                    if (selectedArchetypeData.features && selectedArchetypeData.features.length > 0) {
                        htmlContent += `<h6>Key Archetype Features:</h6><ul>`;
                        selectedArchetypeData.features.forEach(feature => {
                             htmlContent += `<li><strong>${feature.name}:</strong> ${feature.desc.substring(0,150)}...</li>`; // Example
                             textSummary += `Archetype Feature: ${feature.name}\n`;
                        });
                        htmlContent += `</ul>`;
                    }
                   htmlContent += '<hr>'; // Separator
               } else {
                   descriptionContainer.innerHTML = `<p class="error">Could not find archetype details for ${selectionSlug} within ${baseClassData.name}.</p>`;
                   return;
               }
           }

           // Display Base Class Information
           htmlContent += `<h4>${baseClassData.name} (Base Class)</h4>`;
           textSummary += `Base Class: ${baseClassData.name}\n`;

           if (baseClassData.desc && !parentClassSlug) { // Show base class desc only if no archetype was selected, or it's very general
                htmlContent += `<h5>Class Description</h5><p>${baseClassData.desc.replace(/\n/g, '<br>')}</p>`;
                textSummary += `Base Class Description: ${baseClassData.desc}\n\n`;
           } else if (baseClassData.desc && parentClassSlug) {
                htmlContent += `<h5>Parent Class Core Info</h5><p><em>Core description of ${baseClassData.name} is available if selected directly.</em></p>`;
           }


           htmlContent += '<h5>Details</h5>';
           if (baseClassData.hit_die) {
               htmlContent += `<p><strong>Hit Die:</strong> d${baseClassData.hit_die}</p>`;
               textSummary += `Hit Die: d${baseClassData.hit_die}\n`;
           }
           if (baseClassData.hp_at_1st_level) {
               htmlContent += `<p><strong>HP at 1st Level:</strong> ${baseClassData.hp_at_1st_level}</p>`;
               textSummary += `HP at 1st Level: ${baseClassData.hp_at_1st_level}\n`;
           }

           let proficienciesHTML = "";
           // Armor
           if (baseClassData.prof_armor) {
               if (typeof baseClassData.prof_armor === 'string' && baseClassData.prof_armor.trim() !== '') {
                   proficienciesHTML += `<li><strong>Armor:</strong> ${baseClassData.prof_armor}</li>`;
                   textSummary += `Proficient Armor: ${baseClassData.prof_armor}\n`;
               } else if (Array.isArray(baseClassData.prof_armor) && baseClassData.prof_armor.length > 0) {
                   proficienciesHTML += `<li><strong>Armor:</strong> ${baseClassData.prof_armor.map(p => p.name || p).join(', ')}</li>`;
                   textSummary += `Proficient Armor: ${baseClassData.prof_armor.map(p => p.name || p).join(', ')}\n`;
               }
           }
           // Weapons
           if (baseClassData.prof_weapons) {
               if (typeof baseClassData.prof_weapons === 'string' && baseClassData.prof_weapons.trim() !== '') {
                   proficienciesHTML += `<li><strong>Weapons:</strong> ${baseClassData.prof_weapons}</li>`;
                   textSummary += `Proficient Weapons: ${baseClassData.prof_weapons}\n`;
               } else if (Array.isArray(baseClassData.prof_weapons) && baseClassData.prof_weapons.length > 0) {
                   proficienciesHTML += `<li><strong>Weapons:</strong> ${baseClassData.prof_weapons.map(p => p.name || p).join(', ')}</li>`;
                   textSummary += `Proficient Weapons: ${baseClassData.prof_weapons.map(p => p.name || p).join(', ')}\n`;
               }
           }
           // Tools
           if (baseClassData.prof_tools) {
               if (typeof baseClassData.prof_tools === 'string' && baseClassData.prof_tools.trim() !== '') {
                   proficienciesHTML += `<li><strong>Tools:</strong> ${baseClassData.prof_tools}</li>`;
                   textSummary += `Proficient Tools: ${baseClassData.prof_tools}\n`;
               } else if (Array.isArray(baseClassData.prof_tools) && baseClassData.prof_tools.length > 0) {
                   proficienciesHTML += `<li><strong>Tools:</strong> ${baseClassData.prof_tools.map(p => p.name || p).join(', ')}</li>`;
                   textSummary += `Proficient Tools: ${baseClassData.prof_tools.map(p => p.name || p).join(', ')}\n`;
               }
           }
           // Saving Throws
           if (baseClassData.prof_saving_throws) {
               if (typeof baseClassData.prof_saving_throws === 'string' && baseClassData.prof_saving_throws.trim() !== '') {
                   proficienciesHTML += `<li><strong>Saving Throws:</strong> ${baseClassData.prof_saving_throws}</li>`;
                   textSummary += `Proficient Saving Throws: ${baseClassData.prof_saving_throws}\n`;
               } else if (Array.isArray(baseClassData.prof_saving_throws) && baseClassData.prof_saving_throws.length > 0) {
                   proficienciesHTML += `<li><strong>Saving Throws:</strong> ${baseClassData.prof_saving_throws.map(p => p.name || p).join(', ')}</li>`;
                   textSummary += `Proficient Saving Throws: ${baseClassData.prof_saving_throws.map(p => p.name || p).join(', ')}\n`;
               }
           }
           // Skills (typically a string like "Choose two from...")
           if (baseClassData.prof_skills && typeof baseClassData.prof_skills === 'string' && baseClassData.prof_skills.trim() !== '') {
               proficienciesHTML += `<li><strong>Skills:</strong> ${baseClassData.prof_skills}</li>`;
               textSummary += `Skill Proficiencies: ${baseClassData.prof_skills}\n`;
           }

           // This was for a general 'proficiencies' array, which might be different from prof_skills.
           // Keep if API might provide a separate 'proficiencies' array of objects.
           // For now, assuming prof_skills covers the "Choose X from Y" type.
           // if (baseClassData.proficiencies && Array.isArray(baseClassData.proficiencies) && baseClassData.proficiencies.length > 0) {
           //      proficienciesHTML += `<li><strong>General Proficiencies:</strong> ${baseClassData.proficiencies.map(p => p.name).join(', ')}</li>`;
           //      textSummary += `General Proficiencies: ${baseClassData.proficiencies.map(p => p.name).join(', ')}\n`;
           // }

            if (baseClassData.proficiency_choices) {
                baseClassData.proficiency_choices.forEach(choice => {
                    if (choice.desc && choice.choose_from && choice.choose_from.options) {
                         proficienciesHTML += `<li><strong>${choice.desc}:</strong> (Choose ${choice.choose_from.count} from: ${choice.choose_from.options.map(opt => opt.item.name).join(', ')})</li>`;
                         textSummary += `Base Class Proficiency Choice: ${choice.desc}\n`; // Clarified source
                    }
                });
            }

           if(proficienciesHTML) {
               htmlContent += '<h6>Base Class Proficiencies:</h6><ul>' + proficienciesHTML + '</ul>'; // Clarified source
           }

           if (baseClassData.starting_equipment_desc) {
               htmlContent += `<h6>Starting Equipment:</h6><div>${baseClassData.starting_equipment_desc.replace(/\n/g, '<br>')}</div>`;
               textSummary += `\nBase Class Starting Equipment:\n${baseClassData.starting_equipment_desc}\n`; // Clarified
           } else if (baseClassData.starting_equipment && baseClassData.starting_equipment.length > 0) {
                htmlContent += `<h6>Starting Equipment Options:</h6><ul>`;
                baseClassData.starting_equipment.forEach(optionSet => {
                    if(optionSet.desc && optionSet.options) {
                        htmlContent += `<li>${optionSet.desc}<ul>`;
                        optionSet.options.forEach(opt => {
                            htmlContent += `<li>${opt.desc}</li>`;
                        });
                        htmlContent += `</ul></li>`;
                    }
                });
                htmlContent += `</ul>`;
                textSummary += `\nBase Class Starting Equipment: Options available (see details).\n`; // Clarified
           }

           if (baseClassData.spellcasting) { // Spellcasting is typically a base class feature
                htmlContent += `<h6>Spellcasting</h6><p>This class has spellcasting abilities. Spellcasting Ability: ${baseClassData.spellcasting.spellcasting_ability.name}. More details in the Spellcasting step.</p>`;
                textSummary += `Spellcasting Ability: ${baseClassData.spellcasting.spellcasting_ability.name}\n`;
           }

            // Displaying base class features if not an archetype or if archetype doesn't cover them all
            // This part might need refinement based on how features are structured and duplicated (or not) in archetypes
            if (baseClassData.features && Array.isArray(baseClassData.features) && baseClassData.features.length > 0) {
                htmlContent += '<h6>Key Base Class Features (may include higher level features):</h6><ul>';
                baseClassData.features.forEach(feature => {
                    // Avoid duplicating features if already shown by archetype, if slugs match or names match.
                    // This is a simple check; more robust de-duplication might be needed.
                    if (!selectedArchetypeData || !selectedArchetypeData.features || !selectedArchetypeData.features.find(archFeature => archFeature.slug === feature.slug || archFeature.name === feature.name)) {
                        htmlContent += `<li><strong>${feature.name}:</strong> ${feature.desc.substring(0,150)}...</li>`;
                        textSummary += `Base Class Feature: ${feature.name}\n`; // Clarified
                    }
                });
                htmlContent += '</ul>';
            }


           descriptionContainer.innerHTML = htmlContent;
           characterCreationData.step2_selection_details_text = textSummary.trim();
           saveCharacterDataToSession();
           console.log("Details displayed for selection:", selectionSlug, "using base class:", baseClassData.slug);

       } catch (error) {
           console.error(`Error displaying details for ${selectionSlug}:`, error);
           descriptionContainer.innerHTML = `<p class="error">Could not load details for ${selectionSlug}. ${error.message}</p>`;
           characterCreationData.step2_selection_details_text = '';
           saveCharacterDataToSession();
       }
    }
