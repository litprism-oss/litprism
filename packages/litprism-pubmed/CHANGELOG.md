# Changelog

## [Unreleased]

### Added
- Initial scaffold: `PubMedClient`, `AsyncPubMedClient`
- E-utilities wrapper (`esearch`, `efetch`)
- XML → Pydantic parser
- Token-bucket rate limiting (3/s without key, 10/s with key)
- Optional SQLite cache keyed on PMID + fetch date
