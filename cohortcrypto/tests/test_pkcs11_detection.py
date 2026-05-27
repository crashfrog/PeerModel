"""Acceptance tests for PKCS#11 library auto-detection (Issue #3).

This test module covers the requirements from issue #3:
- Detect PKCS#11 libs on Linux
- Detect PKCS#11 libs on macOS
- Respect env var override
- Return list of available paths
- Tests with mock filesystem

These tests are written BEFORE implementation (TDD red phase).
All tests should FAIL until the implementation is complete.
"""

import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from cohortcrypto.hardware.detection import find_all_pkcs11_libraries
from cohortcrypto.exceptions import PKCSLibraryNotFoundError


# Mock filesystem helper
class MockPath:
    """Mock pathlib.Path with controllable exists() behavior."""

    def __init__(self, path_str, exists=False):
        self._path_str = path_str
        self._exists = exists

    def exists(self):
        return self._exists

    def __str__(self):
        return self._path_str

    def __repr__(self):
        return f"MockPath('{self._path_str}', exists={self._exists})"


# Test: Function exists and returns list

def test_find_all_pkcs11_libraries_exists():
    """find_all_pkcs11_libraries function should exist."""
    # This will fail with ImportError until implementation exists
    assert callable(find_all_pkcs11_libraries)


def test_find_all_pkcs11_libraries_returns_list():
    """find_all_pkcs11_libraries should return a list."""
    # Mock filesystem with no libraries present
    with patch('cohortcrypto.hardware.detection.Path') as mock_path_cls:
        mock_path_cls.return_value.exists.return_value = False

        result = find_all_pkcs11_libraries()
        assert isinstance(result, list)


# Test: Environment variable override

def test_env_var_override_single_path(tmp_path):
    """COHORTCRYPTO_PKCS11_PATH with single path should be returned."""
    # Create a temporary library file
    lib_path = tmp_path / "test-pkcs11.so"
    lib_path.touch()

    with patch.dict(os.environ, {'COHORTCRYPTO_PKCS11_PATH': str(lib_path)}):
        result = find_all_pkcs11_libraries()

        assert len(result) == 1
        assert str(lib_path) in result


def test_env_var_override_multiple_paths(tmp_path):
    """COHORTCRYPTO_PKCS11_PATH with colon-separated paths should all be returned."""
    # Create multiple library files
    lib1 = tmp_path / "lib1.so"
    lib2 = tmp_path / "lib2.so"
    lib1.touch()
    lib2.touch()

    env_value = f"{lib1}:{lib2}"

    with patch.dict(os.environ, {'COHORTCRYPTO_PKCS11_PATH': env_value}):
        result = find_all_pkcs11_libraries()

        assert len(result) == 2
        assert str(lib1) in result
        assert str(lib2) in result


def test_env_var_with_nonexistent_path(tmp_path):
    """COHORTCRYPTO_PKCS11_PATH with nonexistent path should be ignored."""
    # Create one real file, reference one fake file
    lib_real = tmp_path / "real.so"
    lib_real.touch()
    lib_fake = tmp_path / "fake.so"

    env_value = f"{lib_real}:{lib_fake}"

    with patch.dict(os.environ, {'COHORTCRYPTO_PKCS11_PATH': env_value}):
        result = find_all_pkcs11_libraries()

        # Only the real file should be in results
        assert str(lib_real) in result
        assert str(lib_fake) not in result


def test_env_var_takes_precedence_over_system_paths(tmp_path):
    """Environment variable paths should be checked first."""
    lib_path = tmp_path / "custom.so"
    lib_path.touch()

    with patch.dict(os.environ, {'COHORTCRYPTO_PKCS11_PATH': str(lib_path)}):
        with patch('platform.system', return_value='Linux'):
            with patch('cohortcrypto.hardware.detection.Path') as mock_path_cls:
                # Mock system paths as NOT existing
                mock_path_cls.return_value.exists.return_value = False

                result = find_all_pkcs11_libraries()

                # Should still find the env var path
                assert len(result) >= 1
                assert str(lib_path) in result


# Test: Linux detection

@patch('platform.system', return_value='Linux')
def test_linux_detects_opensc_x86_64(mock_system):
    """Should detect OpenSC library in /usr/lib/x86_64-linux-gnu/."""
    def path_exists_check(path_str):
        mock = MagicMock()
        mock.exists.return_value = (path_str == '/usr/lib/x86_64-linux-gnu/opensc-pkcs11.so')
        return mock

    with patch('cohortcrypto.hardware.detection.Path', side_effect=path_exists_check):
        result = find_all_pkcs11_libraries()

        assert '/usr/lib/x86_64-linux-gnu/opensc-pkcs11.so' in result


@patch('platform.system', return_value='Linux')
def test_linux_detects_yubikey_lib(mock_system):
    """Should detect YubiKey library on Linux."""
    def path_exists_check(path_str):
        mock = MagicMock()
        mock.exists.return_value = (path_str == '/usr/lib/x86_64-linux-gnu/libykcs11.so')
        return mock

    with patch('cohortcrypto.hardware.detection.Path', side_effect=path_exists_check):
        result = find_all_pkcs11_libraries()

        assert '/usr/lib/x86_64-linux-gnu/libykcs11.so' in result


@patch('platform.system', return_value='Linux')
def test_linux_detects_multiple_libraries(mock_system):
    """Should detect multiple PKCS#11 libraries on Linux."""
    expected_libs = [
        '/usr/lib/x86_64-linux-gnu/opensc-pkcs11.so',
        '/usr/lib/x86_64-linux-gnu/libykcs11.so',
        '/usr/local/lib/opensc-pkcs11.so',
    ]

    def path_exists_check(path_str):
        mock = MagicMock()
        mock.exists.return_value = (path_str in expected_libs)
        return mock

    with patch('cohortcrypto.hardware.detection.Path', side_effect=path_exists_check):
        result = find_all_pkcs11_libraries()

        # All expected libraries should be found
        for lib in expected_libs:
            assert lib in result


@patch('platform.system', return_value='Linux')
def test_linux_searches_standard_paths(mock_system):
    """Should search all standard Linux paths."""
    expected_search_paths = [
        '/usr/lib/x86_64-linux-gnu/opensc-pkcs11.so',
        '/usr/lib/opensc-pkcs11.so',
        '/usr/local/lib/opensc-pkcs11.so',
        '/usr/lib/x86_64-linux-gnu/libykcs11.so',
        '/usr/lib/libykcs11.so',
    ]

    checked_paths = []

    def path_exists_check(path_str):
        checked_paths.append(path_str)
        mock = MagicMock()
        mock.exists.return_value = False
        return mock

    with patch('cohortcrypto.hardware.detection.Path', side_effect=path_exists_check):
        find_all_pkcs11_libraries()

        # Verify all standard paths were checked
        for expected_path in expected_search_paths:
            assert expected_path in checked_paths


# Test: macOS detection

@patch('platform.system', return_value='Darwin')
def test_macos_detects_opensc_library(mock_system):
    """Should detect OpenSC library in /Library/OpenSC/lib/."""
    def path_exists_check(path_str):
        mock = MagicMock()
        mock.exists.return_value = (path_str == '/Library/OpenSC/lib/opensc-pkcs11.so')
        return mock

    with patch('cohortcrypto.hardware.detection.Path', side_effect=path_exists_check):
        result = find_all_pkcs11_libraries()

        assert '/Library/OpenSC/lib/opensc-pkcs11.so' in result


@patch('platform.system', return_value='Darwin')
def test_macos_detects_yubikey_dylib(mock_system):
    """Should detect YubiKey .dylib on macOS."""
    def path_exists_check(path_str):
        mock = MagicMock()
        mock.exists.return_value = (path_str == '/usr/local/lib/libykcs11.dylib')
        return mock

    with patch('cohortcrypto.hardware.detection.Path', side_effect=path_exists_check):
        result = find_all_pkcs11_libraries()

        assert '/usr/local/lib/libykcs11.dylib' in result


@patch('platform.system', return_value='Darwin')
def test_macos_searches_standard_paths(mock_system):
    """Should search all standard macOS paths."""
    expected_search_paths = [
        '/Library/OpenSC/lib/opensc-pkcs11.so',
        '/usr/local/lib/opensc-pkcs11.so',
        '/usr/local/lib/libykcs11.dylib',
    ]

    checked_paths = []

    def path_exists_check(path_str):
        checked_paths.append(path_str)
        mock = MagicMock()
        mock.exists.return_value = False
        return mock

    with patch('cohortcrypto.hardware.detection.Path', side_effect=path_exists_check):
        find_all_pkcs11_libraries()

        # Verify all standard paths were checked
        for expected_path in expected_search_paths:
            assert expected_path in checked_paths


# Test: Windows detection

@patch('platform.system', return_value='Windows')
def test_windows_detects_system32_library(mock_system):
    """Should detect PKCS#11 library in System32."""
    def path_exists_check(path_str):
        mock = MagicMock()
        mock.exists.return_value = (path_str == r'C:\Windows\System32\opensc-pkcs11.dll')
        return mock

    with patch('cohortcrypto.hardware.detection.Path', side_effect=path_exists_check):
        result = find_all_pkcs11_libraries()

        assert r'C:\Windows\System32\opensc-pkcs11.dll' in result


@patch('platform.system', return_value='Windows')
def test_windows_detects_program_files_opensc(mock_system):
    """Should detect OpenSC in Program Files."""
    expected_path = r'C:\Program Files\OpenSC Project\OpenSC\pkcs11\opensc-pkcs11.dll'

    def path_exists_check(path_str):
        mock = MagicMock()
        mock.exists.return_value = (path_str == expected_path)
        return mock

    with patch('cohortcrypto.hardware.detection.Path', side_effect=path_exists_check):
        result = find_all_pkcs11_libraries()

        assert expected_path in result


@patch('platform.system', return_value='Windows')
def test_windows_detects_yubico_library(mock_system):
    """Should detect Yubico PIV Tool library."""
    expected_path = r'C:\Program Files\Yubico\Yubico PIV Tool\bin\libykcs11.dll'

    def path_exists_check(path_str):
        mock = MagicMock()
        mock.exists.return_value = (path_str == expected_path)
        return mock

    with patch('cohortcrypto.hardware.detection.Path', side_effect=path_exists_check):
        result = find_all_pkcs11_libraries()

        assert expected_path in result


@patch('platform.system', return_value='Windows')
def test_windows_searches_standard_paths(mock_system):
    """Should search all standard Windows paths."""
    expected_search_paths = [
        r'C:\Windows\System32\opensc-pkcs11.dll',
        r'C:\Program Files\OpenSC Project\OpenSC\pkcs11\opensc-pkcs11.dll',
        r'C:\Program Files\Yubico\Yubico PIV Tool\bin\libykcs11.dll',
    ]

    checked_paths = []

    def path_exists_check(path_str):
        checked_paths.append(path_str)
        mock = MagicMock()
        mock.exists.return_value = False
        return mock

    with patch('cohortcrypto.hardware.detection.Path', side_effect=path_exists_check):
        find_all_pkcs11_libraries()

        # Verify all standard paths were checked
        for expected_path in expected_search_paths:
            assert expected_path in checked_paths


# Test: Edge cases and error handling

def test_returns_empty_list_when_no_libraries_found():
    """Should return empty list when no libraries are found."""
    with patch('platform.system', return_value='Linux'):
        with patch('cohortcrypto.hardware.detection.Path') as mock_path_cls:
            # All paths return False for exists()
            mock_path_cls.return_value.exists.return_value = False

            with patch.dict(os.environ, {}, clear=True):
                result = find_all_pkcs11_libraries()

                assert result == []


def test_deduplicates_paths():
    """Should not return duplicate paths."""
    # If same library exists in multiple checked locations (symlinks, etc.)
    # only return it once
    with patch('platform.system', return_value='Linux'):
        def path_exists_check(path_str):
            mock = MagicMock()
            # Pretend all paths exist (unrealistic but tests deduplication)
            mock.exists.return_value = True
            mock.__str__ = lambda self: path_str
            return mock

        with patch('cohortcrypto.hardware.detection.Path', side_effect=path_exists_check):
            result = find_all_pkcs11_libraries()

            # Check for duplicates
            assert len(result) == len(set(result)), "Result contains duplicates"


def test_handles_permission_errors_gracefully():
    """Should handle permission errors when checking paths."""
    def path_exists_check(path_str):
        mock = MagicMock()
        # Simulate permission error on exists() check
        mock.exists.side_effect = PermissionError("Access denied")
        return mock

    with patch('platform.system', return_value='Linux'):
        with patch('cohortcrypto.hardware.detection.Path', side_effect=path_exists_check):
            # Should not raise exception, just skip inaccessible paths
            result = find_all_pkcs11_libraries()
            assert isinstance(result, list)


def test_unknown_platform_returns_empty_list():
    """Should return empty list for unknown/unsupported platforms."""
    with patch('platform.system', return_value='UnknownOS'):
        with patch.dict(os.environ, {}, clear=True):
            result = find_all_pkcs11_libraries()
            assert result == []


# Test: Return type and format

def test_returns_list_of_strings():
    """All returned paths should be strings."""
    with patch('platform.system', return_value='Linux'):
        def path_exists_check(path_str):
            mock = MagicMock()
            mock.exists.return_value = True
            mock.__str__ = lambda self: path_str
            return mock

        with patch('cohortcrypto.hardware.detection.Path', side_effect=path_exists_check):
            result = find_all_pkcs11_libraries()

            assert all(isinstance(path, str) for path in result)


def test_returns_absolute_paths():
    """All returned paths should be absolute paths."""
    with patch('platform.system', return_value='Linux'):
        def path_exists_check(path_str):
            mock = MagicMock()
            mock.exists.return_value = (path_str == '/usr/lib/opensc-pkcs11.so')
            mock.__str__ = lambda self: path_str
            return mock

        with patch('cohortcrypto.hardware.detection.Path', side_effect=path_exists_check):
            result = find_all_pkcs11_libraries()

            for path in result:
                assert Path(path).is_absolute() or path.startswith('C:\\')


# Test: Integration with existing find_pkcs11_library()

def test_find_pkcs11_library_uses_find_all_result():
    """Existing find_pkcs11_library() should use first result from find_all."""
    # This verifies the new function integrates with existing code
    from cohortcrypto.hardware.detection import find_pkcs11_library

    with patch('platform.system', return_value='Linux'):
        def path_exists_check(path_str):
            mock = MagicMock()
            mock.exists.return_value = (path_str == '/usr/lib/opensc-pkcs11.so')
            mock.__str__ = lambda self: path_str
            return mock

        with patch('cohortcrypto.hardware.detection.Path', side_effect=path_exists_check):
            # find_all should return list
            all_libs = find_all_pkcs11_libraries()
            assert len(all_libs) > 0

            # find_pkcs11_library should return first item
            single_lib = find_pkcs11_library()
            assert single_lib == all_libs[0]


def test_find_pkcs11_library_raises_when_none_found():
    """Existing find_pkcs11_library() should raise when find_all returns empty."""
    from cohortcrypto.hardware.detection import find_pkcs11_library

    with patch('platform.system', return_value='Linux'):
        with patch('cohortcrypto.hardware.detection.Path') as mock_path_cls:
            mock_path_cls.return_value.exists.return_value = False

            with patch.dict(os.environ, {}, clear=True):
                with pytest.raises(PKCSLibraryNotFoundError):
                    find_pkcs11_library()
