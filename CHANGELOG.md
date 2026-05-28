# Changelog

All notable changes to Injex are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses semantic versioning.

## [Unreleased]

### Added

- Documentation site pages with canonical URLs, sitemap, robots.txt,
  Open Graph metadata, and structured data.
- Article page explaining why a small Python DI container can be useful for
  services, CLIs, workers, tests, and clean architecture.
- Favicon, PNG social preview card, 404 page, and FAQ structured data for the Python
  dependency injection guide.

### Changed

- Public website now links to local documentation pages instead of only GitHub
  Markdown files.
- Landing page and documentation pages now use a more polished visual system,
  improved navigation, responsive cards, focus states, and reduced-motion-safe
  CSS animations.
- Added a Python dependency injection guide for readers comparing manual wiring,
  framework DI, and small containers.
- Sitemap now contains only indexable HTML pages, with service files kept outside
  the sitemap.
- Mobile navigation and social metadata were tightened across the static site.

## [1.2.1] - 2026-05-25

### Added

- Release workflow for tagged builds with wheel smoke tests and release assets.
- Release checklist for maintainers.
- CODEOWNERS and issue template chooser configuration.
- GitHub Pages-ready docs site.
- Positioning guide, usage scenarios, and project overview copy.
- Comparison guide for choosing between manual wiring, framework dependencies,
  Injex, and larger DI containers.

### Changed

- CI now uses `astral-sh/setup-uv`, builds distributions, smoke-tests wheels,
  and avoids failing fork pull requests on Codecov token availability.
- README and docs site now surface the public website more prominently.
- Package description now emphasizes typed dependency injection for Python apps.

## [1.2.0] - 2026-05-25

### Added

- Dependency graph validation through `Container.validate()` and
  `Container.assert_valid()`.
- Public API export list for stable imports from `injex`.
- PEP 561 typing marker for downstream type checkers.
- SPDX license metadata for modern Python packaging.
- API reference, validation guide, roadmap, security policy, and GitHub issue/PR
  templates.

### Fixed

- Invalid lifestyle error message now includes scoped services.
- Tutorial table of contents typos and anchors.

## [1.1.0] - 2026-05-25

### Added

- Temporary dependency overrides for focused tests and local composition changes.
- Real-world examples for clean architecture, CLI applications, and testing.
- Contributor guide with local setup, quality checks, and contribution scope.

### Changed

- README now focuses on practical application wiring, trade-offs, and examples.

## [1.0.0] - 2024-10-23

### Added

- Stable container API for services, factories, instances, named registrations,
  scoped services, optional dependencies, and property injection.
- Python 3.10, 3.11, 3.12, and 3.13 support.

## [0.1.2] - 2024-10-21

### Changed

- Documentation and packaging refinements.

## [0.1.1] - 2024-10-20

### Fixed

- Minor registration and resolution edge cases.

## [0.1.0] - 2024-10-19

### Added

- Initial public release.
