# Custom CSS for Event-Scraper Website

This document explains how to use the custom CSS file to modify the appearance of the website without changing the component code.

## Overview

The `custom.css` file is loaded after the main CSS files, allowing you to override default styles and add custom styling to components. The components have been updated with specific class names to make them easier to target with CSS selectors.

## EventCard Component

The EventCard component has the following structure and class names:

```html
<div class="event-card">
  <div class="flex h-full">
    <div class="date-indicator">
      <!-- Date content -->
    </div>
    
    <div class="main-content">
      <!-- Event details -->
    </div>
    
    <div class="action-bar">
      <!-- Buttons -->
    </div>
  </div>
</div>
```

### Customization Examples

#### Rounded Corners and Padding for Date Indicator

```css
.event-card .date-indicator {
  border-top-left-radius: 0.5rem;
  border-bottom-left-radius: 0.5rem;
  padding-top: 1rem;
  padding-bottom: 1rem;
}
```

This is equivalent to adding the Tailwind classes `py-4` to the element, but using CSS allows you to override the default styles without modifying the component code.

#### Change Action Bar Width and Padding

```css
.event-card .action-bar {
  width: 120px; /* Default is 32px (w-32) */
  padding-top: 1rem;
  padding-bottom: 1rem;
}
```

This is equivalent to adding the Tailwind classes `py-4` to the element, but using CSS allows you to override the default styles without modifying the component code.

#### Change Background Colors

```css
.event-card {
  background-color: #f9f9f9;
}

.event-card .date-indicator {
  background-color: #3b82f6; /* Change the blue color */
}

.event-card .action-bar {
  background-color: #f3f4f6;
}
```

#### Add Box Shadow to Cards

```css
.event-card {
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1), 0 1px 3px rgba(0, 0, 0, 0.08);
}
```

## Adding Styles for Other Components

You can add styles for other components by following the same pattern. First, add a class name to the component, then target that class name in the custom.css file.

For example, to style the Header component:

1. Add a class name to the Header component:
```html
<header class="custom-header">
  <!-- Header content -->
</header>
```

2. Add styles to custom.css:
```css
.custom-header {
  background-color: #1e40af;
  color: white;
}
```

## Best Practices

1. Use specific selectors to avoid affecting other elements
2. Keep the custom CSS organized by component
3. Add comments to explain complex styles
4. Use browser developer tools to test styles before adding them to the custom.css file
