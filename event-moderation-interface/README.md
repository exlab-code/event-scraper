# Event Moderation Interface

A web-based interface for moderating events and providing feedback on LLM relevance determinations. This interface works in conjunction with the `event_analyzer.py` script to create a feedback loop that improves the LLM's relevance determinations over time.

## Features

- View and filter events by approval status, relevance, feedback, and LLM accuracy
- Easily identify events where the LLM made incorrect relevance determinations
- Approve or reject events
- Provide feedback on the LLM's relevance determinations
- Add notes explaining why an event was incorrectly classified
- View statistics on pending, approved, and rejected events
- Track the LLM's accuracy based on moderator feedback

## Setup

1. Place the files in a web server directory:
   - `index.html`
   - `styles.css`
   - `config.js`
   - `app.js`
   - `serve.py` (for local testing)

2. Set up the configuration:
   - The default configuration is in `config.js` (this file should be committed to Git)
   - Create a `config-secrets.js` file for sensitive information:
     - Copy `config-secrets.js.example` to `config-secrets.js`
     - Update the API URL and token in `config-secrets.js`
     - This file should NOT be committed to Git (it's in .gitignore)

3. Run the local server:
   ```
   python event-moderation-interface/serve.py
   ```
   This will start a server on port 8080 and open a browser window automatically.
   
   If port 8080 is already in use, the script will try port 8081 automatically.

4. Alternatively, you can use any web server to host the interface files

## Integration with event_analyzer.py

The moderation interface works with the `event_analyzer.py` script to create a feedback loop:

1. The script processes events and makes initial relevance determinations
2. Events are saved to the Directus database with pending approval status
3. Moderators use this interface to:
   - Approve or reject events
   - Provide feedback on the LLM's relevance determinations
   - Add notes explaining incorrect classifications
4. The script uses this feedback to improve future relevance determinations by:
   - Including examples of incorrectly classified events in the prompt
   - Extracting patterns from feedback to create concise rules
   - Tracking and reporting accuracy statistics
5. The script can also flag events where the LLM's determination doesn't match human feedback:
   ```
   python event_analyzer.py --flag-mismatches
   ```
   Or only flag mismatches without processing new events:
   ```
   python event_analyzer.py --only-flag
   ```

## How the Feedback System Works

The feedback system creates a learning loop that helps the AI get better at identifying relevant events over time. Here's how it works in simple terms:

### 1. Providing Feedback as a Moderator

When you review events in the moderation interface, you can:

- **Approve or Reject Events**: For each event, you can click "Approve" if the event should be included, or "Reject" if it should not be included.

- **Add Feedback Notes**: You can add notes about the event, especially if the LLM's relevance determination was incorrect. For example, "This event is actually relevant because it's specifically for non-profit organizations."

### 2. How Your Feedback Improves the System

Your feedback helps the system improve in three main ways:

#### Learning from Examples

The system remembers events where the AI was wrong and uses them as teaching examples. The next time the AI processes events, it will see these examples and learn from its past mistakes.

#### Finding Patterns in Mistakes

The system analyzes all feedback to find common patterns. For example, it might notice that events with certain words are often misclassified, and create rules to handle these cases better in the future.

#### Tracking Performance

The system keeps track of how often the AI gets it right, showing this as an accuracy percentage. This helps everyone see if the system is improving over time.

### 3. Recent Performance Improvements

We've recently optimized the system to:

- **Run Faster**: The system now collects all feedback once at the beginning of each processing run, rather than repeatedly for each event.

- **Keep Better Records**: The system now creates a detailed log file (`feedback_prompt_additions.log`) that shows exactly what feedback was used during each processing run.

- **Show Clear Statistics**: At the end of processing, the system shows how many feedback examples and patterns were used.

This optimization makes the system run much faster while still getting all the benefits of your feedback.

## Usage

### Viewing Events

- Use the filters at the top to view events by:
  - Status (Pending, Approved, Rejected, All)
  - LLM Relevance (Relevant, Not Relevant, All)
  - Feedback Status (With Feedback, Without Feedback, All)
- Use the search box to find specific events by title or description
- Navigate between pages using the pagination controls

### Moderating Events

For each event card:

1. Review the event details and the LLM's relevance determination
2. Click "Approve" or "Reject" to set the event's approval status
3. Add feedback notes about the event (optional)
4. Click "Save Notes" to save your feedback

### Statistics

The dashboard displays:
- Number of pending events
- Number of approved events
- Number of rejected events
- LLM accuracy based on moderator feedback

## Technical Details

- The interface communicates with the Directus API to fetch and update events
- It uses modern JavaScript (ES6+) and CSS3 features
- The design is responsive and works on desktop and mobile devices
- Statistics are refreshed automatically every minute

## Troubleshooting

### "No events found" Message

If you see a "No events found" message, this could be due to:

1. **No events in the database**: Run the `event_analyzer.py` script to process events:
   ```
   python event_analyzer.py
   ```

2. **Filter settings**: Try changing the filter settings to "All" for Status, Relevance, and Feedback.

3. **API connection issues**: Check the browser console (F12) for error messages.

### API Connection Issues

If you're having trouble connecting to the API:

1. **Check API URL and token**: Verify the API URL and token in `config.js` are correct.

2. **CORS issues**: The Directus server is configured to allow requests from `http://localhost:8080`. If you see CORS errors in the console, you have three options:

   a. **Use the CORS Proxy (Recommended)**:
      - Run the proxy server in a separate terminal:
        ```
        python event-moderation-interface/proxy.py
        ```
      - The proxy runs on port 9090 and forwards requests to the Directus API
      - The `config.js` file is already configured to use the proxy
      - If port 9090 is in use, the proxy will automatically try the next available port

   b. **Use the provided `serve.py` script with the proxy**:
      - Run the web server in one terminal:
        ```
        python event-moderation-interface/serve.py
        ```
      - Run the proxy server in another terminal:
        ```
        python event-moderation-interface/proxy.py
        ```
      - Both scripts will automatically find available ports if the defaults are in use

   c. **Use Demo Mode**:
      - The interface automatically shows sample events when CORS issues are detected
      - This is useful for testing the interface without API access

3. **Authentication**: Ensure the token has read/write permissions for the events collection.

### How the CORS Proxy Works

The `proxy.py` script creates a local server that:

1. Receives requests from the web interface
2. Forwards them to the Directus API
3. Adds the necessary CORS headers to the response
4. Returns the response to the web interface

This allows the interface to communicate with the API even when running on a different port or domain.

### Demo Mode

The interface includes a demo mode that activates automatically when CORS issues are detected:

1. **Sample Events**: Two sample events are displayed to demonstrate the interface functionality
2. **Full Functionality**: You can approve/reject events and provide feedback in demo mode
3. **Local State**: Changes are stored in the browser's memory (not saved to the server)

### Data Issues

1. **Missing fields**: Ensure the Directus database has the required fields:
   - `approved` (Boolean)
   - `relevance_feedback` (Boolean)
   - `feedback_notes` (Text)

2. **Field format issues**: Check that the data types match what the interface expects.

### Debug Mode

To enable detailed logging:

1. Set `debug: true` in the `config.js` file (already enabled by default)
2. Open the browser console (F12) to see API requests and responses
3. Look for error messages or unexpected response formats

### Running the Script

If the Python script fails to run:

1. Ensure all dependencies are installed:
   ```
   pip install -r requirements.txt
   ```

2. Check the API credentials in the script
3. Look for error messages in the console output

## Backlog / Known Issues

### Feedback Statistics Calculation Issue

There is a known issue with the feedback statistics calculation in both the `data-analysis-save-gpt-v2.py` script and the moderation interface:

#### Problem Details

1. **Script Issue**: In `event_analyzer.py`, the `get_feedback_stats` method uses an incorrect query syntax:
   ```python
   # In DirectusClient class, get_feedback_stats method (around line 180)
   url = f"{self.base_url}/items/events?filter[_and][][is_relevant][_eq]=$relevance_feedback&aggregate[count]=*"
   ```
   The `$relevance_feedback` variable substitution doesn't work in the Directus API. This syntax is attempting to find events where the `is_relevant` field equals the value of the `relevance_feedback` field for that same record, but Directus doesn't support this kind of dynamic comparison in its filter syntax.

2. **Interface Issue**: The LLM accuracy statistic displayed in the moderation interface header shows 0% because there's no code in `app.js` that properly calculates and updates this statistic.

3. **Impact**: This issue only affects the accuracy statistics display. The core functionality of event processing and feedback collection works correctly, and the feedback examples and patterns are still being used in the prompts.

#### Detailed Solution

To fix this issue in the future, implement these changes:

1. **For event_analyzer.py**:
   ```python
   def get_feedback_stats(self):
       """Get statistics about feedback and LLM performance"""
       # Get counts of events with feedback
       url = f"{self.base_url}/items/events?filter[relevance_feedback][_nnull]=true&aggregate[count]=*"
       response = requests.get(url, headers=self.headers)
       
       if response.status_code != 200:
           return {"total": 0, "accuracy": 0}
       
       total_feedback = response.json().get('data', [{}])[0].get('count', 0)
       
       if total_feedback == 0:
           return {"total": 0, "accuracy": 0}
       
       # Get events with feedback to calculate accuracy manually
       url = f"{self.base_url}/items/events?filter[relevance_feedback][_nnull]=true&fields=is_relevant,relevance_feedback&limit=100"
       response = requests.get(url, headers=self.headers)
       
       if response.status_code != 200:
           return {"total": total_feedback, "accuracy": 0}
       
       events = response.json().get('data', [])
       
       # Count matches manually
       correct_count = sum(1 for e in events if e.get('is_relevant') == e.get('relevance_feedback'))
       
       return {
           "total": total_feedback,
           "accuracy": correct_count / total_feedback if total_feedback > 0 else 0
       }
   ```

2. **For the moderation interface (app.js)**:
   Add a function to fetch and calculate the accuracy statistics:
   ```javascript
   // Add to the api object
   fetchStats: async function() {
       try {
           // Fetch events with feedback to calculate accuracy
           const url = `${CONFIG.api.baseUrl}/items/${CONFIG.api.eventsCollection}?filter[relevance_feedback][_nnull]=true&fields=is_relevant,relevance_feedback&limit=100`;
           
           const response = await fetch(url, {
               method: 'GET',
               headers: this.headers,
               mode: 'cors'
           });
           
           if (!response.ok) {
               throw new Error(`API error: ${response.status}`);
           }
           
           const data = await response.json();
           const events = data.data || [];
           
           // Calculate accuracy
           let correctCount = 0;
           events.forEach(event => {
               if (event.is_relevant === event.relevance_feedback) {
                   correctCount++;
               }
           });
           
           const accuracy = events.length > 0 ? (correctCount / events.length) * 100 : 0;
           
           // Update the accuracy display
           document.getElementById('accuracy').textContent = `${accuracy.toFixed(1)}%`;
           
           return accuracy;
       } catch (error) {
           console.error('Error calculating accuracy:', error);
           return 0;
       }
   }
   ```

3. **Call the stats function periodically**:
   ```javascript
   // Add to the init function
   setInterval(() => {
       api.fetchStats();
   }, CONFIG.statsRefreshInterval);
   ```

This approach manually fetches all events with feedback and calculates the accuracy by comparing the `is_relevant` and `relevance_feedback` fields, rather than trying to use the problematic variable substitution syntax.
