# Changelog

## [Unreleased]

## [2.0.0] - 2026-10-07

**Added:**

- Add CI/CD pipeline (#1)
- Project type selection for new projects: hardware, hardware with PlatformIO firmware, PlatformIO firmware and ESP-IDF component
- Input fields for email, GitHub URL and main branch in the dialog for new projects
- Placeholders `BOARD_NAME_LOWER`, `GIT_REPO_LOWER` and `GIT_REPO_UPPER`
- AsciiDoc documentation scaffolding in `firmware/docs/`
- Copy `scripts/` and `.claude/` when adding missing template files to an existing project

**Changed:**

- Support the template project 2.0.0 with the firmware profiles and the grouped workflows (`hw-`, `fw-`, `docs-`, `common-`)
- Name the hardware directory after the board in lowercase, like the init scripts
- Keep only the firmware profile, the workflows, the directories and the skills of the selected project type
- Replace the placeholders in the template files that are added to an existing project
- Require KiCad 10.0 or later

**Fixed:**

- Creating a new project failed, because the dialog had no fields for email, GitHub URL and main branch
- The Git data of the template was not removed when the template is a submodule
- The project file kept the references to the template project name
- An empty company was written as `null`

## [0.0.1] - 2026-01-16

**Added:**

- Initial release

[Unreleased]: https://github.com/Kampi/KiCad-Project-Initialization-Plugin/compare/2.0.0...HEAD
[2.0.0]: https://github.com/Kampi/KiCad-Project-Initialization-Plugin/releases/tag/2.0.0
