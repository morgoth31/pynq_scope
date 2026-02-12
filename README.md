# PYNQ Scope Server

This document describes how to add new configurations and actions to the PYNQ Scope Server.

## Logging

The server and GUI both generate log files that can be used for debugging and monitoring. The log files are located in the `logs` directory.

* `logs/server.log`: Contains logs from the server.
* `logs/gui.log`: Contains logs from the GUI.

The logs are rotated daily, and the last 7 days of logs are kept.

## Error Handling

The server and GUI have been improved to handle errors more gracefully.

* **Server:** The server will catch and log exceptions that occur during data acquisition and action handling.
* **GUI:** The GUI will display a message box when an error occurs, and will log the error to the GUI log file.

## Adding New Configurations and Actions

To add a new configuration or action to the server, you need to modify the `pynq_scope_server.py` file.

### 1. Add a New Action

In the `AcquisitionManager` class, add a new `if` condition to the `handle_action` method. This condition should check for the name of your new action and execute the corresponding logic.

**Example:**

```python
async def handle_action(self, action: str, params: Dict[str, Any]):
    """Gère une action de configuration."""
    logger.info(f"Action reçue: {action} avec les paramètres: {params}")
    # Logique de distribution des actions
    if action == "set_sample_rate":
        # Ici, la logique pour changer SAMPLE_RATE
        pass
    elif action == "new_action":
        # Your new action logic here
        pass
    return {"status": "Action traitée", "action": action}
```

### 2. Send a Configuration Request

To trigger the new action, send a POST request to the `/configure` endpoint with a JSON object containing the action name and any necessary parameters.

**Example:**

curl -X POST -H "Content-Type: application/json" -d '{"action": "new_action", "params": {"param1": "value1"}}' http://127.0.0.1:8000/configure
```

## Testing

The project includes a comprehensive test suite (Unit, Integration, E2E) located in the `tests/` directory.

### Running Tests Locally (Emulation)
To run tests on your development machine (mocks hardware):
```bash
./run_tests.sh
```
This will:
1. Create a virtual environment (`.venv`).
2. Install dependencies.
3. Run all tests.
4. Generate a **Markdown report** at `report.md`.

### Running Tests Remotely (Real Hardware)
To run tests on the PYNQ board (`192.168.144.26`):
```bash
./deploy_test.sh
```
This script deploys the code and runs tests against the real FPGA hardware, generating a `report.md` on the target.

### Test Report
After running tests, you can view the execution summary in `report.md`.
