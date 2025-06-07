function loadStep7Logic() {
    console.log("Step 7 JS loaded");

    // Ensure this global variable is set by the template
    // For example: <script>var isDebugModeEnabled = {{ config.CHARACTER_CREATION_DEBUG_MODE | tojson }};</script>
    // Default to false if not defined, though it should be.
    const debugModeEnabled = typeof isDebugModeEnabled !== 'undefined' ? isDebugModeEnabled : false;

    const debugDiv = document.getElementById('character-creation-debug-div');
    const debugDataPre = document.getElementById('character-creation-debug-data');

    if (debugModeEnabled && debugDiv && debugDataPre) {
        try {
            const characterDataString = sessionStorage.getItem('characterCreationData');
            if (characterDataString) {
                const characterDataObject = JSON.parse(characterDataString);
                debugDataPre.textContent = JSON.stringify(characterDataObject, null, 2);
                debugDiv.style.display = 'block';
            } else {
                debugDataPre.textContent = 'characterCreationData not found in session storage.';
                debugDiv.style.display = 'block'; // Show div to indicate missing data
            }
        } catch (error) {
            console.error('Error processing character creation debug data:', error);
            debugDataPre.textContent = 'Error loading debug data. Check console for details.';
            debugDiv.style.display = 'block'; // Show div to indicate error
        }
    } else if (debugDiv) {
        debugDiv.style.display = 'none';
    }
}

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
