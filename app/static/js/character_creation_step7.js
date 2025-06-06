async function loadStep7Logic() {
    console.log("Step 7 JS loaded and logic initiated");

    // --- DOM Element References ---
    const weaponSelect = document.getElementById('weapon-select');
    const addWeaponBtn = document.getElementById('add-weapon-btn');
    const selectedWeaponsList = document.getElementById('selected-weapons-list');

    const armorSelect = document.getElementById('armor-select');
    const addArmorBtn = document.getElementById('add-armor-btn');
    const selectedArmorList = document.getElementById('selected-armor-list');

    const customItemNameInput = document.getElementById('custom-item-name');
    const customItemQuantityInput = document.getElementById('custom-item-quantity');
    const customItemDescriptionInput = document.getElementById('custom-item-description');
    const addCustomItemBtn = document.getElementById('add-custom-item-btn');
    const customItemsList = document.getElementById('custom-items-list');

    let characterEquipment = {
        weapons: [], // Stores { name: string, slug: string, type: 'weapon' }
        armor: [],   // Stores { name: string, slug: string, type: 'armor' }
        custom: []   // Stores { name: string, quantity: number, description: string, type: 'custom' }
    };

    // --- Utility Functions ---
    async function fetchData(url) {
        try {
            const response = await fetch(url);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status} for URL: ${url}`);
            }
            return await response.json();
        } catch (error) {
            console.error("Error fetching data:", error);
            showGlobalMessage(`Error fetching data from ${url}: ${error.message}`, "error");
            return null; // Return null or empty array to prevent further errors
        }
    }

    function populateSelect(selectElement, items, placeholder) {
        if (!items || !items.results || !Array.isArray(items.results)) {
            console.error("Invalid items data for populating select:", items);
            selectElement.innerHTML = `<option value="">Error loading ${placeholder}</option>`;
            return;
        }
        selectElement.innerHTML = `<option value="">-- Select ${placeholder} --</option>`; // Clear existing options
        items.results.forEach(item => {
            // Assuming item.data contains the actual details and item.slug is the unique ID
            if (item.data && item.data.name && item.slug) {
                const option = document.createElement('option');
                option.value = item.slug; // Use slug as value
                option.textContent = item.data.name;
                option.dataset.name = item.data.name; // Store name for later use
                selectElement.appendChild(option);
            }
        });
    }

    function renderEquipmentList(listElement, items, type) {
        listElement.innerHTML = ''; // Clear current list
        items.forEach((item, index) => {
            const listItem = document.createElement('li');
            listItem.classList.add('list-group-item', 'd-flex', 'justify-content-between', 'align-items-center');
            let text = item.name;
            if (type === 'custom') {
                text += ` (Qty: ${item.quantity})${item.description ? ' - ' + item.description : ''}`;
            }
            listItem.textContent = text;

            const removeBtn = document.createElement('button');
            removeBtn.classList.add('btn', 'btn-danger', 'btn-sm');
            removeBtn.textContent = 'Remove';
            removeBtn.onclick = () => {
                if (type === 'weapon') characterEquipment.weapons.splice(index, 1);
                else if (type === 'armor') characterEquipment.armor.splice(index, 1);
                else if (type === 'custom') characterEquipment.custom.splice(index, 1);
                updateAndRenderAllLists();
                saveEquipmentToSession();
            };
            listItem.appendChild(removeBtn);
            listElement.appendChild(listItem);
        });
    }

    function updateAndRenderAllLists() {
        renderEquipmentList(selectedWeaponsList, characterEquipment.weapons, 'weapon');
        renderEquipmentList(selectedArmorList, characterEquipment.armor, 'armor');
        renderEquipmentList(customItemsList, characterEquipment.custom, 'custom');
    }

    async function saveEquipmentToSession() {
        const payload = {
            step7_equipment: characterEquipment // Store the whole object
        };
        try {
            const response = await fetch('/creation_wizard/update_session', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ step_key: 'step7_equipment_selection', payload: payload })
            });
            if (!response.ok) throw new Error('Failed to save equipment to session');
            const result = await response.json();
            console.log("Equipment saved to session:", result);
            // Optionally, update UI based on result.message or result.status
        } catch (error) {
            console.error("Error saving equipment to session:", error);
            showGlobalMessage("Error saving equipment choices. Please try again.", "error");
        }
    }

    // --- Event Listeners ---
    addWeaponBtn.addEventListener('click', () => {
        const selectedOption = weaponSelect.options[weaponSelect.selectedIndex];
        if (selectedOption && selectedOption.value) {
            // Check if weapon already added to prevent duplicates by slug
            if (!characterEquipment.weapons.some(w => w.slug === selectedOption.value)) {
                characterEquipment.weapons.push({
                    name: selectedOption.dataset.name,
                    slug: selectedOption.value,
                    type: 'weapon'
                });
                updateAndRenderAllLists();
                saveEquipmentToSession();
            } else {
                showGlobalMessage("Weapon already selected.", "warning");
            }
        } else {
            showGlobalMessage("Please select a weapon.", "info");
        }
    });

    addArmorBtn.addEventListener('click', () => {
        const selectedOption = armorSelect.options[armorSelect.selectedIndex];
        if (selectedOption && selectedOption.value) {
            // Check if armor already added
            if (!characterEquipment.armor.some(a => a.slug === selectedOption.value)) {
                characterEquipment.armor.push({
                    name: selectedOption.dataset.name,
                    slug: selectedOption.value,
                    type: 'armor'
                });
                updateAndRenderAllLists();
                saveEquipmentToSession();
            } else {
                showGlobalMessage("Armor already selected.", "warning");
            }
        } else {
            showGlobalMessage("Please select armor.", "info");
        }
    });

    addCustomItemBtn.addEventListener('click', () => {
        const name = customItemNameInput.value.trim();
        const quantity = parseInt(customItemQuantityInput.value, 10);
        const description = customItemDescriptionInput.value.trim();

        if (name && quantity > 0) {
            characterEquipment.custom.push({ name, quantity, description, type: 'custom' });
            updateAndRenderAllLists();
            saveEquipmentToSession();
            customItemNameInput.value = '';
            customItemQuantityInput.value = '1';
            customItemDescriptionInput.value = '';
        } else {
            showGlobalMessage("Please enter a valid name and quantity for custom items.", "error");
        }
    });

    // --- Initialization ---
    async function initializeStep7() {
        // Load existing equipment from session if available
        const initialData = getCurrentCharacterDataFromSession(); // Assumes this function exists globally or is passed
        if (initialData && initialData.step7_equipment) {
            characterEquipment = initialData.step7_equipment;
        } else if (window.wizardGlobalData && window.wizardGlobalData.current_character_data && window.wizardGlobalData.current_character_data.step7_equipment) {
            // Fallback to a global object if your wizard uses one to load initial step data
            characterEquipment = window.wizardGlobalData.current_character_data.step7_equipment;
        }


        // Fetch and populate weapons
        // The API endpoints are /api/v2/weapons/ and /api/v2/armor/
        // The `get_paginated_results` in open5e_api.py uses these table names 'weapons', 'armor'.
        // The actual routes are registered with a blueprint, so it might be /api/v2/weapons/ etc.
        // Assuming the API base is correctly handled by fetch.
        const weaponsData = await fetchData('/api/v2/weapons/?limit=200'); // Fetch a large number, ideally API supports 'all'
        if (weaponsData) {
            populateSelect(weaponSelect, weaponsData, 'Weapon');
        }

        // Fetch and populate armor
        const armorData = await fetchData('/api/v2/armor/?limit=200'); // Fetch a large number
        if (armorData) {
            populateSelect(armorSelect, armorData, 'Armor');
        }

        updateAndRenderAllLists(); // Render any loaded equipment
    }

    // Helper function to get current character data from session (if your main wizard script provides it)
    // This is a placeholder. You might need to adapt it to how your wizard manages session data access on the client-side.
    function getCurrentCharacterDataFromSession() {
        if (typeof wizardGlobalData !== 'undefined' && wizardGlobalData.current_character_data) {
            return wizardGlobalData.current_character_data;
        }
        // Attempt to get from a global function if your wizard uses one for AJAX updates
        if (typeof getCurrentWizardData === "function") {
             return getCurrentWizardData();
        }
        console.warn("Could not retrieve current character data from session for step 7 initialization.");
        return {};
    }

    // Add a basic showGlobalMessage if not already present from other scripts
    if (typeof showGlobalMessage === 'undefined') {
        window.showGlobalMessage = function(message, type = 'info') {
            // This is a very basic version. Integrate with your actual notification system.
            const messageArea = document.getElementById('global-message-area'); // Assume this exists in your main wizard HTML
            if (messageArea) {
                const alertDiv = document.createElement('div');
                alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
                alertDiv.role = 'alert';
                alertDiv.innerHTML = `${message}<button type="button" class="close" data-dismiss="alert" aria-label="Close"><span aria-hidden="true">&times;</span></button>`;
                messageArea.appendChild(alertDiv);
                setTimeout(() => {
                    // Attempt to dismiss the alert if Bootstrap's JS is loaded
                    if (window.bootstrap && alertDiv.classList.contains('show')) {
                        new window.bootstrap.Alert(alertDiv).close();
                    } else {
                         alertDiv.remove(); // Fallback removal
                    }
                }, 5000);
            } else {
                console.log(`Global Message (${type}): ${message}`);
                alert(`(${type.toUpperCase()}) ${message}`); // Fallback to simple alert
            }
        }
    }


    await initializeStep7();
}

// Ensure loadStep7Logic is called when the step is displayed.
// This might be handled by your main character creation wizard script.
// For example, if it dynamically loads content and then calls a specific function:
// document.addEventListener('DOMContentLoaded', loadStep7Logic); // Or called by main wizard script
