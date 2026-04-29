# Login Page — Website Design Brief

## Overview

**Page:** Login  
**Layout:** Two-column split panel (modal card style)  
**Reference:** Moofitask login screen  

---

## Layout

- Centered modal card on a **soft pink background** (`#F9D9D0`)
- Card has **rounded corners** (~24px) and a **white background**
- Card splits into **two equal columns**:
  - **Left:** Mascot illustration panel
  - **Right:** Login form

---

## Left Column — Mascot Panel

- Background color: soft peach (`#F7D5C8`)
- Rounded corners on the left side matching the card
- **Mascot image:** Use `mascots.png` — place it large, filling the panel, cropped naturally at edges
- No text, no extra UI elements — mascot only

---

## Right Column — Login Form

**Top-right:** Close button `×` (icon, no border)

### Heading
- Text: `Login`
- Font: Bold, ~32px
- Color: Near-black (`#1A1A1A`)
- Margin bottom: 24px

### Email Field
- Label: `Email` (above input, small, dark)
- Input: Full width, rounded border (`#D0D0D0`), ~48px height
- Left icon: Envelope icon inside input
- Placeholder: `daniel21fisher@gmail.com` style placeholder text
- Border radius: 10px

### Password Field
- Label: `Password` (above input)
- Input: Full width, same style as email
- Left icon: Eye icon (toggle show/hide password)
- Input type: `password` (dots)
- Border radius: 10px

> ❌ No "Forgot Password" link  
> ❌ No social login buttons (Google, Facebook, Apple)  
> ❌ No "Or Continue With" divider

### Login Button
- Full width
- Background: Coral-pink (`#F07070`)
- Text: `Log In`, white, bold
- Border radius: 12px
- Height: ~52px
- Hover: slightly darker coral

### Sign Up Link
- Below button
- Text: `Don't have an account? Sign Up here`
- `Sign Up here` is a hyperlink — color: coral-pink (`#F07070`), underlined

---

## Typography

| Element        | Size   | Weight | Color      |
|----------------|--------|--------|------------|
| Page heading   | 32px   | 700    | `#1A1A1A`  |
| Field labels   | 14px   | 500    | `#333333`  |
| Input text     | 15px   | 400    | `#1A1A1A`  |
| Placeholder    | 15px   | 400    | `#AAAAAA`  |
| Button text    | 16px   | 600    | `#FFFFFF`  |
| Sign up link   | 14px   | 400    | `#1A1A1A`  |

Font family: System sans-serif or Inter / Poppins

---

## Colors

| Use               | Hex        |
|-------------------|------------|
| Page background   | `#F9D9D0`  |
| Card background   | `#FFFFFF`  |
| Mascot panel bg   | `#F7D5C8`  |
| Primary button    | `#F07070`  |
| Input border      | `#D0D0D0`  |
| Input focus border| `#F07070`  |
| Heading text      | `#1A1A1A`  |
| Label text        | `#333333`  |

---

## Spacing & Sizing

| Element         | Value     |
|-----------------|-----------|
| Card width      | ~900px    |
| Card height     | ~520px    |
| Column split    | 50% / 50% |
| Form padding    | 48px      |
| Input height    | 48px      |
| Button height   | 52px      |
| Gap between fields | 20px  |
| Card border-radius | 24px  |

---

## Responsive Notes

- On mobile: stack columns vertically — hide mascot panel, show form only
- Mascot panel visible only on tablet (`768px+`) and desktop

---

## What to Exclude

- ❌ Forgot Password link
- ❌ Social login (Google / Facebook / Apple)
- ❌ "Or Continue With" divider
- ❌ Any marketing copy or extra text

---

*Brief for developer/designer handoff — April 2026*