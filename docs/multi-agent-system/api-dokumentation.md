# Multi-Agenten-System API-Dokumentation

## Übersicht

Das Multi-Agenten-System bietet eine REST API für die Interaktion mit verschiedenen spezialisierten Agents.

## Endpoints

### 1. Orchestrator Endpoint

**POST** `/api/orchestrator/task`

Erstellt eine neue Forschungsaufgabe.

**Request Body:**
```json
{
  "topic": "string",
  "requirements": "string"
}
```

**Response:**
```json
{
  "request_id": "string",
  "status": "pending",
  "created_at": "string"
}
```

### 2. Vision Endpoint

**POST** `/api/vision/analyze`

Analysiert ein Bild.

**Request Body:**
```json
{
  "image_path": "string"
}
```

**Response:**
```json
{
  "analysis": {
    "scene": "string",
    "mood": "string",
    "colors": ["string"],
    "composition": "string",
    "lighting": "string"
  },
  "timestamp": "string"
}
```

### 3. Swarming Endpoint

**POST** `/api/swarming/distribute`

Verteilt eine Task an einen Agent.

**Request Body:**
```json
{
  "task_description": "string",
  "agent_type": "string"
}
```

**Response:**
```json
{
  "task_id": "string",
  "status": "distributed",
  "timestamp": "string"
}
```

### 4. Summary Endpoint

**POST** `/api/summary/summarize`

Fasst Ergebnisse zusammen.

**Request Body:**
```json
{
  "results": ["string"]
}
```

**Response:**
```json
{
  "summary": "string",
  "timestamp": "string"
}
```

### 5. Alignment Endpoint

**POST** `/api/alignment/validate`

Validiert Ergebnisse.

**Request Body:**
```json
{
  "results": ["string"]
}
```

**Response:**
```json
{
  "validation": {
    "status": "string",
    "issues": ["string"]
  },
  "timestamp": "string"
}
```

## Authentifizierung

Alle API-Endpoints erfordern eine Authentifizierung.

**Header:**
```
Authorization: Bearer <token>
Content-Type: application/json
```

## Fehlerbehandlung

Alle Fehler werden im folgenden Format zurückgegeben:

```json
{
  "error": "string",
  "message": "string",
  "timestamp": "string"
}
```

## Status Codes

- `200`: Erfolgreich
- `400`: Ungültige Anfrage
- `401`: Nicht authentifiziert
- `500`: Server-Fehler
