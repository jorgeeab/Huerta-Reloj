# API Endpoint Overview

This document summarizes how to launch the Flask servers and access the interface that allows the AI control protocols.

## Running the API Server

The API endpoints are implemented in `servidor_plantas.py`. Run the server with:

```bash
python servidor_plantas.py
```

By default the server binds to `0.0.0.0` on port `5000`:

```python
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
```

Once running, you can interact with the API using HTTP requests. The main endpoints include:

- `POST /update_protocol_code` – Update the code for an existing protocol.
- `POST /stop` – Stop any active protocol and halt the motors.
- `POST /update_actuators` – Update actuator values.
- `GET /list_protocols` – List available protocols.
- `POST /create_protocol` – Create a new protocol.
- `POST /activate_protocol` – Activate a protocol.
- `GET /view_protocol/<pid>` – View a protocol's details.
- `DELETE /delete_protocol/<pid>` – Remove a protocol.

## Opening the Control Interface

A basic web interface for manual control is served by `servidor_plantas.py`. Start it with:

```bash
python servidor_plantas.py
```

This will launch a local server (port 5000 by default). Open your browser and navigate to:

```
http://localhost:5000/
```

The page `panel.html` from the `templates` directory will be displayed, allowing manual control and observation of the environment.

## Notes

- Ensure the Python dependencies listed in `requirements.txt` are installed.
- When running remotely, replace `localhost` with the server's address or your ngrok URL.
