# Real-Time Distributed Chat Engine

A production-grade, asynchronous chat application built with FastAPI, PostgreSQL, and Redis. This architecture utilizes a Publish/Subscribe (Pub/Sub) message broker pattern to allow for infinite horizontal scaling of WebSocket connections across isolated worker processes, secured by a stateful token revocation layer.

## Architecture & Tech Stack

* **Backend Framework:** FastAPI (Python 3.12)
* **Real-Time Engine:** WebSockets
* **Message Broker & Cache:** Redis (Pub/Sub & In-Memory Storage)
* **Relational Database:** PostgreSQL 15 (ACID-compliant storage)
* **ORM & Migrations:** SQLAlchemy 2.0 & Alembic
* **Authentication:** Stateless JWT (JSON Web Tokens) with Argon2 hashing
* **Security:** Server-Side Token Revocation (Redis Blacklist)
* **Infrastructure:** Multi-container Docker Compose bridge network
* **CI/CD:** GitHub Actions & Pytest

## System Design Highlights

1. **The Synchronous Vault:** A fully typed SQLAlchemy/Pydantic foundation managing user registration and securely hashing credentials.
2. **The Asynchronous Engine:** Raw TCP WebSocket connections that bypass standard HTTP overhead for zero-latency communication.
3. **Decoupled State:** Uvicorn process memory isolation is solved via Redis. When a message is sent to one worker, it is published to a Redis channel and instantly broadcasted to all other connected Uvicorn workers.
4. **Strict Protocol Security:** The native browser WebSocket API does not support standard HTTP Authorization headers. This engine implements a custom dependency injector to intercept the initial WS handshake, extract the JWT from the query parameters, and strictly validate the user against the database before upgrading the connection.
5. **Enterprise Token Revocation:** Implements a Redis-backed blacklist to securely revoke stateless JWTs upon user logout. Tokens are quarantined in RAM with a Time-To-Live (TTL) matching their cryptographic expiration, ensuring `O(1)` security lookups without database bloat.

## Local Development Setup

### Prerequisites
* Docker and Docker Compose
* Git

### 1. Clone the Repository
```bash
git clone https://github.com/YOUR-USERNAME/real-time-chat.git
cd real-time-chat
```

### 2. Configure the Environment
Create a `.env` file in the root directory. *(Note: This file is ignored by Git for security).*
```env
SECRET_KEY=generate_a_secure_random_string_here
SQLALCHEMY_DATABASE_URL=postgresql://chat_user:chat_password@db/chat_db
```

### 3. Boot the Infrastructure
Spin up the isolated Docker network (API, PostgreSQL, and Redis).
```bash
docker compose up -d --build
```

### 4. Run Database Migrations
Stamp the PostgreSQL database with the necessary tables.
```bash
docker compose exec api alembic upgrade head
```

### 5. Access the Engine
* **Interactive API Docs (Swagger UI):** `http://localhost:8000/docs`
* **Secure Chat Client:** `http://localhost:8000/chat`

## Automated Testing

This project includes a fully automated Pytest suite that acts as a robotic user to verify system integrity. The test suite mathematically validates:
* Database health and dynamic schema generation.
* User registration and Argon2 cryptographic hashing.
* Stateless JWT generation.
* **Stateful Token Revocation:** Verifies that the Redis blacklist successfully intercepts and quarantines revoked tokens before their natural expiration.

To run the tests locally inside the container:
```bash
docker compose exec api pytest
```
*Note: A GitHub Actions pipeline automatically runs this test suite in a remote cloud environment on every push to the `main` branch.*