---
name: timefold-logo
description: Insert or reference the Timefold logo in marketing materials, publications, or application UI. Use it to add the Timefold logo to presentations, drawings, or documents, and during development whenever a logo appears in product UI (app headers, login screens, favicons, loading states, or generated emails/PDFs). Never draw or approximate the logo — always use these official assets.
user-invocable: false
---

## CRITICAL RULE
**NEVER generate, recreate, or approximate the Timefold logo from memory.** The logo contains precise SVG paths that cannot be reproduced correctly by guessing. Always read and copy the exact files from this skill directory.

## Guidelines
When inserting a company logo, follow these guidelines:

1. Use an official logo from this skill's `assets/` directory
2. Prefer SVG format for scalability, fallback to PNG.
3. Prefer `timefold-logo` whenever possible.
4. Use the `negative` variants only for dark backgrounds.
5. Use the `stacked` variants only when explicitly asked to save horizontal space.
6. Use the `logomark` variants only when explicitly asked to have the icon only.
7. Maintain aspect ratio

## How to Use

### In HTML / Web outputs

1. Read the appropriate SVG file from this skill directory
2. Embed the SVG content inline in your HTML

### In documents, images, or other outputs

1. Copy the appropriate PNG file to your output directory
2. Reference it from your document

