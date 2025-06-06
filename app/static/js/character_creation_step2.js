// --- Functions for Step 2: Class Selection ---

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

        if (baseClassData.features && Array.isArray(baseClassData.features) && baseClassData.features.length > 0) {
            htmlContent += '<h6>Key Base Class Features (may include higher level features):</h6><ul>';
            baseClassData.features.forEach(feature => {
                if (!selectedArchetypeData || !selectedArchetypeData.features || !selectedArchetypeData.features.find(archFeature => archFeature.slug === feature.slug || archFeature.name === feature.name)) {
                    htmlContent += `<li><strong>${feature.name}:</strong> ${feature.desc.substring(0,150)}...</li>`;
                    textSummary += `Base Class Feature: ${feature.name}\n`; // Clarified
                }
            });
            htmlContent += '</ul>';
        }


       descriptionContainer.innerHTML = htmlContent;
       // characterCreationData.step2_selection_details_text = textSummary.trim();
       // saveCharacterDataToSession(); // This line is commented out as per instruction for this subtask.
                                     // The main character_creation.js will handle saving after calling these.
       console.log("Details displayed for selection:", selectionSlug, "using base class:", baseClassData.slug);

   } catch (error) {
       console.error(`Error displaying details for ${selectionSlug}:`, error);
       descriptionContainer.innerHTML = `<p class="error">Could not load details for ${selectionSlug}. ${error.message}</p>`;
       characterCreationData.step2_selection_details_text = '';
       saveCharacterDataToSession();
   }
}
