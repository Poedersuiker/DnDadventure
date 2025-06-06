// Global variables for Step 1: Race Selection
let allRacesData = null;
let selectedRaceSlug = null;

// --- Functions for Step 1: Race Selection ---

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
    // IMPORTANT: This event listener is now local to this file.
    // Ensure this file is loaded *after* the main character_creation.js if it relies on global functions from there,
    // OR ensure all dependencies are self-contained or correctly namespaced/imported.
    // For now, assuming direct call is fine as `handleRaceOrSubraceClick` is also moved here.
    raceSelectionList.addEventListener('click', handleRaceOrSubraceClick);
}

async function handleRaceOrSubraceClick(event) { // Made async
    const clickedLi = event.target.closest('li'); // Get the actual LI that was clicked or contains the click target

    if (!clickedLi || !clickedLi.dataset || !clickedLi.dataset.slug) {
        // Click was not on a valid race/subrace list item or its child
        return;
    }

    const slug = clickedLi.dataset.slug;
    selectedRaceSlug = slug; // Update the local selected slug

    // Clear previous selections first, before fetching new data
    characterCreationData.step1_race_selection = null;
    characterCreationData.step1_parent_race_selection = null;
    // Not clearing step1_race_traits_text here, as it might be rebuilt or appended.

    const descriptionContainer = document.getElementById('race-description-container');
    if (!descriptionContainer) {
        console.error('Race description container not found!');
        return;
    }
    descriptionContainer.innerHTML = `<p>Loading details for ${slug}...</p>`; // Show loading message

    try {
        // 1. Fetch the complete data for the selectedRaceSlug
        const raceResponse = await fetch(`/api/v2/races/${slug}/`);
        if (!raceResponse.ok) {
            throw new Error(`Failed to fetch race data for ${slug}: ${raceResponse.status}`);
        }
        const raceData = await raceResponse.json();

        // 2. Store this fetched data in characterCreationData.step1_race_selection
        // The API returns the full object including 'name', 'slug', 'desc', 'traits' etc.
        characterCreationData.step1_race_selection = raceData;
        console.log(`Stored ${raceData.name} in characterCreationData.step1_race_selection`);

        let newHtmlContent = '';
        let traitsTextForStorage = ''; // For step1_race_traits_text

        if (raceData.desc) {
            newHtmlContent += `<h5>Description</h5><p>${raceData.desc.replace(/\n/g, '<br>')}</p>`;
            traitsTextForStorage += `Description:\n${raceData.desc}\n\n`;
        }

        newHtmlContent += '<h5>Traits (Selected Race/Subrace)</h5>';
        traitsTextForStorage += 'Traits (Selected Race/Subrace):\n';
        if (raceData.traits && Array.isArray(raceData.traits)) {
            raceData.traits.forEach(trait => {
                newHtmlContent += `<h6>${trait.name}</h6><p>${trait.desc.replace(/\n/g, '<br>')}</p>`;
                traitsTextForStorage += `${trait.name}\n${trait.desc}\n\n`;
            });
        } else {
            newHtmlContent += '<p>No specific traits listed for this selection.</p>';
        }

        // 3. Handle parent race if it's a subrace
        characterCreationData.step1_parent_race_selection = null; // Reset parent race selection initially
        const parentRaceSlugFromData = raceData.subrace_of ? getSlugFromUrl(raceData.subrace_of) : null;

        if (parentRaceSlugFromData) {
            const parentRaceResponse = await fetch(`/api/v2/races/${parentRaceSlugFromData}/`);
            if (!parentRaceResponse.ok) {
                throw new Error(`Failed to fetch parent race data for ${parentRaceSlugFromData}: ${parentRaceResponse.status}`);
            }
            const parentRaceFullData = await parentRaceResponse.json();
            characterCreationData.step1_parent_race_selection = parentRaceFullData;
            console.log(`Stored ${parentRaceFullData.name} in characterCreationData.step1_parent_race_selection`);

            if (parentRaceFullData && parentRaceFullData.traits && Array.isArray(parentRaceFullData.traits)) {
                newHtmlContent += `<h5>Traits (Parent Race: ${parentRaceFullData.name})</h5>`;
                traitsTextForStorage += `\nTraits (Parent Race: ${parentRaceFullData.name}):\n`;
                parentRaceFullData.traits.forEach(trait => {
                    newHtmlContent += `<h6>${trait.name}</h6><p>${trait.desc.replace(/\n/g, '<br>')}</p>`;
                    traitsTextForStorage += `${trait.name}\n${trait.desc}\n\n`;
                });
            }
        }

        descriptionContainer.innerHTML = newHtmlContent;
        characterCreationData.step1_race_traits_text = traitsTextForStorage.trim();

        // 4. Call saveCharacterDataToSession()
        if (typeof saveCharacterDataToSession === 'function') {
            saveCharacterDataToSession();
        } else {
            console.error("saveCharacterDataToSession function is not defined. Data not saved.");
        }

        // Update .selected-item class on the list
        const raceSelectionList = document.getElementById('race-selection-list');
        if (raceSelectionList) {
            const currentlySelected = raceSelectionList.querySelector('.selected-item');
            if (currentlySelected) {
                currentlySelected.classList.remove('selected-item');
            }
        }
        clickedLi.classList.add('selected-item');
        console.log("Race/Subrace selection processed and saved:", slug);

    } catch (error) {
        console.error("Error in handleRaceOrSubraceClick:", error);
        if(descriptionContainer) descriptionContainer.innerHTML = `<p class="error">Error loading details: ${error.message}</p>`;
        // Clear potentially partially saved data on error
        characterCreationData.step1_race_selection = null;
        characterCreationData.step1_parent_race_selection = null;
        characterCreationData.step1_race_traits_text = '';
        if (typeof saveCharacterDataToSession === 'function') {
            saveCharacterDataToSession(); // Save cleared data
        }
    }
}

// Note: `characterCreationData` and `saveCharacterDataToSession()` are used directly,
// assuming they are globally available from `character_creation.js` and `general.js` respectively.
// `getSlugFromUrl` is also assumed global from `general.js`.
