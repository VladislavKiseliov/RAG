# RAG Chat Application

Advanced chat application with Retrieval-Augmented Generation (RAG) technology that combines the power of large language models with document information retrieval to provide accurate, context-aware responses.

## Overview

This application implements a full-featured chat interface with persistent conversation history, document-based question answering, and a modern web interface. It uses the Google Gemini model for natural language processing and Qdrant for vector document retrieval.

## Features

- **Document Question Answering**: Ask questions about your documents using RAG technology
- **Persistent Conversations**: Save and resume chat sessions using SQLite database
- **Modern Web Interface**: Clean, responsive chat interface with conversation history sidebar
- **Source Attribution**: See which documents formed the basis of each answer
- **Multi-Document Support**: Process and ask questions about multiple PDF documents

## Architecture

The application consists of several key components:

1. **Frontend** (`frontend/src/`): React application with Vite build tool
2. **Backend** (`main.py`): FastAPI server handling API endpoints and routing
3. **Core Logic** (`app/core/`): 
   - Document processing and chunking
   - RAG pipeline setup and question answering
4. **Database Layer** (`app/db/`): Conversation persistence with SQLite and vector storage with Qdrant
5. **Models** (`app/models/`): Data models for database entities

## How It Works

1. **Document Loading**: PDF documents in the `docs/` directory are processed and converted to vector representations
2. **Vector Storage**: Document chunks are stored in the Qdrant vector database with metadata
3. **Question Processing**: User questions are embedded and matched against stored document vectors
4. **Context Retrieval**: Most relevant document chunks are retrieved based on similarity scores
5. **Response Generation**: Google Gemini model generates answers using the retrieved context
6. **Conversation Persistence**: All interactions are saved to SQLite for later review

## Installation Instructions

### Prerequisites
- Python 3.12+
- Node.js 16+
- Poetry (for Python dependency management)

### Backend Setup

1. Install Poetry if not already installed:
   ```bash
   pip install poetry
   ```

2. Install Python dependencies using Poetry:
   ```bash
   poetry install
   ```

3. Activate the Poetry virtual environment:
   ```bash
   poetry shell
   ```
   or
   ```bash
   poetry env activate
   ```

4. Set up environment variables in `.env` file:
   ```env
   GOOGLE_API_KEY=your_api_key_here
   ```

5. Place your PDF documents in the `docs/` folder

### Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install frontend dependencies:
   ```bash
   npm install
   ```

3. Build the frontend:
   ```bash
   npm run build
   ```

### Running the Application

1. Make sure you're in the Poetry virtual environment (from backend setup)
2. Run the application:
   ```bash
   python main.py
   ```

3. Open the web interface at `http://localhost:8000`

## API Endpoints

- `POST /api/conversations` - Create a new conversation
- `GET /api/conversations` - List all conversations
- `GET /api/conversations/{id}` - Get conversation history
- `POST /api/conversations/{id}/messages` - Send a message in a conversation

## Technical Details

- **Web Framework**: FastAPI
- **LLM**: Google Gemini (via `langchain-google-genai`)
- **Embeddings**: BAAI/bge-m3 (via `langchain-huggingface`)
- **Vector Store**: Qdrant
- **Database**: SQLite with SQLAlchemy ORM
- **Frontend**: React with Vite
- **Dependency Management**: Poetry (Python), npm (Frontend)
- **Migration Tool**: Alembic

## Recent Improvements

- Migration from pip to Poetry for Python dependency management
- Enhanced database modules with improved error handling
- Fixed SQLite connection and query issues
- Improved Qdrant integration and collection management
- Optimized document processing workflows
- Enhanced conversation persistence and retrieval