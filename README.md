# PYNQ Scope Server

This document describes how to add new configurations and actions to the PYNQ Scope Server.

## Adding New Configurations and Actions

To add a new configuration or action to the server, you need to modify the `pynq_scope_server.py` file.

### 1. Add a New Action

In the `AcquisitionManager` class, add a new `if` condition to the `handle_action` method. This condition should check for the name of your new action and execute the corresponding logic.

**Example:**

```python
async def handle_action(self, action: str, params: Dict[str, Any]):
    """Gère une action de configuration."""
    print(f"Action reçue: {action} avec les paramètres: {params}")
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

```bash
curl -X POST -H "Content-Type: application/json" -d '{"action": "new_action", "params": {"param1": "value1"}}' http://127.0.0.1:8000/configure
```
