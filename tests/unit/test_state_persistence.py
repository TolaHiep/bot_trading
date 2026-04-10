"""
Unit tests for the StatePersistence module.

Tests saving, loading, and clearing system state.
"""

import asyncio
import json
import pytest
from pathlib import Path
from src.core.state import (
    SystemState,
    StatePersistence,
    Position,
    Order,
    TradingMode,
)


@pytest.fixture
def temp_state_file(tmp_path):
    """Create a temporary state file path."""
    return str(tmp_path / "test_state.json")


@pytest.fixture
def state_persistence(temp_state_file):
    """Create a StatePersistence instance with temp file."""
    return StatePersistence(state_file=temp_state_file)


@pytest.fixture
def sample_state():
    """Create a sample system state for testing."""
    position = Position(
        position_id="pos_123",
        symbol="BTCUSDT",
        side="BUY",
        entry_price="50000.00",
        quantity="0.1",
        opened_at="2024-01-01T00:00:00",
        stop_loss="49000.00",
        unrealized_pnl="100.00"
    )
    
    order = Order(
        order_id="order_456",
        symbol="ETHUSDT",
        side="SELL",
        order_type="LIMIT",
        quantity="1.0",
        price="3000.00",
        state="PENDING"
    )
    
    return SystemState(
        mode="paper",
        balance="10000.00",
        open_positions=[position],
        pending_orders=[order],
        daily_starting_balance="9500.00",
        consecutive_losses=2,
        kill_switch_active=False
    )


@pytest.mark.asyncio
async def test_save_state_creates_file(state_persistence, sample_state):
    """Test that saving state creates a file."""
    await state_persistence.save_state(sample_state)
    
    assert state_persistence.state_file.exists()


@pytest.mark.asyncio
async def test_save_state_content(state_persistence, sample_state):
    """Test that saved state contains correct data."""
    await state_persistence.save_state(sample_state)
    
    with open(state_persistence.state_file, 'r') as f:
        data = json.load(f)
    
    assert data['mode'] == "paper"
    assert data['balance'] == "10000.00"
    assert len(data['open_positions']) == 1
    assert len(data['pending_orders']) == 1
    assert data['consecutive_losses'] == 2
    assert data['kill_switch_active'] is False


@pytest.mark.asyncio
async def test_save_state_updates_timestamp(state_persistence, sample_state):
    """Test that saving state updates the last_updated timestamp."""
    original_timestamp = sample_state.last_updated
    
    await asyncio.sleep(0.01)  # Ensure time passes
    await state_persistence.save_state(sample_state)
    
    assert sample_state.last_updated != original_timestamp


@pytest.mark.asyncio
async def test_load_state_returns_correct_data(state_persistence, sample_state):
    """Test that loading state returns the correct data."""
    await state_persistence.save_state(sample_state)
    
    loaded_state = await state_persistence.load_state()
    
    assert loaded_state is not None
    assert loaded_state.mode == "paper"
    assert loaded_state.balance == "10000.00"
    assert len(loaded_state.open_positions) == 1
    assert len(loaded_state.pending_orders) == 1
    assert loaded_state.consecutive_losses == 2
    assert loaded_state.kill_switch_active is False


@pytest.mark.asyncio
async def test_load_state_position_data(state_persistence, sample_state):
    """Test that position data is loaded correctly."""
    await state_persistence.save_state(sample_state)
    
    loaded_state = await state_persistence.load_state()
    
    position = loaded_state.open_positions[0]
    assert position.position_id == "pos_123"
    assert position.symbol == "BTCUSDT"
    assert position.side == "BUY"
    assert position.entry_price == "50000.00"
    assert position.quantity == "0.1"
    assert position.stop_loss == "49000.00"


@pytest.mark.asyncio
async def test_load_state_order_data(state_persistence, sample_state):
    """Test that order data is loaded correctly."""
    await state_persistence.save_state(sample_state)
    
    loaded_state = await state_persistence.load_state()
    
    order = loaded_state.pending_orders[0]
    assert order.order_id == "order_456"
    assert order.symbol == "ETHUSDT"
    assert order.side == "SELL"
    assert order.order_type == "LIMIT"
    assert order.quantity == "1.0"
    assert order.price == "3000.00"


@pytest.mark.asyncio
async def test_load_state_no_file_returns_none(state_persistence):
    """Test that loading state when no file exists returns None."""
    loaded_state = await state_persistence.load_state()
    
    assert loaded_state is None


@pytest.mark.asyncio
async def test_clear_state_removes_file(state_persistence, sample_state):
    """Test that clearing state removes the file."""
    await state_persistence.save_state(sample_state)
    assert state_persistence.state_file.exists()
    
    await state_persistence.clear_state()
    
    assert not state_persistence.state_file.exists()


@pytest.mark.asyncio
async def test_clear_state_when_no_file(state_persistence):
    """Test that clearing state when no file exists doesn't raise error."""
    await state_persistence.clear_state()  # Should not raise


@pytest.mark.asyncio
async def test_state_exists_returns_true_when_file_exists(state_persistence, sample_state):
    """Test that state_exists returns True when file exists."""
    await state_persistence.save_state(sample_state)
    
    assert state_persistence.state_exists()


@pytest.mark.asyncio
async def test_state_exists_returns_false_when_no_file(state_persistence):
    """Test that state_exists returns False when no file exists."""
    assert not state_persistence.state_exists()


@pytest.mark.asyncio
async def test_save_state_creates_parent_directory(tmp_path):
    """Test that saving state creates parent directories if they don't exist."""
    nested_path = tmp_path / "nested" / "dir" / "state.json"
    persistence = StatePersistence(state_file=str(nested_path))
    
    state = SystemState(mode="paper", balance="1000.00")
    await persistence.save_state(state)
    
    assert nested_path.exists()


@pytest.mark.asyncio
async def test_save_state_atomic_write(state_persistence, sample_state):
    """Test that state is written atomically (temp file then rename)."""
    await state_persistence.save_state(sample_state)
    
    # Temp file should not exist after save
    temp_file = state_persistence.state_file.with_suffix('.tmp')
    assert not temp_file.exists()
    
    # Main file should exist
    assert state_persistence.state_file.exists()


@pytest.mark.asyncio
async def test_load_state_with_empty_positions_and_orders(state_persistence):
    """Test loading state with no positions or orders."""
    state = SystemState(
        mode="paper",
        balance="1000.00",
        open_positions=[],
        pending_orders=[]
    )
    
    await state_persistence.save_state(state)
    loaded_state = await state_persistence.load_state()
    
    assert loaded_state is not None
    assert len(loaded_state.open_positions) == 0
    assert len(loaded_state.pending_orders) == 0


@pytest.mark.asyncio
async def test_load_state_with_multiple_positions(state_persistence):
    """Test loading state with multiple positions."""
    positions = [
        Position(
            position_id=f"pos_{i}",
            symbol="BTCUSDT",
            side="BUY",
            entry_price="50000.00",
            quantity="0.1",
            opened_at="2024-01-01T00:00:00"
        )
        for i in range(5)
    ]
    
    state = SystemState(
        mode="paper",
        balance="10000.00",
        open_positions=positions
    )
    
    await state_persistence.save_state(state)
    loaded_state = await state_persistence.load_state()
    
    assert len(loaded_state.open_positions) == 5


@pytest.mark.asyncio
async def test_save_and_load_preserves_precision(state_persistence):
    """Test that decimal precision is preserved through save/load cycle."""
    state = SystemState(
        mode="paper",
        balance="12345.6789012345",
        daily_starting_balance="12000.1234567890"
    )
    
    await state_persistence.save_state(state)
    loaded_state = await state_persistence.load_state()
    
    assert loaded_state.balance == "12345.6789012345"
    assert loaded_state.daily_starting_balance == "12000.1234567890"


@pytest.mark.asyncio
async def test_load_state_handles_missing_optional_fields(state_persistence):
    """Test that loading state handles missing optional fields gracefully."""
    # Manually create a state file with minimal fields
    minimal_state = {
        "mode": "paper",
        "balance": "1000.00",
        "open_positions": [],
        "pending_orders": []
    }
    
    with open(state_persistence.state_file, 'w') as f:
        json.dump(minimal_state, f)
    
    loaded_state = await state_persistence.load_state()
    
    assert loaded_state is not None
    assert loaded_state.mode == "paper"
    assert loaded_state.balance == "1000.00"
    assert loaded_state.consecutive_losses == 0  # Default value
    assert loaded_state.kill_switch_active is False  # Default value


@pytest.mark.asyncio
async def test_save_state_with_kill_switch_active(state_persistence):
    """Test saving and loading state with kill switch active."""
    state = SystemState(
        mode="paper",
        balance="1000.00",
        kill_switch_active=True
    )
    
    await state_persistence.save_state(state)
    loaded_state = await state_persistence.load_state()
    
    assert loaded_state.kill_switch_active is True


@pytest.mark.asyncio
async def test_multiple_save_load_cycles(state_persistence, sample_state):
    """Test multiple save/load cycles maintain data integrity."""
    # First cycle
    await state_persistence.save_state(sample_state)
    loaded1 = await state_persistence.load_state()
    
    # Modify and save again
    loaded1.balance = "15000.00"
    loaded1.consecutive_losses = 5
    await state_persistence.save_state(loaded1)
    
    # Load again
    loaded2 = await state_persistence.load_state()
    
    assert loaded2.balance == "15000.00"
    assert loaded2.consecutive_losses == 5
