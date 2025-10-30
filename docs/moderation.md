# Event Moderation

Event moderation is handled through the Directus admin interface, which provides a powerful and flexible system for reviewing and managing events.

## Accessing the Moderation Interface

Access the Directus admin interface at: **https://calapi.buerofalk.de/admin**

## Features

The Directus admin interface provides comprehensive moderation capabilities:

- **Filtering and Sorting**: Filter events by approval status, date, tags, and custom fields
- **Bulk Operations**: Approve or reject multiple events at once
- **Custom Views**: Create saved filters and layouts for different workflows
- **Rich Editing**: Edit all event fields with validation
- **User Permissions**: Control who can moderate events with role-based access
- **Activity Tracking**: See who made changes and when
- **Workflows**: Configure automated approval workflows
- **API Access**: Programmatic access for integrations

## Integration with event_analyzer.py

The moderation workflow integrates with the LLM analysis:

1. The `event_analyzer.py` script processes events and makes initial relevance determinations
2. Events are saved to Directus with `approved: false` status
3. Moderators review events in the Directus admin interface:
   - Filter for unapproved events (`approved = false`)
   - Review event details, tags, and relevance
   - Approve relevant events or reject irrelevant ones
   - Add notes or modify tags as needed
4. Approved events appear on the public website at https://exlab-code.github.io

## Moderation Workflow

### 1. View Pending Events

In the Directus admin:
- Navigate to the "events" collection
- Filter by: `approved = false`
- Sort by: `date_created` or `start_date`

### 2. Review Event Details

For each event, check:
- **Title and Description**: Is it clear and accurate?
- **Tags**: Are the tags appropriate? (topic, format, audience, cost)
- **Date and Location**: Is the information correct?
- **Relevance**: Does it fit the nonprofit/NGO focus?
- **LLM Reasoning**: Review the `llm_reasoning` field to understand why it was selected

### 3. Approve or Reject

- **Approve**: Set `approved = true` for relevant events
- **Reject**: Delete the event or set a custom status field
- **Bulk Actions**: Select multiple events and approve/reject at once

### 4. Edit if Needed

- Fix typos or formatting issues
- Add missing tags from the tag groups (topic, format, audience, cost)
- Update location or date information
- Add notes in a custom field

## Best Practices

1. **Regular Reviews**: Check for pending events daily or weekly
2. **Consistent Criteria**: Establish clear guidelines for what's relevant
3. **Use Tags Effectively**: Ensure events have appropriate tags from all groups
4. **Document Decisions**: Use notes fields to explain rejections or major edits
5. **Batch Processing**: Use filters and bulk operations for efficiency

## Custom Fields

The events collection includes these custom fields for moderation:

- `approved` (boolean): Whether the event is approved for public display
- `llm_reasoning` (text): The LLM's explanation for why the event was selected
- `tag_groups` (JSON): Organized tags by category (topic, format, audience, cost)
- `tags` (array): Flattened list of all tags for filtering

## Feedback Loop

While the custom feedback interface has been removed in favor of Directus admin, you can still track LLM accuracy:

1. **Monitor Approval Rates**: Track how many LLM-suggested events are approved
2. **Review Patterns**: Identify common reasons for rejection
3. **Refine Prompts**: Update the LLM prompts in `event_analyzer.py` based on patterns
4. **Adjust Sources**: Modify scraper sources if certain sites produce low-quality events

## Advanced Features

### Custom Layouts

Create custom layouts in Directus for different moderation tasks:
- **Quick Review**: Show only essential fields (title, date, tags, approve button)
- **Detailed Review**: Show all fields including LLM reasoning
- **Bulk Approval**: Optimized for processing many events quickly

### Saved Filters

Create and save common filters:
- "Pending This Week" - `approved = false AND start_date >= [this week]`
- "Online Events" - Filter by "Online" tag
- "High Priority" - Events starting soon that need review

### Workflows

Configure automated workflows in Directus:
- Auto-approve events from trusted sources
- Send notifications when events need review
- Automatically tag events based on patterns

## Troubleshooting

**Can't see events?**
- Check that you're logged into Directus admin
- Verify your user role has permissions for the events collection
- Clear any active filters that might be hiding events

**Changes not appearing on website?**
- The website rebuilds automatically from GitHub Pages
- Allow a few minutes for changes to propagate
- Check that events have `approved = true`

**Need help with Directus?**
- Directus documentation: https://docs.directus.io
- Admin user guide: https://docs.directus.io/app/
