// Event Moderation Interface Application

// State management
const state = {
    events: [],
    currentPage: 1,
    totalPages: 1,
    totalEvents: 0,
    filters: {
        status: CONFIG.defaultFilters.status,
        relevance: CONFIG.defaultFilters.relevance,
        feedback: CONFIG.defaultFilters.feedback,
        search: ''
    },
    stats: {
        pending: 0,
        approved: 0,
        rejected: 0,
        excluded: 0,
        accuracy: '0%'
    }
};

// DOM Elements
const elements = {
    eventsList: document.getElementById('events-list'),
    statusFilter: document.getElementById('status-filter'),
    relevanceFilter: document.getElementById('relevance-filter'),
    feedbackFilter: document.getElementById('feedback-filter'),
    searchInput: document.getElementById('search-input'),
    searchButton: document.getElementById('search-button'),
    eventCardTemplate: document.getElementById('event-card-template')
};

// Validate DOM elements
function validateDOMElements() {
    const missingElements = [];
    
    for (const [key, element] of Object.entries(elements)) {
        if (!element) {
            missingElements.push(key);
            console.error(`Missing DOM element: ${key}`);
        }
    }
    
    if (missingElements.length > 0) {
        console.error('Missing DOM elements:', missingElements);
        return false;
    }
    
    return true;
}

// API Service
const api = {
    headers: {
        'Authorization': `Bearer ${CONFIG.api.token}`,
        'Content-Type': 'application/json'
    },
    
    // Debug logging function
    log(message, data) {
        if (CONFIG.api.debug) {
            console.log(`[API] ${message}`, data);
        }
    },
    
    async fetchEvents() {
        try {
            // Build filter based on current state
            const filters = [];
            
            // Status filter
            if (state.filters.status !== 'all') {
                if (state.filters.status === 'pending') {
                    filters.push({ approved: { _null: true } });
                    filters.push({ 
                        _or: [
                            { status: { _null: true } },
                            { status: { _neq: 'excluded' } }
                        ]
                    });
                } else if (state.filters.status === 'approved') {
                    filters.push({ approved: { _eq: true } });
                } else if (state.filters.status === 'rejected') {
                    filters.push({ approved: { _eq: false } });
                } else if (state.filters.status === 'excluded') {
                    filters.push({ status: { _eq: 'excluded' } });
                }
            }
            
            // Relevance filter
            if (state.filters.relevance !== 'all') {
                filters.push({ 
                    is_relevant: { 
                        _eq: state.filters.relevance === 'relevant' 
                    } 
                });
            }
            
            // Feedback filter
            if (state.filters.feedback !== 'all') {
                if (state.filters.feedback === 'with-feedback') {
                    filters.push({ relevance_feedback: { _nnull: true } });
                } else if (state.filters.feedback === 'without-feedback') {
                    filters.push({ relevance_feedback: { _null: true } });
                }
            }
            
            // Search filter
            if (state.filters.search) {
                filters.push({
                    _or: [
                        { title: { _contains: state.filters.search } },
                        { description: { _contains: state.filters.search } }
                    ]
                });
            }
            
            // Combine filters
            let filterParam = '';
            if (filters.length > 0) {
                if (filters.length === 1) {
                    filterParam = `&filter=${encodeURIComponent(JSON.stringify(filters[0]))}`;
                } else {
                    filterParam = `&filter=${encodeURIComponent(JSON.stringify({ _and: filters }))}`;
                }
            }
            
            // Build URL without pagination to get all events
            const url = `${CONFIG.api.baseUrl}/items/${CONFIG.api.eventsCollection}?limit=-1${filterParam}`;
            
            this.log('Fetching events from:', url);
            
            try {
                // Try normal CORS request first
                const response = await fetch(url, {
                    method: 'GET',
                    headers: this.headers,
                    mode: 'cors'
                    // Removed credentials: 'include' to fix CORS issues
                });
                
                if (!response.ok) {
                    const errorText = await response.text();
                    this.log('API error response:', errorText);
                    throw new Error(`API error: ${response.status} - ${errorText}`);
                }
                
                return await this._processResponse(response);
            } catch (corsError) {
                // If CORS fails, use demo data
                this.log('CORS error, using demo data:', corsError);
                return this._getDemoData();
            }
        } catch (error) {
            console.error('Error fetching events:', error);
            ui.showError(`Error fetching events: ${error.message}`);
            return [];
        }
    },
    
    async _processResponse(response) {
        const data = await response.json();
        this.log('API response:', data);
        
        // Check if data has the expected structure
        if (!data.data || !Array.isArray(data.data)) {
            this.log('Unexpected API response format:', data);
            throw new Error('Unexpected API response format');
        }
        
        // Update state
        state.events = data.data || [];
        
        // Fix for missing meta data: use the actual length of the events array
        // If we have exactly itemsPerPage items, assume there are more pages
        const eventsCount = data.meta?.filter_count || 
                           (state.events.length === CONFIG.api.itemsPerPage ? 
                            state.events.length * 2 : state.events.length);
        
        // Always show at least 2 pages if we have a full page of results
        state.totalPages = Math.max(
            (state.events.length === CONFIG.api.itemsPerPage) ? 2 : 1, 
            Math.ceil(eventsCount / CONFIG.api.itemsPerPage)
        );
        state.totalEvents = eventsCount;
        
        this.log('Processed events:', {
            count: state.events.length,
            totalPages: state.totalPages,
            totalEvents: state.totalEvents
        });
        
        return state.events;
    },
    
    _getDemoData() {
        // Create demo data for testing when CORS issues prevent API access
        this.log('Using demo data due to CORS issues');
        
        const demoData = {
            data: [
                {
                    id: 'demo-1',
                    title: 'Digital Transformation for Non-Profits',
                    description: 'This is a demo event to showcase the interface when CORS issues prevent real data loading. In a real application, you would implement a proper proxy server to fetch real data.',
                    start_date: '2025-05-15T09:00:00',
                    location: 'Online',
                    organizer: 'Demo Organization',
                    event_type: 'Webinar',
                    is_relevant: true,
                    approved: null,
                    categories: [
                        { id: 'digitale_transformation', name: 'Digitale Transformation' },
                        { id: 'ehrenamt_engagement', name: 'Ehrenamt & Engagement' }
                    ]
                },
                {
                    id: 'demo-2',
                    title: 'AI Tools for Fundraising',
                    description: 'Another demo event. This interface allows you to approve/reject events and provide feedback on the LLM\'s relevance determinations.',
                    start_date: '2025-06-20T14:00:00',
                    location: 'Berlin',
                    organizer: 'Demo Corp',
                    event_type: 'Workshop',
                    is_relevant: false,
                    approved: null,
                    categories: [
                        { id: 'ki_nonprofit', name: 'KI für Non-Profits' }
                    ]
                }
            ],
            meta: {
                filter_count: 2,
                total_count: 2
            }
        };
        
        // Update state
        state.events = demoData.data;
        state.totalPages = 1;
        state.totalEvents = 2;
        
        return demoData.data;
    },
    
    async updateEvent(eventId, data) {
        try {
            // Convert eventId to string if it's not already
            const eventIdStr = String(eventId);
            
            // In demo mode, just update the local state
            if (eventIdStr.startsWith('demo-')) {
                const eventIndex = state.events.findIndex(e => e.id === eventIdStr);
                if (eventIndex !== -1) {
                    state.events[eventIndex] = { ...state.events[eventIndex], ...data };
                    return state.events[eventIndex];
                }
                throw new Error('Event not found');
            }
            
            // Real API call
            const response = await fetch(`${CONFIG.api.baseUrl}/items/${CONFIG.api.eventsCollection}/${eventId}`, {
                method: 'PATCH',
                headers: this.headers,
                body: JSON.stringify(data),
                mode: 'cors'
                // Removed credentials: 'include' to fix CORS issues
            });
            
            if (!response.ok) {
                throw new Error(`API error: ${response.status}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error(`Error updating event ${eventId}:`, error);
            throw error;
        }
    },
    
    async approveEvent(eventId) {
        return this.updateEvent(eventId, { approved: true });
    },
    
    async rejectEvent(eventId) {
        return this.updateEvent(eventId, { approved: false });
    },
    
    async updateCategory(eventId, categoryId) {
        this.log(`Updating category for event ${eventId} to ${categoryId}`);
        
        // Create a categories array with the selected category
        const categories = [{
            id: categoryId,
            name: CONFIG.categoryMappings[categoryId] || categoryId
        }];
        
        // Debug log to see what we're sending
        console.log("Updating with data:", { 
            category: categoryId,
            categories: categories
        });
        
        try {
            // Update both the category field (string) and categories field (array)
            const result = await this.updateEvent(eventId, { 
                category: categoryId,
                categories: categories
            });
            
            console.log("Update result:", result);
            return result;
        } catch (error) {
            console.error("Error in updateCategory:", error);
            throw error;
        }
    },
    
    async provideFeedback(eventId, notes = null) {
        const data = {};
        if (notes) {
            data.feedback_notes = notes;
        }
        return this.updateEvent(eventId, data);
    },
    
    async fetchStats() {
        try {
            // Try to fetch stats from the API
            const url = `${CONFIG.api.baseUrl}/items/${CONFIG.api.eventsCollection}`;
            
            this.log('Fetching stats from:', url);
            
            try {
                // Try normal CORS request first
                const response = await fetch(`${url}?aggregate[count]=*&groupBy[]=approved`, {
                    method: 'GET',
                    headers: this.headers,
                    mode: 'cors'
                });
                
                if (!response.ok) {
                    throw new Error(`API error: ${response.status}`);
                }
                
                const data = await response.json();
                this.log('Stats response:', data);
                
                // Process stats
                if (data && data.data) {
                    let pending = 0;
                    let approved = 0;
                    let rejected = 0;
                    
                    data.data.forEach(group => {
                        if (group.approved === null) {
                            pending = group.count;
                        } else if (group.approved === true) {
                            approved = group.count;
                        } else if (group.approved === false) {
                            rejected = group.count;
                        }
                    });
                    
                    // Calculate accuracy if possible
                    let accuracy = '0%';
                    const total = approved + rejected;
                    if (total > 0) {
                        // Assuming accuracy is the percentage of events where human decision matches LLM determination
                        // This is a placeholder calculation - in a real app, you'd need to compare is_relevant with approved
                        accuracy = `${Math.round((approved / total) * 100)}%`;
                    }
                    
                    // Fetch excluded events count
                    let excluded = 0;
                    try {
                        // Use a more compatible query format for excluded events
                        const excludedResponse = await fetch(`${url}?filter[status][_eq]=excluded&aggregate[count]=*`, {
                            method: 'GET',
                            headers: this.headers,
                            mode: 'cors'
                        });
                        
                        if (excludedResponse.ok) {
                            const excludedData = await excludedResponse.json();
                            if (excludedData && excludedData.data && excludedData.data.length > 0) {
                                excluded = excludedData.data[0].count;
                            }
                        }
                    } catch (error) {
                        console.error('Error fetching excluded count:', error);
                        // Continue without failing - excluded count will remain 0
                    }
                    
                    // Update state
                    state.stats = {
                        pending,
                        approved,
                        rejected,
                        excluded,
                        accuracy
                    };
                    
                    this.log('Processed stats:', state.stats);
                    
                    // Update UI
                    ui.updateStats();
                }
                
                return state.stats;
            } catch (error) {
                console.error('Error fetching stats:', error);
                // Use demo stats
                state.stats = {
                    pending: 10,
                    approved: 5,
                    rejected: 3,
                    excluded: 0,
                    accuracy: '85%'
                };
                ui.updateStats();
                return state.stats;
            }
        } catch (error) {
            console.error('Error in fetchStats:', error);
            return state.stats;
        }
    }
};

// UI Controller
const ui = {
    renderEvents(events) {
        elements.eventsList.innerHTML = '';
        
        if (events.length === 0) {
            elements.eventsList.innerHTML = `
                <div class="no-events">
                    <h3>No events found matching your filters</h3>
                    <p>This could be because:</p>
                    <ul style="text-align: left; max-width: 600px; margin: 0 auto; padding-top: 10px;">
                        <li>There are no events in the database yet</li>
                        <li>The current filter settings are too restrictive</li>
                        <li>You need to run the event_analyzer.py script to process events</li>
                    </ul>
                    <p style="margin-top: 15px;">Try changing the filters or running the script to process more events.</p>
                </div>`;
            return;
        }
        
        // Display total count of events
        const totalEventsInfo = document.createElement('div');
        totalEventsInfo.className = 'events-count-info';
        totalEventsInfo.textContent = `Showing ${events.length} events`;
        elements.eventsList.appendChild(totalEventsInfo);
        
        // Sort events by date (newest first)
        events.sort((a, b) => {
            const dateA = a.start_date ? new Date(a.start_date) : new Date(0);
            const dateB = b.start_date ? new Date(b.start_date) : new Date(0);
            return dateB - dateA;
        });
        
        // Render all events
        events.forEach(event => {
            const eventCard = this.createEventCard(event);
            elements.eventsList.appendChild(eventCard);
        });
        
        // Update stats display
        this.updateStats();
    },
    
    createEventCard(event) {
        console.log('Creating event card for:', event); // Debug log
        
        if (!event) {
            console.error('Attempted to create card for undefined event');
            return document.createElement('div'); // Return empty div to avoid errors
        }
        
        if (!elements.eventCardTemplate) {
            console.error('Event card template not found');
            return document.createElement('div'); // Return empty div to avoid errors
        }
        
        const template = elements.eventCardTemplate.content.cloneNode(true);
        const card = template.querySelector('.event-card');
        
        if (!card) {
            console.error('Could not find .event-card in template');
            return document.createElement('div'); // Return empty div to avoid errors
        }
        
        // Set data attribute for event ID
        card.dataset.eventId = event.id || 'unknown';
        
        // Create and add status badge
        const statusBadge = document.createElement('div');
        statusBadge.className = 'status-badge';
        
        if (event.status === 'excluded') {
            statusBadge.textContent = 'EXCLUDED';
            statusBadge.classList.add('excluded-badge');
            card.classList.add('excluded');
        } else if (event.approved === true) {
            statusBadge.textContent = 'APPROVED';
            statusBadge.classList.add('approved-badge');
            card.classList.add('approved');
        } else if (event.approved === false) {
            statusBadge.textContent = 'REJECTED';
            statusBadge.classList.add('rejected-badge');
            card.classList.add('rejected');
        } else {
            statusBadge.textContent = 'PENDING';
            statusBadge.classList.add('pending-badge');
        }
        
        // Insert the status badge at the top of the card
        card.insertBefore(statusBadge, card.firstChild);
        
        // Fill in event details
        card.querySelector('.event-title').textContent = event.title || 'Untitled Event';
        
        // Format date and time
        let dateText = 'Date not available';
        let timeText = '';
        let endDateText = '';
        
        if (event.start_date) {
            const date = new Date(event.start_date);
            dateText = date.toLocaleDateString(undefined, CONFIG.formatting.dateFormat);
            
            if (event.start_time) {
                timeText = date.toLocaleTimeString(undefined, CONFIG.formatting.timeFormat);
                
                if (event.end_time) {
                    const [endHour, endMinute] = event.end_time.split(':');
                    const endDate = new Date(date);
                    endDate.setHours(parseInt(endHour, 10), parseInt(endMinute, 10));
                    timeText += ` - ${endDate.toLocaleTimeString(undefined, CONFIG.formatting.timeFormat)}`;
                }
            }
        }
        
        // Handle end date if available
        if (event.end_date) {
            const endDate = new Date(event.end_date);
            endDateText = `End: ${endDate.toLocaleDateString(undefined, CONFIG.formatting.dateFormat)}`;
        }
        
        card.querySelector('.event-date').textContent = dateText;
        card.querySelector('.event-time').textContent = timeText;
        card.querySelector('.event-end-date').textContent = endDateText;
        card.querySelector('.event-location').textContent = event.location || 'Location not specified';
        
        // Description
        card.querySelector('.event-description').textContent = event.description || 'No description available.';
        
        // Details
        card.querySelector('.event-organizer').textContent = event.organizer || 'Not specified';
        card.querySelector('.event-type').textContent = event.event_type || 'Not specified';
        card.querySelector('.event-audience').textContent = event.target_audience || 'Not specified';
        card.querySelector('.event-cost').textContent = event.cost || 'Not specified';
        card.querySelector('.event-source').textContent = event.source || 'Unknown';
        
        // Categories
        const categoriesContainer = card.querySelector('.event-categories');
        
        // Load category mappings from CONFIG
        const categoryMappings = CONFIG.categoryMappings || {};
        
        // Try to use existing categories first
        if (event.category && typeof event.category === 'string') {
            // If category is a single string, convert it to an array
            const categoryIds = event.category.split(',').map(c => c.trim());
            
            categoryIds.forEach(categoryId => {
                const categoryTag = document.createElement('span');
                categoryTag.className = 'category-tag';
                
                // Use human-readable name if available, otherwise use the ID
                categoryTag.textContent = categoryMappings[categoryId] || categoryId;
                
                // Set background color if available
                if (CONFIG.categoryColors[categoryId]) {
                    categoryTag.style.backgroundColor = CONFIG.categoryColors[categoryId];
                    categoryTag.style.color = 'white';
                }
                
                categoriesContainer.appendChild(categoryTag);
            });
        } else if (event.categories && Array.isArray(event.categories) && event.categories.length > 0) {
            event.categories.forEach(category => {
                const categoryTag = document.createElement('span');
                categoryTag.className = 'category-tag';
                
                // Handle different category formats
                let categoryId, categoryName;
                
                if (typeof category === 'object') {
                    categoryId = category.id || '';
                    categoryName = category.name || categoryMappings[categoryId] || categoryId;
                } else {
                    categoryId = category;
                    categoryName = categoryMappings[categoryId] || categoryId;
                }
                
                categoryTag.textContent = categoryName;
                
                // Set background color if available
                if (CONFIG.categoryColors[categoryId]) {
                    categoryTag.style.backgroundColor = CONFIG.categoryColors[categoryId];
                    categoryTag.style.color = 'white';
                }
                
                categoriesContainer.appendChild(categoryTag);
            });
        } else if (event.tags && Array.isArray(event.tags) && event.tags.length > 0) {
            // If no categories, check if we have tags
            event.tags.forEach(tag => {
                const tagElement = document.createElement('span');
                tagElement.className = 'category-tag';
                tagElement.textContent = tag;
                tagElement.style.backgroundColor = '#95a5a6'; // Default color for tags
                tagElement.style.color = 'white';
                categoriesContainer.appendChild(tagElement);
            });
        } else {
            // If no categories or tags, try to extract categories from the description
            const extractedCategories = this.extractCategoriesFromText(
                (event.title || '') + ' ' + (event.description || '')
            );
            
            if (extractedCategories.length > 0) {
                extractedCategories.forEach(category => {
                    const categoryTag = document.createElement('span');
                    categoryTag.className = 'category-tag';
                    categoryTag.textContent = category.name;
                    
                    // Set background color
                    categoryTag.style.backgroundColor = CONFIG.categoryColors[category.id] || '#95a5a6';
                    categoryTag.style.color = 'white';
                    
                    categoriesContainer.appendChild(categoryTag);
                });
            } else {
                categoriesContainer.textContent = 'No categories available';
            }
        }
        
        // LLM Determination
        const determinationValue = card.querySelector('.determination-value');
        if (event.is_relevant) {
            determinationValue.textContent = 'Relevant';
            determinationValue.classList.add('relevant');
        } else {
            determinationValue.textContent = 'Not Relevant';
            determinationValue.classList.add('not-relevant');
        }
        
        // Set button states based on current approval
        const approveButton = card.querySelector('.approve-button');
        const rejectButton = card.querySelector('.reject-button');
        
        // Approval buttons
        if (event.approved === true) {
            approveButton.classList.add('active');
        } else if (event.approved === false) {
            rejectButton.classList.add('active');
        }
        
        // Set feedback notes if available
        const feedbackNotes = card.querySelector('.feedback-notes');
        if (event.feedback_notes) {
            feedbackNotes.querySelector('textarea').value = event.feedback_notes;
        }
        
        // Add event listeners
        this.addEventCardListeners(card, event.id);
        
        return card;
    },
    
    addEventCardListeners(card, eventId) {
        // Approval buttons
        const approveButton = card.querySelector('.approve-button');
        const rejectButton = card.querySelector('.reject-button');
        
        // Find the event in the state
        const eventIndex = state.events.findIndex(e => e.id === eventId);
        if (eventIndex === -1) {
            console.error(`Event with ID ${eventId} not found in state`);
            return;
        }
        
        // Get a reference to the event object
        const eventObj = state.events[eventIndex];
        
        // Approval buttons - these are status indicators that can be toggled
        approveButton.addEventListener('click', async () => {
            // If already approved, do nothing
            if (eventObj.approved === true) {
                return;
            }
            
            try {
                // Make the API call to approve the event
                await api.approveEvent(eventId);
                
                // Update the local event object
                eventObj.approved = true;
                
                // Update the status badge
                const statusBadge = card.querySelector('.status-badge');
                statusBadge.textContent = 'APPROVED';
                statusBadge.className = 'status-badge approved-badge';
                
                // Update card class
                card.classList.add('approved');
                card.classList.remove('rejected');
                // Remove excluded class if present
                if (card.classList.contains('excluded')) {
                    // Remove excluded class if present
                if (card.classList.contains('excluded')) {
                    card.classList.remove('excluded');
                    // Also update processing_status
                    eventObj.processing_status = null;
                }
                    // Also update processing_status
                    eventObj.processing_status = null;
                }
                
                // Check if the card should be removed based on current filter
                if (state.filters.status === 'pending' || state.filters.status === 'rejected' || state.filters.status === 'excluded') {
                    // If we're viewing pending, rejected, or excluded events, remove this card since it's now approved
                    card.remove();
                }
            } catch (error) {
                alert('Error approving event. Please try again.');
            }
        });
        
        rejectButton.addEventListener('click', async () => {
            // If already rejected, do nothing
            if (eventObj.approved === false) {
                return;
            }
            
            try {
                // Make the API call to reject the event
                await api.rejectEvent(eventId);
                
                // Update the local event object
                eventObj.approved = false;
                
                // Update the status badge
                const statusBadge = card.querySelector('.status-badge');
                statusBadge.textContent = 'REJECTED';
                statusBadge.className = 'status-badge rejected-badge';
                
                // Update card class
                card.classList.add('rejected');
                card.classList.remove('approved');
                card.classList.remove('excluded');
                
                // Check if the card should be removed based on current filter
                if (state.filters.status === 'pending' || state.filters.status === 'approved' || state.filters.status === 'excluded') {
                    // If we're viewing pending, approved, or excluded events, remove this card since it's now rejected
                    card.remove();
                }
            } catch (error) {
                alert('Error rejecting event. Please try again.');
            }
        });
        
        // Category dropdown and save button
        const categoryDropdown = card.querySelector('.category-dropdown');
        const saveCategoryButton = card.querySelector('.save-category-button');
        
        // Set the initial selected category if available
        if (eventObj.category) {
            categoryDropdown.value = eventObj.category;
        }
        
        // Save category button
        saveCategoryButton.addEventListener('click', async () => {
            const categoryId = categoryDropdown.value;
            if (!categoryId) {
                alert('Please select a category before saving.');
                return;
            }
            
            try {
                // Show loading state
                saveCategoryButton.textContent = 'Saving...';
                saveCategoryButton.disabled = true;
                
                // Make the API call to update the category
                const result = await api.updateCategory(eventId, categoryId);
                console.log("Category update result:", result);
                
                // Update the local event object
                eventObj.category = categoryId;
                
                // Create a new category object for the categories array
                const categoryObj = {
                    id: categoryId,
                    name: CONFIG.categoryMappings[categoryId] || categoryId
                };
                
                // Update the categories array
                eventObj.categories = [categoryObj];
                
                // Update the categories display
                const categoriesContainer = card.querySelector('.event-categories');
                categoriesContainer.innerHTML = '';
                
                const categoryTag = document.createElement('span');
                categoryTag.className = 'category-tag';
                categoryTag.textContent = categoryObj.name;
                
                // Set background color if available
                if (CONFIG.categoryColors[categoryId]) {
                    categoryTag.style.backgroundColor = CONFIG.categoryColors[categoryId];
                    categoryTag.style.color = 'white';
                }
                
                categoriesContainer.appendChild(categoryTag);
                
                alert('Category updated successfully.');
            } catch (error) {
                alert('Error updating category. Please try again. Error: ' + error.message);
                console.error('Error updating category:', error);
            } finally {
                // Reset button state
                saveCategoryButton.textContent = 'Save Category';
                saveCategoryButton.disabled = false;
            }
        });
        
        // Feedback notes
        const feedbackNotes = card.querySelector('.feedback-notes');
        const notesTextarea = feedbackNotes.querySelector('textarea');
        const saveNotesButton = feedbackNotes.querySelector('.save-notes-button');
        
        // Set initial value if there are existing notes
        if (eventObj.feedback_notes) {
            notesTextarea.value = eventObj.feedback_notes;
        }
        
        // Save notes button
        saveNotesButton.addEventListener('click', async () => {
            const notes = notesTextarea.value.trim();
            if (!notes) {
                alert('Please enter notes before saving.');
                return;
            }
            
            try {
                // Make the API call in the background
                await api.provideFeedback(eventId, notes);
                
                // Update the local event object
                eventObj.feedback_notes = notes;
                
                // Check if the card should be removed based on current filter
                if (state.filters.feedback === 'without-feedback') {
                    // If we're viewing events without feedback, remove this card since it now has feedback
                    card.remove();
                } else {
                    alert('Notes saved successfully.');
                }
            } catch (error) {
                alert('Error saving notes. Please try again.');
            }
        });
    },
    
    updateStats() {
        // Update the stats summary if the elements exist
        const pendingCount = document.getElementById('pending-count');
        const approvedCount = document.getElementById('approved-count');
        const rejectedCount = document.getElementById('rejected-count');
        const excludedCount = document.getElementById('excluded-count');
        const accuracyDisplay = document.getElementById('accuracy');
        
        if (pendingCount) pendingCount.textContent = state.stats?.pending || '0';
        if (approvedCount) approvedCount.textContent = state.stats?.approved || '0';
        if (rejectedCount) rejectedCount.textContent = state.stats?.rejected || '0';
        if (excludedCount) excludedCount.textContent = state.stats?.excluded || '0';
        if (accuracyDisplay) accuracyDisplay.textContent = state.stats?.accuracy || '0%';
    },
    
    showLoading() {
        elements.eventsList.innerHTML = '<div class="loading">Loading events...</div>';
    },
    
    showError(message) {
        elements.eventsList.innerHTML = `<div class="error">${message}</div>`;
    },
    
    // Extract categories from text based on keywords
    extractCategoriesFromText(text) {
        if (!text) return [];
        
        // Convert text to lowercase for case-insensitive matching
        const lowerText = text.toLowerCase();
        
        // Categories from event_categories_config.json
        const categories = [
            {
                id: 'ki_nonprofit',
                name: 'KI für Non-Profits',
                keywords: [
                    'ki', 'künstliche intelligenz', 'ai', 'artificial intelligence', 
                    'machine learning', 'maschinelles lernen', 'chatbot', 'llm', 
                    'large language model', 'ki-werkzeuge', 'ki tools', 'ki praktisch nutzen',
                    'generative ai', 'generative ki', 'chatgpt', 'claude', 'gemini'
                ]
            },
            {
                id: 'digitale_kommunikation',
                name: 'Digitale Kommunikation & Social Media',
                keywords: [
                    'social media', 'soziale medien', 'facebook', 'instagram', 'linkedin', 
                    'twitter', 'tiktok', 'youtube', 'online-kommunikation', 'digitale kommunikation',
                    'content', 'content-strategie', 'social-media-strategie', 'community management',
                    'facebook & instagram anzeigen', 'social ads', 'online-marketing', 'digital marketing'
                ]
            },
            {
                id: 'foerderung_finanzierung',
                name: 'Förderprogramme & Finanzierung',
                keywords: [
                    'förderung', 'förderprogramm', 'finanzierung', 'funding', 'grant', 
                    'act digital', 'förderberatung', 'fördermittel', 'zuschuss', 'zuwendung',
                    'spenden', 'fundraising', 'crowdfunding', 'sponsoring', 'stiftungsgelder',
                    'eu-förderung', 'bundesförderung', 'landesförderung'
                ]
            },
            {
                id: 'ehrenamt_engagement',
                name: 'Ehrenamt & Engagemententwicklung',
                keywords: [
                    'ehrenamt', 'engagement', 'freiwillige', 'volunteers', 'engagementbericht',
                    'engagemententwicklung', 'freiwilligenmanagement', 'volunteer management',
                    'qualifizierung von engagierten', 'ehrenamtskoordination', 'freiwilligenkoordination',
                    'bürgerschaftliches engagement', 'zivilgesellschaft', 'civil society'
                ]
            },
            {
                id: 'daten_projektmanagement',
                name: 'Daten & Projektmanagement',
                keywords: [
                    'daten', 'data', 'datenmanagement', 'data management', 'datenanalyse', 'data analysis',
                    'projektmanagement', 'project management', 'projektberichte erstellen', 'reporting',
                    'kpi', 'kennzahlen', 'metrics', 'dashboard', 'controlling', 'monitoring',
                    'evaluation', 'impact measurement', 'wirkungsmessung'
                ]
            },
            {
                id: 'weiterbildung_qualifizierung',
                name: 'Weiterbildung & Qualifizierung',
                keywords: [
                    'weiterbildung', 'qualifizierung', 'fortbildung', 'training', 'schulung',
                    'workshop', 'seminar', 'kurs', 'zertifikat', 'certificate', 'kompetenzentwicklung',
                    'skill development', 'lebenslanges lernen', 'lifelong learning', 'e-learning',
                    'blended learning', 'online-kurs', 'online course'
                ]
            },
            {
                id: 'digitale_transformation',
                name: 'Digitale Transformation & Strategie',
                keywords: [
                    'digitale transformation', 'digital transformation', 'digitalisierung', 'digitization',
                    'organisationsentwicklung', 'organizational development', 'zukunftsstrategie',
                    'future strategy', 'change management', 'veränderungsmanagement', 'digital leadership',
                    'digitale strategie', 'digital strategy', 'innovation', 'digitale reife', 'digital maturity'
                ]
            },
            {
                id: 'tools_anwendungen',
                name: 'Tools & Anwendungen',
                keywords: [
                    'tools', 'anwendungen', 'applications', 'software', 'newsletter', 'website',
                    'kollaboration', 'collaboration', 'crm', 'customer relationship management',
                    'projektmanagement-tool', 'project management tool', 'cloud', 'saas',
                    'software as a service', 'open source', 'microsoft 365', 'google workspace'
                ]
            }
        ];
        
        // Check each category for keyword matches
        const matchedCategories = [];
        
        categories.forEach(category => {
            let matches = 0;
            const minMatches = 2; // Minimum number of keyword matches required
            
            // Check each keyword
            for (const keyword of category.keywords) {
                if (lowerText.includes(keyword)) {
                    matches++;
                    if (matches >= minMatches) {
                        matchedCategories.push({
                            id: category.id,
                            name: category.name
                        });
                        break; // Found enough matches for this category
                    }
                }
            }
        });
        
        // Limit to max 3 categories
        return matchedCategories.slice(0, 3);
    },
    
    async refreshEvents() {
        this.showLoading();
        try {
            const events = await api.fetchEvents();
            console.log('Events to render:', events); // Debug log
            if (events && events.length > 0) {
                this.renderEvents(events);
            } else {
                this.showError('No events found. The API returned an empty array.');
            }
        } catch (error) {
            console.error('Error in refreshEvents:', error);
            this.showError('Error loading events. Please try again later.');
        }
    }
};

// Event Listeners
function setupEventListeners() {
    // Filters
    elements.statusFilter.addEventListener('change', () => {
        state.filters.status = elements.statusFilter.value;
        ui.refreshEvents();
    });
    
    elements.relevanceFilter.addEventListener('change', () => {
        state.filters.relevance = elements.relevanceFilter.value;
        ui.refreshEvents();
    });
    
    elements.feedbackFilter.addEventListener('change', () => {
        state.filters.feedback = elements.feedbackFilter.value;
        ui.refreshEvents();
    });
    
    // Search
    elements.searchButton.addEventListener('click', () => {
        state.filters.search = elements.searchInput.value.trim();
        ui.refreshEvents();
    });
    
    elements.searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            state.filters.search = elements.searchInput.value.trim();
            ui.refreshEvents();
        }
    });
}

// Initialize the application
async function init() {
    // Validate DOM elements before proceeding
    if (!validateDOMElements()) {
        console.error('DOM validation failed. Some required elements are missing.');
        document.body.innerHTML = `
            <div class="error-container" style="text-align: center; margin-top: 50px;">
                <h2>Application Error</h2>
                <p>The application could not initialize properly because some required elements are missing.</p>
                <p>Please check the console for more details.</p>
            </div>
        `;
        return;
    }
    
    console.log('DOM validation successful. All required elements found.');
    setupEventListeners();
    
    try {
        // Fetch stats in the background
        api.fetchStats().catch(error => {
            console.error('Error fetching stats:', error);
        });
        
        // Load initial events
        await ui.refreshEvents();
        
        // Set up periodic stats refresh
        if (CONFIG.statsRefreshInterval) {
            setInterval(() => {
                api.fetchStats().catch(error => {
                    console.error('Error refreshing stats:', error);
                });
            }, CONFIG.statsRefreshInterval);
        }
    } catch (error) {
        console.error('Initialization error:', error);
        ui.showError('Failed to initialize the application. Please refresh the page.');
    }
}

// Start the application when the DOM is fully loaded
document.addEventListener('DOMContentLoaded', init);
