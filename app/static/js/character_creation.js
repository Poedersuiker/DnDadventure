let currentStep = 0; // Start at Step 0 (Introduction)
    const totalSteps = 9; // Last actual step number for choices

    // Global variables for character creation
    let allRacesData = null;
    let characterCreationData = {};
    let selectedRaceSlug = null;

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
            <p>Each class entry in the Player's Handbook includes information on: Hit Dice, Hit Points at 1st Level, Hit Points at Higher Levels, Proficiencies (Armor, Weapons, Tools, Saving Throws, Skills), Equipment, and class-specific features (e.g., Spellcasting, Channel Divinity, Martial Archetype).</p>`,
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
        4: `<h3>4. Describe Your Character</h3>
            <p>Your character's background describes where you came from, your original occupation, and your place in the D&D world. Your DM might offer additional backgrounds beyond those in the PHB.</p>
            <p>A background usually provides:
            <br> - Skill Proficiencies
            <br> - Tool Proficiencies
            <br> - Languages
            <br> - Starting Equipment
            <br> - A special background feature</p>
            <p>It also offers suggestions for personality traits, ideals, bonds, and flaws. These are roleplaying cues that help you bring your character to life.</p>
            <p>Other details to consider: Name, Sex, Height and Weight, Alignment, Personal Characteristics (appearance, mannerisms).</p>`,
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
        // Clear race-specific content when leaving step 1
        if (stepNumber !== 1) {
            const raceListContainer = document.getElementById('race-list-container');
            const raceDescriptionContainer = document.getElementById('race-description-container');
            if (raceListContainer) raceListContainer.innerHTML = '';
            if (raceDescriptionContainer) raceDescriptionContainer.innerHTML = '';
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
            let selectedData = null;
            if (allRacesData) {
                for (const race of allRacesData) {
                    if (race.slug === selectedRaceSlug) {
                        selectedData = race;
                        break;
                    }
                    if (race.subraces) {
                        for (const subrace of race.subraces) {
                            if (subrace.slug === selectedRaceSlug) {
                                selectedData = subrace; // Storing the subrace object directly
                                // Optionally, add parent race info if needed: selectedData.parent_race_slug = race.slug;
                                break;
                            }
                        }
                    }
                    if (selectedData) break;
                }
            }
            if (selectedData) {
                characterCreationData.step1_race = selectedData;
                console.log("Race selected:", characterCreationData.step1_race); // For debugging
            } else {
                // console.warn("Selected race/subrace slug not found in allRacesData:", selectedRaceSlug);
                // Optionally, prevent moving to next step if selection is critical and not found
                // alert("Please select a valid race or subrace.");
                // return;
            }
        }


        if (currentStep < totalSteps) {
            currentStep++;
            showStep(currentStep);
        } else {
            // Handle Finish action
            alert('Character creation finished! (Review/Finalize placeholder)');
            console.log("Final Character Data:", characterCreationData);
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
            allRacesData = await response.json();
            if (allRacesData && allRacesData.results) { // Adjusting based on typical DRF pagination
                allRacesData = allRacesData.results; // Assuming results contains the array of races
                populateRaceList(allRacesData);
            } else if (Array.isArray(allRacesData)) { // If the API directly returns an array
                 populateRaceList(allRacesData);
            } else {
                 console.error('Fetched race data is not in the expected format:', allRacesData);
                 if(raceListContainer) raceListContainer.innerHTML = '<p>Error: Race data is not in the expected format.</p>';
                 allRacesData = []; // Ensure it's an array to prevent errors later
            }
        } catch (error) {
            console.error('Failed to load race data:', error);
            if(raceListContainer) raceListContainer.innerHTML = '<p>Error loading races. Please try refreshing.</p>';
            allRacesData = []; // Ensure it's an array
        }
    }

    function populateRaceList(races) {
        const raceListContainer = document.getElementById('race-list-container');
        if (!raceListContainer) return;
        raceListContainer.innerHTML = ''; // Clear previous content

        const ul = document.createElement('ul');
        ul.id = 'race-selection-list'; // Add an ID for the UL for easier event delegation

        races.forEach(race => {
            const raceLi = document.createElement('li');
            raceLi.textContent = race.name;
            raceLi.dataset.slug = race.slug;
            ul.appendChild(raceLi);

            if (race.subraces && race.subraces.length > 0) {
                const subUl = document.createElement('ul');
                subUl.classList.add('subrace-list');
                race.subraces.forEach(subrace => {
                    const subLi = document.createElement('li');
                    subLi.textContent = subrace.name;
                    subLi.dataset.slug = subrace.slug;
                    subLi.dataset.parentRaceSlug = race.slug;
                    subLi.classList.add('subrace-item');
                    subUl.appendChild(subLi);
                });
                raceLi.appendChild(subUl); // Append sublist to race's LI
            }
        });
        raceListContainer.appendChild(ul);

        // Add event listener to the UL for clicks on LIs
        ul.addEventListener('click', handleRaceOrSubraceClick);
    }

    function handleRaceOrSubraceClick(event) {
        const targetLi = event.target.closest('li'); // Ensure we get the LI even if a nested element is clicked
        if (!targetLi || !targetLi.dataset.slug) return; // Clicked outside an LI or LI has no slug

        selectedRaceSlug = targetLi.dataset.slug;
        const parentSlug = targetLi.dataset.parentRaceSlug;

        let itemData = null;
        if (allRacesData) {
            if (parentSlug) {
                const parentRace = allRacesData.find(r => r.slug === parentSlug);
                if (parentRace && parentRace.subraces) {
                    itemData = parentRace.subraces.find(sr => sr.slug === selectedRaceSlug);
                }
            } else {
                itemData = allRacesData.find(r => r.slug === selectedRaceSlug);
            }
        }

        const descriptionContainer = document.getElementById('race-description-container');
        if (descriptionContainer) {
            if (itemData) {
                descriptionContainer.textContent = JSON.stringify(itemData, null, 2);

                // Remove 'selected' class from previously selected item
                const currentlySelected = document.querySelector('#race-selection-list .selected-item');
                if (currentlySelected) {
                    currentlySelected.classList.remove('selected-item');
                }
                // Add 'selected' class to the clicked item
                targetLi.classList.add('selected-item');

            } else {
                descriptionContainer.textContent = 'Details not found for the selected item.';
            }
        }
        console.log("Selected item:", selectedRaceSlug, itemData); // For debugging
    }

    // Initialize first step
    showStep(currentStep);
