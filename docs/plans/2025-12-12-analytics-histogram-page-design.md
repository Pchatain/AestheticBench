# Analytics Histogram Page Design

**Date:** 2025-12-12
**Status:** Approved

## Overview

Add a new "Analytics" page to the MoralBench UI that displays histogram visualizations showing the distribution of model performance ratings across three metrics.

## Requirements

- New page accessible from sidebar navigation
- Display three histogram charts showing score distributions (not averages)
- Support filtering by models and topics
- Adjustable bin size for continuous metrics via slider

## Architecture

### Page Location
- New "Analytics" page in sidebar (after "Comparison")
- Component: `src/components/Analytics.tsx`

### Data Flow
1. Fetch individual results from `/api/results` endpoint
2. Filter by selected models and topics
3. Process scores client-side into histogram bins
4. Render three Recharts BarCharts

### Metrics & Histogram Types

**1. Preference 1 (Discrete: -1, 0, 1)**
- Three bars per model showing count of each value
- X-axis: -1, 0, 1
- Y-axis: Count
- Grouped bar chart with models as different colored series

**2. Preference 2 (Continuous: -1 to 1)**
- Adjustable bin size via slider (0.05 to 0.5, default 0.1)
- Bins cover range from -1 to 1
- X-axis: Bin ranges (e.g., [-1.0, -0.9), [-0.9, -0.8), ...)
- Y-axis: Count
- Grouped bar chart with models as different colored series

**3. Justification (Discrete: 1-5)**
- Five bars per model showing count of each rating
- X-axis: 1, 2, 3, 4, 5
- Y-axis: Count
- Grouped bar chart with models as different colored series

## Component Structure

### State
```typescript
// Filters
models: Model[]                    // Available models
topics: string[]                   // Available topics
selectedModels: string[]           // User selection
selectedTopics: string[]           // User selection

// Data
results: Result[]                  // All individual results
loading: boolean

// Histogram controls
binSize: number                    // For Preference 2 slider (default: 0.1)
```

### Layout
```
Analytics.tsx
├── Header: "Model Performance Analytics"
├── Filter section (2-column grid)
│   ├── Model selector (checkboxes with select all)
│   └── Topic selector (checkboxes with select all)
├── Controls section
│   └── Bin size slider for Preference 2
└── Charts section (vertically stacked)
    ├── Preference 1 histogram
    ├── Preference 2 histogram
    └── Justification histogram
```

### Data Processing Functions

**buildDiscreteHistogram()**
- Input: results, selectedModels, scoreField, categories
- Output: Array of objects with category and counts per model
- Filters out ERROR values and null/undefined

**buildContinuousHistogram()**
- Input: results, selectedModels, binSize
- Output: Array of objects with bin ranges and counts per model
- Creates bins from -1 to 1 based on binSize
- Filters out ERROR values and null/undefined

## UI Specifications

### Styling
- Consistent with ModelComparison page
- White cards with rounded corners and shadows
- ~400px height per chart

### Bin Size Slider
- Label: "Preference 2 Bin Size: {value}"
- Range: 0.05 to 0.5
- Steps: 0.05
- Real-time chart updates

### Charts
- Title format: "{Metric} Distribution"
- X-axis label: Category or bin range
- Y-axis label: "Count"
- Tooltip with exact counts
- Legend with model names
- Reuse COLORS array from ModelComparison

## Error Handling
- Skip rows with ERROR scores
- Show message if no valid data after filtering
- Handle missing or null score values gracefully

## Implementation Notes
- Uses Recharts BarChart (already installed)
- Reuses filter UI pattern from ModelComparison
- Client-side histogram binning for performance
