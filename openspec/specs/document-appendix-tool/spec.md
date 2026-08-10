## Purpose
Support for fetching document appendices and maintaining a lightweight document registry, since appendices are never vector-indexed.

## Requirements

### Requirement: Appendix fetched via dedicated endpoint, never via search
Appendix content MUST always be retrieved via a dedicated `get_appendix` call to rag_service, never through the normal search path.

#### Scenario: A user's question concerns appendix content
- **WHEN** the agent determines appendix content is needed
- **THEN** it calls the dedicated appendix endpoint, not `search_docs`

### Requirement: Lazy registry with stale-serve fallback
The document registry MUST be built lazily on first use (not at process startup, to avoid a hard startup dependency), cached with a TTL, and MUST serve the stale cached version if a refresh fails rather than going empty.

#### Scenario: The document registry refresh call to rag_service fails
- **WHEN** the registry's TTL has expired and the refresh call errors
- **THEN** the previously cached registry is still served, not an empty one

### Requirement: Appendix context length cap
Appendix text included in the generation prompt MUST be capped at a fixed character limit before entering the prompt.

#### Scenario: An appendix is much longer than the cap
- **WHEN** a fetched appendix exceeds the configured character limit
- **THEN** only the first portion up to the limit is included in the prompt
