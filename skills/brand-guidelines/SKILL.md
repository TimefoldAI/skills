---
name: brand-guidelines
description: Applies Timefold's official brand colors and typography to any sort of artifact or product UI that may benefit from having Timefold's look-and-feel. Use it when brand colors or style guidelines, visual formatting, or company design standards apply — including during application development whenever picking colors, typography, or theme values in UI code (CSS, Tailwind config, component styling, charts, and visualisations).
user-invocable: false
---

# Timefold Brand Styling

## Overview

To access Timefold's official brand identity and style resources, use this skill.

**Keywords**: branding, corporate identity, visual identity, post-processing, styling, brand colors, typography, Timefold brand, visual formatting, visual design

## Brand Guidelines

### Colors

**Base Colors:**

- Text: `#12131c` - Primary text
- Dark Grey: `#89898b` - Secondary text and subtle elements
- Light Grey: `#e5e5e6` - Backgrounds and dividers

**Brand Colors:**

- Primary: `#4900f8` - Primary brand color
- Purple: `#9353c9` - Purple accent
- Blue: `#4f62f5` - Blue accent
- Green: `#00c85e` - Green accent
- Yellow: `#f5b200` - Yellow accent
- Orange: `#fc6d00` - Orange accent
- Red: `#f51515` - Red / alert
- Brown: `#a65908` - Brown accent

### Typography

- **Headings**: SF Pro (with Inter as fallback and for print / marketing)
- **Body Text**: SF Pro (with Inter as fallback and for print / marketing)
- **Note**: Fonts should be pre-installed in your environment for best results

## Features

### Smart Font Application

- Our font stack: -apple-system, BlinkMacSystemFont, var(--font-inter), sans-serif
- Preserves readability across all systems

### Text Styling

- Headings (24pt+): Inter font, bold
- Body text: Inter font, regular
- Smart color selection based on background
- Preserves text hierarchy and formatting

### Shape and Accent Colors

- Non-text shapes use accent colors
- Cycles through primary blue / purple accents and occasionally the other accent colors.
- Maintains visual interest while staying on-brand

## Technical Details

### Font Management

- On Apple systems, use the system-installed SF Pro font.
- On other systems, you can download and install the SF Pro fonts.
- In a web context we use the Inter webfont as a fallback.

### Color Application

- Uses RGB color values for precise brand matching
- Maintains color fidelity across different systems
