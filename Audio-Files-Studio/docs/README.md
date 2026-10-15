# Documentation — Section Guides

This folder contains one markdown file per section of the application.  
Each section doc describes one part of the application in detail.

## Principles

- **Single source of truth.** When a section changes, its doc is updated in the same commit.
- **Shared map.** These docs are for us, for you, and for any future contributor or AI assistant.
- **Pipeline order.** The files are numbered in the order of the user's workflow:

```
00_overview.md              → High-level map
01_import_and_prepare.md    → Prepare text (books/)
02_audio_studio.md          → Audio Studio (cross-cutting tool)
03_voice_box.md             → Voice Box (Gallery)
04_vocalizer.md             → Vocalizer (Creator)
05_wizard.md                → New Project Wizard
06_pipeline.md              → Pipeline (synthesise)
07_projects.md              → Projects (retrieve output)
08_settings.md              → Settings (cross-cutting)
```

Audio Studio and Settings are cross-cutting tools and appear where they are most likely to be encountered.

## Template

Every section doc follows the same template:

- **Purpose** — one paragraph, why this section exists
- **User journey** — 3–7 steps of what a user does here
- **What it reads** — files, databases, state
- **What it writes** — files, databases, state
- **What it does NOT do** — explicit boundaries, the most important field for preventing drift
- **Key interactions** — how this section connects to others
- **Open questions** — known improvements, not a roadmap
- **Changelog** — dated entries

## Maintenance

When you change a section's code, update its doc in the same commit.  
If a section has no doc yet, create it from the template first.