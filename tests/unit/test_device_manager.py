"""Unit tests for DeviceManager."""

import json
import time

from app.device_manager import DeviceManager


class TestDeviceManager:
    """Test DeviceManager functionality."""

    def test_init_creates_empty_state(self, tmp_state_file):
        """Initialize with no state file."""
        dm = DeviceManager(state_file=tmp_state_file)
        assert dm.current_device is None
        assert dm.cached_devices == []
        assert dm.last_scan_time is None

    def test_select_device_saves_to_disk(self, device_manager, sample_device, tmp_state_file):
        """Selecting device saves to state file."""
        device_manager.select_device(sample_device)

        # Verify in-memory state
        assert device_manager.current_device == sample_device

        # Verify saved to disk
        with open(tmp_state_file) as f:
            data = json.load(f)
            assert data['current_device']['id'] == sample_device['id']
            assert data['current_device']['friendly_name'] == sample_device['friendly_name']

    def test_get_current_device_returns_copy(self, device_manager, sample_device):
        """get_current_device returns copy, not reference."""
        device_manager.select_device(sample_device)

        device1 = device_manager.get_current_device()
        device2 = device_manager.get_current_device()

        # Modify copy
        device1['friendly_name'] = 'Modified'

        # Original should be unchanged
        assert device2['friendly_name'] == 'Test Device'
        assert device_manager.current_device['friendly_name'] == 'Test Device'

    def test_clear_device(self, device_manager, sample_device, tmp_state_file):
        """Clear device removes it from state."""
        device_manager.select_device(sample_device)
        device_manager.clear_device()

        assert device_manager.current_device is None
        assert device_manager.get_current_device() is None

        # Verify saved to disk
        with open(tmp_state_file) as f:
            data = json.load(f)
            assert data['current_device'] is None

    def test_has_device(self, device_manager, sample_device):
        """has_device returns correct status."""
        assert device_manager.has_device() is False

        device_manager.select_device(sample_device)
        assert device_manager.has_device() is True

        device_manager.clear_device()
        assert device_manager.has_device() is False

    def test_update_device_cache(self, device_manager, sample_device):
        """Update device cache with list of devices."""
        devices = [sample_device, {**sample_device, 'id': 'uuid:different', 'ip': '192.168.1.101'}]

        device_manager.update_device_cache(devices)

        assert len(device_manager.cached_devices) == 2
        assert device_manager.last_scan_time is not None

    def test_get_cached_devices(self, device_manager, sample_device):
        """Get cached devices returns list."""
        devices = [sample_device]
        device_manager.update_device_cache(devices)

        cached = device_manager.get_cached_devices()
        assert len(cached) == 1
        assert cached[0]['id'] == sample_device['id']

    def test_get_cache_age(self, device_manager, sample_device):
        """Calculate cache age in seconds."""
        # No scan yet
        assert device_manager.get_cache_age() is None

        # After scan
        device_manager.update_device_cache([sample_device])
        age = device_manager.get_cache_age()
        assert age is not None
        assert age >= 0
        assert age < 1  # Should be very fresh

    def test_find_device_in_cache_by_ip(self, device_manager, sample_device):
        """Find device in cache by IP address."""
        device_manager.update_device_cache([sample_device])

        found = device_manager.find_device_in_cache(ip='192.168.1.100')
        assert found is not None
        assert found['id'] == sample_device['id']

        not_found = device_manager.find_device_in_cache(ip='192.168.1.200')
        assert not_found is None

    def test_load_state_from_existing_file(self, tmp_state_file, sample_device):
        """Load state from existing JSON file."""
        # Create state file manually
        state = {
            'current_device': sample_device,
            'cached_devices': [sample_device],
            'last_scan_time': time.time()
        }
        with open(tmp_state_file, 'w') as f:
            json.dump(state, f)

        # Load it
        dm = DeviceManager(state_file=tmp_state_file)
        assert dm.current_device['id'] == sample_device['id']
        assert len(dm.cached_devices) == 1

    def test_reload_from_disk_multi_worker_simulation(self, tmp_state_file, sample_device):
        """Simulate multi-worker scenario - state syncs via disk."""
        # Worker 1 selects device
        dm1 = DeviceManager(state_file=tmp_state_file)
        dm1.select_device(sample_device)

        # Worker 2 reads state (simulates different process)
        dm2 = DeviceManager(state_file=tmp_state_file)
        device = dm2.get_current_device()

        assert device is not None
        assert device['id'] == sample_device['id']
