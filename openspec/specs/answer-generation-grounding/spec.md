## Purpose
Prompt assembly, grounding/evidence rules, and streaming generation of the final answer.

## Requirements

### Requirement: Context is the sole source of facts
For domain_rag-routed answers, the system prompt MUST instruct the model to use only the retrieved context block for factual/technical claims; conversation history may only resolve pronouns, never supply new facts.

#### Scenario: The user's follow-up question relies on unretrieved prior knowledge
- **WHEN** a domain_rag answer is generated
- **THEN** the model is instructed to answer only from the retrieved context, not from general knowledge or unretrieved history

### Requirement: Retrieved content treated as data, not instructions
Context text inserted into the prompt MUST be treated as inert data by the model, not as instructions to follow — a prompt-injection defense against malicious content embedded in indexed documents.

#### Scenario: A retrieved document chunk contains text resembling an instruction
- **WHEN** a chunk of retrieved context contains text like "ignore previous instructions"
- **THEN** the system prompt's framing prevents that text from being treated as a directive

### Requirement: Three-tier sufficiency disclosure
Answers MUST explicitly disclose whether the context provides a direct answer, a partial answer, or no answer, using explicit "not found" phrasing rather than fabricating a confident-sounding response.

#### Scenario: The retrieved context only partially answers the question
- **WHEN** available context covers part of the user's question but not all of it
- **THEN** the answer explicitly states which part is answered and which is not, rather than presenting a complete-sounding answer

### Requirement: Route determines system prompt
The route decided by planning (`smalltalk` vs `domain_rag`) MUST select which system prompt is used for generation.

#### Scenario: A smalltalk-routed query
- **WHEN** a query is routed to `smalltalk`
- **THEN** `system_prompt_chat` is used, not `system_prompt_rag`
