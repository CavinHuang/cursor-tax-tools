#!/usr/bin/env python3

print("Testing remote update integration...")

try:
    from smart_update_client import SmartUpdateChecker
    print("SmartUpdateChecker: OK")
except Exception as e:
    print(f"SmartUpdateChecker: FAILED - {e}")

try:
    from tariff_gui import TariffGUI

    remote_methods = [
        'setup_remote_update',
        'check_remote_update',
        'force_remote_update',
        'refresh_remote_status'
    ]

    missing = []
    for method in remote_methods:
        if not hasattr(TariffGUI, method):
            missing.append(method)

    if missing:
        print(f"TariffGUI: FAILED - Missing methods: {missing}")
    else:
        print("TariffGUI: OK - All remote methods available")

except Exception as e:
    print(f"TariffGUI: FAILED - {e}")

print("\nTest completed!")