#!/usr/bin/env python3
"""
run_all_tests.py — Universal Zero-Dependency Test Runner for RE:TRACE
Discovers and executes all canonical test suites under tests/, verifies Tiers 1-4,
and outputs formatted pass/fail and tier metrics using Python standard library.
"""

import glob
import os
import sys
import time
import types
import unittest

# 1. Path bootstrapping: Ensure project root and .venv site-packages are in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Auto-detect local virtualenv site-packages so system python3 can load project dependencies
venv_patterns = [
    os.path.join(PROJECT_ROOT, ".venv", "lib", f"python{sys.version_info.major}.{sys.version_info.minor}", "site-packages"),
    os.path.join(PROJECT_ROOT, ".venv", "lib", "python*", "site-packages"),
]
for pat in venv_patterns:
    for matched_path in glob.glob(pat):
        if os.path.isdir(matched_path) and matched_path not in sys.path:
            sys.path.insert(0, matched_path)


def load_tier_suite(module_name: str, target_class_name: str = None) -> unittest.TestSuite:
    """
    Robustly loads a test suite from a module:
    1. Looks for target_class_name (if specified and inherits from unittest.TestCase).
    2. Looks for any unittest.TestCase subclasses in the module.
    3. Falls back to wrapping any standalone test_* functions via unittest.FunctionTestCase.
    """
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()

    try:
        mod = __import__(module_name, fromlist=["*"])
    except Exception as e:
        print(f"[!] Warning: Could not import {module_name}: {e}")
        return suite

    loaded = False

    # 1. Check for specific class
    if target_class_name and hasattr(mod, target_class_name):
        cls = getattr(mod, target_class_name)
        if isinstance(cls, type) and issubclass(cls, unittest.TestCase):
            suite.addTests(loader.loadTestsFromTestCase(cls))
            loaded = True

    # 2. Check for any TestCase classes
    if not loaded:
        for name in dir(mod):
            cls = getattr(mod, name)
            if isinstance(cls, type) and issubclass(cls, unittest.TestCase):
                suite.addTests(loader.loadTestsFromTestCase(cls))
                loaded = True

    # 3. Fallback: Wrap standalone functions
    if not loaded:
        for name in dir(mod):
            if name.startswith("test_"):
                fn = getattr(mod, name)
                if isinstance(fn, (types.FunctionType, types.BuiltinFunctionType)):
                    suite.addTest(unittest.FunctionTestCase(fn))

    return suite


def run_suite():
    print("=" * 70)
    print(" RE:TRACE AUTOMATED TEST TRACK RUNNER (TIERS 1 - 4)")
    print("=" * 70)
    print(f"Project Root: {PROJECT_ROOT}")
    print(f"Python:       {sys.version.split()[0]} ({sys.executable})")
    print(f"Timestamp:    {time.strftime('%Y-%m-%d %H:%M:%SZ', time.gmtime())}")
    print("-" * 70)

    tier_map = {
        "Tier 1 (Mass Balance)": load_tier_suite("tests.test_mass_balance", "TestMassBalanceEngine"),
        "Tier 1 (Evidence Commitment)": load_tier_suite("tests.test_evidence_commitment", "TestEvidenceCommitmentPipeline"),
        "Tier 1 (Evidence Pipeline Hasher)": load_tier_suite("tests.test_evidence_pipeline", "TestEvidencePipeline"),
        "Tier 1 (Lifecycle State Machine)": load_tier_suite("tests.test_state_machine", "TestLifecycleStateMachine"),
        "Tier 2 (FastAPI Backend Integration API)": load_tier_suite("tests.test_backend_api", "TestBackendAPI"),
        "Tier 2 (Custom Verification Workflow)": load_tier_suite("tests.test_custom_verification", "TestCustomVerificationWorkflow"),
        "Tier 2 (Gemini Vision Multimodal Integration)": load_tier_suite("tests.test_gemini_vision_integration", "TestGeminiVisionIntegration"),
        "Tier 3 (Adversarial Suite Cases A-J)": load_tier_suite("tests.test_adversarial", "TestAdversarialSuite"),
        "Tier 2 & 4 (E2E Vertical Slice 12 Stages)": load_tier_suite("tests.test_vertical_slice", "TestVerticalSliceEndToEnd"),
    }

    full_suite = unittest.TestSuite()
    total_tests = 0
    tier_counts = {}

    for name, subsuite in tier_map.items():
        count = subsuite.countTestCases()
        tier_counts[name] = count
        total_tests += count
        full_suite.addTest(subsuite)
        print(f"[*] Loaded {name}: {count} tests")

    print("-" * 70)
    print(f"Total Test Cases Loaded: {total_tests}")
    print("=" * 70)

    start_time = time.time()
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(full_suite)
    elapsed = time.time() - start_time

    print("=" * 70)
    print(" TEST RUN SUMMARY")
    print("=" * 70)
    print(f"Tests Executed:   {result.testsRun}")
    print(f"Passed:           {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures:         {len(result.failures)}")
    print(f"Errors:           {len(result.errors)}")
    print(f"Execution Time:   {elapsed:.4f}s")
    print("-" * 70)

    for name, count in tier_counts.items():
        print(f" - {name:<42} : {count} tests")

    print("=" * 70)

    if result.wasSuccessful() and result.testsRun > 0:
        print(">>> ALL TIERS PASSED VERIFICATION (STATUS: GREEN) <<<")
        print("=" * 70)
        return 0
    else:
        print(">>> TEST VERIFICATION FAILED (STATUS: RED) <<<")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    sys.exit(run_suite())
