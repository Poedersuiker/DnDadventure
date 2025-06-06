// Global variable for step 3 background data
let allBackgroundsData = null;

// --- Functions for Step 3: Background Selection ---

/**
 * Fetches all background data from the API.
 * Populates the background list once data is loaded.
 */
async function loadBackgroundStepData() {
    const backgroundListContainer = document.getElementById('background-list-container');
    if (!backgroundListContainer) {
        console.error("Background list container not found for step 3!");
        return;
    }
    backgroundListContainer.innerHTML = '<p>Loading backgrounds...</p>';
    allBackgroundsData = []; // Initialize or clear previous data

    let nextUrl = '/api/v2/backgrounds/?limit=50';

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
            nextUrl = pageData.next;
        }
        console.log("All backgrounds loaded:", allBackgroundsData);
        populateBackgroundList(allBackgroundsData);
    } catch (error) {
        console.error("Could not load background data:", error);
        if (backgroundListContainer) {
            backgroundListContainer.innerHTML = `<p class="error">Error loading backgrounds: ${error.message}. Please try refreshing or try again later.</p>`;
        }
        allBackgroundsData = [];
    }
}

/**
 * Populates the HTML list with background names.
 * @param {Array} backgroundsData - Array of background objects.
 */
function populateBackgroundList(backgroundsData) {
    const backgroundListContainer = document.getElementById('background-list-container');
    if (!backgroundListContainer) {
        console.error("Background list container #background-list-container not found in populateBackgroundList!");
        return;
    }
    backgroundListContainer.innerHTML = '';

    if (!backgroundsData || backgroundsData.length === 0) {
        backgroundListContainer.innerHTML = '<p>No backgrounds available or error in loading.</p>';
        return;
    }

    const backgroundSelectionList = document.createElement('ul');
    backgroundSelectionList.id = 'background-selection-list';

    backgroundsData.forEach(item => {
        const trueApiSlug = (item.data && item.data.slug) ? item.data.slug : item.slug;

        if (!trueApiSlug) {
            console.warn("Background item missing a usable slug:", item);
            return;
        }

        const displayName = (item.data && item.data.name) ? item.data.name : trueApiSlug;

        const li = document.createElement('li');
        li.textContent = displayName;
        li.dataset.slug = trueApiSlug;

        // Assumes characterCreationData is globally accessible
        if (characterCreationData && characterCreationData.step3_selected_background_slug === trueApiSlug) {
            li.classList.add('selected-item');
        }
        backgroundSelectionList.appendChild(li);
    });

    backgroundListContainer.appendChild(backgroundSelectionList);
    backgroundSelectionList.addEventListener('click', handleBackgroundClick);
}

/**
 * Handles click events on background list items.
 * Updates selection and displays details for the clicked background.
 * @param {Event} event - The click event.
 */
async function handleBackgroundClick(event) {
    const clickedLi = event.target.closest('li');
    if (!clickedLi || !clickedLi.dataset || !clickedLi.dataset.slug) {
        console.log("Clicked element is not a valid background LI or has no slug.");
        return;
    }

    // Assumes characterCreationData and saveCharacterDataToSession are globally accessible
    if (typeof characterCreationData !== 'undefined' && typeof saveCharacterDataToSession === 'function') {
        characterCreationData.step3_background_data_loaded = false;
        saveCharacterDataToSession();
    } else {
        console.error("characterCreationData or saveCharacterDataToSession not available globally for handleBackgroundClick.");
        // Potentially return or handle error if these critical global objects/functions are missing
    }

    const slug = clickedLi.dataset.slug;
    if (typeof characterCreationData !== 'undefined') {
        characterCreationData.step3_selected_background_slug = slug;
    }

    const backgroundSelectionList = document.getElementById('background-selection-list');
    if (backgroundSelectionList) {
        const currentlySelected = backgroundSelectionList.querySelector('.selected-item');
        if (currentlySelected) {
            currentlySelected.classList.remove('selected-item');
        }
    }
    clickedLi.classList.add('selected-item');

    await displayBackgroundDetails(slug);
    console.log("Background selected:", slug);
}

/**
 * Fetches and displays the details of a selected background.
 * Updates characterCreationData with the selection.
 * @param {string} slug - The slug of the background to display.
 */
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

        if (!backgroundDetails || !backgroundDetails.name) {
            throw new Error(`Incomplete data received for background ${slug}.`);
        }

        if (typeof characterCreationData !== 'undefined') {
            characterCreationData.step3_background_selection = backgroundDetails;
        }

        let htmlContent = `<h4>${backgroundDetails.name}</h4>`;

        if (backgroundDetails.desc) {
            htmlContent += `<h5>Description</h5><p>${backgroundDetails.desc.replace(/\n/g, '<br>')}</p>`;
        }

        htmlContent += '<h5>Provided Benefits:</h5><ul>';

        if (backgroundDetails.data && backgroundDetails.data.skill_proficiencies) {
            htmlContent += `<li><strong>Skill Proficiencies:</strong> ${backgroundDetails.data.skill_proficiencies}</li>`;
        } else if (backgroundDetails.skill_proficiencies) {
             htmlContent += `<li><strong>Skill Proficiencies:</strong> ${backgroundDetails.skill_proficiencies}</li>`;
        }

        if (backgroundDetails.data && backgroundDetails.data.tool_proficiencies) {
            htmlContent += `<li><strong>Tool Proficiencies:</strong> ${backgroundDetails.data.tool_proficiencies}</li>`;
        } else if (backgroundDetails.tool_proficiencies) {
            htmlContent += `<li><strong>Tool Proficiencies:</strong> ${backgroundDetails.tool_proficiencies}</li>`;
        }

        if (backgroundDetails.data && backgroundDetails.data.languages) {
            htmlContent += `<li><strong>Languages:</strong> ${backgroundDetails.data.languages}</li>`;
        } else if (backgroundDetails.languages) {
             htmlContent += `<li><strong>Languages:</strong> ${backgroundDetails.languages}</li>`;
        }

        if (backgroundDetails.data && backgroundDetails.data.equipment) {
            htmlContent += `<li><strong>Starting Equipment:</strong><br>${backgroundDetails.data.equipment.replace(/\n/g, '<br>')}</li>`;
        } else if (backgroundDetails.equipment) {
            htmlContent += `<li><strong>Starting Equipment:</strong><br>${backgroundDetails.equipment.replace(/\n/g, '<br>')}</li>`;
        }

        if (backgroundDetails.data && backgroundDetails.data.feature_name && backgroundDetails.data.feature_desc) {
            htmlContent += `<li><strong>Feature: ${backgroundDetails.data.feature_name}</strong><br>${backgroundDetails.data.feature_desc.replace(/\n/g, '<br>')}</li>`;
        } else if (backgroundDetails.feature_name && backgroundDetails.feature_desc) {
            htmlContent += `<li><strong>Feature: ${backgroundDetails.feature_name}</strong><br>${backgroundDetails.feature_desc.replace(/\n/g, '<br>')}</li>`;
        }

        htmlContent += '</ul>';

        if (backgroundDetails.benefits && Array.isArray(backgroundDetails.benefits) && backgroundDetails.benefits.length > 0) {
            htmlContent += `<h5>Benefits</h5>`;
            backgroundDetails.benefits.forEach(benefit => {
                if (benefit.name && benefit.desc) {
                    htmlContent += `<h6>${benefit.name}</h6><p>${benefit.desc.replace(/\n/g, '<br>')}</p>`;
                }
            });
        }

        if (backgroundDetails.data && backgroundDetails.data.suggested_characteristics) {
            htmlContent += `<h5>Suggested Characteristics</h5><div>${backgroundDetails.data.suggested_characteristics.replace(/\n/g, '<br>')}</div>`;
        } else if (backgroundDetails.suggested_characteristics) {
             htmlContent += `<h5>Suggested Characteristics</h5><div>${backgroundDetails.suggested_characteristics.replace(/\n/g, '<br>')}</div>`;
        }

        descriptionContainer.innerHTML = htmlContent;

        if (typeof characterCreationData !== 'undefined' && typeof saveCharacterDataToSession === 'function') {
            characterCreationData.step3_background_data_loaded = true;
            saveCharacterDataToSession();
            console.log("[DEBUG] displayBackgroundDetails: Set step3_background_data_loaded to true for slug:", slug);
        } else {
            console.error("characterCreationData or saveCharacterDataToSession not available globally for displayBackgroundDetails success path.");
        }
        console.log("Background details displayed and stored for:", slug);

    } catch (error) {
        console.error(`Error displaying background details for ${slug}:`, error);
        descriptionContainer.innerHTML = `<p class="error">Could not load details for ${slug}. ${error.message}</p>`;
        if (typeof characterCreationData !== 'undefined' && typeof saveCharacterDataToSession === 'function') {
            characterCreationData.step3_selected_background_slug = null;
            characterCreationData.step3_background_selection = null;
            characterCreationData.step3_background_data_loaded = false;
            saveCharacterDataToSession();
            console.log("[DEBUG] displayBackgroundDetails: Set step3_background_data_loaded to false due to error for slug:", slug);
        } else {
             console.error("characterCreationData or saveCharacterDataToSession not available globally for displayBackgroundDetails error path.");
        }
    }
}

// Note: `characterCreationData` and `saveCharacterDataToSession` are assumed to be globally available.
// If character_creation_step3.js is loaded as a module or in a context where these are not global,
// this script will need modification to correctly access them (e.g., via imports or by passing them as arguments).
