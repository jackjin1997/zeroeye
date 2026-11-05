# Backend API Contract Tests

Local commands:

```bash
# Run all contract edge-case tests
python3 -m pytest -q tests/backend_api/

# Run a single test class
python3 -m pytest -q tests/backend_api/test_contract_edge_cases.py::TestMalformedPayload

# Build (repo root)
python3 build.py
```

No pytest plugins beyond the standard `pytest` package are required —
async tests use `asyncio.run()` directly. All fixtures are in-process;
no network services are touched.
