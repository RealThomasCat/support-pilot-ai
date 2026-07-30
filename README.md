# SupportPilot AI

SupportPilot AI is a FastAPI and PostgreSQL backend for an internal customer-support copilot. It provides ticket management, persistent support-agent conversations, Gemini-powered chat, controlled backend tool calling, persisted tool-call logs, and live eval checks for assistant behavior.

The backend MVP is complete for its current learning-project scope. Frontend work, authentication, deployment hardening, and advanced observability are intentionally outside the current backend.

## Highlights

- FastAPI backend with SQLAlchemy and PostgreSQL persistence
- Ticket create, list, filter, retrieve, and update APIs
- Persistent support-agent conversations and ordered message history
- Gemini chat integration through `google-genai`
- Backend-owned tool-calling loop with Gemini automatic function calling disabled
- Registry-based ticket tools with Pydantic argument validation
- Controlled ticket read/write tools for listing, retrieving, creating, updating status, and updating classification
- Persisted tool-call logs for successful and failed executions
- Tool-call inspection endpoints
- Prompt-guided workflows for ticket lookup, follow-up references, classification, status updates, and reply drafting
- Basic live eval runner with fixed support scenarios
- Deterministic API and service tests with mocked Gemini behavior
- Minimal logging and generic database write error handling

## Features

### Tickets

- Create support tickets with customer and issue details
- List tickets with status, category, priority, search, and limit filters
- Retrieve a ticket by ID
- Partially update ticket fields
- Store ticket status, category, and priority as string enum values
- Default new tickets to `open`, `unknown`, and `medium`

### Conversations and Messages

- Create and list internal support-agent conversations
- Store user and assistant messages in PostgreSQL
- Return ordered conversation history
- Preserve the user message if Gemini fails after the request is saved
- Update conversation activity timestamps when messages are created

### AI Assistant and Tool Calling

- Send conversation history to Gemini for assistant responses
- Expose only registered backend ticket tools to the model
- Validate model-generated tool arguments with Pydantic
- Execute tools through backend services instead of direct model access
- Return structured tool results or tool errors back to Gemini
- Enforce a configurable maximum number of tool-call rounds
- Save only the final assistant response in message history

### Tool-Call Logging

- Persist every completed tool execution attempt
- Record requested arguments, validated arguments, result, status, validation status, failure type, and timing
- Redact sensitive fields such as customer email, tokens, passwords, secrets, and API keys
- Inspect logs by conversation or by individual tool-call ID

### Assistant Workflows

- Search and inspect tickets before answering ticket-specific requests
- Use prior conversation context for clear follow-up references
- Complete multi-step read/write workflows in one chat request
- Draft customer replies in chat without saving or sending them
- Avoid database writes unless the support agent clearly requests a change
- Reject unsupported permanent ticket deletion

### Evals and Tests

- Run fixed live eval cases through the real Gemini assistant workflow
- Seed a separate eval database for repeatable scenarios
- Grade expected tool names, important arguments, execution status, final ticket state, and persisted logs
- Keep normal tests deterministic by mocking Gemini calls

## Tech Stack

| Area                 | Technology                           |
| -------------------- | ------------------------------------ |
| Language             | Python                               |
| API framework        | FastAPI                              |
| ASGI server          | Uvicorn                              |
| Database             | PostgreSQL                           |
| ORM                  | SQLAlchemy 2                         |
| Migrations           | Alembic                              |
| Validation           | Pydantic                             |
| Configuration        | Pydantic Settings                    |
| AI provider          | Google Gemini through `google-genai` |
| Testing              | Pytest, HTTPX, FastAPI TestClient    |
| Local infrastructure | Docker Compose                       |

## Architecture

```text
Client or API caller
  -> FastAPI routes
  -> Service layer
  -> SQLAlchemy session
  -> PostgreSQL
```

Chat and tool-calling flow:

```text
Support agent message
  -> persist user message
  -> load ordered conversation history
  -> send history and tool declarations to Gemini
  -> Gemini returns final text
       -> persist assistant message
  -> or Gemini requests tools
       -> validate arguments
       -> execute registered backend handlers
       -> persist tool-call logs
       -> return tool results to Gemini
       -> repeat until final text or round limit
```

Gemini receives tool declarations, not direct database access. The backend owns validation, execution, persistence, logging, and error handling.

## Project Structure

```text
.
|-- README.md
|-- docker-compose.yml
|-- docs/
`-- backend/
    |-- .env.example
    |-- alembic.ini
    |-- pytest.ini
    |-- requirements.txt
    |-- app/
    |   |-- main.py
    |   |-- api/routes/          # Health, ticket, conversation, message, and tool-call routes
    |   |-- core/                # Settings and logging configuration
    |   |-- db/                  # SQLAlchemy base, session, and models
    |   |-- integrations/llm/    # Gemini provider
    |   |-- schemas/             # API response/request schemas
    |   |-- services/            # Business logic and orchestration
    |   |-- tools/               # Tool definitions, registry, handlers, and result types
    |   `-- evals/               # Live eval cases, runner, seed data, and graders
    |-- migrations/
    `-- tests/
```

## API Overview

| Method  | Endpoint                                      | Purpose                                                |
| ------- | --------------------------------------------- | ------------------------------------------------------ |
| `GET`   | `/health`                                     | Application health check                               |
| `GET`   | `/health/db`                                  | Database connectivity check                            |
| `POST`  | `/tickets`                                    | Create a ticket                                        |
| `GET`   | `/tickets`                                    | List and filter tickets                                |
| `GET`   | `/tickets/{ticket_id}`                        | Get one ticket                                         |
| `PATCH` | `/tickets/{ticket_id}`                        | Partially update a ticket                              |
| `POST`  | `/conversations`                              | Create a conversation                                  |
| `GET`   | `/conversations`                              | List conversations                                     |
| `GET`   | `/conversations/{conversation_id}`            | Get conversation metadata                              |
| `POST`  | `/conversations/{conversation_id}/messages`   | Send a chat message and receive the assistant response |
| `GET`   | `/conversations/{conversation_id}/messages`   | List conversation messages                             |
| `GET`   | `/conversations/{conversation_id}/tool-calls` | List tool calls for a conversation                     |
| `GET`   | `/tool-calls/{tool_call_id}`                  | Get one tool-call log                                  |

## Database Design

| Table           | Responsibility                                                      |
| --------------- | ------------------------------------------------------------------- |
| `tickets`       | Customer support issues, status, category, priority, and timestamps |
| `conversations` | Internal support-agent chat threads                                 |
| `messages`      | Ordered user and assistant message history                          |
| `tool_calls`    | Persisted backend tool execution attempts and results               |

Important schema choices:

- Ticket enum fields are stored as string values.
- Message history is indexed by `conversation_id`.
- Tool-call logs are linked to both the conversation and the triggering user message.
- Tool-call arguments and results are stored in PostgreSQL `JSONB`.
- Tool-call logs redact selected sensitive fields before persistence.

## Local Development

### 1. Start PostgreSQL

Run from the repository root:

```powershell
docker compose up -d postgres
```

### 2. Prepare the Backend Environment

Run from the `backend/` folder:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Set `GEMINI_API_KEY` in `backend/.env` for live assistant calls and evals.

### 3. Apply Migrations

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```

### 4. Run the API

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

The API runs at:

```text
http://127.0.0.1:8000
```

OpenAPI docs:

```text
http://127.0.0.1:8000/docs
```

## Environment Variables

| Variable                    | Purpose                                              |
| --------------------------- | ---------------------------------------------------- |
| `APP_NAME`                  | FastAPI application title                            |
| `ENVIRONMENT`               | Runtime environment label                            |
| `LOG_LEVEL`                 | Application log level                                |
| `DATABASE_URL`              | Main PostgreSQL connection string                    |
| `GEMINI_API_KEY`            | Gemini API key for assistant responses               |
| `GEMINI_MODEL`              | Gemini model name                                    |
| `GEMINI_MAX_TOOL_ROUNDS`    | Maximum Gemini tool-call rounds per chat request     |
| `GEMINI_REQUEST_TIMEOUT_MS` | Optional Gemini request timeout in milliseconds      |
| `EVAL_DATABASE_URL`         | Separate PostgreSQL connection string for live evals |

Do not commit real secrets.

## Useful Commands

| Command                                                                      | Purpose                   |
| ---------------------------------------------------------------------------- | ------------------------- |
| `docker compose up -d postgres`                                              | Start local PostgreSQL    |
| `.\.venv\Scripts\python.exe -m alembic upgrade head`                         | Apply database migrations |
| `.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload`                | Run the API locally       |
| `.\.venv\Scripts\python.exe -m pytest`                                       | Run deterministic tests   |
| `.\.venv\Scripts\python.exe -m app.evals.runner --list`                      | List eval cases           |
| `.\.venv\Scripts\python.exe -m app.evals.runner`                             | Run all live eval cases   |
| `.\.venv\Scripts\python.exe -m app.evals.runner --case update_ticket_status` | Run one eval case         |

## Current Scope and Limitations

- The backend MVP is complete for the current learning-project scope.
- There is no frontend in this repository.
- Authentication and authorization are not implemented.
- Customer replies are drafted in chat only; they are not saved or sent.
- Ticket deletion is intentionally unsupported.
- Intermediate Gemini function-call and function-response turns are not stored as chat messages.
- The eval runner is command-line based and does not include a dashboard or persisted run history.
- Production deployment, monitoring, tracing, and advanced observability are outside the current scope.

## License

This project is developed for educational and portfolio purposes.
