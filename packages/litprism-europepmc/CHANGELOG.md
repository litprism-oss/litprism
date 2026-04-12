# Changelog

## [Unreleased]

### Added
- Initial scaffold: `EuropePMCClient`, `AsyncEuropePMCClient`
- Europe PMC REST API wrapper with cursor-based pagination
- JSON → Pydantic parser
- Token-bucket rate limiting (3/s without key, 10/s with key)
