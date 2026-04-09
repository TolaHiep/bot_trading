# Contributing Guide

## Development Workflow

### 1. Setup

```powershell
# Clone repository
git clone <repository-url>
cd Trading_bot

# Copy environment template
cp .env.example .env

# Update .env with your Bybit Testnet credentials
# BYBIT_API_KEY=your_key
# BYBIT_API_SECRET=your_secret

# Start Docker containers
.\scripts\docker-dev.ps1 start

# Verify setup
.\scripts\docker-dev.ps1 shell trading_bot
python scripts/test_connection_docker.py
exit
```

### 2. Development Process

Follow the tasks in `.kiro/specs/quantitative-trading-bot/tasks.md`:

1. **Task 1**: Project Architecture Setup
2. **Task 2**: Bybit Connector
3. **Task 3**: Database Schema
4. **Task 4**: Data Pipeline
5. **Task 5**: Alpha Model
6. **Task 6**: Risk Model
7. **Task 7**: Execution Model
8. **Task 8**: Backtesting Engine
9. **Task 9**: Monitoring Dashboard
10. **Task 10**: Integration Testing

### 3. Coding Standards

#### Python Style
- Follow PEP 8
- Use type hints
- Maximum line length: 100 characters
- Use Black for formatting: `black src/ tests/`
- Use isort for imports: `isort src/ tests/`
- Use flake8 for linting: `flake8 src/ tests/`

#### Code Structure
```python
"""Module docstring explaining purpose."""

from typing import Optional, Dict, List
import asyncio

# Constants
MAX_RETRIES = 3
TIMEOUT_SECONDS = 30

class MyClass:
    """Class docstring."""
    
    def __init__(self, param: str) -> None:
        """Initialize with param."""
        self.param = param
    
    async def my_method(self, value: int) -> Optional[Dict]:
        """
        Method docstring.
        
        Args:
            value: Description of value
            
        Returns:
            Description of return value
            
        Raises:
            ValueError: When value is invalid
        """
        pass
```

#### Testing
- Write tests for all new code
- Use pytest for unit tests
- Use Hypothesis for property-based tests
- Minimum coverage: 80%

```python
# tests/unit/test_example.py
import pytest
from hypothesis import given, strategies as st

def test_basic_functionality():
    """Test basic case."""
    assert True

@given(st.integers(min_value=0, max_value=100))
def test_property(value: int):
    """Test property holds for all valid inputs."""
    assert value >= 0
```

### 4. Git Workflow

#### Branch Naming
- `feature/task-X-description` - New features
- `fix/issue-description` - Bug fixes
- `refactor/component-name` - Code refactoring
- `docs/what-changed` - Documentation updates

#### Commit Messages
```
type(scope): short description

Longer description if needed.

- Bullet points for details
- Reference issues: #123
```

Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`

Example:
```
feat(connector): add Bybit WebSocket connection

- Implement async WebSocket client
- Add reconnection logic with exponential backoff
- Add heartbeat monitoring

Closes #5
```

#### Pull Request Process
1. Create feature branch from `main`
2. Implement changes following coding standards
3. Write/update tests
4. Run all checks:
   ```powershell
   .\scripts\docker-dev.ps1 test
   docker compose exec trading_bot black --check src/ tests/
   docker compose exec trading_bot flake8 src/ tests/
   docker compose exec trading_bot mypy src/
   ```
5. Update documentation if needed
6. Create PR with description of changes
7. Wait for review and CI checks

### 5. Testing

#### Run All Tests
```powershell
.\scripts\docker-dev.ps1 test
```

#### Run Specific Tests
```powershell
# Unit tests only
docker compose exec trading_bot pytest tests/unit/ -v

# Property tests only
docker compose exec trading_bot pytest tests/property/ -v

# Integration tests only
docker compose exec trading_bot pytest tests/integration/ -v

# Specific test file
docker compose exec trading_bot pytest tests/unit/test_connector.py -v

# Specific test function
docker compose exec trading_bot pytest tests/unit/test_connector.py::test_connection -v
```

#### Coverage Report
```powershell
docker compose exec trading_bot pytest --cov=src --cov-report=html
# Open htmlcov/index.html in browser
```

### 6. Debugging

#### View Logs
```powershell
# All services
.\scripts\docker-dev.ps1 logs

# Specific service
.\scripts\docker-dev.ps1 logs trading_bot
.\scripts\docker-dev.ps1 logs timescaledb
```

#### Interactive Shell
```powershell
# Python shell in container
.\scripts\docker-dev.ps1 shell trading_bot
python

# Database shell
.\scripts\docker-dev.ps1 db
```

#### Debug with pdb
Add breakpoint in code:
```python
import pdb; pdb.set_trace()
```

Run with:
```powershell
docker compose exec trading_bot python -m pdb your_script.py
```

### 7. Database Operations

#### Connect to Database
```powershell
.\scripts\docker-dev.ps1 db
```

#### Common Queries
```sql
-- List all tables
\dt

-- Describe table
\d klines

-- Check hypertables
SELECT * FROM timescaledb_information.hypertables;

-- Query recent data
SELECT * FROM klines ORDER BY timestamp DESC LIMIT 10;

-- Exit
\q
```

#### Backup Database
```powershell
docker compose exec timescaledb pg_dump -U trading_user trading_bot > backup.sql
```

#### Restore Database
```powershell
docker compose exec -T timescaledb psql -U trading_user trading_bot < backup.sql
```

### 8. Performance Profiling

#### Profile Code
```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# Your code here

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)
```

#### Memory Profiling
```python
from memory_profiler import profile

@profile
def my_function():
    # Your code here
    pass
```

### 9. Common Issues

#### Container Won't Start
```powershell
# Check logs
.\scripts\docker-dev.ps1 logs trading_bot

# Rebuild image
.\scripts\docker-dev.ps1 build
.\scripts\docker-dev.ps1 start
```

#### Database Connection Failed
```powershell
# Check database status
docker compose ps

# Restart database
docker compose restart timescaledb

# Check database logs
.\scripts\docker-dev.ps1 logs timescaledb
```

#### Code Changes Not Reflected
- Code is mounted as volume, changes should be immediate
- If using compiled extensions, rebuild:
  ```powershell
  .\scripts\docker-dev.ps1 build
  ```

### 10. Resources

- **Spec Documents**: `.kiro/specs/quantitative-trading-bot/`
- **Docker Guide**: `DOCKER.md`
- **Setup Guide**: `SETUP.md`
- **Bybit API Docs**: https://bybit-exchange.github.io/docs/
- **TimescaleDB Docs**: https://docs.timescale.com/
- **Hypothesis Docs**: https://hypothesis.readthedocs.io/

## Questions?

Open an issue or ask in the team chat.
