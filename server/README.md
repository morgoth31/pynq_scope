# pynq_scope_server

## installation 

```bash
sudo /usr/local/share/pynq-venv/bin/python -m pip install -r requirements.txt
```

attention, il y a un probleme de version sur une librairie
J'ai resolu en downgradant mais il doit y avoir une meilleur solution

downgrade
```bash
sudo /usr/local/share/pynq-venv/bin/python -m pip install "anyio>=3.6.2,<4.0"
```

## lancement du serveur

```bash
sudo ./run_server.sh
```

