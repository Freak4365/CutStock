# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Version numbers follow the date scheme `YYYY.MM.DD` (see `VERSION`).

## [Unreleased]

### Changed

- **Thorough optimization (GA) for bars:** Reworked the fitness function of
  the genetic algorithm. Previously it only counted the placed length, so
  whenever all parts fit, every solution scored the same and the GA could not
  improve on the plain sorted order (FFD). Solutions are now ranked in this
  order:
  1. number of placed parts
  2. placed length
  3. as little opened bar length as possible, i.e. fewer or shorter bars
     (segments of a bar with defects count as one bar)
  4. bundled offcuts: a few large, reusable remnants instead of many small
     ones

  As a result, the GA now often needs fewer bars, e.g. 3 instead of 4, or
  2 instead of 3 for bars with defects.
- As with panels, the GA result for bars is now compared against plain FFD
  and the better plan is returned, so "thorough" is never worse than "fast".

### Fixed

- The thorough optimization (GA) for bars no longer crashes when only a single
  part needs to be cut.

### Added

- Tests for the 1D GA: fewer bars than FFD, never worse than FFD, saw blade
  width (kerf) respected, bars with defects, reproducible results, and a
  single part.

[Unreleased]: https://github.com/orohde/CutStock/compare/2026.10.15...HEAD
